"""Switching the Frigate profile with the alarm state, using the Frigate integration's profile select"""

from collections.abc import AsyncGenerator
from typing import Any

import pytest
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.autoarm.config_flow import (
    CONF_FRIGATE_ENABLED,
    CONF_FRIGATE_PROFILE_ENTITY,
    CONF_USE_ALARM_SERVICE,
    OPTIONS_HELP_PLACEHOLDERS,
)
from custom_components.autoarm.const import CONF_ALARM_PANEL, DOMAIN, YAML_DATA_KEY
from custom_components.autoarm.frigate import async_track_frigate_profile, match_profile

PANEL = "alarm_panel.testing"
PROFILE_SELECT = "select.frigate_profile"
CONTROL_PANEL = "alarm_control_panel.testing"
PROFILE_OPTIONS = ["none", "quiet", "vigilant"]
PROFILES = {"disarmed": "quiet", "armed_away": "vigilant"}


def _register_select(hass: HomeAssistant, fail: bool = False, options: list[str] = PROFILE_OPTIONS) -> list[str]:
    """Stand in for the Frigate integration, moving the profile select to the option chosen"""
    chosen: list[str] = []

    async def handler(call: ServiceCall) -> None:
        if fail:
            raise HomeAssistantError("MQTT not connected")
        chosen.append(call.data["option"])
        hass.states.async_set(PROFILE_SELECT, call.data["option"], {"options": options})

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


async def test_missing_profile_resets_to_base(hass: HomeAssistant, tracking: None, caplog: pytest.LogCaptureFixture) -> None:
    chosen = _register_select(hass)
    hass.states.async_set(PROFILE_SELECT, "vigilant", {"options": ["none", "vigilant"]})

    hass.states.async_set(PANEL, "disarmed")
    await hass.async_block_till_done()

    assert chosen == ["none"]
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


@pytest.mark.parametrize(
    ("state", "available", "expected"),
    [
        ("disarmed", ["none", "Disarmed"], "Disarmed"),
        ("armed_away", ["none", "ARMED_AWAY", "armed"], "ARMED_AWAY"),
        ("armed_night", ["none", "ARMED_AWAY", "Armed"], "Armed"),
        ("disarmed", ["none", "armed"], None),
        ("armed_home", ["none", "quiet"], None),
        # no profile isn't a match for anything
        ("armed_home", ["none"], None),
    ],
)
def test_match_profile(state: str, available: list[str], expected: str | None) -> None:
    assert match_profile(state, available) == expected


async def test_profiles_matched_by_name(hass: HomeAssistant) -> None:
    options = ["none", "Disarmed", "armed", "armed_night"]
    chosen = _register_select(hass, options=options)
    hass.states.async_set(PANEL, "armed_vacation")
    hass.states.async_set(PROFILE_SELECT, "none", {"options": options})
    # a profile given in the options wins over one matched by name, with no profile as a way to opt out
    unsubscribe = await async_track_frigate_profile(hass, PANEL, PROFILE_SELECT, {"armed_away": "none"})

    for state in ("disarmed", "armed_night", "armed_home", "armed_away"):
        hass.states.async_set(PANEL, state)
        await hass.async_block_till_done()
    unsubscribe()

    assert chosen == ["armed", "Disarmed", "armed_night", "armed", "none"]


OTHER_SECTIONS = (
    "assist_options",
    "button_options",
    "notify_options",
    "calendar_options",
    "sun_options",
    "presence_options",
    "advanced_options",
    "time_of_day_options",
)


def _frigate_select(hass: HomeAssistant, entity_registry: er.EntityRegistry, options: list[str], name: str = "profile") -> str:
    """The Frigate integration's profile select, as registered for a Frigate server"""
    entry = entity_registry.async_get_or_create(
        "select", "frigate", f"frigate_{name}:select:profile", suggested_object_id=f"frigate_{name}"
    )
    hass.states.async_set(entry.entity_id, "none", {"options": options})
    return entry.entity_id


