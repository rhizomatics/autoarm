import datetime
import logging
import re
from collections.abc import Callable
from functools import partial
from typing import TYPE_CHECKING, cast

import homeassistant.util.dt as dt_util
from homeassistant.components.alarm_control_panel.const import AlarmControlPanelState
from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.const import CONF_ALIAS, CONF_ENTITY_ID
from homeassistant.helpers import entity_platform
from homeassistant.helpers.event import (
    async_track_point_in_time,
    async_track_utc_time_change,
)
from homeassistant.helpers.typing import ConfigType

from custom_components.autoarm.helpers import alarm_state_as_enum

from .const import (
    CONF_CALENDAR_EVENT_STATES,
    CONF_CALENDAR_POLL_INTERVAL,
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


class TrackedCalendar:
    def __init__(self, calendar_config: ConfigType, armer: "AlarmArmer") -> None:  # type: ignore # noqa: F821
        self.enabled = False
        self.armer = armer
        self.alias: str = cast("str", calendar_config.get(CONF_ALIAS, ""))
        self.entity_id: str = cast("str", calendar_config.get(CONF_ENTITY_ID))
        self.poll_interval: int = calendar_config.get(CONF_CALENDAR_POLL_INTERVAL, 30)
        self.state_mappings: dict[str, list[str]] = cast("dict", calendar_config.get(CONF_CALENDAR_EVENT_STATES))
        self.tracked_events: dict[str, TrackedCalendarEvent] = {}
        self.poller_listener: CALLBACK_TYPE | None = None

    async def initialize(self, calendar_platform: entity_platform.EntityPlatform) -> None:
        try:
            calendar_entity: CalendarEntity = cast("CalendarEntity", calendar_platform.domain_entities[self.entity_id])
            if calendar_entity is None:
                _LOGGER.warning("AUTOARM Unable to access calendar %s", self.entity_id)
            else:
                self.calendar_entity = calendar_entity
                _LOGGER.info("AUTOARM Configured calendar %s from %s", self.entity_id, calendar_platform.platform_name)
                self.poller_listener = async_track_utc_time_change(
                    self.armer.hass,
                    self.on_timed_poll,
                    "*",
                    minute=f"/{self.poll_interval}",
                    second=0,
                    local=True,
                )
                self.enabled = True
                # force an initial poll
                await self.match_events()

        except Exception as _e:
            _LOGGER.exception("AUTOARM Failed to initialize calendar entity %s", self.entity_id)

    def shutdown(self) -> None:
        unlisten(self.poller_listener)
        self.poller_listener = None
        for tracked_event in self.tracked_events.values():
            tracked_event.shutdown()
        self.enabled = False
        self.tracked_events.clear()

    async def on_timed_poll(self, _called_time: datetime.datetime) -> None:
        _LOGGER.debug("AUTOARM Calendar Poll")
        await self.match_events()
        await self.prune_events()

    def has_active_event(self) -> bool:
        return any(tevent.is_current() for tevent in self.tracked_events.values())

    def active_events(self) -> list[CalendarEvent]:
        return [v.event for v in self.tracked_events.values() if v.is_current()]

    async def match_events(self) -> None:
        now_local = dt_util.now()
        start_dt = now_local - datetime.timedelta(minutes=15)
        end_dt = now_local + datetime.timedelta(minutes=self.poll_interval + 5)

        events: list[CalendarEvent] = await self.calendar_entity.async_get_events(self.armer.hass, start_dt, end_dt)

        for event in events:
            # presume the events are sorted by start time
            event_id = TrackedCalendarEvent.event_id(self.calendar_entity.entity_id, event)
            _LOGGER.debug("AUTOARM Calendar Event: %s", event_id)
            for state_str, patterns in self.state_mappings.items():
                if any(
                    re.match(
                        patt,
                        event.summary,
                    )
                    for patt in patterns
                ):
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
                            _LOGGER.info(
                                "AUTOARM Calendar %s matched event %s for state %s",
                                self.calendar_entity.entity_id,
                                event.summary,
                                state_str,
                            )

                            self.tracked_events[event_id] = TrackedCalendarEvent(
                                self.calendar_entity.entity_id, event, state, self.armer
                            )
                            await self.tracked_events[event_id].initialize()

    async def prune_events(self) -> None:
        to_remove: list[str] = []
        for event_id, tevent in self.tracked_events.items():
            if not tevent.is_current() and not tevent.is_future():
                _LOGGER.debug("AUTOARM Pruning expire calendar event: %s", tevent.event.uid)
                to_remove.append(event_id)
                await tevent.end(dt_util.now())
        for event_id in to_remove:
            del self.tracked_events[event_id]


class TrackedCalendarEvent:
    def __init__(
        self,
        calendar_id: str,
        event: CalendarEvent,
        arming_state: AlarmControlPanelState,
        armer: "AlarmArmer",  # type: ignore # noqa: F821
    ) -> None:
        self.tracked_at = dt_util.now()
        self.calendar_id = calendar_id
        self.id = TrackedCalendarEvent.event_id(calendar_id, event)
        self.event: CalendarEvent = event
        self.arming_state: AlarmControlPanelState = arming_state
        self.start_listener: Callable | None = None
        self.end_listener: Callable | None = None
        self.armer = armer
        self.previous_state: AlarmControlPanelState | None = armer.armed_state()
        self.track_status: str = "pending"

    async def initialize(self) -> None:

        if self.event.end_datetime_local < self.tracked_at:
            _LOGGER.debug("AUTOARM Ignoring past event")
            self.track_status = "ended"
            return
        if self.event.start_datetime_local > self.tracked_at:
            self.start_listener = async_track_point_in_time(
                self.armer.hass,
                partial(self.armer.on_calendar_event_start, self),
                self.event.start_datetime_local,
            )
        else:
            await self.armer.on_calendar_event_start(self, dt_util.now())
            self.track_status = "started"
        if self.event.end_datetime_local > self.tracked_at:
            self.end_listener = async_track_point_in_time(
                self.armer.hass,
                self.end,
                self.event.end_datetime_local,
            )
        _LOGGER.info("AUTOARM Now tracking %s event %s, %s", self.calendar_id, self.event.uid, self.event.summary)

    async def end(self, event_time: datetime.datetime) -> None:
        _LOGGER.debug("AUTOARM Calendar event %s ended, event_time: %s", self.id, event_time)
        self.track_status = "ended"
        await self.armer.on_calendar_event_end(self, dt_util.now())
        self.shutdown()

    @classmethod
    def event_id(cls, calendar_id: str, event: CalendarEvent) -> str:
        uid = event.uid or str(hash((event.summary, event.description, event.start.isoformat(), event.end.isoformat())))
        return f"{calendar_id}:{uid}"

    def is_current(self) -> bool:
        if self.track_status == "ended":
            return False
        now_local: datetime.datetime = dt_util.now()
        return now_local >= self.event.start_datetime_local and now_local <= self.event.end_datetime_local

    def is_future(self) -> bool:
        if self.track_status == "ended":
            return False
        now_local: datetime.datetime = dt_util.now()
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
