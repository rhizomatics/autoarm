from typing import Any

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, EntityCategory
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.autoarm.config_flow import CONF_PERSON_ENTITIES, CONF_USE_ALARM_SERVICE
from custom_components.autoarm.const import CONF_ALARM_PANEL, DOMAIN, YAML_DATA_KEY

ENTITY_IDS = (
    "binary_sensor.autoarm_initialized",
    "sensor.autoarm_failures",
    "sensor.autoarm_last_calculation",
    "sensor.autoarm_last_intervention",
    "sensor.autoarm_last_calendar_event",
)


async def _setup_entry(hass: HomeAssistant) -> MockConfigEntry:
    hass.data[YAML_DATA_KEY] = {}
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_ALARM_PANEL: "alarm_panel.testing"},
        options={CONF_PERSON_ENTITIES: ["person.house_owner"], CONF_USE_ALARM_SERVICE: True},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_entities_registered_on_service_device(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, device_registry: dr.DeviceRegistry, mock_notify: Any
) -> None:
    entry = await _setup_entry(hass)

    [device] = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    assert device.identifiers == {(DOMAIN, entry.entry_id)}
    assert device.entry_type == dr.DeviceEntryType.SERVICE
    for entity_id in ENTITY_IDS:
        registered = entity_registry.async_get(entity_id)
        assert registered is not None, entity_id
        assert registered.config_entry_id == entry.entry_id
        assert registered.device_id == device.id
        assert registered.unique_id == f"{entry.entry_id}_{entity_id.split('.')[1].removeprefix('autoarm_')}"
    assert entity_registry.async_get("sensor.autoarm_failures").entity_category == EntityCategory.DIAGNOSTIC  # type: ignore
    assert entity_registry.async_get("binary_sensor.autoarm_initialized").entity_category == EntityCategory.DIAGNOSTIC  # type: ignore


async def test_entity_ids_independent_of_language(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, mock_notify: Any
) -> None:
    hass.config.language = "de"
    await _setup_entry(hass)

    for entity_id in ENTITY_IDS:
        assert entity_registry.async_get(entity_id) is not None, entity_id


async def test_initial_states(hass: HomeAssistant, mock_notify: Any) -> None:
    await _setup_entry(hass)

    assert hass.states.get("binary_sensor.autoarm_initialized").state == "on"  # type: ignore
    assert hass.states.get("sensor.autoarm_failures").state == "0"  # type: ignore
    # nothing has happened yet, so no value rather than a fake 'unavailable'
    assert hass.states.get("sensor.autoarm_last_intervention").state == STATE_UNKNOWN  # type: ignore
    assert hass.states.get("sensor.autoarm_last_calendar_event").state == STATE_UNKNOWN  # type: ignore
    last_calculation = hass.states.get("sensor.autoarm_last_calculation")
    assert last_calculation is not None
    assert last_calculation.attributes["device_class"] == "timestamp"
    assert last_calculation.attributes["source"] == "startup"
    assert last_calculation.attributes["changed"] is True


async def test_states_follow_armer(hass: HomeAssistant, mock_notify: Any) -> None:
    armer = (await _setup_entry(hass)).runtime_data

    await hass.services.async_call(DOMAIN, "reset_state", None, blocking=True, return_response=True)
    await hass.async_block_till_done()
    intervention = hass.states.get("sensor.autoarm_last_intervention")
    assert intervention is not None
    assert intervention.state == "action"
    assert intervention.attributes["device_class"] == "enum"

    armer.app_health_tracker.record_runtime_error()
    await hass.async_block_till_done()
    assert hass.states.get("sensor.autoarm_failures").state == "1"  # type: ignore

    armer.app_health_tracker.record_initialization_error("calendar")
    await hass.async_block_till_done()
    initialized = hass.states.get("binary_sensor.autoarm_initialized")
    assert initialized is not None
    assert initialized.state == "off"
    assert initialized.attributes["calendar"] == 1
    assert hass.states.get("sensor.autoarm_failures").attributes["initialization_errors"] == {"calendar": 1}  # type: ignore


@pytest.mark.parametrize("entity_id", ENTITY_IDS)
async def test_unload_leaves_no_live_state(hass: HomeAssistant, mock_notify: Any, entity_id: str) -> None:
    entry = await _setup_entry(hass)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED
    state = hass.states.get(entity_id)
    assert state is None or state.state == STATE_UNAVAILABLE


async def test_states_carry_context_of_cause(hass: HomeAssistant, mock_notify: Any) -> None:
    await _setup_entry(hass)
    context = Context()

    await hass.services.async_call(DOMAIN, "reset_state", None, blocking=True, return_response=True, context=context)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.autoarm_last_intervention").context.id == context.id  # type: ignore
    assert hass.states.get("sensor.autoarm_last_calculation").context.id == context.id  # type: ignore
