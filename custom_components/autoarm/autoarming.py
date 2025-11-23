import asyncio
import datetime
import logging
import re
import time
from collections.abc import Callable
from functools import partial
from typing import cast

import homeassistant.util.dt as dt_util
from homeassistant.components.alarm_control_panel.const import AlarmControlPanelState
from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.components.calendar.const import DOMAIN as CALENDAR_DOMAIN
from homeassistant.components.sun.const import STATE_BELOW_HORIZON
from homeassistant.const import (
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
    STATE_HOME,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, State, callback
from homeassistant.helpers import entity_platform
from homeassistant.helpers.event import (
    async_track_point_in_time,
    async_track_state_change_event,
    async_track_sunrise,
    async_track_sunset,
    async_track_utc_time_change,
)
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_ACTIONS,
    CONF_ALARM_PANEL,
    CONF_ARM_AWAY_DELAY,
    CONF_AUTO_ARM,
    CONF_BUTTON_ENTITY_AWAY,
    CONF_BUTTON_ENTITY_DISARM,
    CONF_BUTTON_ENTITY_RESET,
    CONF_CALENDAR_ENTITY,
    CONF_CALENDAR_EVENT_STATES,
    CONF_CALENDAR_NO_EVENT,
    CONF_CALENDAR_POLL_INTERVAL,
    CONF_NOTIFY,
    CONF_OCCUPANTS,
    CONF_SLEEP_END,
    CONF_SLEEP_START,
    CONF_SUNRISE_CUTOFF,
    CONF_THROTTLE_CALLS,
    CONF_THROTTLE_SECONDS,
    CONFIG_SCHEMA,
    DOMAIN,
    NO_CAL_EVENT_MODE_AUTO,
    NO_CAL_EVENT_MODE_MANUAL,
)

_LOGGER = logging.getLogger(__name__)

OVERRIDE_STATES = (AlarmControlPanelState.ARMED_VACATION, AlarmControlPanelState.ARMED_CUSTOM_BYPASS)
EPHEMERAL_STATES = (
    AlarmControlPanelState.PENDING,
    AlarmControlPanelState.ARMING,
    AlarmControlPanelState.DISARMING,
    AlarmControlPanelState.TRIGGERED,
)
ZOMBIE_STATES = ("unknown", "unavailable")
NS_MOBILE_ACTIONS = "mobile_actions"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    _ = CONFIG_SCHEMA
    config = config.get(DOMAIN, {})
    hass.states.async_set(
        f"{DOMAIN}.configured",
        "True",
        {
            CONF_ALARM_PANEL: config.get(CONF_ALARM_PANEL),
            CONF_AUTO_ARM: config.get(CONF_AUTO_ARM, True),
            CONF_SLEEP_START: config.get(CONF_SLEEP_START),
            CONF_SLEEP_END: config.get(CONF_SLEEP_END),
            CONF_SUNRISE_CUTOFF: config.get(CONF_SUNRISE_CUTOFF),
            CONF_CALENDAR_ENTITY: config.get(CONF_CALENDAR_ENTITY),
            CONF_CALENDAR_EVENT_STATES: config.get(CONF_CALENDAR_EVENT_STATES, {}),
            CONF_CALENDAR_POLL_INTERVAL: config.get(CONF_CALENDAR_POLL_INTERVAL, 30),
            CONF_ARM_AWAY_DELAY: config.get(CONF_ARM_AWAY_DELAY, ()),
            CONF_BUTTON_ENTITY_RESET: config.get(CONF_BUTTON_ENTITY_RESET),
            CONF_BUTTON_ENTITY_AWAY: config.get(CONF_BUTTON_ENTITY_AWAY),
            CONF_BUTTON_ENTITY_DISARM: config.get(CONF_BUTTON_ENTITY_DISARM),
            CONF_OCCUPANTS: config.get(CONF_OCCUPANTS, []),
            CONF_ACTIONS: config.get(CONF_ACTIONS, []),
            CONF_NOTIFY: config.get(CONF_NOTIFY, {}),
            CONF_THROTTLE_SECONDS: config.get(CONF_THROTTLE_SECONDS, 60),
            CONF_THROTTLE_CALLS: config.get(CONF_THROTTLE_CALLS, 6),
        },
    )

    armer = AlarmArmer(
        hass,
        alarm_panel=config[CONF_ALARM_PANEL],
        auto_disarm=config[CONF_AUTO_ARM],
        sleep_start=cast("datetime.time", config.get(CONF_SLEEP_START)),
        sleep_end=cast("datetime.time", config.get(CONF_SLEEP_END)),
        sunrise_cutoff=cast("datetime.time", config.get(CONF_SUNRISE_CUTOFF)),
        arm_away_delay=config[CONF_ARM_AWAY_DELAY],
        reset_button=config.get(CONF_BUTTON_ENTITY_RESET),
        away_button=config.get(CONF_BUTTON_ENTITY_AWAY),
        disarm_button=config.get(CONF_BUTTON_ENTITY_DISARM),
        occupants=config[CONF_OCCUPANTS],
        actions=config[CONF_ACTIONS],
        notify=config[CONF_NOTIFY],
        throttle_calls=config.get(CONF_THROTTLE_CALLS, 6),
        throttle_seconds=config.get(CONF_THROTTLE_SECONDS, 60),
        calendar_entity_ids=config.get(CONF_CALENDAR_ENTITY, []),
        calendar_interval=config.get(CONF_CALENDAR_POLL_INTERVAL, 30),
        calendar_event_patterns=config.get(CONF_CALENDAR_EVENT_STATES, {}),
        calendar_no_event_mode=config.get(CONF_CALENDAR_NO_EVENT, NO_CAL_EVENT_MODE_AUTO),
    )
    await armer.initialize()
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, armer.async_shutdown)

    return True


