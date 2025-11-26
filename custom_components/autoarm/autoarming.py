import asyncio
import contextlib
import datetime
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, Any, cast

import homeassistant.util.dt as dt_util
import voluptuous as vol
from homeassistant.components.alarm_control_panel.const import AlarmControlPanelState
from homeassistant.components.calendar import CalendarEvent
from homeassistant.components.calendar.const import DOMAIN as CALENDAR_DOMAIN
from homeassistant.components.sun.const import STATE_BELOW_HORIZON
from homeassistant.const import CONF_CONDITIONS, EVENT_HOMEASSISTANT_STOP, SERVICE_RELOAD, STATE_HOME
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ConditionError, HomeAssistantError
from homeassistant.helpers import condition as condition
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_platform
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import (
    async_track_point_in_time,
    async_track_state_change_event,
    async_track_sunrise,
    async_track_sunset,
    async_track_time_change,
)
from homeassistant.helpers.reload import (
    async_integration_yaml_config,
)
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

from custom_components.autoarm.hass_api import HomeAssistantAPI

from .calendar import TrackedCalendar, TrackedCalendarEvent
from .const import (
    CONF_ALARM_PANEL,
    CONF_ARM_AWAY_DELAY,
    CONF_BUTTON_ENTITY_AWAY,
    CONF_BUTTON_ENTITY_DISARM,
    CONF_BUTTON_ENTITY_RESET,
    CONF_CALENDAR_CONTROL,
    CONF_CALENDAR_NO_EVENT,
    CONF_CALENDARS,
    CONF_NOTIFY,
    CONF_OCCUPANTS,
    CONF_OCCUPIED_DAY_DEFAULT,
    CONF_SUNRISE_CUTOFF,
    CONF_THROTTLE_CALLS,
    CONF_THROTTLE_SECONDS,
    CONF_TRANSITIONS,
    CONFIG_SCHEMA,
    DEFAULT_TRANSITIONS,
    DOMAIN,
    NO_CAL_EVENT_MODE_AUTO,
    NO_CAL_EVENT_MODE_MANUAL,
    ChangeSource,
    ConditionVariables,
)
from .helpers import alarm_state_as_enum, safe_state

if TYPE_CHECKING:
    from homeassistant.helpers.condition import ConditionCheckerType

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
PLATFORMS = ["autoarm"]

HASS_DATA_KEY: HassKey["AutoArmData"] = HassKey(DOMAIN)


@dataclass
class AutoArmData:
    armer: "AlarmArmer"
    other_data: dict[str, Any]


# async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
async def async_setup(
    hass: HomeAssistant,
    config: ConfigType,
) -> bool:
    _ = CONFIG_SCHEMA
    if DOMAIN not in config:
        _LOGGER.warning("AUTOARM No config found")
        return True
    config = config.get(DOMAIN, {})
    expose_config_entity(hass, config)
    hass.data[HASS_DATA_KEY] = AutoArmData(_async_process_config(hass, config), {})
    await hass.data[HASS_DATA_KEY].armer.initialize()

    async def reload_service_handler(service_call: ServiceCall) -> None:
        """Reload yaml entities."""
        config = None
        _LOGGER.info("AUTOARM Reloading %s.%s component, data %s", service_call.domain, service_call.service, service_call.data)
        with contextlib.suppress(HomeAssistantError):
            config = await async_integration_yaml_config(hass, DOMAIN)
        if config is None or DOMAIN not in config:
            _LOGGER.warning("AUTOARM reload rejected for lack of config: %s", config)
            return
        hass.data[HASS_DATA_KEY].armer.shutdown()
        expose_config_entity(hass, config[DOMAIN])
        hass.data[HASS_DATA_KEY].armer = _async_process_config(hass, config[DOMAIN])
        await hass.data[HASS_DATA_KEY].armer.initialize()

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_RELOAD,
        reload_service_handler,
    )
    return True


