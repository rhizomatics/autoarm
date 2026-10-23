"""Calendar match rules, poll interval and notification grace period in the options, including those brought over from YAML"""

import datetime as dt
from typing import Any

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.autoarm.config_flow import (
    CONF_CALENDAR_ENTITIES,
    CONF_CALENDAR_MATCH_RULES,
    CONF_CALENDAR_NOTIFY_GRACE_SECONDS,
    CONF_CALENDAR_POLL_MINUTES,
)
from custom_components.autoarm.const import CONF_ALARM_PANEL, CONFIG_SCHEMA, DOMAIN, YAML_DATA_KEY

PANEL = "alarm_control_panel.testing"
YAML_CALENDAR_CONTROL: dict[str, Any] = {
    "notify_grace_period": 90,
    "calendars": [
        {
            "entity_id": "calendar.family",
            "poll_interval": 300,
            "state_patterns": {"armed_vacation": ["Holiday.*", "Camping Trip.*"], "armed_away": "Working at Office"},
        },
        {"entity_id": "calendar.alarm_control", "poll_interval": 60, "state_patterns": {"disarmed": ["Disarmed"]}},
        {"entity_id": "calendar.plain"},
    ],
}


async def _setup_entry(
    hass: HomeAssistant, options: dict[str, Any], calendar_control: dict[str, Any] | None = None
) -> MockConfigEntry:
    hass.data[YAML_DATA_KEY] = (
        CONFIG_SCHEMA({DOMAIN: {"calendar_control": calendar_control}})[DOMAIN] if calendar_control else {}
    )
    entry = MockConfigEntry(domain=DOMAIN, title="Auto Arm", data={CONF_ALARM_PANEL: PANEL}, options=options)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _calendar_config(entry: MockConfigEntry) -> dict[str, dict[str, Any]]:
    return {calendar["entity_id"]: calendar for calendar in entry.runtime_data.calendar_configs}


async def test_yaml_calendar_control_migrated_to_options(hass: HomeAssistant, mock_notify: Any) -> None:
    calendars = ["calendar.family", "calendar.alarm_control", "calendar.plain"]
    entry = await _setup_entry(hass, {CONF_CALENDAR_ENTITIES: calendars}, YAML_CALENDAR_CONTROL)

    # nothing for the calendar that only had the default patterns
    assert entry.options[CONF_CALENDAR_MATCH_RULES] == [
        {"calendar": "calendar.family", "state": "armed_vacation", "patterns": ["Holiday.*", "Camping Trip.*"]},
        {"calendar": "calendar.family", "state": "armed_away", "patterns": ["Working at Office"]},
        {"calendar": "calendar.alarm_control", "state": "disarmed", "patterns": ["Disarmed"]},
    ]
    # the shortest of them, now there's one for all calendars
    assert entry.options[CONF_CALENDAR_POLL_MINUTES] == 15
    assert entry.options[CONF_CALENDAR_NOTIFY_GRACE_SECONDS] == 90

    configured = _calendar_config(entry)
    assert configured["calendar.family"]["state_patterns"] == {
        "armed_vacation": ["Holiday.*", "Camping Trip.*"],
        "armed_away": ["Working at Office"],
    }
    assert configured["calendar.alarm_control"]["state_patterns"] == {"disarmed": ["Disarmed"]}
    assert configured["calendar.plain"]["state_patterns"]["armed_vacation"] == ["Vacation", "Holiday"]
    assert entry.runtime_data.calendar_notify_grace_period == dt.timedelta(seconds=90)


async def test_yaml_calendar_control_not_migrated_over_options(hass: HomeAssistant, mock_notify: Any) -> None:
    entry = await _setup_entry(
        hass,
        {CONF_CALENDAR_ENTITIES: ["calendar.family"], CONF_CALENDAR_MATCH_RULES: [], CONF_CALENDAR_POLL_MINUTES: 5},
        YAML_CALENDAR_CONTROL,
    )

    assert entry.options[CONF_CALENDAR_MATCH_RULES] == []
    assert entry.options[CONF_CALENDAR_POLL_MINUTES] == 5
    # only what isn't already in the options comes over
    assert entry.options[CONF_CALENDAR_NOTIFY_GRACE_SECONDS] == 90
    configured = _calendar_config(entry)
    assert configured["calendar.family"]["poll_interval"] == 5
    assert configured["calendar.family"]["state_patterns"]["armed_away"] == ["Away"]


