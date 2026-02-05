import asyncio
import datetime as dt
import json
from typing import Any

from homeassistant.components.alarm_control_panel.const import ATTR_CHANGED_BY, AlarmControlPanelState
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_CONDITIONS, CONF_DELAY_TIME, CONF_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.autoarm.config_flow import (
    CONF_CALENDAR_ENTITIES,
    CONF_NO_EVENT_MODE,
    CONF_OCCUPANCY_DEFAULT_DAY,
    CONF_OCCUPANCY_DEFAULT_NIGHT,
    CONF_PERSON_ENTITIES,
)
from custom_components.autoarm.const import (
    ATTR_RESET,
    CONF_ALARM_PANEL,
    CONF_BUTTONS,
    CONF_DIURNAL,
    CONF_EARLIEST,
    CONF_NOTIFY,
    CONF_OCCUPANCY,
    CONF_SUNRISE,
    CONF_TRANSITIONS,
    DOMAIN,
    YAML_DATA_KEY,
)

YAML_CONFIG: dict[str, Any] = {
    CONF_DIURNAL: {CONF_SUNRISE: {CONF_EARLIEST: "06:30:00"}},
    CONF_BUTTONS: {
        ATTR_RESET: {CONF_ENTITY_ID: ["binary_sensor.button_left"]},
        AlarmControlPanelState.ARMED_AWAY: {
            CONF_DELAY_TIME: dt.timedelta(seconds=2),
            CONF_ENTITY_ID: ["binary_sensor.button_right"],
        },
        AlarmControlPanelState.DISARMED: {CONF_ENTITY_ID: ["binary_sensor.button_middle"]},
    },
    CONF_NOTIFY: {
        "common": {
            "service": "notify.send_message",
            "data": {"message": "alarm changed"},
        },
        "quiet": {"data": {"priority": "low"}},
        "normal": {"data": {"priority": "medium"}},
    },
}

ENTRY_DATA: dict[str, Any] = {CONF_ALARM_PANEL: "alarm_panel.testing"}
ENTRY_OPTIONS: dict[str, Any] = {
    CONF_CALENDAR_ENTITIES: [],
    CONF_PERSON_ENTITIES: ["person.house_owner", "person.tenant"],
    CONF_OCCUPANCY_DEFAULT_DAY: "armed_home",
    CONF_OCCUPANCY_DEFAULT_NIGHT: None,
    CONF_NO_EVENT_MODE: "auto",
}


async def _setup_entry(hass: HomeAssistant, yaml_config: dict[str, Any] | None = None) -> MockConfigEntry:
    """Set up a config entry with optional YAML config."""
    hass.data[YAML_DATA_KEY] = yaml_config or YAML_CONFIG
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Auto Arm",
        data=ENTRY_DATA,
        options=ENTRY_OPTIONS,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_configure(hass: HomeAssistant, mock_notify: Any) -> None:  # noqa: ARG001
    await _setup_entry(hass)

    hass.states.async_set("alarm_panel.testing", "disarmed")
    await hass.async_block_till_done()


async def test_exposed_entities(hass: HomeAssistant, mock_notify: Any) -> None:  # noqa: ARG001
    await _setup_entry(hass)

    configuration = hass.states.get("binary_sensor.autoarm_initialized")
    assert configuration is not None
    assert configuration.state == "valid"

    assert hass.states.get("sensor.autoarm_last_calendar_event") is not None


async def test_actions(hass: HomeAssistant, mock_notify: Any) -> None:  # noqa: ARG001
    await _setup_entry(hass)

    config: Any = await hass.services.async_call("autoarm", "enquire_configuration", None, blocking=True, return_response=True)
    assert config is not None
    assert "error" not in config
    assert config["alarm_panel"] == "alarm_panel.testing"
    assert json.dumps(config)


async def test_reset_service(hass: HomeAssistant, mock_notify: Any) -> None:  # noqa: ARG001
    await _setup_entry(hass)

    response = await hass.services.async_call("autoarm", "reset_state", None, blocking=True, return_response=True)
    assert response is not None
    assert response["change"] == "armed_away"
    assert hass.states.get("sensor.autoarm_last_intervention").state == "action"  # type: ignore


async def test_broken_condition_raises_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_notify: Any,  # noqa: ARG001
) -> None:
    yaml_config = {
        CONF_TRANSITIONS: {
            "armed_home": {CONF_CONDITIONS: cv.CONDITIONS_SCHEMA("{{ autoarm.morning_coffee and not autoarm.occupied }}")}
        },
    }
    await _setup_entry(hass, yaml_config=yaml_config)

    assert ("autoarm", "transition_condition_armed_home") in issue_registry.issues
    issue = issue_registry.issues["autoarm", "transition_condition_armed_home"]
    assert issue.translation_key == "transition_condition"
    assert issue.translation_placeholders == {
        "state": "armed_home",
        "error": "UndefinedError: 'dict object' has no attribute 'morning_coffee'",
    }
    assert issue.severity == ir.IssueSeverity.ERROR


