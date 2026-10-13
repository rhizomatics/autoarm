import datetime as dt
from unittest.mock import AsyncMock

import homeassistant.util.dt as dt_util
from homeassistant.components.alarm_control_panel.const import AlarmControlPanelState
from homeassistant.const import CONF_DELAY_TIME, CONF_ENTITY_ID
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from conftest import TEST_PANEL
from custom_components.autoarm.autoarming import AlarmArmer
from custom_components.autoarm.const import ATTR_RESET
from custom_components.autoarm.notifier import Notifier

AWAY_BUTTON = "binary_sensor.away_button"
RESET_BUTTON = "binary_sensor.reset_button"


async def _armer(hass: HomeAssistant) -> AlarmArmer:
    hass.states.async_set("sun.sun", "above_horizon")
    hass.states.async_set(TEST_PANEL, "armed_home")
    armer = AlarmArmer(
        hass,
        TEST_PANEL,
        use_alarm_service=False,
        buttons={
            AlarmControlPanelState.ARMED_AWAY: {CONF_ENTITY_ID: [AWAY_BUTTON], CONF_DELAY_TIME: dt.timedelta(seconds=120)},
            ATTR_RESET: {CONF_ENTITY_ID: [RESET_BUTTON]},
        },
    )
    await armer.initialize_logic()
    armer.initialize_buttons()
    armer.notifier = AsyncMock(spec=Notifier)
    return armer


async def _press(hass: HomeAssistant, button: str) -> None:
    hass.states.async_set(button, "off")
    hass.states.async_set(button, "on")
    await hass.async_block_till_done()


async def test_reset_button_answers_and_calls_off_delayed_arm(hass: HomeAssistant) -> None:
    """Reset pressed during the away button's delay leaves the state as it is, so has to say what it did"""
    armer = await _armer(hass)
    await _press(hass, AWAY_BUTTON)
    assert armer.pending_arm_state() == AlarmControlPanelState.ARMED_AWAY
    assert armer.notifier is not None
    armer.notifier.notify.reset_mock()  # type: ignore

    await _press(hass, RESET_BUTTON)

    assert armer.armed_state() == AlarmControlPanelState.ARMED_HOME
    armer.notifier.notify.assert_called_once()  # type: ignore
    notified = armer.notifier.notify.call_args.kwargs  # type: ignore
    assert notified["title"] == "Alarm reset"
    assert notified["message"] == "Alarm reset, staying Armed Home, and the change to Armed Away is cancelled"

    async_fire_time_changed(hass, dt_util.utcnow() + dt.timedelta(seconds=130))
    await hass.async_block_till_done()
    assert armer.armed_state() == AlarmControlPanelState.ARMED_HOME
    assert armer.pending_arm is None
    armer.shutdown()


async def test_reset_button_answers_when_nothing_to_change(hass: HomeAssistant) -> None:
    armer = await _armer(hass)

    await _press(hass, RESET_BUTTON)

    assert armer.notifier is not None
    assert armer.notifier.notify.call_args.kwargs["message"] == "Alarm reset, staying Armed Home"  # type: ignore
    armer.shutdown()


async def test_reset_button_change_of_state_notified_once(hass: HomeAssistant) -> None:
    armer = await _armer(hass)
    hass.states.async_set(TEST_PANEL, "armed_away")
    await hass.async_block_till_done()
    assert armer.notifier is not None
    armer.notifier.notify.reset_mock()  # type: ignore

    await _press(hass, RESET_BUTTON)

    assert armer.armed_state() == AlarmControlPanelState.ARMED_HOME
    armer.notifier.notify.assert_called_once()  # type: ignore
    assert armer.notifier.notify.call_args.kwargs["to_state"] == AlarmControlPanelState.ARMED_HOME  # type: ignore
    armer.shutdown()


async def test_delayed_arm_goes_ahead_when_left_alone(hass: HomeAssistant) -> None:
    armer = await _armer(hass)
    await _press(hass, AWAY_BUTTON)

    async_fire_time_changed(hass, dt_util.utcnow() + dt.timedelta(seconds=130))
    await hass.async_block_till_done()

    assert armer.armed_state() == AlarmControlPanelState.ARMED_AWAY
    assert armer.pending_arm is None
    armer.shutdown()