class TrackedCalendarEvent:
    def __init__(self, calendar_id: str, event: CalendarEvent, arming_state: str, armer: "AlarmArmer") -> None:
        self.tracked_at = dt_util.now()
        self.calendar_id = calendar_id
        self.id = TrackedCalendarEvent.event_id(calendar_id, event)
        _LOGGER.info("AUTOARM N")
        self.event: CalendarEvent = event
        self.arming_state: str = arming_state
        self.start_listener: Callable | None = None
        self.end_listener: Callable | None = None
        if event.start_datetime_local > self.tracked_at:
            self.start_listener = async_track_point_in_time(
                armer.hass,
                partial(armer.on_calendar_event_start, self),
                event.start_datetime_local,
            )
        if event.end_datetime_local > self.tracked_at:
            self.end_listener = async_track_point_in_time(
                armer.hass,
                partial(armer.on_calendar_event_end, self),
                event.end_datetime_local,
            )

    @classmethod
    def event_id(cls, calendar_id: str, event: CalendarEvent) -> str:
        uid = event.uid or str(hash((event.summary, event.description, event.start.isoformat(), event.end.isoformat())))
        return f"{calendar_id}:{uid}"

    def is_current(self) -> bool:
        now_local: datetime.datetime = dt_util.now()
        return now_local >= self.event.start_datetime_local and now_local <= self.event.end_datetime_local

    def is_future(self) -> bool:
        now_local: datetime.datetime = dt_util.now()
        return self.event.start_datetime_local > now_local

    def cancel_listeners(self) -> None:
        if self.start_listener:
            self.start_listener()
            self.start_listener = None
        if self.end_listener:
            self.end_listener()
            self.end_listener = None

    def __eq__(self, other: object) -> bool:
        """Compare two events based on underlying calendar event"""
        if not isinstance(other, TrackedCalendarEvent):
            return False
        return self.event.uid == other.event.uid


