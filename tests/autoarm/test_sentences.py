"""Sentences for Home Assistant's built-in conversation agent (sentences.py)

The agent itself needs hassil and the rest of the voice stack, so it isn't run here - the
commands are called directly, and the trigger registration is checked with it patched.
"""

import datetime as dt
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, Mock, patch

import homeassistant.util.dt as dt_util
from homeassistant.components.alarm_control_panel.const import AlarmControlPanelState
from homeassistant.components.calendar import CalendarEvent
from homeassistant.core import Context, HomeAssistant, ServiceCall
from pytest_homeassistant_custom_component.common import MockConfigEntry

from conftest import TEST_PANEL
from custom_components.autoarm.autoarming import AlarmArmer
from custom_components.autoarm.config_flow import CONF_SENTENCE_COMMANDS
from custom_components.autoarm.const import CONF_ALARM_PANEL, DOMAIN, YAML_DATA_KEY, ChangeSource
from custom_components.autoarm.sentences import SENTENCES, async_respond, explain

if TYPE_CHECKING:
    from freezegun.api import FrozenDateTimeFactory

USER_ID = "jey-user-id"


async def _panel_starts(hass: HomeAssistant, armer: AlarmArmer, state: str) -> None:
    """Set the panel's starting state, without it counting as someone changing it"""
    hass.states.async_set(TEST_PANEL, state)
    await hass.async_block_till_done()
    armer.interventions.clear()


async def test_arm_away(hass: HomeAssistant, autoarmer: AlarmArmer) -> None:
    await _panel_starts(hass, autoarmer, "disarmed")

    response = await async_respond(autoarmer, "armed_away", Context(user_id=USER_ID))

    assert response == "The alarm is now armed away"
    assert autoarmer.armed_state() == AlarmControlPanelState.ARMED_AWAY
    [intervention] = autoarmer.interventions
    assert intervention.source == ChangeSource.VOICE
    assert intervention.state == AlarmControlPanelState.ARMED_AWAY
    assert autoarmer.last_change is not None
    assert autoarmer.last_change.source == ChangeSource.VOICE
    assert autoarmer.last_change.context["user_id"] == USER_ID


async def test_disarm(hass: HomeAssistant, autoarmer: AlarmArmer) -> None:
    await _panel_starts(hass, autoarmer, "armed_night")

    assert await async_respond(autoarmer, "disarmed", Context()) == "The alarm is now disarmed"
    assert autoarmer.armed_state() == AlarmControlPanelState.DISARMED


async def test_already_in_state(hass: HomeAssistant, autoarmer: AlarmArmer) -> None:
    await _panel_starts(hass, autoarmer, "armed_night")

    assert await async_respond(autoarmer, "armed_night", Context()) == "The alarm is already armed for the night"
    assert autoarmer.interventions == []


async def test_arm_refused(hass: HomeAssistant, autoarmer: AlarmArmer) -> None:
    await _panel_starts(hass, autoarmer, "disarmed")
    autoarmer.arming_in_progress.set()

    assert await async_respond(autoarmer, "armed_home", Context()) == "Sorry, the alarm couldn't be armed home"
    assert autoarmer.armed_state() == AlarmControlPanelState.DISARMED


async def test_arm_with_exit_delay(hass: HomeAssistant) -> None:
    async def start_arming(_call: ServiceCall) -> None:
        hass.states.async_set(TEST_PANEL, "arming")

    hass.services.async_register("alarm_control_panel", "alarm_arm_vacation", start_arming)
    hass.states.async_set(TEST_PANEL, "disarmed")
    armer = AlarmArmer(hass, TEST_PANEL, use_alarm_service=True)

    response = await async_respond(armer, "armed_vacation", Context())

    assert response == "The alarm is arming, and will be armed for vacation after the exit delay"


async def test_unknown_command(autoarmer: AlarmArmer) -> None:
    assert "doesn't know" in await async_respond(autoarmer, "dance", Context())


async def test_why_before_any_change(hass: HomeAssistant) -> None:
    hass.states.async_set(TEST_PANEL, "disarmed")
    armer = AlarmArmer(hass, TEST_PANEL)

    assert await async_respond(armer, "why", Context()) == (
        "The alarm is disarmed. AutoArm hasn't changed it since Home Assistant started."
    )


async def test_why_after_occupancy_change(hass: HomeAssistant, autoarmer: AlarmArmer, day: None, unoccupied: None) -> None:
    await _panel_starts(hass, autoarmer, "disarmed")
    await autoarmer.reset_armed_state(source=ChangeSource.OCCUPANCY)
    when = dt_util.now().strftime("%H:%M")

    assert explain(autoarmer) == (
        f"The alarm is armed away. AutoArm set it to armed away at {when} after a change in who's home."
        " Everyone was out, and it was daytime."
    )


async def test_why_after_sunset_without_occupants(hass: HomeAssistant, night: None) -> None:
    hass.states.async_set(TEST_PANEL, "disarmed")
    armer = AlarmArmer(hass, TEST_PANEL)
    await armer.arm(AlarmControlPanelState.ARMED_NIGHT, source=ChangeSource.SUNSET)

    assert explain(armer).endswith("at sunset. It was night.")


async def test_why_after_calendar_event(hass: HomeAssistant, autoarmer: AlarmArmer) -> None:
    await _panel_starts(hass, autoarmer, "disarmed")
    await autoarmer.arm(
        AlarmControlPanelState.ARMED_VACATION, source=ChangeSource.CALENDAR, change_context={"summary": "Skiing"}
    )

    assert "set it to armed for vacation at" in explain(autoarmer)
    assert explain(autoarmer).endswith("for the calendar event Skiing.")


