"""Tests for the Auto Arm config flow."""

from typing import Any

from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.autoarm.config_flow import (
    CONF_BEDTIME_ENTITIES,
    CONF_CALENDAR_ARMED_END_MODE,
    CONF_CALENDAR_DISARMED_END_MODE,
    CONF_CALENDAR_ENTITIES,
    CONF_CALENDAR_OCCUPANCY_OVERRIDE_STATES,
    CONF_NO_EVENT_MODE,
    CONF_NOTIFY_ACTION,
    CONF_NOTIFY_TARGETS,
    CONF_OCCUPANCY_DEFAULT_DAY,
    CONF_OCCUPANCY_DEFAULT_NIGHT,
    CONF_OCCUPIED_TRIGGER,
    CONF_PERSON_ENTITIES,
    CONF_SENTENCE_ARM,
    CONF_SENTENCE_DISARM,
    CONF_SUNRISE_EARLIEST,
    CONF_SUNRISE_TRIGGER,
    CONF_SUNSET_TRIGGER,
    CONF_UNOCCUPIED_TRIGGER,
    CONF_USE_ALARM_SERVICE,
    RECIPE_URL,
    SETUP_HELP_PLACEHOLDERS,
)
from custom_components.autoarm.const import (
    CONF_ALARM_PANEL,
    CONF_CALENDAR_CONTROL,
    CONF_CALENDAR_EVENT_STATES,
    CONF_CALENDAR_NO_EVENT,
    CONF_CALENDARS,
    CONF_OCCUPANCY,
    CONF_OCCUPANCY_DEFAULT,
    DOMAIN,
    YAML_DATA_KEY,
)


async def test_user_flow_complete(hass: HomeAssistant, mock_notify: Any) -> None:
    """Test the quick setup config flow, a single step set up for the recommended recipe."""
    hass.data[YAML_DATA_KEY] = {}

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "user"
    assert result["menu_options"] == ["quick_setup", "advanced_setup"]

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "quick_setup"})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "quick_setup"
    assert result["description_placeholders"] == SETUP_HELP_PLACEHOLDERS

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_ALARM_PANEL: "alarm_control_panel.home",
            CONF_BEDTIME_ENTITIES: ["binary_sensor.bedtime"],
            CONF_CALENDAR_ENTITIES: ["calendar.family", "calendar.work"],
            CONF_PERSON_ENTITIES: ["person.alice", "person.bob"],
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Auto Arm"
    assert result["data"] == {CONF_ALARM_PANEL: "alarm_control_panel.home"}
    assert result["options"][CONF_BEDTIME_ENTITIES] == ["binary_sensor.bedtime"]
    assert result["options"][CONF_CALENDAR_ENTITIES] == ["calendar.family", "calendar.work"]
    assert result["options"][CONF_PERSON_ENTITIES] == ["person.alice", "person.bob"]
    # the recommended recipe, disarmed by day and armed home from sunset until bedtime
    assert result["options"][CONF_OCCUPANCY_DEFAULT_DAY] == "disarmed"
    assert result["options"][CONF_OCCUPANCY_DEFAULT_NIGHT] == "armed_home"
    assert result["options"][CONF_CALENDAR_ARMED_END_MODE] == "auto"
    assert result["options"][CONF_CALENDAR_DISARMED_END_MODE] == "auto"


async def test_user_flow_minimal(hass: HomeAssistant, mock_notify: Any) -> None:
    """Test minimal user flow - alarm panel only, no bedtime sensor, calendars or persons."""
    hass.data[YAML_DATA_KEY] = {}

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "quick_setup"})

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ALARM_PANEL: "alarm_control_panel.home"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_ALARM_PANEL: "alarm_control_panel.home"}
    assert result["options"][CONF_BEDTIME_ENTITIES] == []
    assert result["options"][CONF_CALENDAR_ENTITIES] == []
    assert result["options"][CONF_PERSON_ENTITIES] == []


async def test_user_flow_preselects_known_persons(hass: HomeAssistant, mock_notify: Any) -> None:
    """Everyone known to Home Assistant is selected to start with, and kept if left alone."""
    hass.data[YAML_DATA_KEY] = {}
    hass.states.async_set("person.bob", "home")
    hass.states.async_set("person.alice", "not_home")

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "quick_setup"})
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_ALARM_PANEL: "alarm_control_panel.home"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"][CONF_PERSON_ENTITIES] == ["person.alice", "person.bob"]


