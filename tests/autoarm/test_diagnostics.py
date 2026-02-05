from typing import Any

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.autoarm.config_flow import (
    CONF_CALENDAR_ENTITIES,
    CONF_NO_EVENT_MODE,
    CONF_OCCUPANCY_DEFAULT_DAY,
    CONF_OCCUPANCY_DEFAULT_NIGHT,
    CONF_PERSON_ENTITIES,
)
from custom_components.autoarm.const import CONF_ALARM_PANEL, DOMAIN, YAML_DATA_KEY
from custom_components.autoarm.diagnostics import async_get_config_entry_diagnostics


async def _setup_entry(hass: HomeAssistant) -> MockConfigEntry:
    hass.data[YAML_DATA_KEY] = {}
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Auto Arm",
        data={CONF_ALARM_PANEL: "alarm_panel.testing"},
        options={
            CONF_CALENDAR_ENTITIES: [],
            CONF_PERSON_ENTITIES: ["person.house_owner"],
            CONF_OCCUPANCY_DEFAULT_DAY: "armed_home",
            CONF_OCCUPANCY_DEFAULT_NIGHT: None,
            CONF_NO_EVENT_MODE: "auto",
        },
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_diagnostics(hass: HomeAssistant, mock_notify: Any) -> None:  # noqa: ARG001
    entry = await _setup_entry(hass)

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["entry_data"] == {CONF_ALARM_PANEL: "alarm_panel.testing"}
    assert result["entry_options"][CONF_PERSON_ENTITIES] == ["person.house_owner"]
    assert result["yaml_keys"] == []
    assert "armer" in result
    assert result["armer"]["alarm_panel"] == "alarm_panel.testing"
    assert result["armer"]["calendar_count"] == 0
    assert result["armer"]["occupants"] == ["person.house_owner"]
    assert result["armer"]["failures"] == 0
    assert result["armer"]["initialization_errors"] == {}


async def test_diagnostics_without_armer(hass: HomeAssistant) -> None:
    """Test diagnostics when armer is not yet set up."""
    hass.data[YAML_DATA_KEY] = {"some_key": "some_value"}
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Auto Arm",
        data={CONF_ALARM_PANEL: "alarm_panel.testing"},
        options={},
    )

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert result["entry_data"] == {CONF_ALARM_PANEL: "alarm_panel.testing"}
    assert result["yaml_keys"] == ["some_key"]
    assert "armer" not in result
