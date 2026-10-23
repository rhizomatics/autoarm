"""Config flow for Auto Arm integration."""

import datetime as dt
import re
from collections.abc import Mapping
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_ENABLED, CONF_ENTITY_ID, CONF_SERVICE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import section
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    ObjectSelector,
    ObjectSelectorConfig,
    Selector,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TargetSelector,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
    TimeSelector,
)

from .compat import vol
from .const import (
    ATTR_RESET,
    CALENDAR_END_MODE_OPTIONS,
    CONF_ALARM_PANEL,
    CONF_CALENDAR_ARMED_END,
    CONF_CALENDAR_CONTROL,
    CONF_CALENDAR_DISARMED_END,
    CONF_CALENDAR_NO_EVENT,
    CONF_CALENDARS,
    CONF_DAY,
    CONF_DIURNAL,
    CONF_EARLIEST,
    CONF_LATEST,
    CONF_NIGHT,
    CONF_NOTIFY,
    CONF_OCCUPANCY,
    CONF_OCCUPANCY_DEFAULT,
    CONF_SUNRISE,
    CONF_SUNSET,
    DEFAULT_CALENDAR_NOTIFY_GRACE,
    DOMAIN,
    FRIGATE_NO_PROFILE,
    NO_CAL_EVENT_MODE_AUTO,
    NOTIFY_COMMON,
    NOTIFY_PRIORITY_DEFAULTS,
    NOTIFY_PRIORITY_SOURCES,
    PUBLIC_ALARM_STATES,
    SUN_TRIGGER_OPTIONS,
    SUPERNOTIFY_ACTION,
    SUPERNOTIFY_PRIORITIES,
    TRIGGER_AUTO,
)
from .crypto import async_encrypt
from .frigate import frigate_profile_selects, frigate_profiles, match_profile
from .supernotify_api import deliveries, supernotify_available

CONF_CALENDAR_ENTITIES = "calendar_entities"
CONF_PERSON_ENTITIES = "person_entities"
CONF_OCCUPANCY_DEFAULT_DAY = "occupancy_default_day"
CONF_OCCUPANCY_DEFAULT_NIGHT = "occupancy_default_night"
# replaced by the armed and disarmed end modes, kept to migrate entries and read YAML
CONF_NO_EVENT_MODE = "no_event_mode"
CONF_CALENDAR_ARMED_END_MODE = "calendar_armed_end_mode"
CONF_CALENDAR_DISARMED_END_MODE = "calendar_disarmed_end_mode"
# each a calendar, an alarm state and the patterns for the events of that calendar that set the state
CONF_CALENDAR_MATCH_RULES = "calendar_match_rules"
CONF_RULE_CALENDAR = "calendar"
CONF_RULE_STATE = "state"
CONF_RULE_PATTERNS = "patterns"
# minutes between looking at each calendar
CONF_CALENDAR_POLL_MINUTES = "calendar_poll_interval"
DEFAULT_CALENDAR_POLL_MINUTES = 15
# seconds to hold a notification of a calendar change, so that changes close together are told as one
CONF_CALENDAR_NOTIFY_GRACE_SECONDS = "calendar_notify_grace"
CONF_CALENDAR_OCCUPANCY_OVERRIDE_STATES = "calendar_occupancy_override_states"
CONF_CALENDAR_OCCUPANCY_ENDS_AWAY = "calendar_occupancy_ends_away"
CONF_NOTIFY_ACTION = "notify_action"
CONF_NOTIFY_TARGETS = "notify_targets"
# as the `target` and `custom_target` of supernotify.notify, and the deliveries to keep to
CONF_NOTIFY_TARGET = "notify_target"
CONF_NOTIFY_CUSTOM_TARGET = "notify_custom_target"
CONF_NOTIFY_DELIVERIES = "notify_deliveries"


def notify_priority_option(kind: str) -> str:
    """Option holding the Supernotify priority for a kind of change, as keyed in NOTIFY_PRIORITY_SOURCES"""
    return f"notify_priority_{kind}"


