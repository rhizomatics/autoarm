"""Switching the Frigate profile with the alarm state, using the Frigate integration's profile select"""

from collections.abc import AsyncGenerator
from typing import Any

import pytest
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.autoarm.config_flow import CONF_FRIGATE_PROFILE_ENTITY, CONF_USE_ALARM_SERVICE
from custom_components.autoarm.const import CONF_ALARM_PANEL, DOMAIN, YAML_DATA_KEY
from custom_components.autoarm.frigate import async_track_frigate_profile

PANEL = "alarm_panel.testing"
PROFILE_SELECT = "select.frigate_profile"
PROFILE_OPTIONS = ["none", "quiet", "vigilant"]
PROFILES = {"disarmed": "quiet", "armed_away": "vigilant"}


def _register_select(hass: HomeAssistant, fail: bool = False) -> list[str]:
    """Stand in for the Frigate integration, moving the profile select to the option chosen"""
    chosen: list[str] = []

    async def handler(call: ServiceCall) -> None:
        if fail:
            raise HomeAssistantError("MQTT not connected")
        chosen.append(call.data["option"])
        hass.states.async_set(PROFILE_SELECT, call.data["option"], {"options": PROFILE_OPTIONS})

    hass.services.async_register("select", "select_option", handler)
    return chosen


@pytest.fixture
async def tracking(hass: HomeAssistant) -> AsyncGenerator[None]:
    hass.states.async_set(PANEL, "armed_home")
    hass.states.async_set(PROFILE_SELECT, "none", {"options": PROFILE_OPTIONS})
    unsubscribe = await async_track_frigate_profile(hass, PANEL, PROFILE_SELECT, PROFILES)
    yield
    unsubscribe()


async def test_profile_follows_alarm_state(hass: HomeAssistant, tracking: None) -> None:
    chosen = _register_select(hass)

    for state in ("disarmed", "armed_away", "armed_home"):
        hass.states.async_set(PANEL, state)
        await hass.async_block_till_done()

    assert chosen == ["quiet", "vigilant", "none"]


async def test_transitional_states_leave_profile(hass: HomeAssistant, tracking: None) -> None:
    chosen = _register_select(hass)

    for state in ("disarmed", "arming", "pending", "triggered", "unavailable"):
        hass.states.async_set(PANEL, state)
        await hass.async_block_till_done()

    assert chosen == ["quiet"]


async def test_synced_at_start(hass: HomeAssistant) -> None:
    chosen = _register_select(hass)
    hass.states.async_set(PANEL, "disarmed")
    hass.states.async_set(PROFILE_SELECT, "none", {"options": PROFILE_OPTIONS})

    unsubscribe = await async_track_frigate_profile(hass, PANEL, PROFILE_SELECT, PROFILES)
    unsubscribe()

    assert chosen == ["quiet"]


async def test_already_on_profile_not_reselected(hass: HomeAssistant, tracking: None) -> None:
    chosen = _register_select(hass)
    hass.states.async_set(PROFILE_SELECT, "quiet", {"options": PROFILE_OPTIONS})

    hass.states.async_set(PANEL, "disarmed")
    await hass.async_block_till_done()

    assert chosen == []


async def test_missing_profile_left_alone(hass: HomeAssistant, tracking: None, caplog: pytest.LogCaptureFixture) -> None:
    chosen = _register_select(hass)
    hass.states.async_set(PROFILE_SELECT, "none", {"options": ["none", "vigilant"]})

    hass.states.async_set(PANEL, "disarmed")
    await hass.async_block_till_done()

    assert chosen == []
    assert "No Frigate profile quiet" in caplog.text


async def test_failed_select_logged(hass: HomeAssistant, tracking: None, caplog: pytest.LogCaptureFixture) -> None:
    _register_select(hass, fail=True)

    hass.states.async_set(PANEL, "disarmed")
    await hass.async_block_till_done()

    assert "MQTT not connected" in caplog.text


async def test_catches_up_when_frigate_returns(hass: HomeAssistant, tracking: None) -> None:
    chosen = _register_select(hass)
    hass.states.async_set(PROFILE_SELECT, "unavailable", {"options": PROFILE_OPTIONS})
    hass.states.async_set(PANEL, "disarmed")
    await hass.async_block_till_done()
    assert chosen == []

    hass.states.async_set(PROFILE_SELECT, "none", {"options": PROFILE_OPTIONS})
    await hass.async_block_till_done()

    assert chosen == ["quiet"]