async def test_why_after_calendar_event_ended(hass: HomeAssistant, autoarmer: AlarmArmer) -> None:
    await _panel_starts(hass, autoarmer, "armed_vacation")
    await autoarmer.arm(
        AlarmControlPanelState.DISARMED, source=ChangeSource.CALENDAR, change_context={"no_event_mode": "disarmed"}
    )

    assert explain(autoarmer).endswith("because the calendar event ended.")


async def test_why_without_known_source(hass: HomeAssistant, autoarmer: AlarmArmer) -> None:
    await _panel_starts(hass, autoarmer, "disarmed")
    await autoarmer.arm(AlarmControlPanelState.ARMED_HOME)
    when = dt_util.now().strftime("%H:%M")

    assert explain(autoarmer) == f"The alarm is armed home. AutoArm set it to armed home at {when}."


async def test_why_after_panel_change(hass: HomeAssistant, autoarmer: AlarmArmer) -> None:
    await _panel_starts(hass, autoarmer, "disarmed")
    await autoarmer.arm(AlarmControlPanelState.ARMED_AWAY, source=ChangeSource.OCCUPANCY)
    hass.states.async_set(TEST_PANEL, "disarmed")
    await hass.async_block_till_done()

    assert "It was changed on the alarm panel at" in explain(autoarmer)
    assert explain(autoarmer).endswith(", not by AutoArm.")


async def test_why_after_forgotten_outside_change(hass: HomeAssistant, autoarmer: AlarmArmer) -> None:
    await _panel_starts(hass, autoarmer, "disarmed")
    await autoarmer.arm(AlarmControlPanelState.ARMED_AWAY, source=ChangeSource.OCCUPANCY)
    hass.states.async_set(TEST_PANEL, "armed_home")
    await hass.async_block_till_done()
    autoarmer.interventions.clear()  # expired by housekeeping

    assert "It was changed outside AutoArm. AutoArm last set it to armed away at" in explain(autoarmer)


async def test_why_on_another_day(hass: HomeAssistant, autoarmer: AlarmArmer, freezer: "FrozenDateTimeFactory") -> None:
    freezer.move_to(dt_util.as_utc(dt.datetime(2026, 9, 24, 18, 30, tzinfo=dt_util.get_default_time_zone())))
    await _panel_starts(hass, autoarmer, "disarmed")
    await autoarmer.arm(AlarmControlPanelState.ARMED_AWAY, source=ChangeSource.BUTTON)
    freezer.move_to(dt_util.as_utc(dt.datetime(2026, 9, 25, 9, 0, tzinfo=dt_util.get_default_time_zone())))

    assert "at 18:30 on Thursday 24 September when a button was pressed." in explain(autoarmer)


async def test_why_mentions_active_calendar_event(hass: HomeAssistant, autoarmer: AlarmArmer) -> None:
    await _panel_starts(hass, autoarmer, "armed_away")
    end = dt_util.now().replace(hour=23, minute=0)
    event = CalendarEvent(start=dt_util.now(), end=end, summary="Away for the day")
    with patch.object(autoarmer, "active_calendar_event", return_value=Mock(event=event)):
        assert explain(autoarmer).endswith("The calendar event Away for the day is in control until 23:00.")


async def _setup(hass: HomeAssistant, sentence_commands: bool) -> MockConfigEntry:
    hass.states.async_set(TEST_PANEL, "disarmed")
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_ALARM_PANEL: TEST_PANEL}, options={CONF_SENTENCE_COMMANDS: sentence_commands}
    )
    entry.add_to_hass(hass)
    hass.data[YAML_DATA_KEY] = {}
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_sentences_not_registered_unless_switched_on(hass: HomeAssistant) -> None:
    with patch("custom_components.autoarm.sentences.async_initialize_triggers") as initialize:
        await _setup(hass, sentence_commands=False)

    initialize.assert_not_called()


async def test_sentences_registered_and_answer(hass: HomeAssistant) -> None:
    remove = Mock()
    initialize = AsyncMock(return_value=remove)

    async def validate(_hass: HomeAssistant, config: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return config

    with (
        patch("custom_components.autoarm.sentences.async_validate_trigger_config", side_effect=validate),
        patch("custom_components.autoarm.sentences.async_initialize_triggers", initialize),
    ):
        entry = await _setup(hass, sentence_commands=True)

    configs: list[dict[str, Any]] = initialize.call_args.args[1]
    assert {c["id"]: c["command"] for c in configs} == SENTENCES
    assert all(c["platform"] == "conversation" for c in configs)

    action = initialize.call_args.args[2]
    result = await action({
        "trigger": {"id": "armed_night", "user_input": {"context": {"id": "abc", "user_id": USER_ID}}},
    })
    assert result.conversation_response == "The alarm is now armed for the night"
    assert hass.states.get(TEST_PANEL).state == "armed_night"  # type: ignore[union-attr]

    assert await hass.config_entries.async_unload(entry.entry_id)
    remove.assert_called_once()


async def test_sentences_not_registered_when_conversation_unavailable(hass: HomeAssistant) -> None:
    with (
        patch(
            "custom_components.autoarm.sentences.async_validate_trigger_config",
            side_effect=ImportError("No module named 'hassil'"),
        ),
        patch("custom_components.autoarm.sentences.async_initialize_triggers") as initialize,
    ):
        await _setup(hass, sentence_commands=True)

    initialize.assert_not_called()