CONF_NOTIFY_DATA = "notify_data"
CONF_NOTIFY_ENABLED = "notify_enabled"
# for the dark between bedtime ending and sunrise
CONF_OCCUPANCY_DEFAULT_AFTER_BEDTIME = "occupancy_default_after_bedtime"
CONF_SUNRISE_TRIGGER = "sunrise_trigger"
CONF_SUNSET_TRIGGER = "sunset_trigger"
CONF_OCCUPIED_TRIGGER = "occupied_trigger"
CONF_UNOCCUPIED_TRIGGER = "unoccupied_trigger"
CONF_SUNRISE_EARLIEST = "sunrise_earliest"
CONF_SUNRISE_LATEST = "sunrise_latest"
CONF_SUNSET_EARLIEST = "sunset_earliest"
CONF_SUNSET_LATEST = "sunset_latest"
CONF_USE_ALARM_SERVICE = "use_alarm_service"
# guard against loops, at most so many changes within a period of seconds
CONF_RATE_LIMIT_MAX_CALLS = "rate_limit_max_calls"
CONF_RATE_LIMIT_SECONDS = "rate_limit_period"
DEFAULT_RATE_LIMIT_MAX_CALLS = 5
DEFAULT_RATE_LIMIT_SECONDS = 60
# seconds to wait after someone arrives or leaves before working out the state
CONF_OCCUPIED_DELAY = "occupied_delay"
CONF_UNOCCUPIED_DELAY = "unoccupied_delay"
# time for a tracker to settle, or to come back for something forgotten, before arming for an empty house
DEFAULT_OCCUPANCY_DELAYS: dict[str, int] = {CONF_OCCUPIED_DELAY: 0, CONF_UNOCCUPIED_DELAY: 120}
# held encrypted, see crypto
CONF_PANEL_CODE = "panel_code"
# only a form field, to remove the stored code, since that isn't shown to be blanked out
CONF_PANEL_CODE_CLEAR = "panel_code_clear"
CONF_SENTENCE_ARM = "sentence_arm"
CONF_SENTENCE_DISARM = "sentence_disarm"
# switch Frigate profiles with the alarm state, using the Frigate integration's profile select
CONF_FRIGATE_ENABLED = "frigate_enabled"
# only needed to choose between more than one Frigate server
CONF_FRIGATE_PROFILE_ENTITY = "frigate_profile_entity"

DEFAULT_CALENDAR_OCCUPANCY_OVERRIDE_STATES: list[str] = ["disarmed", "armed_home", "armed_night", "armed_away"]
RECIPE_URL = "https://autoarm.rhizomatics.org.uk/configuration/examples/recommended_recipe/"
# My Home Assistant deep links into the built-in helpers that can stand in for a missing entity,
# a stable redirect rather than a hardcoded frontend path: https://www.home-assistant.io/integrations/my/
ALARM_PANEL_HELP_URL = "https://my.home-assistant.io/redirect/config_flow_start/?domain=template"
CALENDAR_HELP_URL = "https://my.home-assistant.io/redirect/config_flow_start/?domain=local_calendar"
TIME_OF_DAY_HELP_URL = "https://my.home-assistant.io/redirect/config_flow_start/?domain=tod"
PERSON_HELP_URL = "https://my.home-assistant.io/redirect/people/"
FRIGATE_PROFILES_URL = "https://docs.frigate.video/configuration/profiles/"
SETUP_HELP_PLACEHOLDERS: dict[str, str] = {
    "recipe_url": RECIPE_URL,
    "alarm_panel_help_url": ALARM_PANEL_HELP_URL,
    "calendar_help_url": CALENDAR_HELP_URL,
    "bedtime_help_url": TIME_OF_DAY_HELP_URL,
    "person_help_url": PERSON_HELP_URL,
    "frigate_profiles_url": FRIGATE_PROFILES_URL,
}
OPTIONS_HELP_PLACEHOLDERS: dict[str, str] = {"recipe_url": RECIPE_URL, "frigate_profiles_url": FRIGATE_PROFILES_URL}
# option holding the Times of the Day sensors for each alarm state, a daily period doesn't suit vacations
TIME_OF_DAY_OPTIONS: dict[str, str] = {
    f"time_of_day_{state}": state for state in PUBLIC_ALARM_STATES if state != "armed_vacation"
}
# option holding the Frigate profile for each alarm state, a state without one matched to a profile by name
FRIGATE_PROFILE_OPTIONS: dict[str, str] = {f"frigate_profile_{state}": state for state in PUBLIC_ALARM_STATES}
# a reset button, and buttons for each alarm state, each with a delay in seconds before it acts
BUTTON_USES: list[str] = [ATTR_RESET, *PUBLIC_ALARM_STATES]
BUTTON_DOMAINS: list[str] = ["binary_sensor", "button", "input_button"]
# time to get out of the door
DEFAULT_BUTTON_DELAYS: dict[str, int] = {"armed_away": 120}


def button_option(use: str) -> str:
    return f"button_{use}"


def button_delay_option(use: str) -> str:
    return f"button_{use}_delay"


# the bedtime sensor of the recommended recipe, asked for up front rather than in the Times of the Day section
CONF_BEDTIME_ENTITIES = "time_of_day_armed_night"


def _time_to_str(t: dt.time | None) -> str | None:
    """Convert a datetime.time to HH:MM:SS string for ConfigEntry storage."""
    return t.isoformat() if t else None


DEFAULT_NOTIFY_ACTION = "notify.send_message"