async def _setup_entry(hass: HomeAssistant, options: dict[str, Any]) -> MockConfigEntry:
    hass.data[YAML_DATA_KEY] = {}
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_ALARM_PANEL: PANEL}, options={CONF_USE_ALARM_SERVICE: False, **options})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _field(data_schema: Any, section: str | None, key: str) -> Any:
    fields = data_schema.schema[section].schema.schema if section else data_schema.schema
    return next(k for k in fields if str(k) == key)


async def test_frigate_select_found_when_enabled(
    hass: HomeAssistant, mock_notify: Any, entity_registry: er.EntityRegistry
) -> None:
    profile_select = _frigate_select(hass, entity_registry, ["none", "Disarmed", "armed"])
    hass.states.async_set(PANEL, "disarmed")

    entry = await _setup_entry(hass, {CONF_FRIGATE_ENABLED: True})

    assert entry.runtime_data.frigate_profile_entity == profile_select
    # states never saved in the options are matched by name
    assert entry.runtime_data.frigate_profiles == {}


async def test_frigate_off_unless_enabled(hass: HomeAssistant, mock_notify: Any, entity_registry: er.EntityRegistry) -> None:
    _frigate_select(hass, entity_registry, ["none", "Disarmed"])

    entry = await _setup_entry(hass, {})

    assert entry.runtime_data.frigate_profile_entity is None


async def test_chosen_select_used_over_found(
    hass: HomeAssistant, mock_notify: Any, entity_registry: er.EntityRegistry, caplog: pytest.LogCaptureFixture
) -> None:
    _frigate_select(hass, entity_registry, ["none"], name="first")
    second = _frigate_select(hass, entity_registry, ["none"], name="second")

    entry = await _setup_entry(hass, {CONF_FRIGATE_ENABLED: True, CONF_FRIGATE_PROFILE_ENTITY: second})

    assert entry.runtime_data.frigate_profile_entity == second
    assert "choose another" not in caplog.text


async def test_first_of_several_selects_used(
    hass: HomeAssistant, mock_notify: Any, entity_registry: er.EntityRegistry, caplog: pytest.LogCaptureFixture
) -> None:
    first = _frigate_select(hass, entity_registry, ["none"], name="first")
    _frigate_select(hass, entity_registry, ["none"], name="second")

    entry = await _setup_entry(hass, {CONF_FRIGATE_ENABLED: True})

    assert entry.runtime_data.frigate_profile_entity == first
    assert "choose another" in caplog.text


async def test_enabled_without_frigate_warns(hass: HomeAssistant, mock_notify: Any, caplog: pytest.LogCaptureFixture) -> None:
    entry = await _setup_entry(hass, {CONF_FRIGATE_ENABLED: True})

    assert entry.runtime_data.frigate_profile_entity is None
    assert "no Frigate profile select found" in caplog.text


async def test_saved_profiles_used_as_is(hass: HomeAssistant, mock_notify: Any) -> None:
    chosen = _register_select(hass)
    hass.states.async_set(PANEL, "disarmed")
    hass.states.async_set(PROFILE_SELECT, "none", {"options": PROFILE_OPTIONS})

    entry = await _setup_entry(
        hass,
        {
            CONF_FRIGATE_ENABLED: True,
            CONF_FRIGATE_PROFILE_ENTITY: PROFILE_SELECT,
            "frigate_profile_disarmed": "quiet",
            "frigate_profile_armed_away": "vigilant",
            "frigate_profile_armed_home": "none",
            # as it may have been stored when cleared
            "frigate_profile_armed_night": "",
        },
    )

    assert entry.runtime_data.frigate_profiles == {
        "disarmed": "quiet",
        "armed_away": "vigilant",
        "armed_home": "none",
        "armed_night": "none",
    }
    panel = hass.states.get(PANEL)
    assert panel is not None
    assert chosen[-1] == entry.runtime_data.frigate_profiles.get(panel.state, "none")


