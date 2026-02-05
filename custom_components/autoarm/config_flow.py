"""Config flow for Auto Arm integration."""

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_ENTITY_ID
from homeassistant.helpers.selector import (
    EntitySelector,
    EntitySelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    ALARM_STATES,
    CONF_ALARM_PANEL,
    CONF_CALENDAR_CONTROL,
    CONF_CALENDAR_NO_EVENT,
    CONF_CALENDARS,
    CONF_DAY,
    CONF_NIGHT,
    CONF_OCCUPANCY,
    CONF_OCCUPANCY_DEFAULT,
    DOMAIN,
    NO_CAL_EVENT_OPTIONS,
)

CONF_CALENDAR_ENTITIES = "calendar_entities"
CONF_PERSON_ENTITIES = "person_entities"
CONF_OCCUPANCY_DEFAULT_DAY = "occupancy_default_day"
CONF_OCCUPANCY_DEFAULT_NIGHT = "occupancy_default_night"
CONF_NO_EVENT_MODE = "no_event_mode"

DEFAULT_OPTIONS: dict[str, Any] = {
    CONF_CALENDAR_ENTITIES: [],
    CONF_PERSON_ENTITIES: [],
    CONF_OCCUPANCY_DEFAULT_DAY: "armed_home",
    CONF_OCCUPANCY_DEFAULT_NIGHT: None,
    CONF_NO_EVENT_MODE: "auto",
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

        options = {
            CONF_CALENDAR_ENTITIES: calendar_entities,
            CONF_PERSON_ENTITIES: person_entities,
            CONF_OCCUPANCY_DEFAULT_DAY: occupancy_defaults.get(CONF_DAY, DEFAULT_OPTIONS[CONF_OCCUPANCY_DEFAULT_DAY]),
            CONF_OCCUPANCY_DEFAULT_NIGHT: occupancy_defaults.get(CONF_NIGHT),
            CONF_NO_EVENT_MODE: no_event_mode,
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
            return self.async_create_entry(title="", data=user_input)

        options = self.config_entry.options

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
                    description={"suggested_value": options.get(CONF_OCCUPANCY_DEFAULT_NIGHT)},
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
            }),
        )
