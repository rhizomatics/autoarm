import asyncio
import contextlib
import datetime as dt
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, Any

import homeassistant.util.dt as dt_util
import voluptuous as vol
from homeassistant.components.alarm_control_panel.const import ATTR_CHANGED_BY, AlarmControlPanelState
from homeassistant.components.calendar import CalendarEvent
from homeassistant.components.calendar.const import DOMAIN as CALENDAR_DOMAIN
from homeassistant.components.sun.const import STATE_BELOW_HORIZON
from homeassistant.const import (
    CONF_CONDITIONS,
    CONF_ENTITY_ID,
    EVENT_HOMEASSISTANT_STOP,
    SERVICE_RELOAD,
    STATE_HOME,
)
from homeassistant.core import (
    Event,
    EventStateChangedData,
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    State,
    SupportsResponse,
    callback,
)
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
from homeassistant.helpers.json import ExtendedJSONEncoder
from homeassistant.helpers.reload import (
    async_integration_yaml_config,
)
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

from custom_components.autoarm.hass_api import HomeAssistantAPI
from custom_components.autoarm.notifier import Notifier

from .calendar import TrackedCalendar
from .const import (
    ATTR_RESET,
    CONF_ALARM_PANEL,
    CONF_BUTTONS,
    CONF_CALENDAR_CONTROL,
    CONF_CALENDAR_NO_EVENT,
    CONF_CALENDARS,
    CONF_DAY,
    CONF_DELAY_TIME,
    CONF_DIURNAL,
    CONF_EARLIEST,
    CONF_NOTIFY,
    CONF_OCCUPANCY,
    CONF_OCCUPANCY_DEFAULT,
    CONF_RATE_LIMIT,
    CONF_RATE_LIMIT_CALLS,
    CONF_RATE_LIMIT_PERIOD,
    CONF_SUNRISE,
    CONF_TRANSITIONS,
    CONFIG_SCHEMA,
    DEFAULT_TRANSITIONS,
    DOMAIN,
    NO_CAL_EVENT_MODE_AUTO,
    NO_CAL_EVENT_MODE_MANUAL,
    ChangeSource,
    ConditionVariables,
)
from .helpers import AppHealthTracker, Limiter, alarm_state_as_enum, deobjectify, safe_state

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
    other_data: dict[str, str | dict[str, str] | list[str] | int | float | bool | None]


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
        hass.data[HASS_DATA_KEY].armer = _async_process_config(hass, config[DOMAIN])
        await hass.data[HASS_DATA_KEY].armer.initialize()

    async_register_admin_service(
        hass,
        DOMAIN,
        SERVICE_RELOAD,
        reload_service_handler,
    )

    def supplemental_action_enquire_configuration(_call: ServiceCall) -> ConfigType:
        data: ConfigType = {
            CONF_ALARM_PANEL: config.get(CONF_ALARM_PANEL, {}).get(CONF_ENTITY_ID),
            CONF_DIURNAL: config.get(CONF_DIURNAL),
            CONF_CALENDAR_CONTROL: config.get(CONF_CALENDAR_CONTROL),
            CONF_BUTTONS: config.get(CONF_BUTTONS, {}),
            CONF_OCCUPANCY: config.get(CONF_OCCUPANCY, {}),
            CONF_NOTIFY: config.get(CONF_NOTIFY, {}),
            CONF_RATE_LIMIT: config.get(CONF_RATE_LIMIT, {}),
        }
        try:
            jsonized: str = json.dumps(obj=data, cls=ExtendedJSONEncoder)
            return json.loads(jsonized)
        except Exception as e:
            _LOGGER.error("AUTOARM Failed to expose config data as entity: %s, %s", data, e)
            return {"error": str(e)}

    hass.services.async_register(
        DOMAIN,
        "enquire_configuration",
        supplemental_action_enquire_configuration,
        supports_response=SupportsResponse.ONLY,
    )

    return True


