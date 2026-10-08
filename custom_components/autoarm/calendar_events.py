import asyncio
import datetime as dt
import logging
import re
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast

import homeassistant.util.dt as dt_util
from homeassistant.auth import HomeAssistant
from homeassistant.components.alarm_control_panel.const import AlarmControlPanelState
from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.const import CONF_ALIAS, CONF_ENTITY_ID
from homeassistant.core import Event, EventStateChangedData
from homeassistant.helpers import entity_platform
from homeassistant.helpers.event import (
    async_track_point_in_time,
    async_track_state_change_event,
    async_track_utc_time_change,
)
from homeassistant.helpers.typing import ConfigType

from custom_components.autoarm.helpers import AppHealthTracker, alarm_state_as_enum

from .const import (
    ALARM_STATES,
    CONF_CALENDAR_EVENT_STATES,
    CONF_CALENDAR_POLL_INTERVAL,
    NO_CAL_EVENT_MODE_AUTO_OCCUPANCY,
    NO_CAL_EVENT_MODE_AUTO_SUN,
    ChangeSource,
)

if TYPE_CHECKING:
    from homeassistant.core import CALLBACK_TYPE

_LOGGER = logging.getLogger(__name__)


def unlisten(listener: Callable[[], None] | None) -> None:
    if listener:
        try:
            listener()
        except Exception as e:
            _LOGGER.debug("AUTOARM Failure closing calendar listener %s: %s", listener, e)


