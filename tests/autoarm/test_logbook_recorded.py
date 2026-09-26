"""The logbook, with a real recorder, shows AutoArm as the cause of changes it makes on its own"""

import datetime as dt
from typing import Any
from unittest.mock import patch

import homeassistant.util.dt as dt_util
import pytest
from homeassistant.components.alarm_control_panel.const import AlarmControlPanelState
from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.components.recorder.common import async_wait_recording_done
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from conftest import TEST_PANEL
from custom_components.autoarm.autoarming import AlarmArmer
from custom_components.autoarm.const import DOMAIN, EVENT_TRIGGERED, ChangeSource


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(recorder_mock: Any, enable_custom_integrations: Any) -> None:
    """Start the recorder before hass, as it must be, ahead of the other autouse fixtures"""
    return


async def _setup_logbook(hass: HomeAssistant) -> None:
    # the frontend package isn't installed, and the logbook only needs it for its panel
    hass.config.components.add("frontend")
    # AutoArm's logbook platform is picked up as the integration is loaded
    hass.config.components.add(DOMAIN)
    with patch("homeassistant.components.frontend.async_register_built_in_panel"):
        assert await async_setup_component(hass, "logbook", {})


async def _panel_entry(hass_ws_client: WebSocketGenerator, start: dt.datetime, state: str) -> dict[str, Any]:
    client = await hass_ws_client()
    await client.send_json({"id": 1, "type": "logbook/get_events", "start_time": start.isoformat(), "entity_ids": [TEST_PANEL]})
    response = await client.receive_json()
    return next(e for e in response["result"] if e.get("state") == state)


async def test_logbook_shows_autoarm_as_cause(
    recorder_mock: Any, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # the frontend package isn't installed, and the logbook only needs it for its panel
    await _setup_logbook(hass)
    hass.states.async_set(TEST_PANEL, "disarmed")
    await hass.async_block_till_done()
    armer = AlarmArmer(hass, TEST_PANEL, use_alarm_service=False)
    start = dt_util.utcnow()

    await armer.arm(AlarmControlPanelState.ARMED_NIGHT, source=ChangeSource.SUNSET)
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    panel_entry = await _panel_entry(hass_ws_client, start, "armed_night")
    assert panel_entry["context_event_type"] == EVENT_TRIGGERED
    assert panel_entry["context_domain"] == DOMAIN
    assert panel_entry["context_name"] == "AutoArm"
    assert panel_entry["context_source"] == "sunset"


async def test_logbook_shows_button_as_cause_when_using_panel_action(
    recorder_mock: Any, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    await _setup_logbook(hass)

    async def disarm(call: ServiceCall) -> None:
        # as a panel integration would, attributing its state change to the action's context
        hass.states.async_set(TEST_PANEL, "disarmed", context=call.context)

    hass.services.async_register("alarm_control_panel", "alarm_disarm", disarm)
    hass.states.async_set(TEST_PANEL, "armed_night")
    hass.states.async_set("binary_sensor.button", "off")
    await hass.async_block_till_done()
    armer = AlarmArmer(
        hass,
        TEST_PANEL,
        use_alarm_service=True,
        buttons={AlarmControlPanelState.DISARMED: {CONF_ENTITY_ID: ["binary_sensor.button"]}},
    )
    armer.initialize_buttons()
    start = dt_util.utcnow()

    hass.states.async_set("binary_sensor.button", "on")
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    panel_entry = await _panel_entry(hass_ws_client, start, "disarmed")
    assert panel_entry["context_event_type"] == EVENT_TRIGGERED
    assert panel_entry["context_source"] == "button"
    armer.shutdown()
