"""Changing state with the alarm_control_panel actions, for panels like Alarmo, rather than setting it directly"""

from collections.abc import AsyncGenerator
from typing import Any

import pytest
from homeassistant.components.alarm_control_panel.const import AlarmControlPanelState
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from conftest import TEST_PANEL
from custom_components.autoarm.autoarming import AlarmArmer
from custom_components.autoarm.config_flow import CONF_USE_ALARM_SERVICE
from custom_components.autoarm.const import CONF_ALARM_PANEL, DOMAIN, YAML_DATA_KEY, ChangeSource


def _register_panel_actions(hass: HomeAssistant, to_state: str | None = None, fail: bool = False) -> list[ServiceCall]:
    """Stand in for the panel integration, moving the panel to `to_state`, or the requested state if None"""
    calls: list[ServiceCall] = []

    async def handler(call: ServiceCall) -> None:
        calls.append(call)
        if fail:
            raise HomeAssistantError("code required")
        requested = call.service.replace("alarm_arm_", "armed_").replace("alarm_disarm", "disarmed")
        hass.states.async_set(TEST_PANEL, to_state or requested)

    for service in ("alarm_arm_away", "alarm_arm_home", "alarm_arm_night", "alarm_arm_vacation", "alarm_disarm"):
        hass.services.async_register("alarm_control_panel", service, handler)
    return calls


@pytest.fixture
async def service_armer(hass: HomeAssistant) -> AsyncGenerator[AlarmArmer]:
    hass.states.async_set(TEST_PANEL, "disarmed")
    uut = AlarmArmer(hass, TEST_PANEL, use_alarm_service=True)
    await uut.initialize()
    yield uut
    uut.shutdown()


async def test_direct_state_set_when_configured(hass: HomeAssistant) -> None:
    calls = _register_panel_actions(hass)
    hass.states.async_set(TEST_PANEL, "disarmed")
    autoarmer = AlarmArmer(hass, TEST_PANEL, use_alarm_service=False)

    assert await autoarmer.arm(AlarmControlPanelState.ARMED_AWAY, source=ChangeSource.BUTTON) == "armed_away"

    assert calls == []
    panel = hass.states.get(TEST_PANEL)
    assert panel is not None
    assert panel.attributes["changed_by"] == "autoarm.button"


async def test_service_used_when_configured(hass: HomeAssistant, service_armer: AlarmArmer) -> None:
    calls = _register_panel_actions(hass)

    result = await service_armer.arm(AlarmControlPanelState.ARMED_NIGHT, source=ChangeSource.SUNSET)
    await hass.async_block_till_done()

    assert result == AlarmControlPanelState.ARMED_NIGHT
    assert [(c.service, c.data["entity_id"]) for c in calls] == [("alarm_arm_night", TEST_PANEL)]
    assert service_armer.armed_state() == AlarmControlPanelState.ARMED_NIGHT
    # the panel's own state change isn't mistaken for someone changing it by hand
    assert service_armer.interventions == []
    assert service_armer.last_change is not None
    assert service_armer.last_change.source == ChangeSource.SUNSET


async def test_service_failure_leaves_state_alone(hass: HomeAssistant, service_armer: AlarmArmer) -> None:
    hass.states.async_set(TEST_PANEL, "disarmed")
    await hass.async_block_till_done()
    last_change = service_armer.last_change
    _register_panel_actions(hass, fail=True)

    assert await service_armer.arm(AlarmControlPanelState.ARMED_AWAY, source=ChangeSource.BUTTON) is None

    assert service_armer.armed_state() == AlarmControlPanelState.DISARMED
    assert service_armer.last_change is last_change


async def test_service_without_state_change_is_not_forced(hass: HomeAssistant, service_armer: AlarmArmer) -> None:
    _register_panel_actions(hass, to_state="disarmed")

    assert await service_armer.arm(AlarmControlPanelState.ARMED_AWAY, source=ChangeSource.BUTTON) is None

    assert service_armer.armed_state() == AlarmControlPanelState.DISARMED