async def test_toggle_only_offered_with_frigate(
    hass: HomeAssistant, setup_autoarm: MockConfigEntry, entity_registry: er.EntityRegistry
) -> None:
    result = await hass.config_entries.options.async_init(setup_autoarm.entry_id)
    data_schema = result["data_schema"]
    assert data_schema is not None
    assert CONF_FRIGATE_ENABLED not in data_schema.schema
    assert "frigate_options" not in data_schema.schema
    hass.config_entries.options.async_abort(result["flow_id"])

    _frigate_select(hass, entity_registry, ["none", "Disarmed", "armed"])
    result = await hass.config_entries.options.async_init(setup_autoarm.entry_id)

    data_schema = result["data_schema"]
    assert data_schema is not None
    assert CONF_FRIGATE_ENABLED in data_schema.schema
    assert "frigate_options" in data_schema.schema
    assert result["description_placeholders"] == OPTIONS_HELP_PLACEHOLDERS


async def test_options_flow_fills_in_matched_profiles(
    hass: HomeAssistant, setup_autoarm: MockConfigEntry, entity_registry: er.EntityRegistry
) -> None:
    _frigate_select(hass, entity_registry, ["none", "Disarmed", "armed", "armed_night"])

    result = await hass.config_entries.options.async_init(setup_autoarm.entry_id)

    data_schema = result["data_schema"]
    assert data_schema is not None
    frigate_section = data_schema.schema["frigate_options"].schema.schema
    assert [str(k) for k in frigate_section] == [
        "frigate_profile_disarmed",
        "frigate_profile_armed_home",
        "frigate_profile_armed_away",
        "frigate_profile_armed_night",
        "frigate_profile_armed_vacation",
        "frigate_profile_armed_custom_bypass",
        # last, and left blank, as only an override for more than one Frigate server
        CONF_FRIGATE_PROFILE_ENTITY,
    ]
    assert _field(data_schema, "frigate_options", CONF_FRIGATE_PROFILE_ENTITY).description["suggested_value"] is None
    suggested = {str(k): k.description["suggested_value"] for k in frigate_section if str(k) != CONF_FRIGATE_PROFILE_ENTITY}
    assert suggested == {
        "frigate_profile_disarmed": "Disarmed",
        "frigate_profile_armed_home": "armed",
        "frigate_profile_armed_away": "armed",
        "frigate_profile_armed_night": "armed_night",
        "frigate_profile_armed_vacation": "armed",
        "frigate_profile_armed_custom_bypass": "armed",
    }
    # no profile first, then those of the Frigate integration's profile select
    assert frigate_section[_field(data_schema, "frigate_options", "frigate_profile_disarmed")].config["options"] == [
        "none",
        "Disarmed",
        "armed",
        "armed_night",
    ]


async def _save_options(
    hass: HomeAssistant, entry: MockConfigEntry, enabled: bool = True, changes: dict[str, str | None] | None = None
) -> None:
    """Save the options as the form sends them, with fields left as filled in unless changed, and None for cleared"""
    result = await hass.config_entries.options.async_init(entry.entry_id)
    data_schema = result["data_schema"]
    assert data_schema is not None
    frigate: dict[str, Any] = {
        str(k): k.description["suggested_value"]
        for k in data_schema.schema["frigate_options"].schema.schema
        if k.description and k.description.get("suggested_value") is not None
    }
    frigate.update(changes or {})
    await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_ALARM_PANEL: CONTROL_PANEL,
            CONF_FRIGATE_ENABLED: enabled,
            **{section: {} for section in OTHER_SECTIONS},
            "frigate_options": {k: v for k, v in frigate.items() if v is not None},
        },
    )
    await hass.async_block_till_done()


async def _alarm_to(hass: HomeAssistant, state: str) -> None:
    hass.states.async_set(CONTROL_PANEL, state)
    await hass.async_block_till_done()


async def test_switched_on_with_profiles_just_works(
    hass: HomeAssistant, setup_autoarm: MockConfigEntry, entity_registry: er.EntityRegistry
) -> None:
    """Frigate already has profiles, and the only change is switching Frigate on"""
    profiles = ["none", "Disarmed", "armed"]
    _frigate_select(hass, entity_registry, profiles)
    chosen = _register_select(hass, options=profiles)

    await _save_options(hass, setup_autoarm)

    assert not [k for k in setup_autoarm.options if k.startswith("frigate_profile_")]
    armer = setup_autoarm.runtime_data
    assert armer.frigate_profile_entity == PROFILE_SELECT
    await _alarm_to(hass, "armed_night")
    await _alarm_to(hass, "disarmed")
    assert chosen[-2:] == ["armed", "Disarmed"]