async def test_profile_chosen_by_hand_left_alone(hass: HomeAssistant, tracking: None) -> None:
    chosen = _register_select(hass)

    hass.states.async_set(PROFILE_SELECT, "vigilant", {"options": PROFILE_OPTIONS})
    await hass.async_block_till_done()

    assert chosen == []


async def test_stops_when_unsubscribed(hass: HomeAssistant) -> None:
    hass.states.async_set(PANEL, "armed_home")
    hass.states.async_set(PROFILE_SELECT, "none", {"options": PROFILE_OPTIONS})
    unsubscribe = await async_track_frigate_profile(hass, PANEL, PROFILE_SELECT, PROFILES)
    chosen = _register_select(hass)
    unsubscribe()

    hass.states.async_set(PANEL, "disarmed")
    await hass.async_block_till_done()

    assert chosen == []


async def test_options_from_config_entry(hass: HomeAssistant, mock_notify: Any) -> None:
    chosen = _register_select(hass)
    hass.states.async_set(PANEL, "disarmed")
    hass.states.async_set(PROFILE_SELECT, "none", {"options": PROFILE_OPTIONS})
    hass.data[YAML_DATA_KEY] = {}
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_ALARM_PANEL: PANEL},
        options={
            CONF_USE_ALARM_SERVICE: False,
            CONF_FRIGATE_PROFILE_ENTITY: PROFILE_SELECT,
            "frigate_profile_disarmed": "quiet",
            "frigate_profile_armed_away": "vigilant",
            # cleared in the form
            "frigate_profile_armed_home": "",
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.runtime_data.frigate_profile_entity == PROFILE_SELECT
    assert entry.runtime_data.frigate_profiles == PROFILES
    # whatever state AutoArm settles on at start up, Frigate is put on the profile for it
    panel = hass.states.get(PANEL)
    assert panel is not None
    assert chosen[-1] == PROFILES.get(panel.state, "none")


async def test_options_flow_saves_frigate_options(hass: HomeAssistant, setup_autoarm: MockConfigEntry) -> None:
    hass.states.async_set(PROFILE_SELECT, "none", {"options": PROFILE_OPTIONS})
    hass.config_entries.async_update_entry(
        setup_autoarm, options={**setup_autoarm.options, CONF_FRIGATE_PROFILE_ENTITY: PROFILE_SELECT}
    )
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(setup_autoarm.entry_id)
    data_schema = result["data_schema"]
    assert data_schema is not None
    frigate_section = data_schema.schema["frigate_options"].schema.schema
    # the profiles offered are those of the select already chosen
    assert [str(k) for k in frigate_section] == [
        CONF_FRIGATE_PROFILE_ENTITY,
        "frigate_profile_disarmed",
        "frigate_profile_armed_home",
        "frigate_profile_armed_away",
        "frigate_profile_armed_night",
        "frigate_profile_armed_vacation",
        "frigate_profile_armed_custom_bypass",
    ]
    profile_selector = next(v for k, v in frigate_section.items() if str(k) == "frigate_profile_disarmed")
    assert profile_selector.config["options"] == ["quiet", "vigilant"]

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_ALARM_PANEL: "alarm_control_panel.testing",
            **{
                section: {}
                for section in (
                    "assist_options",
                    "button_options",
                    "notify_options",
                    "calendar_options",
                    "sun_options",
                    "presence_options",
                    "advanced_options",
                    "time_of_day_options",
                )
            },
            # a profile not yet in Frigate can be typed in
            "frigate_options": {
                CONF_FRIGATE_PROFILE_ENTITY: PROFILE_SELECT,
                "frigate_profile_armed_away": "vigilant",
                "frigate_profile_armed_vacation": "holiday",
            },
        },
    )

    assert setup_autoarm.options[CONF_FRIGATE_PROFILE_ENTITY] == PROFILE_SELECT
    assert setup_autoarm.options["frigate_profile_armed_away"] == "vigilant"
    assert setup_autoarm.options["frigate_profile_armed_vacation"] == "holiday"
    assert "frigate_profile_disarmed" not in setup_autoarm.options