async def test_exit_delay_completion_is_not_an_intervention(hass: HomeAssistant, service_armer: AlarmArmer) -> None:
    _register_panel_actions(hass, to_state="arming")

    result = await service_armer.arm(AlarmControlPanelState.ARMED_AWAY, source=ChangeSource.CALENDAR)
    await hass.async_block_till_done()
    assert result == AlarmControlPanelState.ARMED_AWAY
    assert service_armer.armed_state() == AlarmControlPanelState.ARMING

    # the panel finishes arming after its exit delay
    hass.states.async_set(TEST_PANEL, "armed_away")
    await hass.async_block_till_done()

    assert service_armer.interventions == []


async def test_exit_delay_cancelled_is_an_intervention(hass: HomeAssistant, service_armer: AlarmArmer) -> None:
    _register_panel_actions(hass, to_state="arming")
    await service_armer.arm(AlarmControlPanelState.ARMED_AWAY, source=ChangeSource.CALENDAR)
    await hass.async_block_till_done()

    # someone disarms at the panel during the exit delay
    hass.states.async_set(TEST_PANEL, "disarmed")
    await hass.async_block_till_done()

    [intervention] = service_armer.interventions
    assert intervention.source == ChangeSource.ALARM_PANEL
    assert intervention.state == AlarmControlPanelState.DISARMED


async def test_pending_held_by_autoarm_not_panel(hass: HomeAssistant, service_armer: AlarmArmer) -> None:
    calls = _register_panel_actions(hass)
    panel_before = service_armer.panel_state()

    assert await service_armer.arm(AlarmControlPanelState.PENDING, source=ChangeSource.CALENDAR) == "pending"

    assert calls == []
    assert service_armer.panel_state() == panel_before
    assert service_armer.armed_state() == AlarmControlPanelState.PENDING


async def test_pending_cleared_when_autoarm_changes_state(hass: HomeAssistant, service_armer: AlarmArmer) -> None:
    _register_panel_actions(hass)
    await service_armer.arm(AlarmControlPanelState.PENDING, source=ChangeSource.CALENDAR)

    assert await service_armer.arm(AlarmControlPanelState.ARMED_AWAY, source=ChangeSource.CALENDAR) == "armed_away"
    await hass.async_block_till_done()

    assert service_armer.armed_state() == AlarmControlPanelState.ARMED_AWAY
    assert service_armer.interventions == []


async def test_pending_cleared_by_panel_change(hass: HomeAssistant, service_armer: AlarmArmer) -> None:
    await service_armer.arm(AlarmControlPanelState.PENDING, source=ChangeSource.CALENDAR)

    hass.states.async_set(TEST_PANEL, "armed_night")
    await hass.async_block_till_done()

    assert service_armer.armed_state() == AlarmControlPanelState.ARMED_NIGHT


async def test_pending_forces_reset_like_direct_mode(hass: HomeAssistant, service_armer: AlarmArmer) -> None:
    """Calendar end moves via pending so the reset isn't held back by an earlier manual intervention"""
    hass.states.async_set(TEST_PANEL, "armed_vacation")
    await hass.async_block_till_done()
    assert service_armer.last_state_intervention() is not None

    await service_armer.pending_state(source=ChangeSource.CALENDAR)
    await service_armer.reset_armed_state(source=ChangeSource.SUNRISE)

    assert service_armer.pre_pending_state == AlarmControlPanelState.ARMED_VACATION
    assert service_armer.armed_state() not in (AlarmControlPanelState.PENDING, AlarmControlPanelState.ARMED_VACATION)


async def test_state_without_panel_action_left_unchanged(hass: HomeAssistant, service_armer: AlarmArmer) -> None:
    calls = _register_panel_actions(hass)
    panel_before = service_armer.armed_state()

    assert await service_armer.arm(AlarmControlPanelState.TRIGGERED, source=ChangeSource.CALENDAR) is None

    assert calls == []
    assert service_armer.armed_state() == panel_before


@pytest.mark.parametrize(
    ("options", "configured"),
    [
        ({CONF_USE_ALARM_SERVICE: True}, True),
        ({CONF_USE_ALARM_SERVICE: False}, False),
        # entries created before the option existed keep setting the state directly
        ({}, False),
    ],
)
async def test_option_passed_from_config_entry(
    hass: HomeAssistant, mock_notify: Any, options: dict[str, Any], configured: bool
) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_ALARM_PANEL: TEST_PANEL},
        options=options,
    )
    entry.add_to_hass(hass)
    hass.data[YAML_DATA_KEY] = {}
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.runtime_data.use_alarm_service is configured