# as the recommended recipe, disarmed by day, armed home from sunset and armed night for bedtime
DEFAULT_OPTIONS: dict[str, Any] = {
    CONF_CALENDAR_ENTITIES: [],
    CONF_PERSON_ENTITIES: [],
    CONF_BEDTIME_ENTITIES: [],
    CONF_OCCUPANCY_DEFAULT_DAY: "disarmed",
    CONF_OCCUPANCY_DEFAULT_AFTER_BEDTIME: "armed_home",
    CONF_OCCUPANCY_DEFAULT_NIGHT: "armed_home",
    CONF_CALENDAR_ARMED_END_MODE: NO_CAL_EVENT_MODE_AUTO,
    CONF_CALENDAR_DISARMED_END_MODE: NO_CAL_EVENT_MODE_AUTO,
    CONF_CALENDAR_OCCUPANCY_OVERRIDE_STATES: DEFAULT_CALENDAR_OCCUPANCY_OVERRIDE_STATES,
    CONF_CALENDAR_OCCUPANCY_ENDS_AWAY: True,
    CONF_NOTIFY_ENABLED: True,
    CONF_NOTIFY_ACTION: DEFAULT_NOTIFY_ACTION,
    CONF_NOTIFY_TARGETS: [],
    CONF_NOTIFY_DATA: {},
    CONF_SUNRISE_TRIGGER: TRIGGER_AUTO,
    CONF_SUNSET_TRIGGER: TRIGGER_AUTO,
    CONF_OCCUPIED_TRIGGER: True,
    CONF_UNOCCUPIED_TRIGGER: True,
    CONF_SUNRISE_EARLIEST: None,
    CONF_SUNRISE_LATEST: None,
    CONF_SUNSET_EARLIEST: None,
    CONF_SUNSET_LATEST: None,
    CONF_USE_ALARM_SERVICE: True,
    **DEFAULT_OCCUPANCY_DELAYS,
    CONF_RATE_LIMIT_MAX_CALLS: DEFAULT_RATE_LIMIT_MAX_CALLS,
    CONF_RATE_LIMIT_SECONDS: DEFAULT_RATE_LIMIT_SECONDS,
    CONF_SENTENCE_ARM: True,
    CONF_SENTENCE_DISARM: False,
}


def _top_level_fields(
    options: Mapping[str, Any], alarm_panel_default: str | None = None, frigate_available: bool = False
) -> dict[Any, Any]:
    """Alarm panel plus the recommended-recipe entities, shared by every setup path and the options flow."""
    alarm_panel_marker = (
        vol.Required(CONF_ALARM_PANEL, default=alarm_panel_default) if alarm_panel_default else vol.Required(CONF_ALARM_PANEL)
    )
    return {
        alarm_panel_marker: EntitySelector(EntitySelectorConfig(domain="alarm_control_panel")),
        vol.Optional(CONF_BEDTIME_ENTITIES, default=options.get(CONF_BEDTIME_ENTITIES, [])): _time_of_day_selector(),
        vol.Optional(CONF_CALENDAR_ENTITIES, default=options.get(CONF_CALENDAR_ENTITIES, [])): EntitySelector(
            EntitySelectorConfig(domain="calendar", multiple=True)
        ),
        vol.Optional(CONF_PERSON_ENTITIES, default=options.get(CONF_PERSON_ENTITIES, [])): EntitySelector(
            EntitySelectorConfig(domain="person", multiple=True)
        ),
        **(
            {vol.Optional(CONF_FRIGATE_ENABLED, default=options.get(CONF_FRIGATE_ENABLED, False)): BooleanSelector()}
            if frigate_available
            else {}
        ),
    }


def _frigate_available(hass: HomeAssistant, options: Mapping[str, Any]) -> bool:
    """There's a Frigate with profiles, or profiles are already on, so they can be turned off after Frigate has gone"""
    return bool(frigate_profile_selects(hass)) or bool(options.get(CONF_FRIGATE_ENABLED))


def _default_notify_action(hass: HomeAssistant) -> str:
    """Notification action for a new install, Supernotify if that's already there"""
    return SUPERNOTIFY_ACTION if supernotify_available(hass) else DEFAULT_NOTIFY_ACTION


