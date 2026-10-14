"""Occupancy delays and rate limit set up in the options, including those brought over from YAML"""

import datetime as dt
from typing import Any

from homeassistant.const import CONF_DELAY_TIME
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.autoarm.config_flow import (
    CONF_OCCUPIED_DELAY,
    CONF_PERSON_ENTITIES,
    CONF_RATE_LIMIT_MAX_CALLS,
    CONF_RATE_LIMIT_SECONDS,
    CONF_UNOCCUPIED_DELAY,
    CONF_USE_ALARM_SERVICE,
)
from custom_components.autoarm.const import (
    CONF_ALARM_PANEL,
    CONF_OCCUPANCY,
    CONF_RATE_LIMIT,
    CONF_RATE_LIMIT_CALLS,
    CONF_RATE_LIMIT_PERIOD,
    CONFIG_SCHEMA,
    DOMAIN,
    YAML_DATA_KEY,
)

PANEL = "alarm_panel.testing"


async def _setup_entry(
    hass: HomeAssistant, options: dict[str, Any], yaml_config: dict[str, Any] | None = None
) -> MockConfigEntry:
    hass.data[YAML_DATA_KEY] = yaml_config or {}
    hass.states.async_set("person.tenant", "home")
    hass.states.async_set("sun.sun", "above_horizon")
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Auto Arm",
        data={CONF_ALARM_PANEL: PANEL},
        options={CONF_PERSON_ENTITIES: ["person.tenant"], CONF_USE_ALARM_SERVICE: False, **options},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def panel_state(hass: HomeAssistant) -> str | None:
    state = hass.states.get(PANEL)
    return state.state if state else None


async def test_defaults_without_options_or_yaml(hass: HomeAssistant, mock_notify: Any) -> None:
    entry = await _setup_entry(hass, {})

    armer = entry.runtime_data
    # two minutes after the last person leaves, and straight away when someone arrives
    assert armer.occupied_delay == {"not_home": dt.timedelta(seconds=120)}
    assert CONF_UNOCCUPIED_DELAY not in entry.options
    assert armer.rate_limiter.window == dt.timedelta(seconds=60)
    assert armer.rate_limiter.max_calls == 5
    assert CONF_RATE_LIMIT_SECONDS not in entry.options


async def test_rate_limit_from_options(hass: HomeAssistant, mock_notify: Any) -> None:
    # as the options form gives them, numbers that may not be whole
    entry = await _setup_entry(hass, {CONF_RATE_LIMIT_MAX_CALLS: 2.0, CONF_RATE_LIMIT_SECONDS: 30.0})

    assert entry.runtime_data.rate_limiter.window == dt.timedelta(seconds=30)
    assert entry.runtime_data.rate_limiter.max_calls == 2

    response = await hass.services.async_call(DOMAIN, "enquire_configuration", None, blocking=True, return_response=True)
    assert response is not None
    assert response["rate_limit"] == {"period": "30 seconds", "max_calls": 2}


async def test_unoccupied_delay_from_options(hass: HomeAssistant, mock_notify: Any) -> None:
    entry = await _setup_entry(hass, {CONF_UNOCCUPIED_DELAY: 180, CONF_OCCUPIED_DELAY: 0})
    assert entry.runtime_data.occupied_delay == {"not_home": dt.timedelta(seconds=180)}
    assert panel_state(hass) == "disarmed"

    hass.states.async_set("person.tenant", "not_home")
    await hass.async_block_till_done()
    assert panel_state(hass) == "disarmed"

    async_fire_time_changed(hass, dt.datetime.now(dt.UTC) + dt.timedelta(seconds=190))
    await hass.async_block_till_done()
    assert panel_state(hass) == "armed_away"


async def test_yaml_migrated_to_options(hass: HomeAssistant, mock_notify: Any) -> None:
    yaml_config = {
        CONF_OCCUPANCY: {CONF_DELAY_TIME: {"not_home": dt.timedelta(minutes=3)}},
        CONF_RATE_LIMIT: {CONF_RATE_LIMIT_PERIOD: dt.timedelta(seconds=90), CONF_RATE_LIMIT_CALLS: 6},
    }

    entry = await _setup_entry(hass, {}, yaml_config)

    assert entry.options[CONF_UNOCCUPIED_DELAY] == 180
    assert CONF_OCCUPIED_DELAY not in entry.options
    assert entry.options[CONF_RATE_LIMIT_SECONDS] == 90
    assert entry.options[CONF_RATE_LIMIT_MAX_CALLS] == 6
    armer = entry.runtime_data
    assert armer.occupied_delay == {"not_home": dt.timedelta(minutes=3)}
    assert armer.rate_limiter.window == dt.timedelta(seconds=90)
    assert armer.rate_limiter.max_calls == 6


async def test_yaml_not_migrated_over_options(hass: HomeAssistant, mock_notify: Any) -> None:
    yaml_config = {
        CONF_OCCUPANCY: {CONF_DELAY_TIME: {"not_home": dt.timedelta(minutes=3)}},
        CONF_RATE_LIMIT: {CONF_RATE_LIMIT_PERIOD: dt.timedelta(seconds=90), CONF_RATE_LIMIT_CALLS: 6},
    }

    entry = await _setup_entry(hass, {CONF_UNOCCUPIED_DELAY: 0, CONF_RATE_LIMIT_MAX_CALLS: 3}, yaml_config)

    assert entry.options[CONF_UNOCCUPIED_DELAY] == 0
    assert entry.options[CONF_RATE_LIMIT_MAX_CALLS] == 3
    # only what isn't already in the options comes over
    assert entry.options[CONF_RATE_LIMIT_SECONDS] == 90
    assert entry.runtime_data.occupied_delay == {}


async def test_yaml_defaults_not_migrated(hass: HomeAssistant, mock_notify: Any) -> None:
    """A YAML config without occupancy or rate limit brings no defaults of its own over to the options"""
    yaml_config = CONFIG_SCHEMA({DOMAIN: {}})[DOMAIN]
    assert yaml_config == {}

    entry = await _setup_entry(hass, {}, yaml_config)

    assert CONF_RATE_LIMIT_MAX_CALLS not in entry.options
    assert CONF_RATE_LIMIT_SECONDS not in entry.options
    assert entry.runtime_data.rate_limiter.max_calls == 5


async def test_yaml_partial_rate_limit_migrated_alone(hass: HomeAssistant, mock_notify: Any) -> None:
    yaml_config = CONFIG_SCHEMA({DOMAIN: {CONF_RATE_LIMIT: {CONF_RATE_LIMIT_CALLS: 3}}})[DOMAIN]

    entry = await _setup_entry(hass, {}, yaml_config)

    assert entry.options[CONF_RATE_LIMIT_MAX_CALLS] == 3
    assert CONF_RATE_LIMIT_SECONDS not in entry.options
