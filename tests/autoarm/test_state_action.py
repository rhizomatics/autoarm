"""Actions run on each change of alarm state, chosen in the options"""

from typing import Any
from unittest.mock import Mock

from homeassistant.core import Context, HomeAssistant, ServiceCall
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError

from custom_components.autoarm.config_flow import CONF_STATE_ACTION
from custom_components.autoarm.const import CONF_ALARM_PANEL, DOMAIN
from custom_components.autoarm.helpers import AppHealthTracker
from custom_components.autoarm.state_action import async_track_state_action
from tests.ha_testing import MockConfigEntry, MockUser

PANEL = "alarm_control_panel.testing"
DISPLAY_ACTION: list[dict[str, Any]] = [
    {
        "action": "test.display",
        "data": {
            "panel": "{{ alarm_panel }}",
            "from": "{{ from_state }}",
            "to": "{{ to_state }}",
            "text": "Alarm {{ friendly_state }}",
        },
    }
]


def _record_calls(hass: HomeAssistant, fail: bool = False) -> list[ServiceCall]:
    calls: list[ServiceCall] = []

    async def record(call: ServiceCall) -> None:
        calls.append(call)
        if fail:
            raise HomeAssistantError("display offline")

    hass.services.async_register("test", "display", record)
    return calls


async def test_runs_action_with_state_variables(hass: HomeAssistant) -> None:
    calls = _record_calls(hass)
    hass.states.async_set(PANEL, "disarmed")
    unsubscribe = await async_track_state_action(hass, PANEL, DISPLAY_ACTION, Mock(spec=AppHealthTracker))
    assert unsubscribe is not None

    hass.states.async_set(PANEL, "armed_vacation")
    await hass.async_block_till_done()

    assert [call.data for call in calls] == [
        {"panel": PANEL, "from": "disarmed", "to": "armed_vacation", "text": "Alarm Armed Vacation"}
    ]
    unsubscribe()
    hass.states.async_set(PANEL, "disarmed")
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_runs_as_no_user_linked_to_change(hass: HomeAssistant, hass_read_only_user: MockUser) -> None:
    calls = _record_calls(hass)
    hass.states.async_set(PANEL, "disarmed")
    unsubscribe = await async_track_state_action(hass, PANEL, DISPLAY_ACTION, Mock(spec=AppHealthTracker))
    assert unsubscribe is not None

    change = Context(user_id=hass_read_only_user.id)
    hass.states.async_set(PANEL, "armed_away", context=change)
    await hass.async_block_till_done()

    assert calls[0].context.user_id is None
    assert calls[0].context.parent_id == change.id
    unsubscribe()


async def test_skips_attribute_changes_and_unavailable(hass: HomeAssistant) -> None:
    calls = _record_calls(hass)
    hass.states.async_set(PANEL, "disarmed")
    unsubscribe = await async_track_state_action(hass, PANEL, DISPLAY_ACTION, Mock(spec=AppHealthTracker))
    assert unsubscribe is not None

    hass.states.async_set(PANEL, "disarmed", {"changed_by": "someone"})
    hass.states.async_set(PANEL, "unavailable")
    await hass.async_block_till_done()
    assert calls == []

    # back from unavailable is a change worth showing
    hass.states.async_set(PANEL, "armed_home")
    await hass.async_block_till_done()
    assert [call.data["from"] for call in calls] == ["unavailable"]
    unsubscribe()


async def test_invalid_action_not_run(hass: HomeAssistant) -> None:
    tracker = Mock(spec=AppHealthTracker)
    assert await async_track_state_action(hass, PANEL, [{"action": "not a service"}], tracker) is None
    tracker.record_initialization_error.assert_called_once_with("state_action")


async def test_failing_action_recorded(hass: HomeAssistant) -> None:
    calls = _record_calls(hass, fail=True)
    tracker = Mock(spec=AppHealthTracker)
    hass.states.async_set(PANEL, "disarmed")
    unsubscribe = await async_track_state_action(hass, PANEL, DISPLAY_ACTION, tracker)
    assert unsubscribe is not None

    hass.states.async_set(PANEL, "armed_away")
    await hass.async_block_till_done()

    assert len(calls) == 1
    tracker.record_runtime_error.assert_called_once()
    unsubscribe()


async def test_action_from_options_runs(hass: HomeAssistant, mock_notify: Any) -> None:
    calls = _record_calls(hass)
    hass.states.async_set(PANEL, "disarmed")
    entry = MockConfigEntry(
        domain=DOMAIN, title="Auto Arm", data={CONF_ALARM_PANEL: PANEL}, options={CONF_STATE_ACTION: DISPLAY_ACTION}
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data.state_action == DISPLAY_ACTION

    hass.states.async_set(PANEL, "armed_night")
    await hass.async_block_till_done()

    # autoarm's own change on starting up is shown as well as the one made outside it
    assert [call.data["to"] for call in calls] == ["armed_home", "armed_night"]


async def test_options_flow_rejects_invalid_action(
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
        "calendar_options": {},
        "advanced_options": {CONF_STATE_ACTION: [{"action": "not a service"}]},
    }

    result = await hass.config_entries.options.async_configure(result["flow_id"], user_input)

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_action"}
    assert CONF_STATE_ACTION not in setup_autoarm.options

    user_input["advanced_options"][CONF_STATE_ACTION] = DISPLAY_ACTION
    result = await hass.config_entries.options.async_configure(result["flow_id"], user_input)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert setup_autoarm.options[CONF_STATE_ACTION] == DISPLAY_ACTION