async def _section_fields(hass: HomeAssistant, options: Mapping[str, Any]) -> dict[Any, Any]:
    """The alarm panel code and the full set of options flow sections, shared by advanced setup and the options flow."""
    notify_services = sorted(f"notify.{service}" for service in hass.services.async_services().get("notify", {}))
    notify_target_fields: dict[Any, Any]
    if supernotify_available(hass):
        notify_services.insert(0, SUPERNOTIFY_ACTION)
        # the same pair of target fields as supernotify.notify itself, with targets from before they were split now custom
        typed_targets: list[str] = [*options.get(CONF_NOTIFY_TARGETS, []), *options.get(CONF_NOTIFY_CUSTOM_TARGET, [])]
        notify_target_fields = {
            vol.Optional(CONF_NOTIFY_TARGET, default=options.get(CONF_NOTIFY_TARGET, {})): TargetSelector(),
            vol.Optional(CONF_NOTIFY_CUSTOM_TARGET, default=list(dict.fromkeys(typed_targets))): TextSelector(
                TextSelectorConfig(multiple=True)
            ),
            # a delivery since removed from Supernotify is still shown, to be taken off
            vol.Optional(CONF_NOTIFY_DELIVERIES, default=options.get(CONF_NOTIFY_DELIVERIES, [])): SelectSelector(
                SelectSelectorConfig(options=await deliveries(hass), multiple=True, custom_value=True)
            ),
            **{
                vol.Optional(
                    notify_priority_option(kind),
                    default=options.get(notify_priority_option(kind), NOTIFY_PRIORITY_DEFAULTS[kind]),
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=SUPERNOTIFY_PRIORITIES, mode=SelectSelectorMode.DROPDOWN, translation_key="notify_priority"
                    )
                )
                for kind in NOTIFY_PRIORITY_SOURCES
            },
        }
    else:
        notify_target_fields = {
            vol.Optional(CONF_NOTIFY_TARGETS, default=options.get(CONF_NOTIFY_TARGETS, [])): TextSelector(
                TextSelectorConfig(multiple=True)
            ),
        }

    return {
        # never filled in with the stored code, so that isn't sent back out to a browser
        vol.Optional(CONF_PANEL_CODE): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD, autocomplete="off")),
        **({vol.Optional(CONF_PANEL_CODE_CLEAR, default=False): BooleanSelector()} if options.get(CONF_PANEL_CODE) else {}),
        vol.Required("assist_options"): section(
            vol.Schema({
                vol.Required(
                    CONF_SENTENCE_ARM,
                    default=options.get(CONF_SENTENCE_ARM, True),
                ): BooleanSelector(),
                vol.Required(
                    CONF_SENTENCE_DISARM,
                    default=options.get(CONF_SENTENCE_DISARM, False),
                ): BooleanSelector(),
            }),
            {"collapsed": True},
        ),
        vol.Required("button_options"): section(
            vol.Schema({
                marker: selector
                for use in BUTTON_USES
                for marker, selector in (
                    (
                        vol.Optional(button_option(use), default=options.get(button_option(use), [])),
                        EntitySelector(EntitySelectorConfig(domain=BUTTON_DOMAINS, multiple=True)),
                    ),
                    (
                        vol.Optional(
                            button_delay_option(use),
                            default=options.get(button_delay_option(use), DEFAULT_BUTTON_DELAYS.get(use, 0)),
                        ),
                        NumberSelector(
                            NumberSelectorConfig(min=0, max=3600, mode=NumberSelectorMode.BOX, unit_of_measurement="s")
                        ),
                    ),
                )
            }),
            {"collapsed": True},
        ),
        vol.Required("notify_options"): section(
            vol.Schema({
                vol.Required(
                    CONF_NOTIFY_ENABLED,
                    default=options.get(CONF_NOTIFY_ENABLED, True),
                ): BooleanSelector(),
                vol.Optional(
                    CONF_NOTIFY_ACTION,
                    default=options.get(CONF_NOTIFY_ACTION, DEFAULT_NOTIFY_ACTION),
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=notify_services,
                        multiple=False,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                **notify_target_fields,
                vol.Optional(
                    CONF_NOTIFY_DATA,
                    default=options.get(CONF_NOTIFY_DATA, {}),
                ): ObjectSelector(),
            }),
            {"collapsed": True},
        ),
        vol.Required("calendar_options"): section(
            vol.Schema({
                vol.Required(
                    CONF_CALENDAR_ARMED_END_MODE,
                    default=options.get(CONF_CALENDAR_ARMED_END_MODE, NO_CAL_EVENT_MODE_AUTO),
                ): _calendar_end_mode_selector(),
                vol.Required(
                    CONF_CALENDAR_DISARMED_END_MODE,
                    default=options.get(CONF_CALENDAR_DISARMED_END_MODE, NO_CAL_EVENT_MODE_AUTO),
                ): _calendar_end_mode_selector(),
                vol.Optional(
                    CONF_CALENDAR_MATCH_RULES,
                    default=options.get(CONF_CALENDAR_MATCH_RULES, []),
                ): ObjectSelector(
                    ObjectSelectorConfig(
                        multiple=True,
                        label_field=CONF_RULE_STATE,
                        description_field=CONF_RULE_CALENDAR,
                        translation_key="calendar_match_rule",
                        fields={
                            CONF_RULE_CALENDAR: {
                                "selector": EntitySelector(EntitySelectorConfig(domain="calendar")),
                                "required": True,
                            },
                            CONF_RULE_STATE: {"selector": _alarm_state_selector(), "required": True},
                            CONF_RULE_PATTERNS: {
                                "selector": TextSelector(TextSelectorConfig(multiple=True)),
                                "required": True,
                            },
                        },
                    )
                ),
                vol.Optional(
                    CONF_CALENDAR_POLL_MINUTES,
                    default=options.get(CONF_CALENDAR_POLL_MINUTES, DEFAULT_CALENDAR_POLL_MINUTES),
                ): NumberSelector(
                    NumberSelectorConfig(min=1, max=1440, mode=NumberSelectorMode.BOX, unit_of_measurement="min")
                ),
                vol.Optional(
                    CONF_CALENDAR_NOTIFY_GRACE_SECONDS,
                    default=options.get(CONF_CALENDAR_NOTIFY_GRACE_SECONDS, int(DEFAULT_CALENDAR_NOTIFY_GRACE.total_seconds())),
                ): _seconds_selector(),
            }),
            {"collapsed": True},
        ),
        vol.Required("sun_options"): section(
            vol.Schema({
                vol.Optional(
                    CONF_OCCUPANCY_DEFAULT_DAY,
                    default=options.get(CONF_OCCUPANCY_DEFAULT_DAY, "disarmed"),
                ): _alarm_state_selector(),
                vol.Optional(
                    CONF_OCCUPANCY_DEFAULT_AFTER_BEDTIME,
                    default=options.get(CONF_OCCUPANCY_DEFAULT_AFTER_BEDTIME, "armed_home"),
                ): _alarm_state_selector(),
                vol.Optional(
                    CONF_OCCUPANCY_DEFAULT_NIGHT,
                    description={"suggested_value": options.get(CONF_OCCUPANCY_DEFAULT_NIGHT, "armed_night")},
                ): _alarm_state_selector(),
                vol.Required(
                    CONF_SUNRISE_TRIGGER,
                    default=options.get(CONF_SUNRISE_TRIGGER, TRIGGER_AUTO),
                ): _sun_trigger_selector(),
                vol.Optional(
                    CONF_SUNRISE_EARLIEST,
                    description={"suggested_value": options.get(CONF_SUNRISE_EARLIEST)},
                ): TimeSelector(),
                vol.Optional(
                    CONF_SUNRISE_LATEST,
                    description={"suggested_value": options.get(CONF_SUNRISE_LATEST)},
                ): TimeSelector(),
                vol.Required(
                    CONF_SUNSET_TRIGGER,
                    default=options.get(CONF_SUNSET_TRIGGER, TRIGGER_AUTO),
                ): _sun_trigger_selector(),
                vol.Optional(
                    CONF_SUNSET_EARLIEST,
                    description={"suggested_value": options.get(CONF_SUNSET_EARLIEST)},
                ): TimeSelector(),
                vol.Optional(
                    CONF_SUNSET_LATEST,
                    description={"suggested_value": options.get(CONF_SUNSET_LATEST)},
                ): TimeSelector(),
            }),
            {"collapsed": True},
        ),
        vol.Required("presence_options"): section(
            vol.Schema({
                vol.Required(
                    CONF_OCCUPIED_TRIGGER,
                    default=options.get(CONF_OCCUPIED_TRIGGER, True),
                ): BooleanSelector(),
                vol.Required(
                    CONF_UNOCCUPIED_TRIGGER,
                    default=options.get(CONF_UNOCCUPIED_TRIGGER, True),
                ): BooleanSelector(),
                vol.Optional(
                    CONF_CALENDAR_OCCUPANCY_OVERRIDE_STATES,
                    default=options.get(CONF_CALENDAR_OCCUPANCY_OVERRIDE_STATES, DEFAULT_CALENDAR_OCCUPANCY_OVERRIDE_STATES),
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=PUBLIC_ALARM_STATES,
                        multiple=True,
                        mode=SelectSelectorMode.LIST,
                    )
                ),
                vol.Required(
                    CONF_CALENDAR_OCCUPANCY_ENDS_AWAY,
                    default=options.get(CONF_CALENDAR_OCCUPANCY_ENDS_AWAY, True),
                ): BooleanSelector(),
                **{
                    vol.Optional(option, default=options.get(option, default)): _seconds_selector()
                    for option, default in DEFAULT_OCCUPANCY_DELAYS.items()
                },
            }),
            {"collapsed": True},
        ),
        **_frigate_section(hass, options),
        vol.Required("advanced_options"): section(
            vol.Schema({
                vol.Required(
                    CONF_USE_ALARM_SERVICE,
                    default=options.get(CONF_USE_ALARM_SERVICE, True),
                ): BooleanSelector(),
                vol.Optional(
                    CONF_RATE_LIMIT_MAX_CALLS,
                    default=options.get(CONF_RATE_LIMIT_MAX_CALLS, DEFAULT_RATE_LIMIT_MAX_CALLS),
                ): NumberSelector(NumberSelectorConfig(min=1, max=100, mode=NumberSelectorMode.BOX)),
                vol.Optional(
                    CONF_RATE_LIMIT_SECONDS,
                    default=options.get(CONF_RATE_LIMIT_SECONDS, DEFAULT_RATE_LIMIT_SECONDS),
                ): _seconds_selector(minimum=1),
            }),
            {"collapsed": True},
        ),
        vol.Required("time_of_day_options"): section(
            vol.Schema({
                vol.Optional(option, default=options.get(option, [])): _time_of_day_selector()
                for option in TIME_OF_DAY_OPTIONS
                if option != CONF_BEDTIME_ENTITIES
            }),
            {"collapsed": True},
        ),
    }


