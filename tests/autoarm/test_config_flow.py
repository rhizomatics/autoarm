"""Tests for the Auto Arm config flow."""

from typing import Any

from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.autoarm.config_flow import (
    CONF_CALENDAR_ENTITIES,
    CONF_NO_EVENT_MODE,
    CONF_OCCUPANCY_DEFAULT_DAY,
    CONF_OCCUPANCY_DEFAULT_NIGHT,
    CONF_PERSON_ENTITIES,
)
from custom_components.autoarm.const import (
    CONF_ALARM_PANEL,
    CONF_CALENDAR_CONTROL,
    CONF_CALENDAR_EVENT_STATES,
    CONF_CALENDAR_NO_EVENT,
    CONF_CALENDARS,
    CONF_OCCUPANCY,
    CONF_OCCUPANCY_DEFAULT,
    DOMAIN,
    YAML_DATA_KEY,
)


async def test_user_flow_complete(hass: HomeAssistant, mock_notify: Any) -> None:  # noqa: ARG001
    """Test the full user config flow with all steps."""
    hass.data[YAML_DATA_KEY] = {}

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ALARM_PANEL: "alarm_control_panel.home"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "calendars"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_CALENDAR_ENTITIES: ["calendar.family", "calendar.work"]},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "persons"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PERSON_ENTITIES: ["person.alice", "person.bob"]},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Auto Arm"
    assert result["data"] == {CONF_ALARM_PANEL: "alarm_control_panel.home"}
    assert result["options"][CONF_CALENDAR_ENTITIES] == ["calendar.family", "calendar.work"]
    assert result["options"][CONF_PERSON_ENTITIES] == ["person.alice", "person.bob"]
    assert result["options"][CONF_OCCUPANCY_DEFAULT_DAY] == "armed_home"
    assert result["options"][CONF_NO_EVENT_MODE] == "auto"


async def test_user_flow_minimal(hass: HomeAssistant, mock_notify: Any) -> None:  # noqa: ARG001
    """Test minimal user flow - alarm panel only, no calendars or persons."""
    hass.data[YAML_DATA_KEY] = {}

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ALARM_PANEL: "alarm_control_panel.home"},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_ALARM_PANEL: "alarm_control_panel.home"}
    assert result["options"][CONF_CALENDAR_ENTITIES] == []
    assert result["options"][CONF_PERSON_ENTITIES] == []


async def test_user_flow_already_configured(hass: HomeAssistant, mock_notify: Any) -> None:  # noqa: ARG001
    """Test that a second config entry is aborted."""
    hass.data[YAML_DATA_KEY] = {}
    existing = MockConfigEntry(
        domain=DOMAIN,
        title="Auto Arm",
        data={CONF_ALARM_PANEL: "alarm_control_panel.home"},
        unique_id=DOMAIN,
    )
    existing.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ALARM_PANEL: "alarm_control_panel.other"},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import_flow(hass: HomeAssistant, mock_notify: Any) -> None:  # noqa: ARG001
    """Test YAML import creates correct config entry."""
    hass.data[YAML_DATA_KEY] = {}
    import_data: dict[str, Any] = {
        CONF_ALARM_PANEL: {CONF_ENTITY_ID: "alarm_control_panel.home"},
        CONF_OCCUPANCY: {
            CONF_ENTITY_ID: ["person.alice", "person.bob"],
            CONF_OCCUPANCY_DEFAULT: {"day": "disarmed", "night": "armed_night"},
        },
        CONF_CALENDAR_CONTROL: {
            CONF_CALENDAR_NO_EVENT: "manual",
            CONF_CALENDARS: [
                {
                    CONF_ENTITY_ID: "calendar.family",
                    CONF_CALENDAR_EVENT_STATES: {"armed_vacation": ["Holiday.*"]},
                },
            ],
        },
    }

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_IMPORT}, data=import_data)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_ALARM_PANEL: "alarm_control_panel.home"}
    assert result["options"][CONF_PERSON_ENTITIES] == ["person.alice", "person.bob"]
    assert result["options"][CONF_CALENDAR_ENTITIES] == ["calendar.family"]
    assert result["options"][CONF_OCCUPANCY_DEFAULT_DAY] == "disarmed"
    assert result["options"][CONF_OCCUPANCY_DEFAULT_NIGHT] == "armed_night"
    assert result["options"][CONF_NO_EVENT_MODE] == "manual"


async def test_import_flow_already_configured(hass: HomeAssistant, mock_notify: Any) -> None:  # noqa: ARG001
    """Test YAML import aborts when config entry already exists."""
    hass.data[YAML_DATA_KEY] = {}
    existing = MockConfigEntry(
        domain=DOMAIN,
        title="Auto Arm",
        data={CONF_ALARM_PANEL: "alarm_control_panel.home"},
        unique_id=DOMAIN,
    )
    existing.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_ALARM_PANEL: {CONF_ENTITY_ID: "alarm_control_panel.other"},
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow(hass: HomeAssistant, setup_autoarm: MockConfigEntry) -> None:
    """Test options flow updates entry options."""
    entry = setup_autoarm

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_CALENDAR_ENTITIES: ["calendar.holidays"],
            CONF_PERSON_ENTITIES: ["person.new_person"],
            CONF_OCCUPANCY_DEFAULT_DAY: "disarmed",
            CONF_OCCUPANCY_DEFAULT_NIGHT: "armed_night",
            CONF_NO_EVENT_MODE: "manual",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    assert entry.options[CONF_CALENDAR_ENTITIES] == ["calendar.holidays"]
    assert entry.options[CONF_PERSON_ENTITIES] == ["person.new_person"]
    assert entry.options[CONF_OCCUPANCY_DEFAULT_DAY] == "disarmed"
    assert entry.options[CONF_OCCUPANCY_DEFAULT_NIGHT] == "armed_night"
    assert entry.options[CONF_NO_EVENT_MODE] == "manual"