def expose_config_entity(hass: HomeAssistant, config: ConfigType) -> None:
    hass.states.async_set(
        f"{DOMAIN}.configured",
        "True",
        {
            CONF_ALARM_PANEL: config.get(CONF_ALARM_PANEL),
            CONF_SUNRISE_CUTOFF: config.get(CONF_SUNRISE_CUTOFF),
            CONF_OCCUPIED_DAY_DEFAULT: config.get(CONF_OCCUPIED_DAY_DEFAULT),
            CONF_CALENDAR_CONTROL: config.get(CONF_CALENDAR_CONTROL),
            CONF_ARM_AWAY_DELAY: config.get(CONF_ARM_AWAY_DELAY, ()),
            CONF_BUTTON_ENTITY_RESET: config.get(CONF_BUTTON_ENTITY_RESET),
            CONF_BUTTON_ENTITY_AWAY: config.get(CONF_BUTTON_ENTITY_AWAY),
            CONF_BUTTON_ENTITY_DISARM: config.get(CONF_BUTTON_ENTITY_DISARM),
            CONF_OCCUPANTS: config.get(CONF_OCCUPANTS, []),
            CONF_NOTIFY: config.get(CONF_NOTIFY, {}),
            CONF_THROTTLE_SECONDS: config.get(CONF_THROTTLE_SECONDS, 60),
            CONF_THROTTLE_CALLS: config.get(CONF_THROTTLE_CALLS, 6),
        },
    )


def _async_process_config(hass: HomeAssistant, config: ConfigType) -> "AlarmArmer":
    calendar_config: ConfigType = config.get(CONF_CALENDAR_CONTROL, {})
    return AlarmArmer(
        hass,
        alarm_panel=config[CONF_ALARM_PANEL],
        sunrise_cutoff=cast("datetime.time", config.get(CONF_SUNRISE_CUTOFF)),
        arm_away_delay=config[CONF_ARM_AWAY_DELAY],
        reset_button=config.get(CONF_BUTTON_ENTITY_RESET),
        away_button=config.get(CONF_BUTTON_ENTITY_AWAY),
        disarm_button=config.get(CONF_BUTTON_ENTITY_DISARM),
        occupants=config[CONF_OCCUPANTS],
        notify=config[CONF_NOTIFY],
        occupied_daytime_default=config[CONF_OCCUPIED_DAY_DEFAULT],
        throttle_calls=config.get(CONF_THROTTLE_CALLS, 6),
        throttle_seconds=config.get(CONF_THROTTLE_SECONDS, 60),
        calendars=calendar_config.get(CONF_CALENDARS, []),
        transitions=config.get(CONF_TRANSITIONS),
        calendar_no_event_mode=calendar_config.get(CONF_CALENDAR_NO_EVENT, NO_CAL_EVENT_MODE_AUTO),
    )


def unlisten(listener: Callable[[], None] | None) -> None:
    if listener:
        try:
            listener()
        except Exception as e:
            _LOGGER.debug("AUTOARM Failure closing listener %s: %s", listener, e)


@dataclass
class Intervention:
    created_at: datetime.datetime
    source: ChangeSource
    state: AlarmControlPanelState | None