def _async_process_config(hass: HomeAssistant, config: ConfigType) -> "AlarmArmer":
    calendar_config: ConfigType = config.get(CONF_CALENDAR_CONTROL, {})
    migrate(hass)
    service: AlarmArmer = AlarmArmer(
        hass,
        alarm_panel=config[CONF_ALARM_PANEL].get(CONF_ENTITY_ID),
        diurnal=config.get(CONF_DIURNAL, {}),
        buttons=config.get(CONF_BUTTONS, {}),
        occupancy=config[CONF_OCCUPANCY],
        notify=config[CONF_NOTIFY],
        rate_limit=config.get(CONF_RATE_LIMIT, {}),
        calendar_config=calendar_config,
        transitions=config.get(CONF_TRANSITIONS),
    )
    return service


def migrate(hass: HomeAssistant) -> None:
    for entity_id in (
        "autoarm.configured",
        "autoarm.last_calendar_event",
        "autoarm.last_intervention",
        "autoarm.initialized",
        "autoarm.last_calculation",
    ):
        try:
            if hass.states.get(entity_id):
                _LOGGER.info("AUTOARM Migration removing legacy entity_id: %s", entity_id)
                hass.states.async_remove(entity_id)
        except Exception as e:
            _LOGGER.warning("AUTOARM Migration fail for %s:%s", entity_id, e)


def unlisten(listener: Callable[[], None] | None) -> None:
    if listener:
        try:
            listener()
        except Exception as e:
            _LOGGER.debug("AUTOARM Failure closing listener %s: %s", listener, e)


@dataclass
class Intervention:
    """Record of a manual intervention, such as a button push, mobile action or alarm panel change"""

    created_at: dt.datetime
    source: ChangeSource
    state: AlarmControlPanelState | None

    def as_dict(self) -> dict[str, str | None]:
        return {
            "created_at": self.created_at.isoformat(),
            "source": str(self.source),
            "state": str(self.state) if self.state is not None else None,
        }


class AlarmArmer:
    def __init__(
        self,
        hass: HomeAssistant,
        alarm_panel: str,
        buttons: dict[str, ConfigType] | None = None,
        occupancy: ConfigType | None = None,
        actions: list[str] | None = None,
        notify: ConfigType | None = None,
        diurnal: ConfigType | None = None,
        rate_limit: ConfigType | None = None,
        calendar_config: ConfigType | None = None,
        transitions: dict[str, dict[str, list[ConfigType]]] | None = None,
    ) -> None:
        occupancy = occupancy or {}
        rate_limit = rate_limit or {}
        diurnal = diurnal or {}

        self.hass: HomeAssistant = hass
        self.app_health_tracker: AppHealthTracker = AppHealthTracker(hass)
        self.notifier: Notifier = Notifier(notify, hass, self.app_health_tracker)
        self.local_tz = dt_util.get_time_zone(self.hass.config.time_zone)
        calendar_config = calendar_config or {}
        self.calendar_configs: list[ConfigType] = calendar_config.get(CONF_CALENDARS, []) or []
        self.calendars: list[TrackedCalendar] = []
        self.calendar_no_event_mode: str | None = calendar_config.get(CONF_CALENDAR_NO_EVENT, NO_CAL_EVENT_MODE_AUTO)
        self.alarm_panel: str = alarm_panel
        self.sunrise_cutoff: dt.time | None = diurnal.get(CONF_SUNRISE, {}).get(CONF_EARLIEST)
        self.occupants: list[str] = occupancy.get(CONF_ENTITY_ID, [])
        self.occupied_defaults: dict[str, AlarmControlPanelState] = occupancy.get(
            CONF_OCCUPANCY_DEFAULT, {CONF_DAY: AlarmControlPanelState.ARMED_HOME}
        )
        self.occupied_delay: dict[str, dt.timedelta] = occupancy.get(CONF_DELAY_TIME, {})
        self.buttons: ConfigType = buttons or {}

        self.actions: list[str] = actions or []
        self.unsubscribes: list[Callable[[], None]] = []
        self.pre_pending_state: AlarmControlPanelState | None = None
        self.button_device: dict[str, str] = {}
        self.arming_in_progress: asyncio.Event = asyncio.Event()

        self.rate_limiter: Limiter = Limiter(
            window=rate_limit.get(CONF_RATE_LIMIT_PERIOD, dt.timedelta(seconds=60)),
            max_calls=rate_limit.get(CONF_RATE_LIMIT_CALLS, 5),
        )

        self.hass_api: HomeAssistantAPI = HomeAssistantAPI(hass)
        self.transitions: dict[AlarmControlPanelState, ConditionCheckerType] = {}
        self.transition_config: dict[str, dict[str, list[ConfigType]]] = transitions or {}

        self.interventions: list[Intervention] = []
        self.intervention_ttl: int = 60

    async def initialize(self) -> None:
        """Async initialization"""
        _LOGGER.info("AUTOARM occupied=%s, state=%s, calendars=%s", self.is_occupied(), self.armed_state(), len(self.calendars))

        self.initialize_alarm_panel()
        await self.initialize_calendar()
        await self.initialize_logic()
        self.initialize_diurnal()
        self.initialize_occupancy()
        self.initialize_buttons()
        self.initialize_integration()
        self.initialize_housekeeping()
        self.initialize_home_assistant()
        await self.reset_armed_state(source=ChangeSource.STARTUP)

        _LOGGER.info("AUTOARM Initialized, state: %s", self.armed_state())

    def initialize_home_assistant(self) -> None:
        self.stop_listener: Callable[[], None] | None = self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, self.async_shutdown
        )
        self.app_health_tracker.app_initialized()
        self.hass.states.async_set(f"sensor.{DOMAIN}_last_calculation", "unavailable", attributes={})

        self.hass.services.async_register(
            DOMAIN,
            "reset_state",
            self.reset_service,
            supports_response=SupportsResponse.OPTIONAL,
        )

    async def reset_service(self, _call: ServiceCall) -> ServiceResponse:
        new_state = await self.reset_armed_state(intervention=self.record_intervention(source=ChangeSource.ACTION, state=None))
        return {"change": new_state or "NO_CHANGE"}

    def initialize_integration(self) -> None:
        self.hass.states.async_set(f"sensor.{DOMAIN}_last_intervention", "unavailable", attributes={})

        self.unsubscribes.append(self.hass.bus.async_listen("mobile_app_notification_action", self.on_mobile_action))

    def initialize_alarm_panel(self) -> None:
        """Set up automation for Home Assistant alarm panel

        See https://www.home-assistant.io/integrations/alarm_control_panel/

        Succeeds even if control panel has not yet started, listener will pick up events when it does
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

        for button_use, button_config in self.buttons.items():
            delay: dt.timedelta | None = button_config.get(CONF_DELAY_TIME)
            for entity_id in button_config[CONF_ENTITY_ID]:
                if button_use == ATTR_RESET:
                    setup_button(ATTR_RESET, entity_id, partial(self.on_reset_button, delay))
                else:
                    setup_button(
                        button_use, entity_id, partial(self.on_alarm_state_button, AlarmControlPanelState(button_use), delay)
                    )

    async def initialize_calendar(self) -> None:
        """Configure calendar polling (optional)"""
        stage: str = "calendar"
        self.hass.states.async_set(f"sensor.{DOMAIN}_last_calendar_event", "unavailable", attributes={})
        if not self.calendar_configs:
            return
        try:
            platforms: list[entity_platform.EntityPlatform] = entity_platform.async_get_platforms(self.hass, CALENDAR_DOMAIN)
            if platforms:
                platform: entity_platform.EntityPlatform = platforms[0]
            else:
                self.app_health_tracker.record_initialization_error(stage)
                _LOGGER.error("AUTOARM Calendar platform not available from Home Assistant")
                return
        except Exception as _e:
            self.app_health_tracker.record_initialization_error(stage)
            _LOGGER.exception("AUTOARM Unable to access calendar platform")
            return
        for calendar_config in self.calendar_configs:
            tracked_calendar = TrackedCalendar(
                self.hass, calendar_config, self.calendar_no_event_mode, self, self.app_health_tracker
            )
            await tracked_calendar.initialize(platform)
            self.calendars.append(tracked_calendar)

    async def initialize_logic(self) -> None:
        stage: str = "logic"
        for state_str, raw_condition in DEFAULT_TRANSITIONS.items():
            if state_str not in self.transition_config:
                _LOGGER.info("AUTOARM Defaulting transition condition for %s", state_str)
                self.transition_config[state_str] = {CONF_CONDITIONS: cv.CONDITIONS_SCHEMA(raw_condition)}

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
                        _LOGGER.debug(f"AUTOARM Validated transition logic for {state_str}")
                        self.transitions[state] = cond
                    else:
                        _LOGGER.warning(f"AUTOARM Failed to validate transition logic for {state_str}")
                        error = "Condition validation failed"
                except ValueError as ve:
                    self.app_health_tracker.record_initialization_error(stage)
                    error = f"Invalid state {ve}"
                    _LOGGER.error(f"AUTOARM Invalid state in {state_str} transition - {ve}")
                except vol.Invalid as vi:
                    self.app_health_tracker.record_initialization_error(stage)
                    _LOGGER.error(f"AUTOARM Transition {state_str} conditions fails Home Assistant schema check {vi}")
                    error = f"Schema error {vi}"
                except ConditionError as ce:
                    _LOGGER.error(f"AUTOARM Transition {state_str} conditions fails Home Assistant condition check {ce}")
                    if hasattr(ce, "message"):
                        error = ce.message  # type: ignore
                    elif hasattr(ce, "error") and hasattr(ce.error, "message"):  # type: ignore[attr-defined]
                        error = ce.error.message  # type: ignore
                    else:
                        error = str(ce)
                except Exception as e:
                    self.app_health_tracker.record_initialization_error(stage)
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

    def active_calendar_event(self) -> CalendarEvent | None:
        events: list[CalendarEvent] = []
        for cal in self.calendars:
            events.extend(cal.active_events())
        if events:
            # TODO: consider sorting events to LIFO
            return events[0]
        return None

    def has_active_calendar_event(self) -> bool:
        return any(cal.has_active_event() for cal in self.calendars)

    def is_occupied(self) -> bool:
        return any(safe_state(self.hass.states.get(p)) == STATE_HOME for p in self.occupants)

    def at_home(self) -> list[str]:
        return [p for p in self.occupants if safe_state(self.hass.states.get(p)) == STATE_HOME]

    def not_home(self) -> list[str]:
        return [p for p in self.occupants if safe_state(self.hass.states.get(p)) != STATE_HOME]

    def is_unoccupied(self) -> bool:
        return all(safe_state(self.hass.states.get(p)) != STATE_HOME for p in self.occupants)

    def is_night(self) -> bool:
        return safe_state(self.hass.states.get("sun.sun")) == STATE_BELOW_HORIZON

    def armed_state(self) -> AlarmControlPanelState:
        raw_state: str | None = safe_state(self.hass.states.get(self.alarm_panel))
        alarm_state = alarm_state_as_enum(raw_state)
        if alarm_state is None:
            _LOGGER.warning("AUTOARM No alarm state available - treating as PENDING")
            return AlarmControlPanelState.PENDING
        return alarm_state

    def _extract_event(self, event: Event[EventStateChangedData]) -> tuple[str | None, str | None, str | None, dict[str, str]]:
        entity_id = old = new = None
        new_attributes: dict[str, str] = {}
        if event and event.data:
            entity_id = event.data.get("entity_id")
            old_obj = event.data.get("old_state")
            if old_obj:
                old = old_obj.state
            new_obj = event.data.get("new_state")
            if new_obj:
                new = new_obj.state
                new_attributes = new_obj.attributes
        return entity_id, old, new, new_attributes

    async def pending_state(self, source: ChangeSource | None) -> None:
        self.pre_pending_state = self.armed_state()
        await self.arm(AlarmControlPanelState.PENDING, source=source)

    @callback
    async def delayed_reset_armed_state(self, triggered_at: dt.datetime, requested_at: dt.datetime | None, **kwargs) -> None:
        _LOGGER.debug("AUTOARM delayed_arm at %s, requested_at: %s", triggered_at, requested_at)
        if self.is_intervention_since_request(requested_at):
            return
        await self.reset_armed_state(**kwargs)

    async def reset_armed_state(
        self, intervention: Intervention | None = None, source: ChangeSource | None = None
    ) -> str | None:
        """Logic to automatically work out appropriate current armed state"""
        state: AlarmControlPanelState | None = None
        existing_state: AlarmControlPanelState | None = None
        must_change_state: bool = False
        last_state_intervention: Intervention | None = None
        active_calendar_event: CalendarEvent | None = None

        if source is None and intervention is not None:
            source = intervention.source
        _LOGGER.debug(
            "AUTOARM reset_armed_state(intervention=%s,source=%s)",
            intervention,
            source,
        )

        try:
            existing_state = self.armed_state()
            state = existing_state
            if self.calendars:
                active_calendar_event = self.active_calendar_event()
                if active_calendar_event:
                    _LOGGER.debug("AUTOARM Ignoring reset while calendar event active")
                    return existing_state
                if self.calendar_no_event_mode == NO_CAL_EVENT_MODE_MANUAL:
                    _LOGGER.debug(
                        "AUTOARM Ignoring reset while calendar configured, no active event, and default mode is manual"
                    )
                    return existing_state
                if self.calendar_no_event_mode in AlarmControlPanelState:
                    # TODO: may be dupe logic with on_cal event
                    _LOGGER.debug("AUTOARM Applying fixed reset on end of calendar event, %s", self.calendar_no_event_mode)
                    return await self.arm(alarm_state_as_enum(self.calendar_no_event_mode), ChangeSource.CALENDAR)
                if self.calendar_no_event_mode == NO_CAL_EVENT_MODE_AUTO:
                    _LOGGER.debug("AUTOARM Applying reset while calendar configured, no active event, and default mode is auto")
                else:
                    _LOGGER.warning("AUTOARM Unexpected state for calendar no event mode: %s", self.calendar_no_event_mode)

            # TODO: expose as config ( for manual disarm override ) and condition logic
            must_change_state = existing_state is None or existing_state == AlarmControlPanelState.PENDING
            if intervention or source in (ChangeSource.CALENDAR, ChangeSource.OCCUPANCY) or must_change_state:
                _LOGGER.debug("AUTOARM Ignoring previous interventions")
            else:
                last_state_intervention = self.last_state_intervention()
                if last_state_intervention:
                    _LOGGER.debug(
                        "AUTOARM Ignoring automated reset for %s set by %s at %s",
                        last_state_intervention.state,
                        last_state_intervention.source,
                        last_state_intervention.created_at,
                    )
                    return existing_state
            state = self.determine_state()
            if state is not None and state != AlarmControlPanelState.PENDING and state != existing_state:
                state = await self.arm(state, source=source)
        finally:
            self.hass.states.async_set(
                f"sensor.{DOMAIN}_last_calculation",
                str(state is not None and state != existing_state),
                attributes={
                    "new_state": str(state),
                    "old_state": str(existing_state),
                    "source": source,
                    "active_calendar_event": deobjectify(active_calendar_event),
                    "occupied": self.is_occupied(),
                    "night": self.is_night(),
                    "must_change_state": str(must_change_state),
                    "last_state_intervention": deobjectify(last_state_intervention),
                    "intervention": intervention.as_dict() if intervention else None,
                    "time": dt_util.now().isoformat(),
                },
            )

        return state

    def is_intervention_since_request(self, requested_at: dt.datetime | None) -> bool:
        if requested_at is not None and self.has_intervention_since(requested_at):
            _LOGGER.debug(
                "AUTOARM Cancelling delayed operation since subsequent manual action",
            )
            return True
        return False

    def determine_state(self) -> AlarmControlPanelState | None:
        """Compute a new state using occupancy, sun and transition conditions"""
        evaluated_state: AlarmControlPanelState | None = None
        condition_vars: ConditionVariables = ConditionVariables(
            self.is_occupied(),
            self.is_night(),
            state=self.armed_state(),
            calendar_event=self.active_calendar_event(),
            occupied_defaults=self.occupied_defaults,
            at_home=self.at_home(),
            not_home=self.not_home(),
        )
        for state, checker in self.transitions.items():
            if self.hass_api.evaluate_condition(checker, condition_vars):
                _LOGGER.debug("AUTOARM Computed state as %s from condition", state)
                evaluated_state = state
                break
        if evaluated_state is None:
            return None
        return AlarmControlPanelState(evaluated_state)

    @callback
    async def delayed_arm(self, triggered_at: dt.datetime, requested_at: dt.datetime | None, **kwargs: Any) -> None:
        _LOGGER.debug("AUTOARM delayed_arm at %s, requested_at: %s", triggered_at, requested_at)
        if self.is_intervention_since_request(requested_at):
            return
        await self.arm(**kwargs)

    async def arm(
        self, arming_state: AlarmControlPanelState | None, source: ChangeSource | None = None
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
        if arming_state is None:
            return None
        if self.armed_state() == arming_state:
            return None
        if self.rate_limiter.triggered():
            _LOGGER.debug("AUTOARM Rate limit triggered by %s, skipping arm", source)
            return None
        try:
            self.arming_in_progress.set()
            existing_state: AlarmControlPanelState | None = self.armed_state()
            if arming_state != existing_state:
                attrs: dict[str, str] = {}
                panel_state: State | None = self.hass.states.get(self.alarm_panel)
                if panel_state:
                    attrs.update(panel_state.attributes)
                attrs[ATTR_CHANGED_BY] = f"{DOMAIN}.{source}"
                self.hass.states.async_set(entity_id=self.alarm_panel, new_state=str(arming_state), attributes=attrs)
                _LOGGER.info("AUTOARM Setting %s from %s to %s for %s", self.alarm_panel, existing_state, arming_state, source)
                if source and arming_state:
                    await self.notifier.notify(source=source, from_state=existing_state, to_state=arming_state)
                return arming_state
            _LOGGER.debug("Skipping arm for %s, as %s already %s", source, self.alarm_panel, arming_state)
            return existing_state
        except Exception as e:
            _LOGGER.error("AUTOARM Failed to arm: %s", e)
            self.app_health_tracker.record_runtime_error()
        finally:
            self.arming_in_progress.clear()
        return None

    def schedule_state(
        self,
        trigger_time: dt.datetime,
        state: AlarmControlPanelState | None,
        intervention: Intervention | None,
        source: ChangeSource | None = None,
    ) -> None:
        source = source or intervention.source if intervention else None

        job: Callable
        if state is None:
            _LOGGER.debug("Delayed reset, triggered at: %s, source%s", trigger_time, source)
            job = partial(self.delayed_reset_armed_state, intervention=intervention, source=source, requested_at=dt_util.now())
        else:
            _LOGGER.debug("Delayed arm %s, triggered at: %s, source%s", state, trigger_time, source)

            job = partial(self.delayed_arm, arming_state=state, source=source, requested_at=dt_util.now())

        self.unsubscribes.append(
            async_track_point_in_time(
                self.hass,
                job,
                trigger_time,
            )
        )

    def record_intervention(self, source: ChangeSource, state: AlarmControlPanelState | None) -> Intervention:
        intervention = Intervention(dt_util.now(), source, state)
        self.interventions.append(intervention)
        self.hass.states.async_set(f"sensor.{DOMAIN}_last_intervention", source, attributes=intervention.as_dict())

        return intervention

    def has_intervention_since(self, cutoff: dt.datetime) -> bool:
        """Has there been a manual intervention since the cutoff time"""
        if not self.interventions:
            return False
        return any(intervention.created_at > cutoff for intervention in self.interventions)

    def last_state_intervention(self) -> Intervention | None:
        candidates: list[Intervention] = [i for i in self.interventions if i.state is not None]
        if candidates:
            return candidates[-1]
        return None

    @callback
    async def on_sunrise(self, *args: Any) -> None:  # noqa: ARG002
        _LOGGER.debug("AUTOARM Sunrise")
        now = dt_util.now()  # uses Home Assistant's time zone setting
        if not self.sunrise_cutoff or now.time() >= self.sunrise_cutoff:
            # sun is up, and not earlier than cutoff
            await self.reset_armed_state(source=ChangeSource.SUNRISE)
        elif self.sunrise_cutoff and now.time() < self.sunrise_cutoff:
            _LOGGER.debug(
                "AUTOARM Rescheduling delayed sunrise action to %s",
                self.sunrise_cutoff,
            )
            self.schedule_state(
                dt.datetime.combine(now.date(), self.sunrise_cutoff, tzinfo=dt_util.DEFAULT_TIME_ZONE),
                intervention=None,
                state=None,
                source=ChangeSource.SUNRISE,
            )

    @callback
    async def on_sunset(self, *args: Any) -> None:  # noqa: ARG002
        _LOGGER.debug("AUTOARM Sunset")
        await self.reset_armed_state(source=ChangeSource.SUNSET)

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
    async def on_alarm_state_button(self, state: AlarmControlPanelState, delay: dt.timedelta | None, event: Event) -> None:
        _LOGGER.debug("AUTOARM Alarm %s Button: %s", state, event)
        intervention = self.record_intervention(source=ChangeSource.BUTTON, state=state)
        if delay:
            self.schedule_state(dt_util.now() + delay, state, intervention, source=ChangeSource.BUTTON)
            await self.notifier.notify(
                ChangeSource.BUTTON,
                from_state=self.armed_state(),
                to_state=state,
                message=f"Alarm will be set to {state} in {delay}",
                title=f"Arm set to {state} process starting",
            )
        else:
            await self.arm(state, source=ChangeSource.BUTTON)

    @callback
    async def on_reset_button(self, delay: dt.timedelta | None, event: Event) -> None:
        _LOGGER.debug("AUTOARM Reset Button: %s", event)
        intervention = self.record_intervention(source=ChangeSource.BUTTON, state=None)
        if delay:
            self.schedule_state(dt_util.now() + delay, None, intervention, ChangeSource.BUTTON)

            await self.notifier.notify(
                ChangeSource.BUTTON,
                message=f"Alarm will be reset in {delay}",
                title="Alarm reset wait initiated",
            )
        else:
            await self.reset_armed_state(intervention=self.record_intervention(source=ChangeSource.BUTTON, state=None))

    @callback
    async def on_occupancy_change(self, event: Event[EventStateChangedData]) -> None:
        """Listen for person state events

        Args:
        ----
            event (Event[EventStateChangedData]): state change event

        """
        entity_id, old, new, new_attributes = self._extract_event(event)
        if old == new:
            _LOGGER.debug(
                "AUTOARM Occupancy Non-state Change: %s, state:%s->%s, event: %s, attrs:%s",
                entity_id,
                old,
                new,
                event,
                new_attributes,
            )
            return
        _LOGGER.debug(
            "AUTOARM Occupancy state Change: %s, state:%s->%s, event: %s, attrs:%s", entity_id, old, new, event, new_attributes
        )
        if new in self.occupied_delay:
            self.schedule_state(
                dt_util.now() + self.occupied_delay[new], state=None, intervention=None, source=ChangeSource.OCCUPANCY
            )
        else:
            await self.reset_armed_state(source=ChangeSource.OCCUPANCY)

    @callback
    async def on_panel_change(self, event: Event[EventStateChangedData]) -> None:
        """Alarm Control Panel has been changed outside of AutoArm"""
        entity_id, old, new, new_attributes = self._extract_event(event)
        if new_attributes:
            changed_by = new_attributes.get(ATTR_CHANGED_BY)
            if changed_by and changed_by.startswith(f"{DOMAIN}."):
                _LOGGER.debug(
                    "AUTOARM Panel Change Ignored: %s,%s: %s-->%s",
                    entity_id,
                    event.event_type,
                    old,
                    new,
                )
                return
        new_state: AlarmControlPanelState | None = alarm_state_as_enum(new)
        old_state: AlarmControlPanelState | None = alarm_state_as_enum(old)

        _LOGGER.info(
            "AUTOARM Panel Change: %s,%s: %s-->%s",
            entity_id,
            event.event_type,
            old,
            new,
        )
        self.record_intervention(ChangeSource.ALARM_PANEL, new_state)
        if new in ZOMBIE_STATES:
            _LOGGER.warning("AUTOARM Dezombifying %s ...", new)
            await self.reset_armed_state(source=ChangeSource.ZOMBIFICATION)
        elif new != old:
            await self.notifier.notify(ChangeSource.ALARM_PANEL, old_state, new_state)
        else:
            _LOGGER.debug("AUTOARM panel change leaves state unchanged at %s", new)

    @callback
    async def housekeeping(self, triggered_at: dt.datetime) -> None:
        _LOGGER.debug("AUTOARM Housekeeping starting, triggered at %s", triggered_at)
        now = dt_util.now()
        self.interventions = [i for i in self.interventions if now < i.created_at + dt.timedelta(minutes=self.intervention_ttl)]
        for cal in self.calendars:
            await cal.prune_events()
        _LOGGER.debug("AUTOARM Housekeeping finished")
