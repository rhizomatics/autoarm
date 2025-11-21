import asyncio
import datetime
import logging
import time
from collections.abc import Callable
from functools import partial
from typing import cast

import homeassistant.util.dt as dt_util
from homeassistant.components.alarm_control_panel.const import AlarmControlPanelState
from homeassistant.components.sun.const import STATE_BELOW_HORIZON
from homeassistant.const import (
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
    STATE_HOME,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, State, callback
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
    CONF_NOTIFY,
    CONF_OCCUPANTS,
    CONF_SLEEP_END,
    CONF_SLEEP_START,
    CONF_SUNRISE_CUTOFF,
    CONF_THROTTLE_CALLS,
    CONF_THROTTLE_SECONDS,
    CONFIG_SCHEMA,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def total_secs(t: datetime.time) -> int:
    return t.hour * 3600 + t.minute * 60 + t.second


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
    )
    await armer.initialize()
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, armer.async_shutdown)

    return True


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
    ) -> None:
        self.hass: HomeAssistant = hass
        self.local_tz = dt_util.get_time_zone(self.hass.config.time_zone)
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
        if existing_state == AlarmControlPanelState.DISARMED and not force_arm:
            _LOGGER.debug("AUTOARM Ignoring unforced reset for disarmed")
            return existing_state

        if existing_state in OVERRIDE_STATES:
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
        self,
        arming_state: str,
        reset: bool,
        requested_at: datetime.datetime,
        triggered_at: datetime.datetime,
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
            notify_service = merged_profile["service"].replace("notify.", "")

            title = title or "Alarm Auto Arming"
            if merged_profile:
                data = merged_profile.get("data", {})
                await self.hass.services.async_call(
                    "notify",
                    notify_service,
                    service_data={"message": message, "title": title, "data": data},
                )

        except Exception as e:
            _LOGGER.error("AUTOARM %s failed %s", notify_service, e)

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
        if not self.sunrise_cutoff or datetime.datetime.now(tz=self.local_tz).time() >= self.sunrise_cutoff:
            await self.reset_armed_state(force_arm=False)
        elif self.sleep_end and self.sunrise_cutoff < self.sleep_end:
            sunrise_delay = total_secs(self.sleep_end) - total_secs(self.sunrise_cutoff)
            _LOGGER.debug(
                "AUTOARM Rescheduling delayed sunrise action in %s seconds",
                sunrise_delay,
            )
            self.unsubscribes.append(
                async_track_point_in_time(
                    self.hass,
                    partial(
                        self.delayed_arm,
                        AlarmControlPanelState.ARMED_HOME,
                        True,
                        dt_util.utc_from_timestamp(time.time()),
                    ),
                    dt_util.utc_from_timestamp(time.time() + sunrise_delay),
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