async def test_user_flow_already_configured(hass: HomeAssistant, mock_notify: Any) -> None:
    """Test that a second config entry is aborted."""
    hass.data[YAML_DATA_KEY] = {}
    existing = MockConfigEntry(
        domain=DOMAIN,
        title="Auto Arm",
        data={CONF_ALARM_PANEL: "alarm_control_panel.home"},
        unique_id=DOMAIN,
    )
    existing.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_advanced_setup(hass: HomeAssistant, mock_notify: Any) -> None:
    """Advanced setup shows the full set of options up front, instead of the quick recipe's defaults."""
    hass.data[YAML_DATA_KEY] = {}

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "advanced_setup"})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "advanced_setup"
    assert result["description_placeholders"] == SETUP_HELP_PLACEHOLDERS
    data_schema = result["data_schema"]
    assert data_schema is not None
    assert CONF_ALARM_PANEL in data_schema.schema
    assert "notify_options" in data_schema.schema

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_ALARM_PANEL: "alarm_control_panel.home",
            CONF_BEDTIME_ENTITIES: [],
            CONF_CALENDAR_ENTITIES: [],
            CONF_PERSON_ENTITIES: [],
            "calendar_options": {},
            "time_of_day_options": {},
            "trigger_options": {CONF_SUNRISE_TRIGGER: "off", CONF_SUNSET_TRIGGER: "off"},
            "sunrise_options": {},
            "sunset_options": {},
            "assist_options": {CONF_SENTENCE_ARM: False, CONF_SENTENCE_DISARM: True},
            "advanced_options": {
                CONF_USE_ALARM_SERVICE: True,
                CONF_OCCUPANCY_DEFAULT_DAY: "disarmed",
                CONF_OCCUPANCY_DEFAULT_NIGHT: "armed_night",
                CONF_CALENDAR_ARMED_END_MODE: "manual",
                CONF_CALENDAR_DISARMED_END_MODE: "manual",
            },
            "notify_options": {CONF_NOTIFY_ACTION: "notify.supernotify", CONF_NOTIFY_TARGETS: []},
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_ALARM_PANEL: "alarm_control_panel.home"}
    assert result["options"][CONF_SENTENCE_ARM] is False
    assert result["options"][CONF_SENTENCE_DISARM] is True
    assert result["options"][CONF_CALENDAR_ARMED_END_MODE] == "manual"
    assert result["options"][CONF_CALENDAR_DISARMED_END_MODE] == "manual"
    assert result["options"][CONF_NOTIFY_ACTION] == "notify.supernotify"
    assert CONF_ALARM_PANEL not in result["options"]


async def test_import_flow(hass: HomeAssistant, mock_notify: Any) -> None:
    """Test YAML import creates correct config entry."""
    hass.data[YAML_DATA_KEY] = {}
    import_data: dict[str, Any] = {
        CONF_ALARM_PANEL: {CONF_ENTITY_ID: "alarm_control_panel.home"},
        CONF_OCCUPANCY: {
            CONF_ENTITY_ID: ["person.alice", "person.bob"],
            CONF_OCCUPANCY_DEFAULT: {"day": "disarmed", "night": "armed_night"},
        },
        CONF_CALENDAR_CONTROL: {
            CONF_CALENDAR_NO_EVENT: "manual",
            CONF_CALENDARS: [
                {
                    CONF_ENTITY_ID: "calendar.family",
                    CONF_CALENDAR_EVENT_STATES: {"armed_vacation": ["Holiday.*"]},
                },
            ],
        },
    }

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_IMPORT}, data=import_data)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_ALARM_PANEL: "alarm_control_panel.home"}
    assert result["options"][CONF_PERSON_ENTITIES] == ["person.alice", "person.bob"]
    assert result["options"][CONF_CALENDAR_ENTITIES] == ["calendar.family"]
    assert result["options"][CONF_OCCUPANCY_DEFAULT_DAY] == "disarmed"
    assert result["options"][CONF_OCCUPANCY_DEFAULT_NIGHT] == "armed_night"
    assert result["options"][CONF_CALENDAR_ARMED_END_MODE] == "manual"
    assert result["options"][CONF_CALENDAR_DISARMED_END_MODE] == "manual"


