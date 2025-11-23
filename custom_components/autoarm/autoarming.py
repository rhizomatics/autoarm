import asyncio
import contextlib
import datetime
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import Any, cast

import homeassistant.util.dt as dt_util
from homeassistant.components.alarm_control_panel.const import AlarmControlPanelState
from homeassistant.components.calendar.const import DOMAIN as CALENDAR_DOMAIN
from homeassistant.components.sun.const import STATE_BELOW_HORIZON
from homeassistant.const import EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP, SERVICE_RELOAD, STATE_HOME
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, ServiceCall, State, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_platform
from homeassistant.helpers.event import (
    async_track_point_in_time,
    async_track_state_change_event,
    async_track_sunrise,
    async_track_sunset,
)
from homeassistant.helpers.reload import (
    async_integration_yaml_config,
)
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

from .calendar import TrackedCalendar, TrackedCalendarEvent
from .const import (
    CONF_ACTIONS,
    CONF_ALARM_PANEL,
    CONF_ARM_AWAY_DELAY,
    CONF_AUTO_ARM,
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
    CONFIG_SCHEMA,
    DOMAIN,
    NO_CAL_EVENT_MODE_AUTO,
    NO_CAL_EVENT_MODE_MANUAL,
)

_LOGGER = logging.getLogger(__name__)

OVERRIDE_STATES = (AlarmControlPanelState.ARMED_VACATION,
                   AlarmControlPanelState.ARMED_CUSTOM_BYPASS)
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
    hass.data[HASS_DATA_KEY] = AutoArmData(
        _async_process_config(hass, config), {})
    await hass.data[HASS_DATA_KEY].armer.initialize()

    async def reload_service_handler(service_call: ServiceCall) -> None:
        """Reload yaml entities."""
        config = None
        _LOGGER.info("AUTOARM Reloading %s.%s component, data %s",
                     service_call.domain, service_call.service, service_call.data)
        with contextlib.suppress(HomeAssistantError):
            config = await async_integration_yaml_config(hass, DOMAIN)
        if config is None or DOMAIN not in config:
            _LOGGER.warning(
                "AUTOARM reload rejected for lack of config: %s", config)
            return
        hass.data[HASS_DATA_KEY].armer.shutdown()
        expose_config_entity(hass, config[DOMAIN])
        hass.data[HASS_DATA_KEY].armer = _async_process_config(
            hass, config[DOMAIN])
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
            CONF_AUTO_ARM: config.get(CONF_AUTO_ARM, True),
            CONF_SUNRISE_CUTOFF: config.get(CONF_SUNRISE_CUTOFF),
            CONF_OCCUPIED_DAY_DEFAULT: config.get(CONF_OCCUPIED_DAY_DEFAULT),
            CONF_CALENDAR_CONTROL: config.get(CONF_CALENDAR_CONTROL),
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


def _async_process_config(hass: HomeAssistant, config: ConfigType) -> "AlarmArmer":
    calendar_config: ConfigType = config.get(CONF_CALENDAR_CONTROL, {})
    return AlarmArmer(
        hass,
        alarm_panel=config[CONF_ALARM_PANEL],
        auto_disarm=config[CONF_AUTO_ARM],
        sunrise_cutoff=cast("datetime.time", config.get(CONF_SUNRISE_CUTOFF)),
        arm_away_delay=config[CONF_ARM_AWAY_DELAY],
        reset_button=config.get(CONF_BUTTON_ENTITY_RESET),
        away_button=config.get(CONF_BUTTON_ENTITY_AWAY),
        disarm_button=config.get(CONF_BUTTON_ENTITY_DISARM),
        occupants=config[CONF_OCCUPANTS],
        actions=config[CONF_ACTIONS],
        notify=config[CONF_NOTIFY],
        occupied_daytime_default=config[CONF_OCCUPIED_DAY_DEFAULT],
        throttle_calls=config.get(CONF_THROTTLE_CALLS, 6),
        throttle_seconds=config.get(CONF_THROTTLE_SECONDS, 60),
        calendars=calendar_config.get(CONF_CALENDARS, []),
        calendar_no_event_mode=calendar_config.get(
            CONF_CALENDAR_NO_EVENT, NO_CAL_EVENT_MODE_AUTO),
    )


def unlisten(listener: Callable[[], None] | None) -> None:
    if listener:
        try:
            listener()
        except Exception as e:
            _LOGGER.debug(
                "AUTOARM Failure closing listener %s: %s", listener, e)


