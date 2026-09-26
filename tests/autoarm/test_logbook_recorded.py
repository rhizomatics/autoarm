"""The logbook, with a real recorder, shows AutoArm as the cause of changes it makes on its own"""

from typing import Any
from unittest.mock import patch

import homeassistant.util.dt as dt_util
import pytest
from homeassistant.components.alarm_control_panel.const import AlarmControlPanelState
from homeassistant.core import HomeAssistant
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


async def test_logbook_shows_autoarm_as_cause(
    recorder_mock: Any, hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    # the frontend package isn't installed, and the logbook only needs it for its panel
    hass.config.components.add("frontend")
    # AutoArm's logbook platform is picked up as the integration is loaded
    hass.config.components.add(DOMAIN)
    with patch("homeassistant.components.frontend.async_register_built_in_panel"):
        assert await async_setup_component(hass, "logbook", {})
    hass.states.async_set(TEST_PANEL, "disarmed")
    await hass.async_block_till_done()
    armer = AlarmArmer(hass, TEST_PANEL, use_alarm_service=False)
    start = dt_util.utcnow()

    await armer.arm(AlarmControlPanelState.ARMED_NIGHT, source=ChangeSource.SUNSET)
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    client = await hass_ws_client()
    await client.send_json({"id": 1, "type": "logbook/get_events", "start_time": start.isoformat(), "entity_ids": [TEST_PANEL]})
    response = await client.receive_json()
    panel_entry = next(e for e in response["result"] if e.get("state") == "armed_night")
    assert panel_entry["context_event_type"] == EVENT_TRIGGERED
    assert panel_entry["context_domain"] == DOMAIN
    assert panel_entry["context_name"] == "AutoArm"
    assert panel_entry["context_source"] == "sunset"