async def test_import_flow_already_configured(hass: HomeAssistant, mock_notify: Any) -> None:
    """Test YAML import aborts when config entry already exists."""
    hass.data[YAML_DATA_KEY] = {}
    existing = MockConfigEntry(
        domain=DOMAIN,
        title="Auto Arm",
        data={CONF_ALARM_PANEL: "alarm_control_panel.home"},
        unique_id=DOMAIN,
    )
    existing.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_ALARM_PANEL: {CONF_ENTITY_ID: "alarm_control_panel.other"},
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow(hass: HomeAssistant, setup_autoarm: MockConfigEntry) -> None:
    """Test options flow updates entry options."""
    entry = setup_autoarm

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["description_placeholders"] == {"recipe_url": RECIPE_URL}
    data_schema = result["data_schema"]
    assert data_schema is not None
    # the bedtime sensor is asked for up front, the other states have their own section
    assert CONF_BEDTIME_ENTITIES in data_schema.schema
    time_of_day_section = data_schema.schema["time_of_day_options"].schema.schema
    assert CONF_BEDTIME_ENTITIES not in time_of_day_section
    assert "time_of_day_armed_home" in time_of_day_section

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_ALARM_PANEL: "alarm_control_panel.new_panel",
            CONF_BEDTIME_ENTITIES: ["binary_sensor.bedtime"],
            CONF_CALENDAR_ENTITIES: ["calendar.holidays"],
            CONF_PERSON_ENTITIES: ["person.new_person"],
            "calendar_options": {
                CONF_CALENDAR_OCCUPANCY_OVERRIDE_STATES: ["armed_home", "disarmed"],
            },
            "time_of_day_options": {"time_of_day_armed_home": ["binary_sensor.evening"]},
            "notify_options": {
                CONF_NOTIFY_ACTION: "notify.supernotify",
                CONF_NOTIFY_TARGETS: ["mobile_app_phone"],
            },
            "assist_options": {CONF_SENTENCE_ARM: False, CONF_SENTENCE_DISARM: True},
            "trigger_options": {CONF_SUNSET_TRIGGER: "off", CONF_UNOCCUPIED_TRIGGER: False},
            "sunrise_options": {CONF_SUNRISE_EARLIEST: "05:30:00"},
            "sunset_options": {},
            "advanced_options": {
                CONF_USE_ALARM_SERVICE: True,
                CONF_OCCUPANCY_DEFAULT_DAY: "disarmed",
                CONF_OCCUPANCY_DEFAULT_NIGHT: "armed_night",
                CONF_CALENDAR_ARMED_END_MODE: "auto_occupancy",
                CONF_CALENDAR_DISARMED_END_MODE: "manual",
            },
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    assert entry.data[CONF_ALARM_PANEL] == "alarm_control_panel.new_panel"
    assert entry.options[CONF_USE_ALARM_SERVICE] is True
    assert entry.options[CONF_SENTENCE_ARM] is False
    assert entry.options[CONF_SENTENCE_DISARM] is True
    assert CONF_ALARM_PANEL not in entry.options
    assert entry.options[CONF_CALENDAR_ENTITIES] == ["calendar.holidays"]
    assert entry.options[CONF_PERSON_ENTITIES] == ["person.new_person"]
    assert entry.options[CONF_OCCUPANCY_DEFAULT_DAY] == "disarmed"
    assert entry.options[CONF_OCCUPANCY_DEFAULT_NIGHT] == "armed_night"
    assert entry.options[CONF_CALENDAR_ARMED_END_MODE] == "auto_occupancy"
    assert entry.options[CONF_CALENDAR_DISARMED_END_MODE] == "manual"
    assert entry.options[CONF_SUNRISE_TRIGGER] == "auto"
    assert entry.options[CONF_SUNSET_TRIGGER] == "off"
    assert entry.options[CONF_OCCUPIED_TRIGGER] is True
    assert entry.options[CONF_UNOCCUPIED_TRIGGER] is False
    assert entry.options[CONF_CALENDAR_OCCUPANCY_OVERRIDE_STATES] == ["armed_home", "disarmed"]
    assert entry.options[CONF_BEDTIME_ENTITIES] == ["binary_sensor.bedtime"]
    assert entry.options["time_of_day_armed_home"] == ["binary_sensor.evening"]
    assert entry.options["time_of_day_disarmed"] == []
    assert "time_of_day_armed_vacation" not in entry.options
    assert entry.options[CONF_NOTIFY_ACTION] == "notify.supernotify"
    assert entry.options[CONF_NOTIFY_TARGETS] == ["mobile_app_phone"]
    assert entry.options[CONF_SUNRISE_EARLIEST] == "05:30:00"


async def test_options_flow_offers_supernotify_action(hass: HomeAssistant, setup_autoarm: MockConfigEntry) -> None:
    """supernotify.notify is offered as the notification action when Supernotify provides it."""
    hass.services.async_register("supernotify", "notify", lambda _call: None)

    result = await hass.config_entries.options.async_init(setup_autoarm.entry_id)

    data_schema = result["data_schema"]
    assert data_schema is not None
    notify_section = data_schema.schema["notify_options"].schema.schema
    action_selector = next(v for k, v in notify_section.items() if k == CONF_NOTIFY_ACTION)
    assert action_selector.config["options"][0] == "supernotify.notify"


async def test_options_flow_without_supernotify_action(hass: HomeAssistant, setup_autoarm: MockConfigEntry) -> None:
    result = await hass.config_entries.options.async_init(setup_autoarm.entry_id)

    data_schema = result["data_schema"]
    assert data_schema is not None
    notify_section = data_schema.schema["notify_options"].schema.schema
    action_selector = next(v for k, v in notify_section.items() if k == CONF_NOTIFY_ACTION)
    assert "supernotify.notify" not in action_selector.config["options"]


async def test_migrate_no_event_mode_to_end_modes(hass: HomeAssistant, mock_notify: Any) -> None:
    """Entries from before the split carry their no_event_mode over to both armed and disarmed end modes."""
    hass.data[YAML_DATA_KEY] = {}
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        minor_version=1,
        data={CONF_ALARM_PANEL: "alarm_control_panel.test_panel"},
        options={CONF_NO_EVENT_MODE: "manual"},
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.minor_version == 2
    assert CONF_NO_EVENT_MODE not in entry.options
    assert entry.options[CONF_CALENDAR_ARMED_END_MODE] == "manual"
    assert entry.options[CONF_CALENDAR_DISARMED_END_MODE] == "manual"
