from collections.abc import AsyncGenerator

import pytest
from homeassistant.core import HomeAssistant

from custom_components.autoarm.autoarming import AlarmArmer

TEST_PANEL = "alarm_control_panel.test_panel"


@pytest.fixture
async def autoarmer(hass: HomeAssistant) -> AsyncGenerator[AlarmArmer]:
    uut = AlarmArmer(hass, TEST_PANEL, occupants=["person.tester_bob"])
    await uut.initialize()
    yield uut
    uut.shutdown()


def test_not_occupied(hass: HomeAssistant, autoarmer: AlarmArmer) -> None:
    hass.states.async_set("person.tester_bob", "away")
    assert autoarmer.is_occupied() is False


def test_occupied(hass: HomeAssistant, autoarmer: AlarmArmer) -> None:
    hass.states.async_set("person.tester_bob", "home")
    assert autoarmer.is_occupied() is True


def test_day(hass: HomeAssistant, autoarmer: AlarmArmer) -> None:
    hass.states.async_set("sun.sun", "above_horizon")
    assert autoarmer.is_night() is False


async def test_reset_armed_state_sets_night(hass: HomeAssistant, autoarmer: AlarmArmer) -> None:
    hass.states.async_set(TEST_PANEL, "disarmed")
    hass.states.async_set("sun.sun", "below_horizon")
    hass.states.async_set("person.tester_bob", "home")
    assert await autoarmer.reset_armed_state() == "armed_night"


async def test_reset_armed_state_sets_home(hass: HomeAssistant, autoarmer: AlarmArmer) -> None:
    hass.states.async_set("sun.sun", "above_horizon")
    hass.states.async_set("person.tester_bob", "home")
    hass.states.async_set(TEST_PANEL, "disarmed")
    assert await autoarmer.reset_armed_state() == "armed_home"


async def test_unforced_reset_leaves_disarmed(hass: HomeAssistant, autoarmer: AlarmArmer) -> None:
    hass.states.async_set("sun.sun", "above_horizon")
    hass.states.async_set("person.tester_bob", "home")
    hass.states.async_set(TEST_PANEL, "disarmed")
    assert await autoarmer.reset_armed_state(force_arm=False) == "disarmed"


async def test_forced_reset_sets_armed_home_from_disarmed(hass: HomeAssistant, autoarmer: AlarmArmer) -> None:
    hass.states.async_set("sun.sun", "above_horizon")
    hass.states.async_set("person.tester_bob", "home")
    hass.states.async_set(TEST_PANEL, "disarmed")
    assert await autoarmer.reset_armed_state(force_arm=True) == "armed_home"


async def test_reset_sets_disarmed_from_unknown(hass: HomeAssistant, autoarmer: AlarmArmer) -> None:
    hass.states.async_set("sun.sun", "above_horizon")
    hass.states.async_set("person.tester_bob", "home")
    hass.states.async_set(TEST_PANEL, "unknown")
    assert await autoarmer.reset_armed_state(force_arm=False) == "armed_home"


async def test_reset_armed_state_uses_daytime_defaulr(hass: HomeAssistant) -> None:
    autoarmer = AlarmArmer(hass, TEST_PANEL, occupied_daytime_default="disarmed", occupants=["person.tester_bob"])
    await autoarmer.initialize()
    hass.states.async_set("sun.sun", "above_horizon")
    hass.states.async_set("person.tester_bob", "home")
    hass.states.async_set(TEST_PANEL, "unknown")
    assert await autoarmer.reset_armed_state(force_arm=False) == "disarmed"
