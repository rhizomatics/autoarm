"""Buttons set up in the options, including those brought over from YAML"""

import datetime as dt
from typing import Any

from homeassistant.components.alarm_control_panel.const import AlarmControlPanelState
from homeassistant.const import CONF_DELAY_TIME, CONF_ENTITY_ID
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.autoarm.config_flow import CONF_PERSON_ENTITIES, CONF_USE_ALARM_SERVICE
from custom_components.autoarm.const import CONF_ALARM_PANEL, CONF_BUTTONS, DOMAIN, YAML_DATA_KEY, ChangeSource

PANEL = "alarm_panel.testing"
BUTTON = "binary_sensor.door_button"


async def _setup_entry(
    hass: HomeAssistant, options: dict[str, Any], yaml_config: dict[str, Any] | None = None
) -> MockConfigEntry:
    hass.data[YAML_DATA_KEY] = yaml_config or {}
    hass.states.async_set("person.tenant", "home")
    hass.states.async_set("sun.sun", "above_horizon")
    hass.states.async_set(BUTTON, "off")
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Auto Arm",
        data={CONF_ALARM_PANEL: PANEL},
        options={CONF_PERSON_ENTITIES: ["person.tenant"], CONF_USE_ALARM_SERVICE: True, **options},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def panel_state(hass: HomeAssistant) -> str | None:
    state = hass.states.get(PANEL)
    return state.state if state else None


async def test_button_from_options(hass: HomeAssistant, mock_notify: Any) -> None:
    entry = await _setup_entry(hass, {"button_armed_vacation": [BUTTON], "button_armed_vacation_delay": 0})
    assert panel_state(hass) == AlarmControlPanelState.DISARMED

    hass.states.async_set(BUTTON, "on")
    await hass.async_block_till_done()

    assert panel_state(hass) == AlarmControlPanelState.ARMED_VACATION
    assert entry.runtime_data.last_change.source == ChangeSource.BUTTON


async def test_button_delay_from_options(hass: HomeAssistant, mock_notify: Any) -> None:
    entry = await _setup_entry(hass, {"button_armed_away": [BUTTON], "button_armed_away_delay": 120, "button_reset": []})

    assert entry.runtime_data.buttons == {"armed_away": {CONF_ENTITY_ID: [BUTTON], CONF_DELAY_TIME: dt.timedelta(seconds=120)}}

    hass.states.async_set(BUTTON, "on")
    await hass.async_block_till_done()
    assert panel_state(hass) == AlarmControlPanelState.DISARMED


async def test_yaml_buttons_migrated_to_options(hass: HomeAssistant, mock_notify: Any) -> None:
    yaml_config = {
        CONF_BUTTONS: {
            "armed_away": {CONF_ENTITY_ID: [BUTTON], CONF_DELAY_TIME: dt.timedelta(minutes=3)},
            "reset": {CONF_ENTITY_ID: ["binary_sensor.reset_button"]},
        }
    }

    entry = await _setup_entry(hass, {}, yaml_config)

    assert entry.options["button_armed_away"] == [BUTTON]
    assert entry.options["button_armed_away_delay"] == 180
    assert entry.options["button_reset"] == ["binary_sensor.reset_button"]
    assert entry.options["button_reset_delay"] == 0
    assert entry.runtime_data.buttons["armed_away"][CONF_DELAY_TIME] == dt.timedelta(minutes=3)


async def test_yaml_buttons_not_migrated_over_options(hass: HomeAssistant, mock_notify: Any) -> None:
    yaml_config = {CONF_BUTTONS: {"armed_away": {CONF_ENTITY_ID: [BUTTON]}}}

    entry = await _setup_entry(hass, {"button_armed_away": []}, yaml_config)

    assert entry.options["button_armed_away"] == []
    assert entry.runtime_data.buttons == {}