async def test_profile_added_later_just_works(
    hass: HomeAssistant, setup_autoarm: MockConfigEntry, entity_registry: er.EntityRegistry
) -> None:
    """Frigate is switched on before it has any profiles, and one is added later"""
    _frigate_select(hass, entity_registry, ["none"])
    await _save_options(hass, setup_autoarm)
    assert not [k for k in setup_autoarm.options if k.startswith("frigate_profile_")]

    profiles = ["none", "Armed"]
    hass.states.async_set(PROFILE_SELECT, "none", {"options": profiles})
    chosen = _register_select(hass, options=profiles)
    await _alarm_to(hass, "armed_home")

    assert chosen == ["Armed"]


async def test_cleared_profile_stays_cleared(
    hass: HomeAssistant, setup_autoarm: MockConfigEntry, entity_registry: er.EntityRegistry
) -> None:
    _frigate_select(hass, entity_registry, ["none", "Disarmed", "armed"])

    await _save_options(
        hass, setup_autoarm, changes={"frigate_profile_armed_home": None, "frigate_profile_armed_vacation": "holiday"}
    )

    # only what differs from the profiles matched by name is kept
    assert {k: v for k, v in setup_autoarm.options.items() if k.startswith("frigate_profile_")} == {
        "frigate_profile_armed_home": "none",
        "frigate_profile_armed_vacation": "holiday",
    }
    assert setup_autoarm.runtime_data.frigate_profiles == {"armed_home": "none", "armed_vacation": "holiday"}

    # and isn't filled in by name again, nor changed by saving again
    result = await hass.config_entries.options.async_init(setup_autoarm.entry_id)
    data_schema = result["data_schema"]
    assert data_schema is not None
    assert _field(data_schema, "frigate_options", "frigate_profile_armed_home").description["suggested_value"] == "none"
    hass.config_entries.options.async_abort(result["flow_id"])
    await _save_options(hass, setup_autoarm)
    assert setup_autoarm.options["frigate_profile_armed_home"] == "none"


async def test_cleared_without_match_left_to_match(
    hass: HomeAssistant, setup_autoarm: MockConfigEntry, entity_registry: er.EntityRegistry
) -> None:
    _frigate_select(hass, entity_registry, ["none", "Disarmed"])

    # armed_home has no match, so is blank, and stays to be matched when a profile is added
    await _save_options(hass, setup_autoarm, changes={"frigate_profile_armed_home": None})

    assert not [k for k in setup_autoarm.options if k.startswith("frigate_profile_")]


async def test_overrides_kept_while_off(
    hass: HomeAssistant, setup_autoarm: MockConfigEntry, entity_registry: er.EntityRegistry
) -> None:
    _frigate_select(hass, entity_registry, ["none", "Disarmed", "armed"])

    await _save_options(hass, setup_autoarm, enabled=False, changes={"frigate_profile_armed_away": "vigilant"})

    assert setup_autoarm.options[CONF_FRIGATE_ENABLED] is False
    assert setup_autoarm.options["frigate_profile_armed_away"] == "vigilant"
    assert setup_autoarm.runtime_data.frigate_profile_entity is None


async def test_quick_setup_offers_frigate(hass: HomeAssistant, mock_notify: Any, entity_registry: er.EntityRegistry) -> None:
    _frigate_select(hass, entity_registry, ["none", "Disarmed", "armed"])
    hass.data[YAML_DATA_KEY] = {}
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "quick_setup"})
    data_schema = result["data_schema"]
    assert data_schema is not None
    assert CONF_FRIGATE_ENABLED in data_schema.schema

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ALARM_PANEL: "alarm_control_panel.home", CONF_FRIGATE_ENABLED: True}
    )

    assert result["options"][CONF_FRIGATE_ENABLED] is True
    # left to be matched by name, with nothing yet saved for each state
    assert not any(k.startswith("frigate_profile_") for k in result["options"])
