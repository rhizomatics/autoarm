import asyncio

from homeassistant.const import CONF_ICON
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.autoarm.const import (
    CONF_ACTION,
    CONF_ACTIONS,
    CONF_ALARM_PANEL,
    CONF_ARM_AWAY_DELAY,
    CONF_AUTO_ARM,
    CONF_BUTTON_ENTITY_AWAY,
    CONF_BUTTON_ENTITY_DISARM,
    CONF_BUTTON_ENTITY_RESET,
    CONF_NOTIFY,
    CONF_OCCUPANTS,
    CONF_SUNRISE_CUTOFF,
    CONF_TITLE,
    DOMAIN,
)

CONFIG = {
    DOMAIN: {
        CONF_ALARM_PANEL: "alarm_panel.testing",
        CONF_AUTO_ARM: True,
        CONF_ARM_AWAY_DELAY: 1,
        CONF_SUNRISE_CUTOFF: "06:30:00",
        CONF_BUTTON_ENTITY_RESET: "binary_sensor.button_left",
        CONF_BUTTON_ENTITY_AWAY: "binary_sensor.button_right",
        CONF_BUTTON_ENTITY_DISARM: "binary_sensor.button_middle",
        CONF_OCCUPANTS: ["person.house_owner", "person.tenant"],
        CONF_NOTIFY: {
            "common": {
                "service": "notify.supernotifier",
                "data": {"actions": {"action_groups": "alarm_panel", "action_category": "alarm_panel"}},
            },
            "quiet": {"data": {"priority": "low"}},
            "normal": {"data": {"priority": "medium"}},
        },
        CONF_ACTIONS: [
            {CONF_ACTION: "ALARM_PANEL_DISARM", CONF_TITLE: "Disarm Alarm Panel", CONF_ICON: "sfsymbols:bell.slash"},
            {CONF_ACTION: "ALARM_PANEL_RESET", CONF_TITLE: "Reset Alarm Panel", CONF_ICON: "sfsymbols:bell"},
            {CONF_ACTION: "ALARM_PANEL_AWAY", CONF_TITLE: "Arm Alarm Panel for Going Awa", CONF_ICON: "sfsymbols:airplane"},
        ],
    }
}


async def test_configure(hass: HomeAssistant) -> None:
    assert await async_setup_component(hass, "autoarm", CONFIG)

    await hass.async_block_till_done()

    hass.states.async_set("alarm_panel.testing", "disarmed")
    await hass.async_block_till_done()


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
    hass.states.async_set("alarm_panel.testing", "disarmed")
    assert await async_setup_component(hass, "autoarm", CONFIG)
    await hass.async_block_till_done()

    hass.states.async_set("binary_sensor.button_right", "on")
    await hass.async_block_till_done()
    await asyncio.sleep(2)
    assert hass.states.get("alarm_panel.testing").state == "armed_away"  # type: ignore