class TrackedCalendarEvent:
    """Generate alarm state changes for a Home Assistant Calendar event"""

    def __init__(
        self,
        calendar_id: str,
        event: CalendarEvent,
        arming_state: AlarmControlPanelState,
        armer: "AlarmArmer",  # type: ignore # ruff:ignore[undefined-name]
        hass: HomeAssistant,
    ) -> None:
        self.tracked_at: dt.datetime = dt_util.now()
        self.calendar_id: str = calendar_id
        self.id: str = TrackedCalendarEvent.event_id(calendar_id, event)
        self.event: CalendarEvent = event
        self.arming_state: AlarmControlPanelState = arming_state
        self.start_listener: CALLBACK_TYPE | None = None
        self.end_listener: CALLBACK_TYPE | None = None
        self.armer: AlarmArmer = armer  # type: ignore # ruff:ignore[undefined-name]
        self.hass: HomeAssistant = hass
        self.previous_state: AlarmControlPanelState | None = armer.armed_state()
        self.track_status: str = "pending"

    async def initialize(self) -> None:
        if self.event.end_datetime_local < self.tracked_at:
            _LOGGER.debug("AUTOARM Ignoring past event")
            self.track_status = "ended"
            return
        if self.event.start_datetime_local > self.tracked_at:
            self.start_listener = async_track_point_in_time(
                self.hass,
                self.on_calendar_event_start,
                self.event.start_datetime_local,
            )
        else:
            await self.on_calendar_event_start(dt_util.now())
        if self.event.end_datetime_local > self.tracked_at:
            self.end_listener = async_track_point_in_time(
                self.hass,
                self.end,
                self.event.end_datetime_local,
            )
        _LOGGER.debug("AUTOARM Now tracking %s event %s, %s", self.calendar_id, self.event.uid, self.event.summary)

    async def end(self, event_time: dt.datetime) -> None:
        """Handle an event that has reached its finish date and time"""
        if self.track_status == "ended":
            # already handled, e.g. by end listener before pruning
            return
        _LOGGER.debug("AUTOARM Calendar event %s ended, event_time: %s", self.id, event_time)
        self.track_status = "ended"
        await self.on_calendar_event_end(dt_util.now())
        self.shutdown()

    async def update(self, new_event: CalendarEvent) -> None:
        _LOGGER.debug("AUTOARM Calendar event updated for %s: %s", self.id, self.event.summary)
        was_current = self.is_current()
        self.event = new_event
        if not self.is_current() and was_current:
            await self.end(dt_util.now())

    async def remove(self) -> None:
        _LOGGER.debug("AUTOARM Calendar event deletion for %s: %s", self.id, self.event.summary)
        if self.track_status == "started":
            await self.end(dt_util.now())
        else:
            self.track_status = "ended"
            self.shutdown()

    async def on_calendar_event_start(self, triggered_at: dt.datetime) -> None:
        _LOGGER.debug("AUTOARM on_calendar_event_start(%s,%s)", self.id, triggered_at)
        self.track_status = "started"
        target_state: AlarmControlPanelState = self.arming_state
        new_state: AlarmControlPanelState | None = None
        overridden: bool = False

        # optionally allow occupancy overrides of recurring events
        overridable_event: bool = str(self.arming_state) in self.armer.calendar_occupancy_override_states
        if self.is_recurring() and overridable_event:
            occupied = self.armer.is_occupied()
            current_state: AlarmControlPanelState = self.armer.armed_state()
            if (
                occupied is False
                and target_state
                in (AlarmControlPanelState.DISARMED, AlarmControlPanelState.ARMED_HOME, AlarmControlPanelState.ARMED_NIGHT)
                and current_state in (AlarmControlPanelState.ARMED_AWAY)
            ):
                _LOGGER.debug(
                    "AUTOARM Calendar event %s: empty occupancy override cancelling calendar change to %s",
                    self.id,
                    self.arming_state,
                )
                overridden = True
            elif (
                occupied is True
                and target_state in (AlarmControlPanelState.ARMED_AWAY)
                and current_state
                in (AlarmControlPanelState.DISARMED, AlarmControlPanelState.ARMED_HOME, AlarmControlPanelState.ARMED_NIGHT)
            ):
                _LOGGER.debug(
                    "AUTOARM Calendar event %s: present occupancy override cancelling calendar change to %s",
                    self.id,
                    self.arming_state,
                )
                overridden = True

        # same context for the change and the status, as the calendar event caused both
        context = self.armer.cause(ChangeSource.CALENDAR, self.event.summary)
        if overridden:
            _LOGGER.info("AUTOARM Calendar arming to %s overridden by occupancy", target_state)
        else:
            new_state = await self.armer.arm(
                arming_state=target_state,
                source=ChangeSource.CALENDAR,
                change_context={
                    "caller": "calendar.on_calendar_event_start",
                    "calendar_id": self.calendar_id,
                    "event_id": self.id,
                    "summary": self.event.summary,
                    "recurring": self.is_recurring(),
                    "overridable_event": overridable_event,
                },
                context=context,
            )
        self.armer.publish_status(
            "last_calendar_event",
            self.event.summary or str(self.id),
            {
                "calendar": self.calendar_id,
                "start": self.event.start_datetime_local,
                "end": self.event.end_datetime_local,
                "summary": self.event.summary,
                "description": self.event.description,
                "uid": self.event.uid,
                "new_state": new_state,
                "overridden": overridden,
            },
            context=context,
        )

    async def on_calendar_event_end(self, ended_at: dt.datetime) -> None:
        _LOGGER.debug("AUTOARM on_calendar_event_end(%s,%s)", self.id, ended_at)
        if self.armer.has_active_calendar_event():
            _LOGGER.debug("AUTOARM No action on event end since other cal event active")
            return
        if await self.armer.resume_time_of_day():
            _LOGGER.debug("AUTOARM Calendar event %s ended, back to live time of day sensor", self.id)
            return
        end_mode: str = await self.armer.calendar_end_mode(self.arming_state)
        change_context: dict[str, Any] = {
            "caller": "calendar.on_calendar_event_end",
            "calendar_id": self.calendar_id,
            "event_id": self.id,
            "no_event_mode": end_mode,
        }
        if end_mode == NO_CAL_EVENT_MODE_AUTO_SUN:
            _LOGGER.info("AUTOARM Calendar event %s ended, and arming state", self.id)
            # same context for the move via pending and the reset, as both are the one change
            context = self.armer.cause(ChangeSource.CALENDAR, self.event.summary)
            # avoid having state locked in vacation by state calculator by moving via 'Pending'
            await self.armer.pending_state(source=ChangeSource.CALENDAR, change_context=change_context, context=context)
            await self.armer.reset_armed_state(source=ChangeSource.CALENDAR, context=context)
        elif end_mode == NO_CAL_EVENT_MODE_AUTO_OCCUPANCY:
            target_state = self.armer.occupancy_end_state(self.arming_state)
            _LOGGER.info("AUTOARM Calendar event %s ended, and arming by occupancy to %s", self.id, target_state)
            await self.armer.arm(target_state, source=ChangeSource.CALENDAR, change_context=change_context)
        elif end_mode in AlarmControlPanelState:
            _LOGGER.info("AUTOARM Calendar event %s ended, and returning to fixed state %s", self.id, end_mode)
            await self.armer.arm(alarm_state_as_enum(end_mode), source=ChangeSource.CALENDAR, change_context=change_context)
        else:
            _LOGGER.debug("AUTOARM Reinstate previous state on calendar event end in manual mode")
            await self.armer.arm(self.previous_state, source=ChangeSource.CALENDAR, change_context=change_context)

    @classmethod
    def event_id(cls, calendar_id: str, event: CalendarEvent) -> str:
        """Generate an ID for the calendar even if it doesn't natively support `uid`"""
        uid = event.uid or str(hash((event.summary, event.description, event.start.isoformat(), event.end.isoformat())))
        return f"{calendar_id}:{uid}"

    def is_current(self) -> bool:
        if self.track_status == "ended":
            return False
        now_local: dt.datetime = dt_util.now()
        return now_local >= self.event.start_datetime_local and now_local <= self.event.end_datetime_local

    def is_recurring(self) -> bool:
        return self.event.recurrence_id is not None

    def is_future(self) -> bool:
        if self.track_status == "ended":
            return False
        now_local: dt.datetime = dt_util.now()
        return self.event.start_datetime_local > now_local

    def shutdown(self) -> None:
        unlisten(self.start_listener)
        self.start_listener = None
        unlisten(self.end_listener)
        self.end_listener = None

    def __eq__(self, other: object) -> bool:
        """Compare two events based on underlying calendar event"""
        if not isinstance(other, TrackedCalendarEvent):
            return False
        return self.event.uid == other.event.uid


