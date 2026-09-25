"""Voice and chat commands for Home Assistant's built-in conversation agent - beta.

The built-in agent doesn't use an AI model, it matches fixed sentences, so AutoArm registers a few
of its own, the same way an automation with a conversation trigger does. These take priority over
the built-in agent's own alarm sentences, so a change by voice counts as a manual intervention.
English only for now, and switched on in the options.
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.alarm_control_panel.const import AlarmControlPanelState
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.core import Context as HAContext
from homeassistant.helpers.script import ScriptRunResult
from homeassistant.helpers.trigger import async_initialize_triggers, async_validate_trigger_config
from homeassistant.util import dt as dt_util

from .const import DOMAIN, ChangeSource
from .helpers import alarm_state_as_enum

if TYPE_CHECKING:
    from .autoarming import AlarmArmer, StateChange

_LOGGER = logging.getLogger(__name__)

# hassil sentence templates - (a|b) is a choice, [a] is optional
ALARM = "[the] (alarm|security system|burglar alarm)"
SENTENCES: dict[str, list[str]] = {
    AlarmControlPanelState.ARMED_AWAY: [f"arm {ALARM}", f"arm {ALARM} [in|to] away [mode]", f"set {ALARM} to away [mode]"],
    AlarmControlPanelState.ARMED_HOME: [f"arm {ALARM} [in|to] home [mode]", f"set {ALARM} to home [mode]"],
    AlarmControlPanelState.ARMED_NIGHT: [f"arm {ALARM} [in|to|for] [the] night [mode]", f"set {ALARM} to night [mode]"],
    AlarmControlPanelState.ARMED_VACATION: [
        f"arm {ALARM} [in|to|for] (vacation|holiday) [mode]",
        f"set {ALARM} to (vacation|holiday) [mode]",
    ],
    AlarmControlPanelState.DISARMED: [f"disarm {ALARM}"],
    "why": [
        f"why is {ALARM} [armed|disarmed|on|off|set] [to] [away|home|night|vacation]",
        f"why (was|has) {ALARM} [been] (armed|disarmed|changed|set)",
        f"(what|who) (armed|disarmed|changed|set) {ALARM}",
    ],
}

SPOKEN_STATES: dict[AlarmControlPanelState, str] = {
    AlarmControlPanelState.ARMED_AWAY: "armed away",
    AlarmControlPanelState.ARMED_HOME: "armed home",
    AlarmControlPanelState.ARMED_NIGHT: "armed for the night",
    AlarmControlPanelState.ARMED_VACATION: "armed for vacation",
    AlarmControlPanelState.ARMED_CUSTOM_BYPASS: "armed with custom bypass",
}

SPOKEN_SOURCES: dict[ChangeSource, str] = {
    ChangeSource.CALENDAR: "from the calendar",
    ChangeSource.MOBILE: "from a mobile notification action",
    ChangeSource.OCCUPANCY: "after a change in who's home",
    ChangeSource.BUTTON: "when a button was pressed",
    ChangeSource.ACTION: "from the reset action",
    ChangeSource.SUNRISE: "at sunrise",
    ChangeSource.SUNSET: "at sunset",
    ChangeSource.ZOMBIFICATION: "because the panel had become unavailable",
    ChangeSource.VOICE: "by a voice command",
    ChangeSource.STARTUP: "when it started up",
}
# changes worked out from who's home and the time of day, so worth saying what those were
COMPUTED_SOURCES = (ChangeSource.OCCUPANCY, ChangeSource.SUNRISE, ChangeSource.SUNSET, ChangeSource.STARTUP)


async def async_register_sentences(hass: HomeAssistant, armer: AlarmArmer) -> CALLBACK_TYPE | None:
    """Register the sentences with the built-in conversation agent, returning how to remove them"""

    async def action(run_variables: dict[str, Any], _context: HAContext | None = None) -> ScriptRunResult:
        trigger: dict[str, Any] = run_variables["trigger"]
        response = await async_respond(armer, trigger["id"], _requester(trigger))
        return ScriptRunResult(conversation_response=response, service_response=None, variables={})

    try:
        config = await async_validate_trigger_config(
            hass,
            [
                {"platform": "conversation", "id": str(command), "command": sentences}
                for command, sentences in SENTENCES.items()
            ],
        )
    except Exception as e:
        _LOGGER.warning("AUTOARM Unable to register sentences with the built-in conversation agent: %s", e)
        return None
    return await async_initialize_triggers(hass, config, action, DOMAIN, "AutoArm sentences", _log)


def _log(level: int, msg: str, **kwargs: Any) -> None:
    _LOGGER.log(level, "AUTOARM Sentences: %s", msg, **kwargs)


def _requester(trigger: dict[str, Any]) -> HAContext:
    """The context of the conversation, so a change can be linked to who asked"""
    context: dict[str, Any] = (trigger.get("user_input") or {}).get("context") or {}
    return HAContext(user_id=context.get("user_id"), parent_id=context.get("id"))


async def async_respond(armer: AlarmArmer, command: str, context: HAContext) -> str:
    """Carry out a command, returning what to say back"""
    if command == "why":
        return explain(armer)
    state: AlarmControlPanelState | None = alarm_state_as_enum(command)
    if state is None:
        return f"AutoArm doesn't know the command {command}"
    if armer.armed_state() == state:
        return f"The alarm is already {_say(state)}"
    armer.record_intervention(source=ChangeSource.VOICE, state=state)
    new_state = await armer.arm(
        state, source=ChangeSource.VOICE, change_context={"caller": "sentences", "user_id": context.user_id}
    )
    if new_state is None:
        return f"Sorry, the alarm couldn't be {_say(state)}"
    if armer.armed_state() == AlarmControlPanelState.ARMING:
        return f"The alarm is arming, and will be {_say(state)} after the exit delay"
    return f"The alarm is now {_say(state)}"


def explain(armer: AlarmArmer) -> str:
    """Why the alarm is in its current state, as far as AutoArm knows"""
    state: AlarmControlPanelState = armer.armed_state()
    change: StateChange | None = armer.last_change
    intervention = armer.last_state_intervention()
    reply = [f"The alarm is {_say(state)}."]

    if (
        intervention is not None
        and intervention.source == ChangeSource.ALARM_PANEL
        and intervention.state == state
        and (change is None or intervention.created_at >= change.created_at)
    ):
        reply.append(f"It was changed on the alarm panel at {_when(intervention.created_at)}, not by AutoArm.")
    elif change is not None and (change.to_state == state or state == AlarmControlPanelState.ARMING):
        reason = _reason(change)
        reply.append(
            f"AutoArm set it to {_say(change.to_state)} at {_when(change.created_at)}{' ' + reason if reason else ''}."
        )
        if change.source in COMPUTED_SOURCES:
            reply.append(_situation(change))
    elif change is not None:
        reply.append(
            f"It was changed outside AutoArm. AutoArm last set it to {_say(change.to_state)} at {_when(change.created_at)}."
        )
    else:
        reply.append("AutoArm hasn't changed it since Home Assistant started.")

    active = armer.active_calendar_event()
    if active is not None:
        reply.append(f"The calendar event {active.event.summary} is in control until {_when(active.event.end_datetime_local)}.")
    return " ".join(reply)


def _say(state: AlarmControlPanelState) -> str:
    return SPOKEN_STATES.get(state, str(state).replace("_", " "))


def _when(at: dt.datetime) -> str:
    local = dt_util.as_local(at)
    if local.date() == dt_util.now().date():
        return local.strftime("%H:%M")
    return local.strftime("%H:%M on %A %d %B")


def _reason(change: StateChange) -> str:
    if change.source == ChangeSource.CALENDAR:
        if change.context.get("summary"):
            return f"for the calendar event {change.context['summary']}"
        if change.context.get("no_event_mode"):
            return "because the calendar event ended"
    return SPOKEN_SOURCES.get(change.source, "") if change.source else ""


def _situation(change: StateChange) -> str:
    time_of_day = "night" if change.night else "daytime"
    if change.occupied is None:
        return f"It was {time_of_day}."
    who = "Someone was home" if change.occupied else "Everyone was out"
    return f"{who}, and it was {time_of_day}."
