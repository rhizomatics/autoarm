"""Config flow for Auto Arm integration."""

import datetime as dt
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_ENABLED, CONF_ENTITY_ID, CONF_SERVICE
from homeassistant.data_entry_flow import section
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TimeSelector,
)

from .const import (
    ALARM_STATES,
    CONF_ALARM_PANEL,
    CONF_CALENDAR_CONTROL,
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
    DOMAIN,
    NO_CAL_EVENT_OPTIONS,
    NOTIFY_COMMON,
)

CONF_CALENDAR_ENTITIES = "calendar_entities"
CONF_PERSON_ENTITIES = "person_entities"
CONF_OCCUPANCY_DEFAULT_DAY = "occupancy_default_day"
CONF_OCCUPANCY_DEFAULT_NIGHT = "occupancy_default_night"
CONF_NO_EVENT_MODE = "no_event_mode"
CONF_NOTIFY_ACTION = "notify_action"
CONF_NOTIFY_TARGETS = "notify_targets"
CONF_NOTIFY_ENABLED = "notify_enabled"
CONF_SUNRISE_EARLIEST = "sunrise_earliest"
CONF_SUNRISE_LATEST = "sunrise_latest"
CONF_SUNSET_EARLIEST = "sunset_earliest"
CONF_SUNSET_LATEST = "sunset_latest"


def _time_to_str(t: dt.time | None) -> str | None:
    """Convert a datetime.time to HH:MM:SS string for ConfigEntry storage."""
    return t.isoformat() if t else None


DEFAULT_NOTIFY_ACTION = "notify.send_message"

DEFAULT_OPTIONS: dict[str, Any] = {
    CONF_CALENDAR_ENTITIES: [],
    CONF_PERSON_ENTITIES: [],
    CONF_OCCUPANCY_DEFAULT_DAY: "armed_home",
    CONF_OCCUPANCY_DEFAULT_NIGHT: None,
    CONF_NO_EVENT_MODE: "auto",
    CONF_NOTIFY_ENABLED:True,
    CONF_NOTIFY_ACTION: DEFAULT_NOTIFY_ACTION,
    CONF_NOTIFY_TARGETS: [],
    CONF_SUNRISE_EARLIEST: None,
    CONF_SUNRISE_LATEST: None,
    CONF_SUNSET_EARLIEST: None,
    CONF_SUNSET_LATEST: None,
}


class AutoArmConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Auto Arm."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._alarm_panel: str = ""
        self._calendar_entities: list[str] = []

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the alarm panel selection step."""
        if user_input is not None:
            self._alarm_panel = user_input[CONF_ALARM_PANEL]
            return await self.async_step_calendars()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_ALARM_PANEL): EntitySelector(EntitySelectorConfig(domain="alarm_control_panel")),
            }),
        )

    async def async_step_calendars(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the calendar entity selection step."""
        if user_input is not None:
            self._calendar_entities = user_input.get(CONF_CALENDAR_ENTITIES, [])
            return await self.async_step_persons()

        return self.async_show_form(
            step_id="calendars",
            data_schema=vol.Schema({
                vol.Optional(CONF_CALENDAR_ENTITIES, default=[]): EntitySelector(
                    EntitySelectorConfig(domain="calendar", multiple=True)
                ),
            }),
        )

    async def async_step_persons(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the person entity selection step."""
        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()

            options = {
                CONF_CALENDAR_ENTITIES: self._calendar_entities,
                CONF_PERSON_ENTITIES: user_input.get(CONF_PERSON_ENTITIES, []),
                CONF_OCCUPANCY_DEFAULT_DAY: DEFAULT_OPTIONS[CONF_OCCUPANCY_DEFAULT_DAY],
                CONF_OCCUPANCY_DEFAULT_NIGHT: DEFAULT_OPTIONS[CONF_OCCUPANCY_DEFAULT_NIGHT],
                CONF_NO_EVENT_MODE: DEFAULT_OPTIONS[CONF_NO_EVENT_MODE],
                CONF_NOTIFY_ACTION: DEFAULT_NOTIFY_ACTION,
                CONF_NOTIFY_ENABLED: True,
                CONF_NOTIFY_TARGETS: [],
                CONF_SUNRISE_EARLIEST: None,
                CONF_SUNRISE_LATEST: None,
                CONF_SUNSET_EARLIEST: None,
                CONF_SUNSET_LATEST: None,
            }

            return self.async_create_entry(
                title="Auto Arm",
                data={CONF_ALARM_PANEL: self._alarm_panel},
                options=options,
            )

        return self.async_show_form(
            step_id="persons",
            data_schema=vol.Schema({
                vol.Optional(CONF_PERSON_ENTITIES, default=[]): EntitySelector(
                    EntitySelectorConfig(domain="person", multiple=True)
                ),
            }),
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
        no_event_mode = calendar_config.get(CONF_CALENDAR_NO_EVENT, DEFAULT_OPTIONS[CONF_NO_EVENT_MODE])

        notify_config = import_data.get(CONF_NOTIFY, {})
        notify_action = notify_config.get(NOTIFY_COMMON, {}).get(CONF_SERVICE, DEFAULT_NOTIFY_ACTION)
        notify_enabled: bool=notify_config.get(NOTIFY_COMMON, {}).get(CONF_ENABLED, True)

        diurnal_config = import_data.get(CONF_DIURNAL, {})
        sunrise_config = diurnal_config.get(CONF_SUNRISE, {}) if diurnal_config else {}
        sunset_config = diurnal_config.get(CONF_SUNSET, {}) if diurnal_config else {}

        options = {
            CONF_CALENDAR_ENTITIES: calendar_entities,
            CONF_PERSON_ENTITIES: person_entities,
            CONF_OCCUPANCY_DEFAULT_DAY: occupancy_defaults.get(CONF_DAY, DEFAULT_OPTIONS[CONF_OCCUPANCY_DEFAULT_DAY]),
            CONF_OCCUPANCY_DEFAULT_NIGHT: occupancy_defaults.get(CONF_NIGHT),
            CONF_NO_EVENT_MODE: no_event_mode,
            CONF_NOTIFY_ENABLED: notify_enabled,
            CONF_NOTIFY_ACTION: notify_action,
            CONF_NOTIFY_TARGETS: [],
            CONF_SUNRISE_EARLIEST: _time_to_str(sunrise_config.get(CONF_EARLIEST)),
            CONF_SUNRISE_LATEST: _time_to_str(sunrise_config.get(CONF_LATEST)),
            CONF_SUNSET_EARLIEST: _time_to_str(sunset_config.get(CONF_EARLIEST)),
            CONF_SUNSET_LATEST: _time_to_str(sunset_config.get(CONF_LATEST)),
        }

        return self.async_create_entry(
            title="Auto Arm",
            data={CONF_ALARM_PANEL: alarm_panel},
            options=options,
        )

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> "AutoArmOptionsFlow":  # noqa: ARG004
        """Get the options flow for this handler."""
        return AutoArmOptionsFlow()


class AutoArmOptionsFlow(OptionsFlow):
    """Handle options flow for Auto Arm."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            # Flatten section dicts into top-level options
            data = {k: v for k, v in user_input.items() if not isinstance(v, dict)}
            for v in user_input.values():
                if isinstance(v, dict):
                    data.update(v)
            return self.async_create_entry(title="", data=data)

        options = self.config_entry.options
        notify_services = sorted(f"notify.{service}" for service in self.hass.services.async_services().get("notify", {}))

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_CALENDAR_ENTITIES,
                    default=options.get(CONF_CALENDAR_ENTITIES, []),
                ): EntitySelector(EntitySelectorConfig(domain="calendar", multiple=True)),
                vol.Optional(
                    CONF_PERSON_ENTITIES,
                    default=options.get(CONF_PERSON_ENTITIES, []),
                ): EntitySelector(EntitySelectorConfig(domain="person", multiple=True)),
                vol.Optional(
                    CONF_OCCUPANCY_DEFAULT_DAY,
                    default=options.get(CONF_OCCUPANCY_DEFAULT_DAY, "armed_home"),
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=ALARM_STATES,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(
                    CONF_OCCUPANCY_DEFAULT_NIGHT,
                    description={"suggested_value": options.get(CONF_OCCUPANCY_DEFAULT_NIGHT, "armed_night")},
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=ALARM_STATES,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(
                    CONF_NO_EVENT_MODE,
                    default=options.get(CONF_NO_EVENT_MODE, "auto"),
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=NO_CAL_EVENT_OPTIONS,
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required("notify_options"): section(
                    vol.Schema({
                        vol.Required(CONF_NOTIFY_ENABLED, default=False): BooleanSelector(),
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
                        vol.Optional(
                            CONF_NOTIFY_TARGETS,
                            default=options.get(CONF_NOTIFY_TARGETS, []),
                        ): TextSelector(TextSelectorConfig(multiple=True)),
                    }),
                    {"collapsed": True},
                ),
                vol.Required("sunrise_options"): section(
                    vol.Schema({
                        vol.Optional(
                            CONF_SUNRISE_EARLIEST,
                            description={"suggested_value": options.get(CONF_SUNRISE_EARLIEST)},
                        ): TimeSelector(),
                        vol.Optional(
                            CONF_SUNRISE_LATEST,
                            description={"suggested_value": options.get(CONF_SUNRISE_LATEST)},
                        ): TimeSelector(),
                    }),
                    {"collapsed": True},
                ),
                vol.Required("sunset_options"): section(
                    vol.Schema({
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
            }),
        )