async def test_on_panel_change_ignores_autoarm_generated_event(hass: HomeAssistant, mock_notify: Any) -> None:  # noqa: ARG001
    await _setup_entry(hass)

    hass.states.async_set("binary_sensor.button_middle", "on")
    await hass.async_block_till_done()
    assert hass.states.get("sensor.autoarm_last_intervention").state == "button"  # type: ignore
    panel_entity = hass.states.get("alarm_panel.testing")
    assert panel_entity is not None
    assert panel_entity.attributes[ATTR_CHANGED_BY] == "autoarm.button"

    hass.states.async_set("alarm_panel.testing", "armed_vacation")
    await hass.async_block_till_done()
    assert hass.states.get("sensor.autoarm_last_intervention").state == "alarm_panel"  # type: ignore


async def test_arm_on_away(hass: HomeAssistant, mock_notify: Any) -> None:  # noqa: ARG001
    hass.states.async_set("person.house_owner", "not_home", {"friendly_name": "Jack"})
    hass.states.async_set("person.tenant", "home", {"friendly_name": "Jill"})
    hass.states.async_set("alarm_panel.testing", "disarmed")

    await _setup_entry(hass)

    hass.states.async_set("person.house_owner", "not_home")
    hass.states.async_set("person.tenant", "not_home")
    await hass.async_block_till_done()
    assert hass.states.get("alarm_panel.testing").state == "armed_away"  # type: ignore


async def test_disarm_on_button(hass: HomeAssistant, mock_notify: Any) -> None:  # noqa: ARG001
    hass.states.async_set("alarm_panel.testing", "armed_away")
    await _setup_entry(hass)

    hass.states.async_set("binary_sensor.button_middle", "on")
    await hass.async_block_till_done()
    assert hass.states.get("alarm_panel.testing").state == "disarmed"  # type: ignore


async def test_disarm_on_mobile_action(hass: HomeAssistant, mock_notify: Any) -> None:  # noqa: ARG001
    hass.states.async_set("alarm_panel.testing", "armed_away")
    await _setup_entry(hass)

    hass.bus.async_fire("mobile_app_notification_action", {"action": "ALARM_PANEL_DISARM"})
    await hass.async_block_till_done()
    assert hass.states.get("alarm_panel.testing").state == "disarmed"  # type: ignore


async def test_delayed_arm_on_button(hass: HomeAssistant, mock_notify: Any) -> None:  # noqa: ARG001
    await _setup_entry(hass)
    hass.states.async_set("alarm_panel.testing", "disarmed")

    hass.states.async_set("binary_sensor.button_right", "on")
    assert hass.states.get("alarm_panel.testing").state == "disarmed"  # type: ignore
    await hass.async_block_till_done()
    await asyncio.sleep(3)
    assert hass.states.get("alarm_panel.testing").state == "armed_away"  # type: ignore


async def test_yaml_import_migration(hass: HomeAssistant, mock_notify: Any) -> None:  # noqa: ARG001
    """Test that YAML config with alarm_panel triggers import flow and creates ConfigEntry."""
    full_yaml_config = {
        DOMAIN: {
            CONF_ALARM_PANEL: {CONF_ENTITY_ID: "alarm_panel.testing"},
            CONF_OCCUPANCY: {CONF_ENTITY_ID: ["person.house_owner", "person.tenant"]},
            CONF_NOTIFY: {
                "common": {"service": "notify.send_message"},
            },
        }
    }
    assert await async_setup_component(hass, DOMAIN, full_yaml_config)
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].data[CONF_ALARM_PANEL] == "alarm_panel.testing"
    assert entries[0].options[CONF_PERSON_ENTITIES] == ["person.house_owner", "person.tenant"]


async def test_setup_entry_raises_not_ready_on_failure(
    hass: HomeAssistant, mock_notify: Any  # noqa: ARG001
) -> None:
    """Test that async_setup_entry raises ConfigEntryNotReady when initialization fails."""
    from unittest.mock import patch

    hass.data[YAML_DATA_KEY] = YAML_CONFIG
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Auto Arm",
        data=ENTRY_DATA,
        options=ENTRY_OPTIONS,
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.autoarm.autoarming._build_armer_from_entry",
        side_effect=Exception("boom"),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY
