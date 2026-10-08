import logging
from collections.abc import Callable
from typing import Any

from homeassistant.auth import HomeAssistant
from homeassistant.components.alarm_control_panel.const import AlarmControlPanelState
from homeassistant.const import STATE_ON
from homeassistant.core import Context, Event, EventStateChangedData, State
from homeassistant.helpers.event import async_track_state_change_event

from .const import NO_CAL_EVENT_MODE_AUTO, NO_CAL_EVENT_MODE_AUTO_OCCUPANCY, NO_CAL_EVENT_MODE_AUTO_SUN, ChangeSource
from .helpers import alarm_state_as_enum, child_context

_LOGGER = logging.getLogger(__name__)


class TrackedTimeOfDay:
    """Generate alarm state changes for a Home Assistant Time of Day sensor

    The alarm is held at the sensor's state for the period it is on, unless a calendar event is live
    """

    def __init__(
        self,
        entity_id: str,
        arming_state: AlarmControlPanelState,
        armer: "AlarmArmer",  # type: ignore # ruff:ignore[undefined-name]
        hass: HomeAssistant,
    ) -> None:
        self.entity_id: str = entity_id
        self.name: str = entity_id
        self.arming_state: AlarmControlPanelState = arming_state
        self.armer: AlarmArmer = armer  # type: ignore # ruff:ignore[undefined-name]
        self.hass: HomeAssistant = hass
        self.active: bool = False
        self.previous_state: AlarmControlPanelState | None = None
        self.listener: Callable[[], None] | None = None

    async def initialize(self) -> None:
        self.listener = async_track_state_change_event(self.hass, [self.entity_id], self.on_sensor_change)
        state: State | None = self.hass.states.get(self.entity_id)
        if state is not None and state.state == STATE_ON:
            self.active = True
            await self.start(state, None)
        _LOGGER.debug("AUTOARM Now tracking time of day sensor %s for %s", self.entity_id, self.arming_state)

    def shutdown(self) -> None:
        if self.listener:
            self.listener()
            self.listener = None

    async def on_sensor_change(self, event: Event[EventStateChangedData]) -> None:
        new_state: State | None = event.data["new_state"]
        # a sensor that is off, unavailable or removed has no period
        is_on: bool = new_state is not None and new_state.state == STATE_ON
        if is_on == self.active:
            return
        self.active = is_on
        context: Context = child_context(event.context)
        if new_state is not None and is_on:
            await self.start(new_state, context)
        else:
            await self.end(context)

    async def start(self, state: State, context: Context | None) -> None:
        _LOGGER.debug("AUTOARM Time of day sensor %s turned on", self.entity_id)
        self.name = state.name
        self.previous_state = self.armer.armed_state()
        if self.armer.has_active_calendar_event():
            _LOGGER.info("AUTOARM Time of day sensor %s on, leaving state to the live calendar event", self.entity_id)
            return
        await self.armer.arm(
            self.armer.time_of_day_state(self),
            source=ChangeSource.TOD,
            change_context={"caller": "time_of_day.start", "entity_id": self.entity_id, "summary": self.name},
            context=context,
        )

    async def end(self, context: Context) -> None:
        _LOGGER.debug("AUTOARM Time of day sensor %s no longer on", self.entity_id)
        if self.armer.has_active_calendar_event():
            _LOGGER.debug("AUTOARM No action on time of day end since calendar event active")
            return
        if await self.armer.resume_time_of_day(context):
            return
        if self.arming_state == AlarmControlPanelState.DISARMED:
            end_mode: str = self.armer.calendar_disarmed_end_mode
        else:
            end_mode = self.armer.calendar_armed_end_mode
        if end_mode == NO_CAL_EVENT_MODE_AUTO:
            # the period ends at a set time, so isn't left to be decided by whether the sun is up yet
            end_mode = NO_CAL_EVENT_MODE_AUTO_OCCUPANCY
        change_context: dict[str, Any] = {
            "caller": "time_of_day.end",
            "entity_id": self.entity_id,
            "summary": self.name,
            "no_event_mode": end_mode,
        }
        if end_mode == NO_CAL_EVENT_MODE_AUTO_SUN:
            # same context for the move via pending and the reset, as both are the one change
            context = self.armer.cause(ChangeSource.TOD, self.name, context)
            await self.armer.pending_state(source=ChangeSource.TOD, change_context=change_context, context=context)
            await self.armer.reset_armed_state(source=ChangeSource.TOD, context=context)
        elif end_mode == NO_CAL_EVENT_MODE_AUTO_OCCUPANCY:
            target_state = self.armer.occupancy_end_state(self.arming_state)
            _LOGGER.info("AUTOARM Time of day %s ended, and arming by occupancy to %s", self.entity_id, target_state)
            await self.armer.arm(target_state, source=ChangeSource.TOD, change_context=change_context, context=context)
        elif end_mode in AlarmControlPanelState:
            _LOGGER.info("AUTOARM Time of day %s ended, and returning to fixed state %s", self.entity_id, end_mode)
            await self.armer.arm(
                alarm_state_as_enum(end_mode), source=ChangeSource.TOD, change_context=change_context, context=context
            )
        else:
            _LOGGER.debug("AUTOARM Reinstate previous state on time of day end in manual mode")
            await self.armer.arm(self.previous_state, source=ChangeSource.TOD, change_context=change_context, context=context)