class AlarmArmer:
    def __init__(
        self,
        hass: HomeAssistant,
        alarm_panel: str,
        auto_disarm: bool = True,
        sleep_start: datetime.time | None = None,
        sleep_end: datetime.time | None = None,
        sunrise_cutoff: datetime.time | None = None,
        arm_away_delay: int | None = None,
        reset_button: str | None = None,
        away_button: str | None = None,
        disarm_button: str | None = None,
        occupants: list | None = None,
        actions: list | None = None,
        notify: dict | None = None,
        throttle_calls: int = 6,
        throttle_seconds: int = 60,
        calendar_entity_ids: list[str] | None = None,
        calendar_no_event_mode: str | None = None,
        calendar_interval: int = 15,
        calendar_event_patterns: dict[str, list[str]] | None = None,
    ) -> None:
        self.hass: HomeAssistant = hass
        self.local_tz = dt_util.get_time_zone(self.hass.config.time_zone)
        self.calendar_entity_ids: list[str] | None = calendar_entity_ids or []
        self.calendar_interval: int = calendar_interval
        self.calendar_no_event_mode = calendar_no_event_mode
        self.calendars: list[CalendarEntity] = []
        self.calendar_event_patterns: dict[str, list[str]] = calendar_event_patterns or {}
        self.alarm_panel: str = alarm_panel
        self.auto_disarm: bool = auto_disarm
        self.sleep_start: datetime.time | None = sleep_start
        self.sleep_end: datetime.time | None = sleep_end
        self.sunrise_cutoff: datetime.time | None = sunrise_cutoff
        self.arm_away_delay: int | None = arm_away_delay
        self.reset_button: str | None = reset_button
        self.away_button: str | None = away_button
        self.disarm_button: str | None = disarm_button
        self.occupants: list[str] = occupants or []
        self.actions: list[str] = actions or []
        self.notify_profiles: dict[str, dict] = notify or {}
        self.unsubscribes: list = []
        self.last_request: datetime.datetime | None = None
        self.calendar_events: dict[str, TrackedCalendarEvent] = {}
        self.button_device: dict[str, str] = {}
        self.arming_in_progress: asyncio.Event = asyncio.Event()
        self.rate_limiter: Limiter = Limiter(window=throttle_seconds, max_calls=throttle_calls)

    async def initialize(self) -> None:
        """Async initialization"""
        _LOGGER.info(
            "AUTOARM auto_disarm=%s, arm_delay=%s, awake=%s, occupied=%s, state=%s",
            self.auto_disarm,
            self.arm_away_delay,
            self.is_awake(),
            self.is_occupied(),
            self.armed_state(),
        )

        self.initialize_alarm_panel()
        await self.initialize_calendar()
        self.initialize_diurnal()
        self.initialize_occupancy()
        self.initialize_bedtime()
        self.initialize_buttons()
        await self.reset_armed_state(force_arm=False)
        self.initialize_integration()
        _LOGGER.info("AUTOARM Initialized, state: %s", self.armed_state())

    def initialize_integration(self) -> None:
        self.unsubscribes.append(self.hass.bus.async_listen("mobile_app_notification_action", self.on_mobile_action))
        self.unsubscribes.append(self.hass.bus.async_listen(EVENT_HOMEASSISTANT_START, self.ha_start))

    @callback
    async def ha_start(self, _event: Event) -> None:
        _LOGGER.debug("AUTOARM Home assistant restarted")
        await self.reset_armed_state(force_arm=False)

    async def async_shutdown(self, _event: Event) -> None:
        _LOGGER.info("AUTOARM shutting down")
        self.shutdown()

    def shutdown(self) -> None:
        for tracked_event in self.calendar_events.values():
            tracked_event.cancel_listeners()
        for unsub in self.unsubscribes:
            unsub()
        _LOGGER.info("AUTOARM shut down")

    def initialize_alarm_panel(self) -> None:
        """Set up automation for Home Assistant alarm panel

        See https://www.home-assistant.io/integrations/alarm_control_panel/
        """
        self.unsubscribes.append(async_track_state_change_event(self.hass, [self.alarm_panel], self.on_panel_change))
        _LOGGER.debug("AUTOARM Auto-arming %s", self.alarm_panel)

    def initialize_diurnal(self) -> None:
        # events API expects a function, however underlying HassJob is fine with coroutines
        self.unsubscribes.append(async_track_sunrise(self.hass, self.on_sunrise, None))  # type: ignore
        self.unsubscribes.append(async_track_sunset(self.hass, self.on_sunset, None))  # type: ignore

    def initialize_occupancy(self) -> None:
        """Configure occupants, and listen for changes in their state"""
        _LOGGER.info("AUTOARM Occupancy determined by %s", ",".join(self.occupants))
        self.unsubscribes.append(async_track_state_change_event(self.hass, self.occupants, self.on_occupancy_change))
        _LOGGER.debug(
            "AUTOARM Occupied: %s, Unoccupied: %s, Night: %s",
            self.is_occupied(),
            self.is_unoccupied(),
            self.is_night(),
        )

    async def initialize_calendar(self, interval: int = 15) -> None:
        """Configure calendar polling (optional)"""
        if not self.calendar_entity_ids:
            return
        try:
            platform: entity_platform.EntityPlatform = entity_platform.async_get_platforms(self.hass, CALENDAR_DOMAIN)[0]
        except Exception as e:
            _LOGGER.error("AUTOARM Unable to access calendar platform", self.calendar_entity_ids, e)
            return
        for entity_id in self.calendar_entity_ids:
            try:
                calendar: CalendarEntity = cast("CalendarEntity", platform.domain_entities[entity_id])
                if calendar is None:
                    _LOGGER.warning("AUTOARM Unable to access calendar %s", entity_id)
                else:
                    self.calendars.append(calendar)
            except Exception as e:
                _LOGGER.error("AUTOARM Failed to initialize calendar entity %s: %s", self.calendar_entity_ids, e)

        await self.on_calendar_poll(datetime.datetime.now(tz=datetime.UTC))

        self.unsubscribes.append(
            async_track_utc_time_change(
                self.hass,
                self.on_calendar_poll,
                "*",
                minute=f"/{interval}",
                second=0,
                local=True,
            )
        )

    async def on_calendar_poll(self, _called_time: datetime.datetime) -> None:
        _LOGGER.debug("AUTOARM Calendar Poll")
        if self.calendars:
            now_local = dt_util.now()
            start_dt = now_local - datetime.timedelta(minutes=15)
            end_dt = now_local + datetime.timedelta(minutes=self.calendar_interval + 5)
            for calendar in self.calendars:
                events: list[CalendarEvent] = await calendar.async_get_events(self.hass, start_dt, end_dt)

                for event in events:
                    # presume the events are sorted by start time
                    event_id = TrackedCalendarEvent.event_id(calendar.entity_id, event)
                    _LOGGER.debug("AUTOARM Calendar Event: %s", event_id)
                    for state, patterns in self.calendar_event_patterns.items():
                        if any(
                            re.match(
                                patt,
                                event.summary,
                            )
                            for patt in patterns
                        ):
                            _LOGGER.debug("AUTOARM Calendar matched %d events for state %s", len(events), state)
                            if event_id not in self.calendar_events:
                                self.calendar_events[event_id] = TrackedCalendarEvent(calendar.entity_id, event, state, self)
                            tracked_event: TrackedCalendarEvent = self.calendar_events[event_id]
                            if tracked_event.is_current():
                                await self.on_calendar_event_start(tracked_event, dt_util.now())

            to_remove: list[str] = []
            for event_id, tevent in self.calendar_events.items():
                if not tevent.is_current() and not tevent.is_future():
                    _LOGGER.debug("AUTOARM Pruning expire calendar event: %s", tevent.event.uid)
                    to_remove.append(event_id)
                    tevent.cancel_listeners()
            for event_id in to_remove:
                del self.calendar_events[event_id]

    def active_calendar_event(self) -> bool:
        return any(tevent.is_current() for tevent in self.calendar_events.values())

    async def on_calendar_event_start(self, event: TrackedCalendarEvent, triggered_at: datetime.datetime) -> None:
        _LOGGER.debug("AUTOARM on_calendar_event_start(%s,%s)", event.id, triggered_at)
        if event.arming_state != self.armed_state():
            _LOGGER.info("AUTOARM Calendar event %s changing arming to %s at %s", event.id, event.arming_state, triggered_at)
            await self.arm(arming_state=event.arming_state)
        self.hass.states.async_set(f"{DOMAIN}.last_calendar_event",
                                   str(event.id),
                                   attributes={"calendar": event.calendar_id,
                                               "start": event.event.start_datetime_local,
                                               "end": event.event.end_datetime_local,
                                               "summary": event.event.summary,
                                               "description": event.event.description,
                                               "uid": event.event.uid})

    async def on_calendar_event_end(self, event: TrackedCalendarEvent, ended_at: datetime.datetime) -> None:
        _LOGGER.debug("AUTOARM on_calendar_event_start(%s,%s)", event.id, ended_at)
        if self.calendar_no_event_mode == NO_CAL_EVENT_MODE_AUTO:
            _LOGGER.info("AUTOARM Calendar event %s ended, and arming state", event.id)
            await self.reset_armed_state()
        elif self.calendar_no_event_mode in AlarmControlPanelState:
            _LOGGER.info("AUTOARM Calendar event %s ended, and returning to fixed state %s", event.id, self.calendar_no_event_mode)
            await self.arm(self.calendar_no_event_mode)
        else:
            _LOGGER.debug("AUTOARM No action on calendar event end in manual mode")

    def initialize_bedtime(self) -> None:
        """Configure usual bed time (optional)"""
        if self.sleep_start:
            self.unsubscribes.append(
                async_track_utc_time_change(
                    self.hass,
                    self.on_sleep_start,
                    self.sleep_start.hour,
                    self.sleep_start.minute,
                    self.sleep_start.second,
                    local=True,
                )
            )
        if self.sleep_end:
            self.unsubscribes.append(
                async_track_utc_time_change(
                    self.hass,
                    self.on_sleep_end,
                    self.sleep_end.hour,
                    self.sleep_end.minute,
                    self.sleep_end.second,
                    local=True,
                )
            )
        _LOGGER.debug("AUTOARM Bed time from %s->%s", self.sleep_start, self.sleep_end)

    def initialize_buttons(self) -> None:
        """Initialize (optional) physical alarm state control buttons"""

        def setup_button(state: str, button_entity: str, cb: Callable) -> None:
            self.button_device[state] = button_entity
            if self.button_device[state]:
                self.unsubscribes.append(async_track_state_change_event(self.hass, [button_entity], cb))

                _LOGGER.debug(
                    "AUTOARM Configured %s button for %s",
                    state,
                    self.button_device[state],
                )

        if self.reset_button:
            setup_button("reset", self.reset_button, self.on_reset_button)
        if self.away_button:
            setup_button("away", self.away_button, self.on_away_button)
        if self.disarm_button:
            setup_button("disarm", self.disarm_button, self.on_disarm_button)

    def safe_state(self, state: State | None) -> str | None:
        try:
            return state.state if state is not None else None
        except Exception as e:
            _LOGGER.debug("AUTOARM Failed to load state %s: %s", state, e)
            return None

    def is_occupied(self) -> bool:
        return any(self.safe_state(self.hass.states.get(p)) == STATE_HOME for p in self.occupants)

    def is_unoccupied(self) -> bool:
        return all(self.safe_state(self.hass.states.get(p)) != STATE_HOME for p in self.occupants)

    def is_night(self) -> bool:
        return self.safe_state(self.hass.states.get("sun.sun")) == STATE_BELOW_HORIZON

    def armed_state(self) -> str | None:
        return self.safe_state(self.hass.states.get(self.alarm_panel))

    @callback
    async def on_panel_change(self, event: Event[EventStateChangedData]) -> None:
        entity_id, old, new = self._extract_event(event)
        if self.arming_in_progress.is_set():
            _LOGGER.debug(
                "AUTOARM Panel Change Ignored: %s,%s: %s-->%s",
                entity_id,
                event.event_type,
                old,
                new,
            )
            return
        _LOGGER.info(
            "AUTOARM Panel Change: %s,%s: %s-->%s",
            entity_id,
            event.event_type,
            old,
            new,
        )

        if new in ZOMBIE_STATES:
            _LOGGER.warning("AUTOARM Dezombifying %s ...", new)
            await self.reset_armed_state()
        else:
            message = f"Home Assistant alert level now set from {old} to {new}"
            await self.notify(message, title=f"Alarm now {new}", profile="quiet")

    def _extract_event(self, event: Event[EventStateChangedData]) -> tuple:
        entity_id = old = new = None
        if event and event.data:
            entity_id = event.data.get("entity_id")
            old_obj = event.data.get("old_state")
            if old_obj:
                old = old_obj.state
            new_obj = event.data.get("new_state")
            if new_obj:
                new = new_obj.state
        return entity_id, old, new

    @callback
    async def on_occupancy_change(self, event: Event[EventStateChangedData]) -> None:
        """Listen for person state events

        Args:
        ----
            event (Event[EventStateChangedData]): state change event

        """
        entity_id, old, new = self._extract_event(event)
        existing_state = self.armed_state()
        _LOGGER.debug("AUTOARM Occupancy Change: %s, %s, %s, %s", entity_id, old, new, event)
        if self.is_unoccupied() and existing_state in (
            AlarmControlPanelState.ARMED_HOME,
            AlarmControlPanelState.DISARMED,
            AlarmControlPanelState.ARMED_NIGHT,
        ):
            _LOGGER.info("AUTOARM Now unoccupied, arming")
            await self.arm(AlarmControlPanelState.ARMED_AWAY)
        elif self.is_occupied() and existing_state == AlarmControlPanelState.ARMED_AWAY:
            _LOGGER.info("AUTOARM Now occupied, resetting armed state")
            await self.reset_armed_state()

    def is_awake(self) -> bool:
        """Use the sleeping time config to work out if occupants should be awake now

        Returns
        -------
            bool: True is in defined waking time

        """
        awake = False
        if self.sleep_start and self.sleep_end:
            now = datetime.datetime.now(tz=self.local_tz)
            if now.time() >= self.sleep_end and now.time() <= self.sleep_start:
                awake = True
        else:
            awake = not self.is_night()
        self.hass.states.async_set(f"{DOMAIN}.awake", str(awake), {})
        return awake

    async def reset_armed_state(self, force_arm: bool = True, hint_arming: str | None = None) -> str | None:
        """Logic to automatically work out appropriate current armed state"""
        _LOGGER.debug(
            "AUTOARM reset_armed_state(force_arm=%s,hint_arming=%s)",
            force_arm,
            hint_arming,
        )

        existing_state = self.armed_state()
        if self.calendar_entity_ids:
            if self.active_calendar_event():
                _LOGGER.debug("AUTOARM Ignoring reset while calendar event active")
                return existing_state
            if self.calendar_no_event_mode == NO_CAL_EVENT_MODE_MANUAL:
                _LOGGER.debug("AUTOARM Ignoring reset while calendar configured, no active event, and default mode is manual")
                return existing_state
            if self.calendar_no_event_mode in AlarmControlPanelState:
                return await self.arm(self.calendar_no_event_mode)
            if self.calendar_no_event_mode == NO_CAL_EVENT_MODE_AUTO:
                _LOGGER.debug("AUTOARM Applying reset while calendar configured, no active event, and default mode is auto")
            else:
                _LOGGER.warning("AUTOARM Unexpected state for calendar no event mode: %s", self.calendar_no_event_mode)
        if existing_state == AlarmControlPanelState.DISARMED and not force_arm:
            _LOGGER.debug("AUTOARM Ignoring unforced reset for disarmed")
            return existing_state

        if existing_state in OVERRIDE_STATES and not force_arm:
            _LOGGER.debug("AUTOARM Ignoring reset for existing state: %s", existing_state)
            return existing_state

        if self.is_occupied():
            if self.auto_disarm and self.is_awake() and not force_arm:
                _LOGGER.info("AUTOARM Disarming for occupied during waking hours")
                return await self.arm(AlarmControlPanelState.DISARMED)
            if not self.is_awake():
                _LOGGER.info("AUTOARM Arming for occupied out of waking hours")
                return await self.arm(AlarmControlPanelState.ARMED_NIGHT)
            if hint_arming:
                _LOGGER.info("AUTOARM Using hinted arming state: %s", hint_arming)
                return await self.arm(hint_arming)
            _LOGGER.info("AUTOARM Defaulting to armed home")
            return await self.arm(AlarmControlPanelState.ARMED_HOME)

        if hint_arming:
            _LOGGER.info("AUTOARM Using hinted arming state: %s", hint_arming)
            return await self.arm(hint_arming)
        _LOGGER.info("AUTOARM Defaulting to armed away")
        return await self.arm(AlarmControlPanelState.ARMED_AWAY)

    async def delayed_arm(
        self, arming_state: str, reset: bool, requested_at: datetime.datetime, triggered_at: datetime.datetime
    ) -> None:
        _LOGGER.debug(
            "Delayed_arm %s, reset: %s, triggered at: %s",
            arming_state,
            reset,
            triggered_at,
        )

        if self.last_request is not None and requested_at is not None:
            if self.last_request > requested_at:
                _LOGGER.debug(
                    "AUTOARM Cancelling delayed request for %s since subsequent manual action",
                    arming_state,
                )
                return
            _LOGGER.debug(
                "AUTOARM Delayed execution of %s requested at %s",
                arming_state,
                requested_at,
            )
        if reset:
            await self.reset_armed_state(force_arm=True, hint_arming=arming_state)
        else:
            await self.arm(arming_state=arming_state)
        return

    async def arm(self, arming_state: str | None = None) -> str | None:
        """Change alarm panel state

        Args:
        ----
            arming_state (str, optional): _description_. Defaults to None.

        Returns:
        -------
            str: New arming state

        """
        if self.rate_limiter.triggered():
            _LOGGER.debug("AUTOARM Rate limit triggered, skipping arm")
            return None
        try:
            self.arming_in_progress.set()
            existing_state = self.armed_state()
            if arming_state != existing_state:
                self.hass.states.async_set(self.alarm_panel, str(arming_state))
                _LOGGER.info(
                    "AUTOARM Setting %s from %s to %s",
                    self.alarm_panel,
                    existing_state,
                    arming_state,
                )
                return arming_state
            _LOGGER.debug("Skipping arm, as %s already %s", self.alarm_panel, arming_state)
            return existing_state
        except Exception as e:
            _LOGGER.debug("AUTOARM Failed to arm: %s", e)
        finally:
            self.arming_in_progress.clear()
        return None

    async def notify(self, message: str, profile: str = "normal", title: str | None = None) -> None:
        notify_service = None
        try:
            # separately merge base dict and data sub-dict as cheap and nasty semi-deep-merge
            selected_profile = self.notify_profiles.get(profile)
            base_profile = self.notify_profiles.get("common", {})
            base_profile_data = base_profile.get("data", {})
            merged_profile = dict(base_profile)
            merged_profile_data = dict(base_profile_data)
            if selected_profile:
                selected_profile_data: dict = selected_profile.get("data", {})
                merged_profile.update(selected_profile)
                merged_profile_data.update(selected_profile_data)
            merged_profile["data"] = merged_profile_data
            notify_service = merged_profile.get("service", "").replace("notify.", "")

            title = title or "Alarm Auto Arming"
            if notify_service and merged_profile:
                data = merged_profile.get("data", {})
                await self.hass.services.async_call(
                    "notify",
                    notify_service,
                    service_data={"message": message, "title": title, "data": data},
                )
            else:
                _LOGGER.debug("AUTOARM Skipped notification, service: %s, data: %s", notify_service, merged_profile)

        except Exception:
            _LOGGER.exception("AUTOARM %s failed", notify_service)

    @callback
    async def on_sleep_start(self, called_time: datetime.datetime) -> None:
        _LOGGER.debug("AUTOARM Sleep Period Start: %s", called_time)
        await self.reset_armed_state(force_arm=True)

    @callback
    async def on_sleep_end(self, called_time: datetime.datetime) -> None:
        _LOGGER.debug("AUTOARM Sleep Period End: %s", called_time)
        await self.reset_armed_state(force_arm=False)

    @callback
    async def on_reset_button(self, event: Event) -> None:
        _LOGGER.debug("AUTOARM Reset Button: %s", event)
        self.register_request()
        await self.reset_armed_state(force_arm=True)

    @callback
    async def on_mobile_action(self, event: Event) -> None:
        _LOGGER.debug("AUTOARM Mobile Action: %s", event)
        self.register_request()
        match event.data.get("action"):
            case "ALARM_PANEL_DISARM":
                await self.arm(AlarmControlPanelState.DISARMED)
            case "ALARM_PANEL_RESET":
                await self.reset_armed_state(force_arm=True)
            case "ALARM_PANEL_AWAY":
                await self.arm(AlarmControlPanelState.ARMED_AWAY)
            case _:
                _LOGGER.debug("AUTOARM Ignoring mobile action: %s", event.data)

    @callback
    async def on_disarm_button(self, event: Event) -> None:
        _LOGGER.info("AUTOARM Disarm Button: %s", event)
        self.register_request()
        await self.arm(AlarmControlPanelState.DISARMED)

    @callback
    async def on_vacation_button(self, event: Event) -> None:
        _LOGGER.info("AUTOARM Vacation Button: %s", event)
        await self.arm(AlarmControlPanelState.ARMED_VACATION)

    def register_request(self) -> None:
        self.last_request = datetime.datetime.now(datetime.UTC)

    @callback
    async def on_away_button(self, event: Event) -> None:
        _LOGGER.info("AUTOARM Away Button: %s", event)
        self.register_request()
        if self.arm_away_delay:
            self.unsubscribes.append(
                async_track_point_in_time(
                    self.hass,
                    partial(
                        self.delayed_arm,
                        AlarmControlPanelState.ARMED_AWAY,
                        False,
                        dt_util.utc_from_timestamp(time.time()),
                    ),
                    dt_util.utc_from_timestamp(time.time() + self.arm_away_delay),
                )
            )
            await self.notify(
                f"Alarm will be armed for away in {self.arm_away_delay} seconds",
                title="Arm for away process starting",
            )
        else:
            await self.arm(AlarmControlPanelState.ARMED_AWAY)

    @callback
    async def on_sunrise(self) -> None:
        _LOGGER.debug("AUTOARM Sunrise")
        now = datetime.datetime.now(tz=self.local_tz)
        if not self.sunrise_cutoff or now.time() >= self.sunrise_cutoff:
            # sun is up, and not earlier than cutoff
            await self.reset_armed_state(force_arm=False)
        elif self.sunrise_cutoff and now.time() < self.sunrise_cutoff:
            _LOGGER.debug(
                "AUTOARM Rescheduling delayed sunrise action to %s",
                self.sunrise_cutoff,
            )
            trigger = datetime.datetime.combine(now.date(), self.sunrise_cutoff, tzinfo=self.local_tz)
            self.unsubscribes.append(
                async_track_point_in_time(
                    self.hass, partial(self.delayed_arm, AlarmControlPanelState.ARMED_HOME, True, now), trigger
                )
            )

    @callback
    async def on_sunset(self) -> None:
        _LOGGER.debug("AUTOARM Sunset")
        await self.reset_armed_state(force_arm=True)


class Limiter:
    """Rate limiting tracker"""

    def __init__(self, window: int = 60, max_calls: int = 4) -> None:
        self.calls: list[float] = []
        self.window: int = window
        self.max_calls: int = max_calls
        _LOGGER.debug(
            "AUTOARM Rate limiter initialized with window %s and max_calls %s",
            window,
            max_calls,
        )

    def triggered(self) -> bool:
        """Register a call and check if window based rate limit triggered"""
        cut_off = time.time() - self.window
        self.calls.append(time.time())
        in_scope = 0

        for call in self.calls[:]:
            if call >= cut_off:
                in_scope += 1
            else:
                self.calls.remove(call)

        return in_scope > self.max_calls