def _frigate_section(hass: HomeAssistant, options: Mapping[str, Any]) -> dict[Any, Any]:
    """Overrides for Frigate profiles, the profiles matched by name, and the select where there's more than one Frigate"""
    if not _frigate_available(hass, options):
        return {}
    profiles: list[str] = _matchable_profiles(hass, options)
    # no profile, for a state cleared, then those in Frigate, others can be typed in while Frigate is down
    profile_choices: list[str] = [FRIGATE_NO_PROFILE, *profiles]
    return {
        vol.Required("frigate_options"): section(
            vol.Schema({
                **{
                    # filled in by name until saved, so a profile cleared stays cleared
                    vol.Optional(
                        option,
                        description={
                            "suggested_value": options[option] if option in options else match_profile(state, profiles)
                        },
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=profile_choices,
                            custom_value=True,
                            mode=SelectSelectorMode.DROPDOWN,
                            translation_key="frigate_profile",
                        )
                    )
                    for option, state in FRIGATE_PROFILE_OPTIONS.items()
                },
                # last, as only an override for more than one Frigate server
                vol.Optional(
                    CONF_FRIGATE_PROFILE_ENTITY,
                    description={"suggested_value": options.get(CONF_FRIGATE_PROFILE_ENTITY)},
                ): EntitySelector(EntitySelectorConfig(domain="select", integration="frigate")),
            }),
            {"collapsed": True},
        ),
    }