class TrackedCalendar:
    """Listener for a Home Assistant Calendar"""

    def __init__(
        self,
        hass: HomeAssistant,
        calendar_config: ConfigType,
        armer: "AlarmArmer",  # type: ignore # ruff:ignore[undefined-name]
        app_health_tracker: AppHealthTracker,
    ) -> None:
        self.enabled = False
        self.armer = armer
        self.app_health_tracker: AppHealthTracker = app_health_tracker
        self.hass: HomeAssistant = hass
        self.alias: str = cast("str", calendar_config.get(CONF_ALIAS, ""))
        self.entity_id: str = cast("str", calendar_config.get(CONF_ENTITY_ID))
        self.poll_interval: int = calendar_config.get(CONF_CALENDAR_POLL_INTERVAL, 15)
        self.state_mappings: dict[str, list[str]] = cast(
            "dict[str, list[str]]", calendar_config.get(CONF_CALENDAR_EVENT_STATES)
        )
        # self.notify_on_change: str = calendar_config.get(CONF_CALENDAR_ENTRY_NOTIFICATIONS, ENTRY_NOTIFICATION_MATCHED)
        self.tracked_events: dict[str, TrackedCalendarEvent] = {}
        self.poller_listener: CALLBACK_TYPE | None = None
        self.state_listener: CALLBACK_TYPE | None = None
        self.poll_lock: asyncio.Lock = asyncio.Lock()

    async def initialize(self, calendar_platform: entity_platform.EntityPlatform) -> None:
        try:
            calendar_entity: CalendarEntity | None = cast(
                "CalendarEntity|None", calendar_platform.domain_entities.get(self.entity_id)
            )
            if calendar_entity is None:
                self.app_health_tracker.record_initialization_error("calendar_setup")
                _LOGGER.warning("AUTOARM Unable to access calendar %s", self.entity_id)
            else:
                self.calendar_entity = calendar_entity
                _LOGGER.info(
                    "AUTOARM Configured calendar %s from %s, polling every %s minutes",
                    self.entity_id,
                    calendar_platform.platform_name,
                    self.poll_interval,
                )
                self.poller_listener = async_track_utc_time_change(
                    self.hass,
                    self.on_timed_poll,
                    "*",
                    minute=f"/{self.poll_interval}",
                    second=0,
                    local=True,
                )
                self.enabled = True
                # force an initial poll
                await self.match_events()
                # calendar state changes on edits affecting current or next event, so poll then too
                self.state_listener = async_track_state_change_event(self.hass, [self.entity_id], self.on_calendar_state_change)

        except Exception as _e:
            self.app_health_tracker.record_runtime_error()
            _LOGGER.exception("AUTOARM Failed to initialize calendar entity %s", self.entity_id)

    def shutdown(self) -> None:
        unlisten(self.poller_listener)
        self.poller_listener = None
        unlisten(self.state_listener)
        self.state_listener = None
        for tracked_event in self.tracked_events.values():
            tracked_event.shutdown()
        self.enabled = False
        self.tracked_events.clear()

    async def on_timed_poll(self, _called_time: dt.datetime) -> None:
        """Check for new and dead events, entry point for the timed calendar tracker listener"""
        _LOGGER.debug("AUTOARM Calendar Poll")
        # timed and state change polls can coincide at event start/end
        async with self.poll_lock:
            await self.match_events()
            await self.prune_events()

    async def on_calendar_state_change(self, _event: Event[EventStateChangedData]) -> None:
        """Poll immediately when calendar entity changes, e.g. on an edit, rather than wait for timed poll"""
        _LOGGER.debug("AUTOARM Calendar %s state changed, polling", self.entity_id)
        await self.on_timed_poll(dt_util.now())

    def has_active_event(self) -> bool:
        """Is there any event matching a state pattern that is currently open"""
        return any(tevent.is_current() for tevent in self.tracked_events.values())

    def active_events(self) -> list[TrackedCalendarEvent]:
        """List all the events matching a state pattern that are currently open"""
        return [v for v in self.tracked_events.values() if v.is_current()]

    async def has_event_on_day(self, day: dt.date) -> bool:
        """Is there a state-matching event that starts, ends or spans this day"""
        if not self.enabled:
            return False
        start_dt: dt.datetime = dt_util.start_of_local_day(day)
        end_dt: dt.datetime = start_dt + dt.timedelta(days=1)
        events: list[CalendarEvent] = await self.calendar_entity.async_get_events(self.hass, start_dt, end_dt)
        return any(self.match_event(event.summary, event.description) is not None for event in events)

    async def last_event_ended_today(self) -> tuple[dt.datetime, AlarmControlPanelState] | None:
        """End time and state of the state-matching event that most recently ended today"""
        if not self.enabled:
            return None
        now: dt.datetime = dt_util.now()
        events: list[CalendarEvent] = await self.calendar_entity.async_get_events(
            self.hass, dt_util.start_of_local_day(now), now
        )
        ended: list[tuple[dt.datetime, AlarmControlPanelState]] = []
        for event in events:
            state = alarm_state_as_enum(self.match_event(event.summary, event.description))
            if state is not None and event.end_datetime_local <= now:
                ended.append((event.end_datetime_local, state))
        return max(ended, key=lambda ended_event: ended_event[0]) if ended else None

    def match_event(self, summary: str | None, description: str | None) -> str | None:
        for state_str in ALARM_STATES:
            if summary and (state_str.upper() in summary):
                return state_str
            if description and (state_str.upper() in description):
                return state_str
        for state_str, patterns in self.state_mappings.items():
            if (
                summary
                and any(
                    re.search(
                        patt,
                        summary,
                    )
                    for patt in patterns
                )
            ) or (
                description
                and any(
                    re.search(
                        patt,
                        description,
                    )
                    for patt in patterns
                )
            ):
                return state_str
        return None

    async def match_events(self) -> None:
        """Query the calendar for events that match state patterns"""
        now_local = dt_util.now()
        start_dt = now_local - dt.timedelta(minutes=15)
        end_dt = now_local + dt.timedelta(minutes=self.poll_interval + 5)

        events: list[CalendarEvent] = await self.calendar_entity.async_get_events(self.hass, start_dt, end_dt)

        for event in events:
            # presume the events are sorted by start time
            event_id = TrackedCalendarEvent.event_id(self.calendar_entity.entity_id, event)
            _LOGGER.debug("AUTOARM Calendar Event: %s [%s]", event.summary, event_id)

            state_str: str | None = self.match_event(event.summary, event.description)
            if state_str is None:
                if event_id in self.tracked_events:
                    existing_event: TrackedCalendarEvent = self.tracked_events[event_id]
                    _LOGGER.info(
                        "AUTOARM Calendar %s found updated event %s no longer matching",
                        self.calendar_entity.entity_id,
                        event.summary,
                    )
                    await existing_event.remove()
                else:
                    _LOGGER.debug("AUTOARM Ignoring untracked unmatched event")
            else:
                if event_id not in self.tracked_events:
                    state: AlarmControlPanelState | None = alarm_state_as_enum(state_str)
                    if state is None:
                        _LOGGER.warning(
                            "AUTOARM Calendar %s found event %s for invalid state %s",
                            self.calendar_entity.entity_id,
                            event.summary,
                            state_str,
                        )
                    else:
                        _LOGGER.debug(
                            "AUTOARM Calendar %s matched event %s for state %s",
                            self.calendar_entity.entity_id,
                            event.summary,
                            state_str,
                        )

                        self.tracked_events[event_id] = TrackedCalendarEvent(
                            self.calendar_entity.entity_id,
                            event=event,
                            arming_state=state,
                            armer=self.armer,
                            hass=self.hass,
                        )
                        await self.tracked_events[event_id].initialize()
                else:
                    existing_event = self.tracked_events[event_id]
                    if existing_event.event != event:
                        _LOGGER.info(
                            "AUTOARM Calendar %s found updated event %s for state %s",
                            self.calendar_entity.entity_id,
                            event.summary,
                            state_str,
                        )
                        await existing_event.update(event)
                    else:
                        _LOGGER.debug("AUTOARM No change to previously tracked event")

    async def prune_events(self) -> None:
        """Remove past events"""
        to_remove: set[str] = set()
        min_start: dt.datetime | None = None
        max_end: dt.datetime | None = None
        for event_id, tevent in self.tracked_events.items():
            if min_start is None or min_start > tevent.event.start_datetime_local:
                min_start = tevent.event.start_datetime_local
            if max_end is None or max_end < tevent.event.end_datetime_local:
                max_end = tevent.event.end_datetime_local
            if not tevent.is_current() and not tevent.is_future():
                _LOGGER.debug("AUTOARM Pruning expire calendar event: %s", tevent.event.uid)
                to_remove.add(event_id)
                await tevent.end(dt_util.now())

        if min_start and max_end:
            live_event_ids: list[str] = [
                e.uid for e in await self.calendar_entity.async_get_events(self.hass, min_start, max_end) if e.uid is not None
            ]
            for tevent in self.tracked_events.values():
                if tevent.event.uid not in live_event_ids:
                    _LOGGER.debug("AUTOARM Pruning dead calendar event: %s", tevent.event.uid)
                    await tevent.remove()
                    to_remove.add(tevent.id)
        for event_id in to_remove:
            del self.tracked_events[event_id]