async def test_rules_for_a_calendar_are_grouped_by_state(hass: HomeAssistant, mock_notify: Any) -> None:
    entry = await _setup_entry(
        hass,
        {
            CONF_CALENDAR_ENTITIES: ["calendar.family", "calendar.other"],
            CONF_CALENDAR_MATCH_RULES: [
                {"calendar": "calendar.family", "state": "armed_away", "patterns": ["Office"]},
                {"calendar": "calendar.family", "state": "armed_away", "patterns": ["Gym", "Pub"]},
                {"calendar": "calendar.family", "state": "disarmed", "patterns": ["Cleaner"]},
                {"calendar": "calendar.unused", "state": "disarmed", "patterns": ["Nobody"]},
            ],
        },
    )

    configured = _calendar_config(entry)
    assert configured["calendar.family"]["state_patterns"] == {"armed_away": ["Office", "Gym", "Pub"], "disarmed": ["Cleaner"]}
    assert configured["calendar.family"]["poll_interval"] == 15
    # without rules of its own it has the defaults
    assert configured["calendar.other"]["state_patterns"]["disarmed"] == ["Disarmed"]
    assert entry.runtime_data.calendar_notify_grace_period == dt.timedelta(seconds=60)


async def test_options_flow_calendar_section(hass: HomeAssistant, setup_autoarm: MockConfigEntry) -> None:
    result = await hass.config_entries.options.async_init(setup_autoarm.entry_id)

    data_schema = result["data_schema"]
    assert data_schema is not None
    assert data_schema.schema["calendar_options"].schema({}) == {
        "calendar_armed_end_mode": "auto",
        "calendar_disarmed_end_mode": "auto",
        "calendar_match_rules": [],
        "calendar_poll_interval": 15,
        "calendar_notify_grace": 60,
    }
    rule_selector = data_schema.schema["calendar_options"].schema.schema["calendar_match_rules"]
    with pytest.raises(Exception, match="Field patterns is required"):
        rule_selector([{"calendar": "calendar.family", "state": "armed_away"}])


async def test_options_flow_rejects_invalid_pattern(
    hass: HomeAssistant, setup_autoarm: MockConfigEntry, mock_notify: Any
) -> None:
    result = await hass.config_entries.options.async_init(setup_autoarm.entry_id)
    user_input: dict[str, Any] = {
        CONF_ALARM_PANEL: PANEL,
        "presence_options": {},
        "sun_options": {},
        "button_options": {},
        "assist_options": {},
        "notify_options": {"notify_action": "notify.supernotify"},
        "time_of_day_options": {},
        "advanced_options": {},
        "calendar_options": {
            "calendar_poll_interval": 30,
            "calendar_match_rules": [
                {"calendar": "calendar.family", "state": "armed_away", "patterns": ["Office", "(unclosed"]}
            ],
        },
    }

    result = await hass.config_entries.options.async_configure(result["flow_id"], user_input)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_pattern"}
    # as it was filled in, to be put right
    data_schema = result["data_schema"]
    assert data_schema is not None
    assert data_schema.schema["calendar_options"].schema({})["calendar_poll_interval"] == 30
    assert CONF_CALENDAR_MATCH_RULES not in setup_autoarm.options

    user_input["calendar_options"]["calendar_match_rules"][0]["patterns"] = ["Office", "(closed)"]
    result = await hass.config_entries.options.async_configure(result["flow_id"], user_input)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert setup_autoarm.options[CONF_CALENDAR_MATCH_RULES] == [
        {"calendar": "calendar.family", "state": "armed_away", "patterns": ["Office", "(closed)"]}
    ]


async def test_advanced_setup_rejects_invalid_pattern(hass: HomeAssistant, mock_notify: Any) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "advanced_setup"})

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_ALARM_PANEL: PANEL,
            "presence_options": {},
            "sun_options": {},
            "button_options": {},
            "assist_options": {},
            "notify_options": {"notify_action": "notify.supernotify"},
            "time_of_day_options": {},
            "advanced_options": {},
            "calendar_options": {
                "calendar_match_rules": [{"calendar": "calendar.family", "state": "armed_away", "patterns": ["[a-"]}]
            },
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_pattern"}
