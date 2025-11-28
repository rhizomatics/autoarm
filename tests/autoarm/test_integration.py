import asyncio
import json

from homeassistant.components.alarm_control_panel.const import ATTR_CHANGED_BY, AlarmControlPanelState
from homeassistant.const import CONF_CONDITIONS, CONF_DELAY_TIME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from custom_components.autoarm.calendar import CONF_ENTITY_ID
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
)

CONFIG = {
    DOMAIN: {
        CONF_ALARM_PANEL: {CONF_ENTITY_ID: "alarm_panel.testing"},
        CONF_DIURNAL: {CONF_SUNRISE: {CONF_EARLIEST: "06:30:00"}},
        CONF_BUTTONS: {
            ATTR_RESET: {CONF_ENTITY_ID: "binary_sensor.button_left"},
            AlarmControlPanelState.ARMED_AWAY: {CONF_DELAY_TIME: 2, CONF_ENTITY_ID: "binary_sensor.button_right"},
            AlarmControlPanelState.DISARMED: {CONF_ENTITY_ID: "binary_sensor.button_middle"},
        },
        CONF_OCCUPANCY: {CONF_ENTITY_ID: ["person.house_owner", "person.tenant"]},
        CONF_NOTIFY: {
            "common": {
                "service": "notify.send_message",
                "data": {"message": "alarm changed"},
            },
            "quiet": {"data": {"priority": "low"}},
            "normal": {"data": {"priority": "medium"}},
        },
    }
}


async def test_configure(hass: HomeAssistant) -> None:
    assert await async_setup_component(hass, "autoarm", CONFIG)

    await hass.async_block_till_done()

    hass.states.async_set("alarm_panel.testing", "disarmed")
    await hass.async_block_till_done()


async def test_exposed_entities(hass: HomeAssistant) -> None:
    assert await async_setup_component(hass, "autoarm", CONFIG)

    await hass.async_block_till_done()
    configuration = hass.states.get("autoarm.configured")
    assert configuration is not None
    assert configuration.state == "valid"
    # check for unserializable classes that will upset HomeAssistant
    assert json.dumps(configuration.attributes)
    assert "error" not in configuration.attributes
    assert configuration.attributes["alarm_panel"] == "alarm_panel.testing"
    assert hass.states.get("autoarm.last_calendar_event") is not None


async def test_reset_service(hass: HomeAssistant) -> None:
    assert await async_setup_component(hass, "autoarm", CONFIG)

    await hass.async_block_till_done()
    response = await hass.services.async_call("autoarm", "reset_state", None, blocking=True, return_response=True)
    assert response is not None
    assert response["change"] == "armed_away"
    assert hass.states.get("autoarm.last_intervention").state == "action"  # type: ignore


async def test_broken_condition_raises_issue(hass: HomeAssistant, issue_registry: ir.IssueRegistry) -> None:
    config = {
        DOMAIN: {
            CONF_ALARM_PANEL: {CONF_ENTITY_ID: "alarm_panel.testing"},
            CONF_TRANSITIONS: {"armed_home": {CONF_CONDITIONS: "{{ autoarm.morning_coffee and not autoarm.occupied }}"}},
        }
    }

    assert await async_setup_component(hass, "autoarm", config)
    await hass.async_block_till_done()

    assert ("autoarm", "transition_condition_armed_home") in issue_registry.issues
    issue = issue_registry.issues["autoarm", "transition_condition_armed_home"]
    assert issue.translation_key == "transition_condition"
    assert issue.translation_placeholders == {
        "state": "armed_home",
        "error": "UndefinedError: 'dict object' has no attribute 'morning_coffee'",
    }

    assert issue.severity == ir.IssueSeverity.ERROR


async def test_on_panel_change_ignores_autoarm_generated_event(hass: HomeAssistant) -> None:

    assert await async_setup_component(hass, "autoarm", CONFIG)
    await hass.async_block_till_done()

    hass.states.async_set("binary_sensor.button_middle", "on")
    await hass.async_block_till_done()
    assert hass.states.get("autoarm.last_intervention").state == "button"  # type: ignore
    panel_entity = hass.states.get("alarm_panel.testing")
    assert panel_entity is not None
    assert panel_entity.attributes[ATTR_CHANGED_BY] == "autoarm.button"

    # when alarm panel is changed directly, this is recorded as an intervention
    hass.states.async_set("alarm_panel.testing", "armed_vacation")
    await hass.async_block_till_done()
    assert hass.states.get("autoarm.last_intervention").state == "alarm_panel"  # type: ignore


async def test_arm_on_away(hass: HomeAssistant) -> None:
    hass.states.async_set("person.house_owner", "not_home", {"friendly_name": "Jack"})
    hass.states.async_set("person.tenant", "home", {"friendly_name": "Jill"})

    hass.states.async_set("alarm_panel.testing", "disarmed")
    assert await async_setup_component(hass, "autoarm", CONFIG)
    await hass.async_block_till_done()

    hass.states.async_set("person.house_owner", "not_home")
    hass.states.async_set("person.tenant", "not_home")
    await hass.async_block_till_done()
    assert hass.states.get("alarm_panel.testing").state == "armed_away"  # type: ignore


async def test_disarm_on_button(hass: HomeAssistant) -> None:
    hass.states.async_set("alarm_panel.testing", "armed_away")
    assert await async_setup_component(hass, "autoarm", CONFIG)
    await hass.async_block_till_done()

    hass.states.async_set("binary_sensor.button_middle", "on")
    await hass.async_block_till_done()
    assert hass.states.get("alarm_panel.testing").state == "disarmed"  # type: ignore


async def test_disarm_on_mobile_action(hass: HomeAssistant) -> None:
    hass.states.async_set("alarm_panel.testing", "armed_away")
    assert await async_setup_component(hass, "autoarm", CONFIG)
    await hass.async_block_till_done()

    hass.bus.async_fire("mobile_app_notification_action", {"action": "ALARM_PANEL_DISARM"})
    await hass.async_block_till_done()
    assert hass.states.get("alarm_panel.testing").state == "disarmed"  # type: ignore


async def test_delayed_arm_on_button(hass: HomeAssistant) -> None:

    assert await async_setup_component(hass, "autoarm", CONFIG)
    await hass.async_block_till_done()
    hass.states.async_set("alarm_panel.testing", "disarmed")

    hass.states.async_set("binary_sensor.button_right", "on")
    assert hass.states.get("alarm_panel.testing").state == "disarmed"  # type: ignore
    await hass.async_block_till_done()
    await asyncio.sleep(3)
    assert hass.states.get("alarm_panel.testing").state == "armed_away"  # type: ignore