class AlarmArmer:
    def __init__(
        self,
        hass: HomeAssistant,
        alarm_panel: str,
        auto_disarm: bool = True,
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
    ) -> None:
        self.hass: HomeAssistant = hass
        self.local_tz = dt_util.get_time_zone(self.hass.config.time_zone)
        self.calendar_configs: list[ConfigType] = calendars or []
        self.calendar_no_event_mode = calendar_no_event_mode
        self.calendars: list[TrackedCalendar] = []
        self.alarm_panel: str = alarm_panel
        self.auto_disarm: bool = auto_disarm
        self.sunrise_cutoff: datetime.time | None = sunrise_cutoff
        occupied_daytime_default = occupied_daytime_default.lower(
        ) if occupied_daytime_default else AlarmControlPanelState.ARMED_HOME.value
        self.occupied_daytime_default: AlarmControlPanelState = AlarmControlPanelState(
            occupied_daytime_default)
        self.arm_away_delay: int | None = arm_away_delay
        self.reset_button: str | None = reset_button
        self.away_button: str | None = away_button
        self.disarm_button: str | None = disarm_button
        self.occupants: list[str] = occupants or []
        self.actions: list[str] = actions or []
        self.notify_profiles: dict[str, dict] = notify or {}
        self.unsubscribes: list = []
        self.last_request: datetime.datetime | None = None
        self.last_state_source: str | None = None
        self.button_device: dict[str, str] = {}
        self.arming_in_progress: asyncio.Event = asyncio.Event()
        self.rate_limiter: Limiter = Limiter(
            window=throttle_seconds, max_calls=throttle_calls)

    async def initialize(self) -> None:
        """Async initialization"""
        _LOGGER.info(
            "AUTOARM auto_disarm=%s, arm_delay=%s, occupied=%s, state=%s",
            self.auto_disarm,
            self.arm_away_delay,
            self.is_occupied(),
            self.armed_state(),
        )

        self.initialize_alarm_panel()
        await self.initialize_calendar()
        self.initialize_diurnal()
        self.initialize_occupancy()
        self.initialize_buttons()
        await self.reset_armed_state(force_arm=False)
        self.initialize_integration()
        self.stop_listener: Callable[[], None] | None = self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, self.async_shutdown
        )

        _LOGGER.info("AUTOARM Initialized, state: %s", self.armed_state())

    def initialize_integration(self) -> None:
        self.unsubscribes.append(self.hass.bus.async_listen(
            "mobile_app_notification_action", self.on_mobile_action))
        self.unsubscribes.append(self.hass.bus.async_listen(
            EVENT_HOMEASSISTANT_START, self.ha_start))

    @callback
    async def ha_start(self, _event: Event) -> None:
        _LOGGER.debug("AUTOARM Home assistant restarted")
        await self.reset_armed_state(force_arm=False)

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

    def initialize_alarm_panel(self) -> None:
        """Set up automation for Home Assistant alarm panel

        See https://www.home-assistant.io/integrations/alarm_control_panel/
        """
        self.unsubscribes.append(async_track_state_change_event(
            self.hass, [self.alarm_panel], self.on_panel_change))
        _LOGGER.debug("AUTOARM Auto-arming %s", self.alarm_panel)

    def initialize_diurnal(self) -> None:
        # events API expects a function, however underlying HassJob is fine with coroutines
        self.unsubscribes.append(async_track_sunrise(
            self.hass, self.on_sunrise, None))  # type: ignore
        self.unsubscribes.append(async_track_sunset(
            self.hass, self.on_sunset, None))  # type: ignore

    def initialize_occupancy(self) -> None:
        """Configure occupants, and listen for changes in their state"""
        _LOGGER.info("AUTOARM Occupancy determined by %s",
                     ",".join(self.occupants))
        self.unsubscribes.append(async_track_state_change_event(
            self.hass, self.occupants, self.on_occupancy_change))
        _LOGGER.debug(
            "AUTOARM Occupied: %s, Unoccupied: %s, Night: %s",
            self.is_occupied(),
            self.is_unoccupied(),
            self.is_night(),
        )

    async def initialize_calendar(self) -> None:
        """Configure calendar polling (optional)"""
        self.hass.states.async_set(
            f"{DOMAIN}.last_calendar_event", "unavailable", attributes={})
        if not self.calendar_configs:
            return
        try:
            platforms: list[entity_platform.EntityPlatform] = entity_platform.async_get_platforms(
                self.hass, CALENDAR_DOMAIN)
            if platforms:
                platform: entity_platform.EntityPlatform = platforms[0]
            else:
                _LOGGER.error(
                    "AUTOARM Calendar platform not available from Home Assistant")
                return
        except Exception as _e:
            _LOGGER.exception("AUTOARM Unable to access calendar platform")
            return
        for calendar_config in self.calendar_configs:
            tracked_calendar = TrackedCalendar(calendar_config, self)
            await tracked_calendar.initialize(platform)
            self.calendars.append(tracked_calendar)

    def active_calendar_event(self) -> bool:
        return any(cal.has_active_event() for cal in self.calendars)

    async def on_calendar_event_start(self, event: TrackedCalendarEvent, triggered_at: datetime.datetime) -> None:
        _LOGGER.debug("AUTOARM on_calendar_event_start(%s,%s)",
                      event.id, triggered_at)
        if event.arming_state != self.armed_state():
            _LOGGER.info("AUTOARM Calendar event %s changing arming to %s at %s",
                         event.id, event.arming_state, triggered_at)
            await self.arm(arming_state=event.arming_state, source="calendar")
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
        _LOGGER.debug("AUTOARM on_calendar_event_start(%s,%s)",
                      event.id, ended_at)
        if any(cal.has_active_event() for cal in self.calendars):
            _LOGGER.debug(
                "AUTOARM No action on event end since other cal event active")
            return
        if self.calendar_no_event_mode == NO_CAL_EVENT_MODE_AUTO:
            _LOGGER.info(
                "AUTOARM Calendar event %s ended, and arming state", event.id)
            await self.reset_armed_state()
        elif self.calendar_no_event_mode in AlarmControlPanelState:
            _LOGGER.info(
                "AUTOARM Calendar event %s ended, and returning to fixed state %s", event.id, self.calendar_no_event_mode
            )
            await self.arm(self.calendar_no_event_mode, source="calendar")
        else:
            _LOGGER.debug(
                "AUTOARM Reinstate previous state on calendar event end in manual mode")
            await self.arm(event.previous_state, source="calendar")

    def initialize_buttons(self) -> None:
        """Initialize (optional) physical alarm state control buttons"""

        def setup_button(state: str, button_entity: str, cb: Callable) -> None:
            self.button_device[state] = button_entity
            if self.button_device[state]:
                self.unsubscribes.append(async_track_state_change_event(
                    self.hass, [button_entity], cb))

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
        _LOGGER.debug("AUTOARM Occupancy Change: %s, %s, %s, %s",
                      entity_id, old, new, event)
        if self.is_unoccupied() and existing_state in (
            AlarmControlPanelState.ARMED_HOME,
            AlarmControlPanelState.DISARMED,
            AlarmControlPanelState.ARMED_NIGHT,
        ):
            _LOGGER.info("AUTOARM Now unoccupied, arming")
            await self.arm(AlarmControlPanelState.ARMED_AWAY, source="occupancy")
        elif self.is_occupied() and existing_state == AlarmControlPanelState.ARMED_AWAY:
            _LOGGER.info("AUTOARM Now occupied, resetting armed state")
            await self.reset_armed_state()

    async def reset_armed_state(self, force_arm: bool = True, hint_arming: str | None = None) -> str | None:
        """Logic to automatically work out appropriate current armed state"""
        _LOGGER.debug(
            "AUTOARM reset_armed_state(force_arm=%s,hint_arming=%s)",
            force_arm,
            hint_arming,
        )

        existing_state = self.armed_state()
        if self.calendars:
            if self.active_calendar_event():
                _LOGGER.debug(
                    "AUTOARM Ignoring reset while calendar event active")
                return existing_state
            if self.calendar_no_event_mode == NO_CAL_EVENT_MODE_MANUAL:
                _LOGGER.debug(
                    "AUTOARM Ignoring reset while calendar configured, no active event, and default mode is manual")
                return existing_state
            if self.calendar_no_event_mode in AlarmControlPanelState:
                return await self.arm(self.calendar_no_event_mode, "calendar")
            if self.calendar_no_event_mode == NO_CAL_EVENT_MODE_AUTO:
                _LOGGER.debug(
                    "AUTOARM Applying reset while calendar configured, no active event, and default mode is auto")
                if self.last_state_source == "calendar":
                    # force reset, may have been left in holiday state by a calendar entry
                    force_arm = True
            else:
                _LOGGER.warning(
                    "AUTOARM Unexpected state for calendar no event mode: %s", self.calendar_no_event_mode)

        if not force_arm:
            if existing_state in OVERRIDE_STATES:
                _LOGGER.debug(
                    "AUTOARM Ignoring reset for existing state: %s", existing_state)
                return existing_state
            if existing_state == AlarmControlPanelState.DISARMED:
                _LOGGER.debug("AUTOARM Ignoring unforced reset for disarmed")
                return existing_state

        if self.is_occupied():
            if hint_arming:
                _LOGGER.info(
                    "AUTOARM Using hinted arming state: %s", hint_arming)
                return await self.arm(hint_arming, source="reset")
            if self.is_night():
                _LOGGER.info("AUTOARM Defaulting to armed night")
                return await self.arm(AlarmControlPanelState.ARMED_NIGHT, source="reset")
            _LOGGER.info("AUTOARM Defaulting to %s",
                         self.occupied_daytime_default)
            return await self.arm(self.occupied_daytime_default, source="reset")

        if hint_arming:
            _LOGGER.info("AUTOARM Using hinted arming state: %s", hint_arming)
            return await self.arm(hint_arming, source="reset")
        _LOGGER.info("AUTOARM Defaulting to armed away")
        return await self.arm(AlarmControlPanelState.ARMED_AWAY, source="reset")

    async def delayed_arm(
        self,
        arming_state: str,
        reset: bool,
        requested_at: datetime.datetime,
        triggered_at: datetime.datetime,
        source: str | None = None,
    ) -> None:
        _LOGGER.debug("Delayed_arm %s, reset: %s, triggered at: %s, source%s",
                      arming_state, reset, triggered_at, source)

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
            await self.arm(arming_state=arming_state, source=source)
        return

    async def arm(self, arming_state: str | None = None, source: str | None = None) -> str | None:
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
            _LOGGER.debug(
                "AUTOARM Rate limit triggered by %s, skipping arm", source)
            return None
        try:
            self.arming_in_progress.set()
            existing_state = self.armed_state()
            if arming_state != existing_state:
                self.hass.states.async_set(self.alarm_panel, str(arming_state))
                _LOGGER.info("AUTOARM Setting %s from %s to %s for %s",
                             self.alarm_panel, existing_state, arming_state, source)
                self.last_state_source = source
                return arming_state
            _LOGGER.debug("Skipping arm for %s, as %s already %s",
                          source, self.alarm_panel, arming_state)
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
            notify_service = merged_profile.get(
                "service", "").replace("notify.", "")

            title = title or "Alarm Auto Arming"
            if notify_service and merged_profile:
                data = merged_profile.get("data", {})
                await self.hass.services.async_call(
                    "notify",
                    notify_service,
                    service_data={"message": message,
                                  "title": title, "data": data},
                )
            else:
                _LOGGER.debug(
                    "AUTOARM Skipped notification, service: %s, data: %s", notify_service, merged_profile)

        except Exception:
            _LOGGER.exception("AUTOARM notify.%s failed", notify_service)

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
                await self.arm(AlarmControlPanelState.DISARMED, source="mobile")
            case "ALARM_PANEL_RESET":
                await self.reset_armed_state(force_arm=True)
            case "ALARM_PANEL_AWAY":
                await self.arm(AlarmControlPanelState.ARMED_AWAY, source="mobile")
            case _:
                _LOGGER.debug("AUTOARM Ignoring mobile action: %s", event.data)

    @callback
    async def on_disarm_button(self, event: Event) -> None:
        _LOGGER.info("AUTOARM Disarm Button: %s", event)
        self.register_request()
        await self.arm(AlarmControlPanelState.DISARMED, source="button")

    @callback
    async def on_vacation_button(self, event: Event) -> None:
        _LOGGER.info("AUTOARM Vacation Button: %s", event)
        await self.arm(AlarmControlPanelState.ARMED_VACATION, source="button")

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
                        source="button",
                    ),
                    dt_util.utc_from_timestamp(
                        time.time() + self.arm_away_delay),
                )
            )
            await self.notify(
                f"Alarm will be armed for away in {self.arm_away_delay} seconds",
                title="Arm for away process starting",
            )
        else:
            await self.arm(AlarmControlPanelState.ARMED_AWAY, source="button")

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
            trigger = datetime.datetime.combine(
                now.date(), self.sunrise_cutoff, tzinfo=self.local_tz)
            self.unsubscribes.append(
                async_track_point_in_time(
                    self.hass,
                    partial(self.delayed_arm, AlarmControlPanelState.ARMED_HOME,
                            True, now, source="sunrise"),
                    trigger,
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