def _matchable_profiles(hass: HomeAssistant, options: Mapping[str, Any]) -> list[str]:
    """Profiles of the select that will be used, the Frigate integration's own unless overridden"""
    return frigate_profiles(hass, options.get(CONF_FRIGATE_PROFILE_ENTITY) or next(iter(frigate_profile_selects(hass)), None))


def _settle_frigate_profiles(hass: HomeAssistant, data: dict[str, Any]) -> None:
    """Keep only the profiles that differ from those matched by name, so the rest go on being matched as Frigate changes

    A state cleared, where there's a match, is kept as no profile so it isn't matched again
    """
    if not _frigate_available(hass, data):
        return
    profiles: list[str] = _matchable_profiles(hass, data)
    for option, state in FRIGATE_PROFILE_OPTIONS.items():
        chosen: str = data.pop(option, None) or FRIGATE_NO_PROFILE
        if chosen != (match_profile(state, profiles) or FRIGATE_NO_PROFILE):
            data[option] = chosen


def _flatten_sections(user_input: dict[str, Any]) -> dict[str, Any]:
    """Flatten the section sub-dicts from a form submission into a single-level options dict."""
    data = {k: v for k, v in user_input.items() if not isinstance(v, dict)}
    for v in user_input.values():
        if isinstance(v, dict):
            data.update(v)
    return data


def _pattern_errors(data: Mapping[str, Any]) -> dict[str, str]:
    """Errors for the form if any calendar match rule has a pattern that isn't a regular expression"""
    for rule in data.get(CONF_CALENDAR_MATCH_RULES, []):
        for pattern in rule.get(CONF_RULE_PATTERNS, []):
            try:
                re.compile(pattern)
            except re.error:
                return {"base": "invalid_pattern"}
    return {}


async def _protect_panel_code(hass: HomeAssistant, data: dict[str, Any], stored: str | None = None) -> None:
    """Swap a code typed in for its encrypted form, keeping the one already stored if none was typed"""
    code: str | None = data.pop(CONF_PANEL_CODE, None)
    clear: bool = data.pop(CONF_PANEL_CODE_CLEAR, False)
    if code:
        data[CONF_PANEL_CODE] = await async_encrypt(hass, code)
    elif stored and not clear:
        data[CONF_PANEL_CODE] = stored


class AutoArmConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Auto Arm."""

    VERSION = 1
    # 2 split no_event_mode into armed and disarmed end modes
    MINOR_VERSION = 2

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Offer a quick recommended-recipe setup, or the full set of options up front."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        return self.async_show_menu(
            step_id="user",
            menu_options=["quick_setup", "advanced_setup"],
            description_placeholders={"recipe_url": RECIPE_URL},
        )

    async def async_step_quick_setup(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle set up, of the alarm panel and the entities used by the recommended recipe."""
        if user_input is not None:
            options = {
                **DEFAULT_OPTIONS,
                CONF_NOTIFY_ACTION: _default_notify_action(self.hass),
                CONF_BEDTIME_ENTITIES: user_input.get(CONF_BEDTIME_ENTITIES, []),
                CONF_CALENDAR_ENTITIES: user_input.get(CONF_CALENDAR_ENTITIES, []),
                CONF_PERSON_ENTITIES: user_input.get(CONF_PERSON_ENTITIES, []),
                CONF_FRIGATE_ENABLED: user_input.get(CONF_FRIGATE_ENABLED, False),
            }

            return self.async_create_entry(
                title="Auto Arm",
                data={CONF_ALARM_PANEL: user_input[CONF_ALARM_PANEL]},
                options=options,
            )

        # everyone known to Home Assistant, to be cut down rather than built up
        default_options = {CONF_PERSON_ENTITIES: sorted(self.hass.states.async_entity_ids("person"))}
        return self.async_show_form(
            step_id="quick_setup",
            data_schema=vol.Schema(
                _top_level_fields(default_options, frigate_available=_frigate_available(self.hass, default_options))
            ),
            description_placeholders=SETUP_HELP_PLACEHOLDERS,
        )

    async def async_step_advanced_setup(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle set up with the full set of options shown up front, instead of the quick recipe's defaults."""
        default_options: dict[str, Any] = {
            **DEFAULT_OPTIONS,
            CONF_NOTIFY_ACTION: _default_notify_action(self.hass),
            CONF_PERSON_ENTITIES: sorted(self.hass.states.async_entity_ids("person")),
        }
        errors: dict[str, str] = {}
        if user_input is not None:
            data = _flatten_sections(user_input)
            _settle_frigate_profiles(self.hass, data)
            errors = _pattern_errors(data)
            if not errors:
                await _protect_panel_code(self.hass, data)
                alarm_panel = data.pop(CONF_ALARM_PANEL)
                return self.async_create_entry(
                    title="Auto Arm",
                    data={CONF_ALARM_PANEL: alarm_panel},
                    options=data,
                )
            # shown again as it was filled in, to put right
            default_options = data

        return self.async_show_form(
            step_id="advanced_setup",
            data_schema=vol.Schema({
                **_top_level_fields(
                    default_options,
                    alarm_panel_default=default_options.get(CONF_ALARM_PANEL),
                    frigate_available=_frigate_available(self.hass, default_options),
                ),
                **await _section_fields(self.hass, default_options),
            }),
            description_placeholders=SETUP_HELP_PLACEHOLDERS,
            errors=errors,
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Handle import from YAML configuration."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        alarm_panel_config = import_data.get(CONF_ALARM_PANEL, {})
        alarm_panel = alarm_panel_config.get(CONF_ENTITY_ID, "") if isinstance(alarm_panel_config, dict) else ""

        occupancy_config = import_data.get(CONF_OCCUPANCY, {})
        person_entities = occupancy_config.get(CONF_ENTITY_ID, [])
        occupancy_defaults = occupancy_config.get(CONF_OCCUPANCY_DEFAULT, {})

        calendar_config = import_data.get(CONF_CALENDAR_CONTROL, {})
        calendar_entities = [cal[CONF_ENTITY_ID] for cal in calendar_config.get(CONF_CALENDARS, []) if CONF_ENTITY_ID in cal]
        no_event_mode = calendar_config.get(CONF_CALENDAR_NO_EVENT, NO_CAL_EVENT_MODE_AUTO)

        notify_config = import_data.get(CONF_NOTIFY, {})
        notify_action = notify_config.get(NOTIFY_COMMON, {}).get(CONF_SERVICE, DEFAULT_NOTIFY_ACTION)
        notify_enabled: bool = notify_config.get(NOTIFY_COMMON, {}).get(CONF_ENABLED, True)

        diurnal_config = import_data.get(CONF_DIURNAL, {})
        sunrise_config = diurnal_config.get(CONF_SUNRISE, {}) if diurnal_config else {}
        sunset_config = diurnal_config.get(CONF_SUNSET, {}) if diurnal_config else {}

        options = {
            CONF_CALENDAR_ENTITIES: calendar_entities,
            CONF_PERSON_ENTITIES: person_entities,
            CONF_OCCUPANCY_DEFAULT_DAY: occupancy_defaults.get(CONF_DAY, "armed_home"),
            CONF_OCCUPANCY_DEFAULT_NIGHT: occupancy_defaults.get(CONF_NIGHT),
            CONF_CALENDAR_ARMED_END_MODE: calendar_config.get(CONF_CALENDAR_ARMED_END, no_event_mode),
            CONF_CALENDAR_DISARMED_END_MODE: calendar_config.get(CONF_CALENDAR_DISARMED_END, no_event_mode),
            CONF_NOTIFY_ENABLED: notify_enabled,
            CONF_NOTIFY_ACTION: notify_action,
            CONF_NOTIFY_TARGETS: [],
            CONF_NOTIFY_DATA: {},
            CONF_SUNRISE_TRIGGER: TRIGGER_AUTO,
            CONF_SUNSET_TRIGGER: TRIGGER_AUTO,
            CONF_OCCUPIED_TRIGGER: True,
            CONF_UNOCCUPIED_TRIGGER: True,
            CONF_SUNRISE_EARLIEST: _time_to_str(sunrise_config.get(CONF_EARLIEST)),
            CONF_SUNRISE_LATEST: _time_to_str(sunrise_config.get(CONF_LATEST)),
            CONF_SUNSET_EARLIEST: _time_to_str(sunset_config.get(CONF_EARLIEST)),
            CONF_SUNSET_LATEST: _time_to_str(sunset_config.get(CONF_LATEST)),
            CONF_USE_ALARM_SERVICE: True,
            CONF_SENTENCE_ARM: True,
            CONF_SENTENCE_DISARM: False,
        }

        return self.async_create_entry(
            title="Auto Arm",
            data={CONF_ALARM_PANEL: alarm_panel},
            options=options,
        )

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> AutoArmOptionsFlow:
        """Get the options flow for this handler."""
        return AutoArmOptionsFlow()


class AutoArmOptionsFlow(OptionsFlow):
    """Handle options flow for Auto Arm."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Manage the options."""
        options: Mapping[str, Any] = self.config_entry.options
        alarm_panel: str = self.config_entry.data.get(CONF_ALARM_PANEL, "")
        errors: dict[str, str] = {}
        if user_input is not None:
            data = _flatten_sections(user_input)
            _settle_frigate_profiles(self.hass, data)
            errors = _pattern_errors(data)
            if not errors:
                await _protect_panel_code(self.hass, data, self.config_entry.options.get(CONF_PANEL_CODE))

                # The alarm panel entity lives in config_entry.data, not options.
                alarm_panel = data.pop(CONF_ALARM_PANEL)
                if alarm_panel != self.config_entry.data.get(CONF_ALARM_PANEL):
                    # along with the options, as one update, so there's a single reload that has both
                    self.hass.config_entries.async_update_entry(
                        self.config_entry,
                        data={**self.config_entry.data, CONF_ALARM_PANEL: alarm_panel},
                        options=data,
                    )

                return self.async_create_entry(title="", data=data)
            # shown again as it was filled in, to put right, other than a panel code which stays as stored
            alarm_panel = data.pop(CONF_ALARM_PANEL)
            options = {**data, CONF_PANEL_CODE: self.config_entry.options.get(CONF_PANEL_CODE)}

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                **_top_level_fields(
                    options, alarm_panel_default=alarm_panel, frigate_available=_frigate_available(self.hass, options)
                ),
                **await _section_fields(self.hass, options),
            }),
            description_placeholders=OPTIONS_HELP_PLACEHOLDERS,
            errors=errors,
        )


def _seconds_selector(minimum: int = 0) -> Selector[NumberSelectorConfig]:
    return NumberSelector(NumberSelectorConfig(min=minimum, max=3600, mode=NumberSelectorMode.BOX, unit_of_measurement="s"))


def _alarm_state_selector() -> Selector[SelectSelectorConfig]:
    return SelectSelector(SelectSelectorConfig(options=PUBLIC_ALARM_STATES, mode=SelectSelectorMode.DROPDOWN))


def _time_of_day_selector() -> Selector[EntitySelectorConfig]:
    return EntitySelector(EntitySelectorConfig(integration="tod", multiple=True))


def _sun_trigger_selector() -> Selector[SelectSelectorConfig]:
    return SelectSelector(
        SelectSelectorConfig(options=SUN_TRIGGER_OPTIONS, mode=SelectSelectorMode.DROPDOWN, translation_key="sun_trigger")
    )


def _calendar_end_mode_selector() -> Selector[SelectSelectorConfig]:
    return SelectSelector(
        SelectSelectorConfig(
            options=CALENDAR_END_MODE_OPTIONS, mode=SelectSelectorMode.DROPDOWN, translation_key="calendar_end_mode"
        )
    )