class AlarmArmer:
    def __init__(
        self,
        hass: HomeAssistant,
        alarm_panel: str,
        sunrise_cutoff: datetime.time | None = None,
        arm_away_delay: int | None = None,
        reset_button: str | None = None,
        away_button: str | None = None,
        disarm_button: str | None = None,
        occupied_daytime_default: str | None = None,
        occupants: list | None = None,
        actions: list | None = None,
        notify: dict | None = None,
        throttle_calls: int = 6,
        throttle_seconds: int = 60,
        calendar_no_event_mode: str | None = None,
        calendars: list[ConfigType] | None = None,
        transitions: dict[str, dict[str, list[ConfigType]]] | None = None,
    ) -> None:
        self.hass: HomeAssistant = hass
        self.local_tz = dt_util.get_time_zone(self.hass.config.time_zone)
        self.calendar_configs: list[ConfigType] = calendars or []
        self.calendar_no_event_mode: str = calendar_no_event_mode or NO_CAL_EVENT_MODE_AUTO
        self.calendars: list[TrackedCalendar] = []
        self.alarm_panel: str = alarm_panel
        self.sunrise_cutoff: datetime.time | None = sunrise_cutoff
        occupied_daytime_default = (
            occupied_daytime_default.lower() if occupied_daytime_default else AlarmControlPanelState.ARMED_HOME.value
        )
        self.occupied_daytime_default: AlarmControlPanelState = AlarmControlPanelState(occupied_daytime_default)
        self.arm_away_delay: int | None = arm_away_delay
        self.reset_button: str | None = reset_button
        self.away_button: str | None = away_button
        self.disarm_button: str | None = disarm_button
        self.occupants: list[str] = occupants or []
        self.actions: list[str] = actions or []
        self.notify_profiles: dict[str, dict] = notify or {}
        self.unsubscribes: list = []
        self.pre_pending_state: AlarmControlPanelState | None = None
        self.button_device: dict[str, str] = {}
        self.arming_in_progress: asyncio.Event = asyncio.Event()
        self.requested_state: AlarmControlPanelState | None = None
        self.requested_state_time: datetime.datetime | None = None
        self.rate_limiter: Limiter = Limiter(window=throttle_seconds, max_calls=throttle_calls)
        self.hass_api: HomeAssistantAPI = HomeAssistantAPI(hass)
        self.transitions: dict[AlarmControlPanelState, ConditionCheckerType] = {}
        self.transition_config: dict[str, dict[str, list[ConfigType]]] = transitions or {
            k: {CONF_CONDITIONS: cv.CONDITIONS_SCHEMA(v)} for k, v in DEFAULT_TRANSITIONS.items()
        }
        self.initialization_errors: dict[str, int] = {}
        self.interventions: list[Intervention] = []
        self.intervention_ttl: int = 60

    async def initialize(self) -> None:
        """Async initialization"""
        _LOGGER.info(
            "AUTOARM arm_delay=%s, occupied=%s, state=%s",
            self.arm_away_delay,
            self.is_occupied(),
            self.armed_state(),
        )

        self.initialize_alarm_panel()
        await self.initialize_calendar()
        await self.initialize_logic()
        self.initialize_diurnal()
        self.initialize_occupancy()
        self.initialize_buttons()
        self.initialize_integration()
        self.initialize_housekeeping()
        await self.reset_armed_state(source=ChangeSource.STARTUP)
        self.stop_listener: Callable[[], None] | None = self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, self.async_shutdown
        )
        self.hass.states.async_set(
            f"{DOMAIN}.initialization",
            "valid" if not self.initialization_errors else "invalid",
            attributes=self.initialization_errors,
        )

        _LOGGER.info("AUTOARM Initialized, state: %s", self.armed_state())

    def record_error(self, stage: str) -> None:
        self.initialization_errors.setdefault(stage, 0)
        self.initialization_errors[stage] += 1

    async def initialize_logic(self) -> None:
        stage: str = "logic"

        for state_str, transition_config in self.transition_config.items():
            error: str = ""
            condition_config = transition_config.get(CONF_CONDITIONS)
            if condition_config is None:
                error = "Empty conditions"
                _LOGGER.warning(f"AUTOARM Found no conditions for {state_str} transition")
            else:
                try:
                    state = AlarmControlPanelState(state_str)
                    cond: ConditionCheckerType | None = await self.hass_api.build_condition(
                        condition_config, strict=True, validate=True, name=state_str
                    )

                    if cond:
                        # re-run without strict wrapper
                        cond = await self.hass_api.build_condition(condition_config, name=state_str)
                    if cond:
                        _LOGGER.info(f"AUTOARM Validated transition logic for {state_str}")
                        self.transitions[state] = cond
                    else:
                        _LOGGER.warning(f"AUTOARM Failed to validate transition logic for {state_str}")
                        error = "Condition validation failed"
                except ValueError as ve:
                    self.record_error(stage)
                    error = f"Invalid state {ve}"
                    _LOGGER.error(f"AUTOARM Invalid state in {state_str} transition - {ve}")
                except vol.Invalid as vi:
                    self.record_error(stage)
                    _LOGGER.error(f"AUTOARM Transition {state_str} conditions fails Home Assistant schema check {vi}")
                    error = f"Schema error {vi}"
                except ConditionError as ce:
                    _LOGGER.error(f"AUTOARM Transition {state_str} conditions fails Home Assistant condition check {ce}")
                    if hasattr(ce, "message"):
                        error = ce.message
                    elif hasattr(ce, "error") and hasattr(ce.error, "message"):
                        error = ce.error.message
                    else:
                        error = str(ce)
                except Exception as e:
                    self.record_error(stage)
                    _LOGGER.exception("AUTOARM Disabling transition %s with error validating %s", state_str, condition_config)
                    error = f"Unknown exception {e}"
            if error:
                _LOGGER.warning(f"AUTOARM raising report issue for {error} on {state_str}")
                self.hass_api.raise_issue(
                    f"transition_condition_{state_str}",
                    is_fixable=False,
                    issue_key="transition_condition",
                    issue_map={"state": state_str, "error": error},
                    severity=ir.IssueSeverity.ERROR,
                    learn_more_url="https://autoarm.rhizomatics.org.uk/scenarios/",
                )

    async def async_shutdown(self, _event: Event) -> None:
        _LOGGER.info("AUTOARM shut down event received")
        self.stop_listener = None
        self.shutdown()

    def shutdown(self) -> None:
        _LOGGER.info("AUTOARM shutting down")
        for calendar in self.calendars:
            calendar.shutdown()
        while self.unsubscribes:
            unlisten(self.unsubscribes.pop())
        unlisten(self.stop_listener)
        self.stop_listener = None
        _LOGGER.info("AUTOARM shut down")

    async def housekeeping(self, triggered_at: datetime.datetime) -> None:
        _LOGGER.debug("AUTOARM Housekeeping starting, triggered at %s", triggered_at)
        now = dt_util.now()
        self.interventions = [
            i for i in self.interventions if now < i.created_at + datetime.timedelta(minutes=self.intervention_ttl)
        ]
        for cal in self.calendars:
            await cal.prune_events()
        _LOGGER.debug("AUTOARM Housekeeping finished")

    def initialize_integration(self) -> None:
        self.unsubscribes.append(self.hass.bus.async_listen("mobile_app_notification_action", self.on_mobile_action))

    def initialize_alarm_panel(self) -> None:
        """Set up automation for Home Assistant alarm panel

        See https://www.home-assistant.io/integrations/alarm_control_panel/
        """
        self.unsubscribes.append(async_track_state_change_event(self.hass, [self.alarm_panel], self.on_panel_change))
        _LOGGER.debug("AUTOARM Auto-arming %s", self.alarm_panel)

    def initialize_housekeeping(self) -> None:
        self.unsubscribes.append(
            async_track_time_change(
                self.hass,
                action=self.housekeeping,
                minute=0,
            )
        )

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

    def initialize_buttons(self) -> None:
        """Initialize (optional) physical alarm state control buttons"""

        def setup_button(state_name: str, button_entity: str, cb: Callable) -> None:
            self.button_device[state_name] = button_entity
            if self.button_device[state_name]:
                self.unsubscribes.append(async_track_state_change_event(self.hass, [button_entity], cb))

                _LOGGER.debug(
                    "AUTOARM Configured %s button for %s",
                    state_name,
                    self.button_device[state_name],
                )

        if self.reset_button:
            setup_button("reset", self.reset_button, self.on_reset_button)
        if self.away_button:
            setup_button("away", self.away_button, self.on_away_button)
        if self.disarm_button:
            setup_button("disarm", self.disarm_button, self.on_disarm_button)

    async def initialize_calendar(self) -> None:
        """Configure calendar polling (optional)"""
        stage: str = "calendar"
        self.hass.states.async_set(f"{DOMAIN}.last_calendar_event", "unavailable", attributes={})
        if not self.calendar_configs:
            return
        try:
            platforms: list[entity_platform.EntityPlatform] = entity_platform.async_get_platforms(self.hass, CALENDAR_DOMAIN)
            if platforms:
                platform: entity_platform.EntityPlatform = platforms[0]
            else:
                self.record_error(stage)
                _LOGGER.error("AUTOARM Calendar platform not available from Home Assistant")
                return
        except Exception as _e:
            self.record_error(stage)
            _LOGGER.exception("AUTOARM Unable to access calendar platform")
            return
        for calendar_config in self.calendar_configs:
            tracked_calendar = TrackedCalendar(calendar_config, self)
            await tracked_calendar.initialize(platform)
            self.calendars.append(tracked_calendar)

    def active_calendar_event(self) -> CalendarEvent | None:
        events: list[CalendarEvent] = []
        for cal in self.calendars:
            events.extend(cal.active_events())
        if events:
            # TODO: consider sorting events to LIFO
            return events[0]
        return None

    async def on_calendar_event_start(self, event: TrackedCalendarEvent, triggered_at: datetime.datetime) -> None:
        _LOGGER.debug("AUTOARM on_calendar_event_start(%s,%s)", event.id, triggered_at)
        if event.arming_state != self.armed_state():
            _LOGGER.info("AUTOARM Calendar event %s changing arming to %s at %s", event.id, event.arming_state, triggered_at)
            await self.arm(arming_state=event.arming_state, source=ChangeSource.CALENDAR)
        self.hass.states.async_set(
            f"{DOMAIN}.last_calendar_event",
            new_state=event.event.summary or str(event.id),
            attributes={
                "calendar": event.calendar_id,
                "start": event.event.start_datetime_local,
                "end": event.event.end_datetime_local,
                "summary": event.event.summary,
                "description": event.event.description,
                "uid": event.event.uid,
            },
        )

    async def on_calendar_event_end(self, event: TrackedCalendarEvent, ended_at: datetime.datetime) -> None:
        _LOGGER.debug("AUTOARM on_calendar_event_start(%s,%s)", event.id, ended_at)
        if any(cal.has_active_event() for cal in self.calendars):
            _LOGGER.debug("AUTOARM No action on event end since other cal event active")
            return
        if self.calendar_no_event_mode == NO_CAL_EVENT_MODE_AUTO:
            _LOGGER.info("AUTOARM Calendar event %s ended, and arming state", event.id)
            # avoid having state locked in vacation by state calculator
            await self.pending_state(source=ChangeSource.CALENDAR)
            await self.reset_armed_state(source=ChangeSource.CALENDAR)
        elif self.calendar_no_event_mode in AlarmControlPanelState:
            _LOGGER.info(
                "AUTOARM Calendar event %s ended, and returning to fixed state %s", event.id, self.calendar_no_event_mode
            )
            await self.arm(alarm_state_as_enum(self.calendar_no_event_mode), source=ChangeSource.CALENDAR)
        else:
            _LOGGER.debug("AUTOARM Reinstate previous state on calendar event end in manual mode")
            await self.arm(event.previous_state, source=ChangeSource.CALENDAR)

    def is_occupied(self) -> bool:
        return any(safe_state(self.hass.states.get(p)) == STATE_HOME for p in self.occupants)

    def is_unoccupied(self) -> bool:
        return all(safe_state(self.hass.states.get(p)) != STATE_HOME for p in self.occupants)

    def is_night(self) -> bool:
        return safe_state(self.hass.states.get("sun.sun")) == STATE_BELOW_HORIZON

    def armed_state(self) -> AlarmControlPanelState | None:
        raw_state: str | None = safe_state(self.hass.states.get(self.alarm_panel))
        return alarm_state_as_enum(raw_state)

    @callback
    async def on_panel_change(self, event: Event[EventStateChangedData]) -> None:
        """Alarm Control Panel has been changed outside of AutoArm"""
        entity_id, old, new = self._extract_event(event)
        new_state = alarm_state_as_enum(new)
        # ignore changes in progress or in last minute from AutoArm itself
        # all other changes are assumed external, e.g. from panel UI in HASS app or another automatio
        if self.arming_in_progress.is_set() or (
            self.requested_state == new_state
            and self.requested_state_time is not None
            and self.requested_state_time > dt_util.now() - datetime.timedelta(minutes=1)
        ):
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
            await self.reset_armed_state(source=ChangeSource.ZOMBIFICATION)
        elif new != old:
            self.record_intervention(ChangeSource.ALARM_PANEL, new_state)
            message = f"Home Assistant alarm level now set from {old} to {new}"
            await self.notify(message, title=f"Alarm now {new}", profile="quiet")
        else:
            _LOGGER.debug("AUTOARM panel change leaves state unchanged at %s", new)

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
        existing_state: AlarmControlPanelState | None = self.armed_state()
        _LOGGER.debug("AUTOARM Occupancy Change: %s, %s, %s, %s", entity_id, old, new, event)
        _LOGGER.info("AUTOARM Resetting armed state %s on occupancy change", existing_state)
        await self.reset_armed_state(source=ChangeSource.OCCUPANCY)

    async def pending_state(self, source: ChangeSource | None) -> None:
        self.pre_pending_state = self.armed_state()
        await self.arm(AlarmControlPanelState.PENDING, source=source)

    async def reset_armed_state(
        self, intervention: Intervention | None = None, source: ChangeSource | None = None
    ) -> str | None:
        """Logic to automatically work out appropriate current armed state"""
        if source is None and intervention is not None:
            source = intervention.source
        _LOGGER.debug(
            "AUTOARM reset_armed_state(intervention=%s,source=%s)",
            intervention,
            source,
        )

        existing_state: AlarmControlPanelState | None = self.armed_state()
        if self.calendars:
            if self.active_calendar_event():
                _LOGGER.debug("AUTOARM Ignoring reset while calendar event active")
                return existing_state
            if self.calendar_no_event_mode == NO_CAL_EVENT_MODE_MANUAL:
                _LOGGER.debug("AUTOARM Ignoring reset while calendar configured, no active event, and default mode is manual")
                return existing_state
            if self.calendar_no_event_mode in AlarmControlPanelState:
                # TODO: may be dupe logic with on_cal event
                return await self.arm(alarm_state_as_enum(self.calendar_no_event_mode), ChangeSource.CALENDAR)
            if self.calendar_no_event_mode == NO_CAL_EVENT_MODE_AUTO:
                _LOGGER.debug("AUTOARM Applying reset while calendar configured, no active event, and default mode is auto")
            else:
                _LOGGER.warning("AUTOARM Unexpected state for calendar no event mode: %s", self.calendar_no_event_mode)

        # TODO: expose as config ( for manual disarm override ) and condition logic
        must_change_state: bool = existing_state is None or existing_state == AlarmControlPanelState.PENDING
        if intervention or source in (ChangeSource.CALENDAR, ChangeSource.OCCUPANCY) or must_change_state:
            _LOGGER.debug("AUTOARM Ignoring previous interventions")
        else:
            last_state_intervention: Intervention | None = self.last_state_intervention()
            if last_state_intervention:
                _LOGGER.debug(
                    "AUTOARM Ignoring automated reset for %s set by %s at %s",
                    last_state_intervention.state,
                    last_state_intervention.source,
                    last_state_intervention.created_at,
                )
                return existing_state
        state: AlarmControlPanelState | None = self.determine_state()
        if state is not None and state != AlarmControlPanelState.PENDING:
            return await self.arm(state, source=source)
        return None

    def determine_state(self) -> AlarmControlPanelState | None:
        evaluated_state: AlarmControlPanelState | None = None
        condition_vars: ConditionVariables = ConditionVariables(
            self.is_occupied(),
            self.is_night(),
            state=self.armed_state(),
            calendar_event=self.active_calendar_event(),
            occupied_daytime_state=self.occupied_daytime_default,
        )
        for state, checker in self.transitions.items():
            if self.hass_api.evaluate_condition(checker, condition_vars):
                _LOGGER.debug("AUTOARM Computed state as % from condition", state)
                evaluated_state = state
                break
        if evaluated_state is None:
            return None
        return AlarmControlPanelState(evaluated_state)

    def has_intervention_since(self, cutoff: datetime.datetime) -> bool:
        """Has there been a manual intervention since the cutoff time"""
        if not self.interventions:
            return False
        return any(intervention.created_at > cutoff for intervention in self.interventions)

    def last_state_intervention(self) -> Intervention | None:
        candidates: list[Intervention] = [i for i in self.interventions if i.state is not None]
        if candidates:
            return candidates[-1]
        return None

    async def delayed_arm(
        self,
        arming_state: AlarmControlPanelState,
        requested_at: datetime.datetime,
        triggered_at: datetime.datetime,
        source: ChangeSource | None = None,
    ) -> None:
        _LOGGER.debug(
            "Delayed_arm %s, requested at %s, triggered at: %s, source%s", arming_state, requested_at, triggered_at, source
        )

        if self.has_intervention_since(requested_at):
            _LOGGER.debug(
                "AUTOARM Cancelling delayed request for %s since subsequent manual action",
                arming_state,
            )
            return

        await self.arm(arming_state=arming_state, source=source)

    async def delayed_reset(
        self,
        requested_at: datetime.datetime,
        triggered_at: datetime.datetime,
        intervention: Intervention | None = None,
        source: ChangeSource | None = None,
    ) -> None:
        _LOGGER.debug("Delayed_reset %s, requested_at: %s, triggered at: %s, source%s", requested_at, triggered_at, source)

        if self.has_intervention_since(requested_at):
            _LOGGER.debug(
                "AUTOARM Cancelling delayed reset for %s since subsequent manual action",
                source,
            )
            return

        await self.reset_armed_state(intervention=intervention, source=source)

    async def arm(
        self, arming_state: AlarmControlPanelState | None = None, source: ChangeSource | None = None
    ) -> AlarmControlPanelState | None:
        """Change alarm panel state

        Args:
        ----
            arming_state (str, optional): _description_. Defaults to None.
            source (str,optional): Source of the change, for example 'calendar' or 'button'

        Returns:
        -------
            str: New arming state

        """
        if self.rate_limiter.triggered():
            _LOGGER.debug("AUTOARM Rate limit triggered by %s, skipping arm", source)
            return None
        try:
            self.requested_state = arming_state
            self.requested_state_time = dt_util.now()
            self.arming_in_progress.set()
            existing_state: AlarmControlPanelState | None = self.armed_state()
            if arming_state != existing_state:
                self.hass.states.async_set(self.alarm_panel, str(arming_state))
                _LOGGER.info("AUTOARM Setting %s from %s to %s for %s", self.alarm_panel, existing_state, arming_state, source)
                return arming_state
            _LOGGER.debug("Skipping arm for %s, as %s already %s", source, self.alarm_panel, arming_state)
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
            _LOGGER.exception("AUTOARM notify.%s failed", notify_service)

    @callback
    async def on_reset_button(self, event: Event) -> None:
        _LOGGER.debug("AUTOARM Reset Button: %s", event)
        await self.reset_armed_state(intervention=self.record_intervention(source=ChangeSource.BUTTON, state=None))

    @callback
    async def on_mobile_action(self, event: Event) -> None:
        _LOGGER.debug("AUTOARM Mobile Action: %s", event)
        source: ChangeSource = ChangeSource.MOBILE

        match event.data.get("action"):
            case "ALARM_PANEL_DISARM":
                self.record_intervention(source=source, state=AlarmControlPanelState.DISARMED)
                await self.arm(AlarmControlPanelState.DISARMED, source=source)
            case "ALARM_PANEL_RESET":
                await self.reset_armed_state(intervention=self.record_intervention(source=ChangeSource.BUTTON, state=None))
            case "ALARM_PANEL_AWAY":
                self.record_intervention(source=source, state=AlarmControlPanelState.ARMED_AWAY)
                await self.arm(AlarmControlPanelState.ARMED_AWAY, source=source)
            case _:
                _LOGGER.debug("AUTOARM Ignoring mobile action: %s", event.data)

    @callback
    async def on_disarm_button(self, event: Event) -> None:
        _LOGGER.info("AUTOARM Disarm Button: %s", event)
        self.record_intervention(source=ChangeSource.BUTTON, state=AlarmControlPanelState.DISARMED)
        await self.arm(AlarmControlPanelState.DISARMED, source=ChangeSource.BUTTON)

    @callback
    async def on_vacation_button(self, event: Event) -> None:
        _LOGGER.info("AUTOARM Vacation Button: %s", event)
        self.record_intervention(source=ChangeSource.BUTTON, state=AlarmControlPanelState.ARMED_VACATION)
        await self.arm(AlarmControlPanelState.ARMED_VACATION, source=ChangeSource.BUTTON)

    def record_intervention(self, source: ChangeSource, state: AlarmControlPanelState | None) -> Intervention:
        intervention = Intervention(dt_util.now(), source, state)
        self.interventions.append(intervention)
        return intervention

    @callback
    async def on_away_button(self, event: Event) -> None:
        _LOGGER.info("AUTOARM Away Button: %s", event)
        self.record_intervention(source=ChangeSource.BUTTON, state=AlarmControlPanelState.ARMED_AWAY)
        if self.arm_away_delay:
            self.unsubscribes.append(
                async_track_point_in_time(
                    self.hass,
                    partial(
                        self.delayed_arm,
                        AlarmControlPanelState.ARMED_AWAY,
                        dt_util.utc_from_timestamp(time.time()),
                        source=ChangeSource.BUTTON,
                    ),
                    dt_util.utc_from_timestamp(time.time() + self.arm_away_delay),
                )
            )
            await self.notify(
                f"Alarm will be armed for away in {self.arm_away_delay} seconds",
                title="Arm for away process starting",
            )
        else:
            await self.arm(AlarmControlPanelState.ARMED_AWAY, source=ChangeSource.BUTTON)

    @callback
    async def on_sunrise(self, *args: Any) -> None:  # noqa: ARG002
        _LOGGER.debug("AUTOARM Sunrise")
        now = datetime.datetime.now(tz=self.local_tz)
        if not self.sunrise_cutoff or now.time() >= self.sunrise_cutoff:
            # sun is up, and not earlier than cutoff
            await self.reset_armed_state(source=ChangeSource.SUNRISE)
        elif self.sunrise_cutoff and now.time() < self.sunrise_cutoff:
            _LOGGER.debug(
                "AUTOARM Rescheduling delayed sunrise action to %s",
                self.sunrise_cutoff,
            )
            trigger = datetime.datetime.combine(now.date(), self.sunrise_cutoff, tzinfo=self.local_tz)
            self.unsubscribes.append(
                async_track_point_in_time(
                    self.hass,
                    partial(self.delayed_reset, now, source=ChangeSource.SUNRISE),
                    trigger,
                )
            )

    @callback
    async def on_sunset(self, *args: Any) -> None:  # noqa: ARG002
        _LOGGER.debug("AUTOARM Sunset")
        await self.reset_armed_state(source=ChangeSource.SUNSET)


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
