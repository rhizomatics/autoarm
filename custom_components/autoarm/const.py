"""The Auto Arm integration"""

import logging
from dataclasses import dataclass
from enum import StrEnum, auto
from typing import Any

import voluptuous as vol
from homeassistant.components.alarm_control_panel.const import AlarmControlPanelState
from homeassistant.components.calendar import CalendarEvent
from homeassistant.const import CONF_ALIAS, CONF_CONDITIONS, CONF_ENTITY_ID, CONF_SERVICE
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

DOMAIN = "autoarm"

ATTR_ACTION = "action"
CONF_DATA = "data"
CONF_NOTIFY = "notify"
CONF_ALARM_PANEL = "alarm_panel"
CONF_CALENDAR_CONTROL = "calendar_control"
CONF_CALENDARS = "calendars"
CONF_CALENDAR_POLL_INTERVAL = "poll_interval"
CONF_CALENDAR_EVENT_STATES = "state_patterns"
CONF_CALENDAR_NO_EVENT = "no_event_mode"
CONF_OCCUPIED_DAY_DEFAULT = "occupied_daytime_state"
CONF_CALENDAR_OCCUPANCY_OVERRIDE = "occupancy_override"
CONF_SUNRISE_CUTOFF = "sunrise_cutoff"
CONF_ARM_AWAY_DELAY = "arm_away_delay"
CONF_BUTTON_ENTITY_RESET = "reset_button"
CONF_BUTTON_ENTITY_AWAY = "away_button"
CONF_BUTTON_ENTITY_DISARM = "disarm_button"
CONF_OCCUPANTS = "occupants"
CONF_THROTTLE_SECONDS = "throttle_seconds"
CONF_THROTTLE_CALLS = "throttle_calls"
CONF_TRANSITIONS = "transitions"
CONF_ALARM_STATES = "alarm_states"

ALARM_STATES = [k.lower() for k in AlarmControlPanelState.__members__]

NO_CAL_EVENT_MODE_AUTO = "auto"
NO_CAL_EVENT_MODE_MANUAL = "manual"
NO_CAL_EVENT_OPTIONS: list[str] = [NO_CAL_EVENT_MODE_AUTO, NO_CAL_EVENT_MODE_MANUAL, *ALARM_STATES]

NOTIFY_COMMON = "common"
NOTIFY_QUIET = "quiet"
NOTIFY_NORMAL = "normal"
NOTIFY_CATEGORIES = [NOTIFY_COMMON, NOTIFY_QUIET, NOTIFY_NORMAL]

_LOGGER = logging.getLogger(__name__)

NOTIFY_DEF_SCHEMA = vol.Schema({vol.Optional(CONF_SERVICE): cv.service, vol.Optional(CONF_DATA): dict})

NOTIFY_SCHEMA = vol.Schema({
    vol.Optional(NOTIFY_COMMON): {vol.Required(CONF_SERVICE): cv.service, vol.Optional(CONF_DATA): dict},
    vol.Optional(NOTIFY_QUIET): NOTIFY_DEF_SCHEMA,
    vol.Optional(NOTIFY_NORMAL): NOTIFY_DEF_SCHEMA,
})

DEFAULT_CALENDAR_MAPPINGS = {
    AlarmControlPanelState.ARMED_AWAY: "Away",
    AlarmControlPanelState.DISARMED: "Disarmed",
    AlarmControlPanelState.ARMED_HOME: "Home",
    AlarmControlPanelState.ARMED_VACATION: "Vacation",
    AlarmControlPanelState.ARMED_VACATION: "Night",
}
CALENDAR_SCHEMA = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Optional(CONF_ALIAS): cv.string,
    vol.Optional(CONF_CALENDAR_POLL_INTERVAL, default=30): cv.positive_int,
    vol.Optional(CONF_CALENDAR_EVENT_STATES, default=DEFAULT_CALENDAR_MAPPINGS): dict[  # type: ignore
        vol.In(ALARM_STATES), vol.All(cv.ensure_list, [cv.string])
    ],
})
CALENDAR_CONTROL_SCHEMA = vol.Schema({
    vol.Optional(CONF_CALENDAR_NO_EVENT, default=NO_CAL_EVENT_MODE_AUTO): vol.All(vol.Lower, vol.In(NO_CAL_EVENT_OPTIONS)),
    vol.Optional(CONF_CALENDARS, default=[]): vol.All(cv.ensure_list, [CALENDAR_SCHEMA]),
})
TRANSITION_SCHEMA = vol.Schema({
    vol.Optional(CONF_ALIAS): cv.string,
    vol.Required(CONF_CONDITIONS): cv.CONDITIONS_SCHEMA
})

DEFAULT_TRANSITIONS: dict[str, Any] = {
    "armed_home": [
        "{{ autoarm.occupied and not autoarm.night }}",
        "{{ autoarm.computed and autoarm.occupied_daytime_state == 'armed_home'}}",
    ],
    "armed_away": "{{ not autoarm.occupied and autoarm.computed}}",
    "disarmed": [
        "{{ autoarm.occupied and not autoarm.night }}",
        "{{ autoarm.computed and autoarm.occupied_daytime_state == 'disarmed'}}",
    ],
    "armed_night": "{{ autoarm.occupied and autoarm.night and autoarm.computed}}",
    "armed_vacation": "{{ autoarm.vacation }}",
}


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema({
            vol.Required(CONF_ALARM_PANEL): cv.entity_id,
            vol.Optional(CONF_SUNRISE_CUTOFF): cv.time,
            vol.Optional(CONF_OCCUPIED_DAY_DEFAULT, default=AlarmControlPanelState.ARMED_HOME.value): vol.All(
                vol.In(ALARM_STATES)
            ),
            vol.Optional(CONF_TRANSITIONS): {vol.In(ALARM_STATES): TRANSITION_SCHEMA},
            vol.Optional(CONF_CALENDAR_CONTROL): CALENDAR_CONTROL_SCHEMA,
            vol.Optional(CONF_ARM_AWAY_DELAY, default=180): cv.positive_int,
            vol.Optional(CONF_BUTTON_ENTITY_RESET): cv.entity_id,
            vol.Optional(CONF_BUTTON_ENTITY_AWAY): cv.entity_id,
            vol.Optional(CONF_BUTTON_ENTITY_DISARM): cv.entity_id,
            vol.Optional(CONF_OCCUPANTS, default=[]): vol.All(cv.ensure_list, [cv.entity_id]),
            # type: ignore
            vol.Optional(CONF_NOTIFY, default={}): NOTIFY_SCHEMA,
            # type: ignore
            vol.Optional(CONF_THROTTLE_SECONDS, default=60): cv.positive_int,
            # type: ignore
            vol.Optional(CONF_THROTTLE_CALLS, default=6): cv.positive_int,
        })
    }
)


@dataclass
class ConditionVariables:
    occupied: bool | None = None
    night: bool | None = None
    state: AlarmControlPanelState | None = None
    calendar_event: CalendarEvent | None = None
    occupied_daytime_state: str | None = None

    def as_dict(self) -> ConfigType:
        return {
            "daytime": not self.night,
            "occupied": self.occupied,
            "vacation": self.state == AlarmControlPanelState.ARMED_VACATION,
            "night": self.night,
            "bypass": self.state == AlarmControlPanelState.ARMED_CUSTOM_BYPASS,
            "manual": self.state in (AlarmControlPanelState.ARMED_VACATION, AlarmControlPanelState.ARMED_CUSTOM_BYPASS),
            "calendar_event": self.calendar_event,
            "state": str(self.state),
            "occupied_daytime_state": self.occupied_daytime_state,
            "disarmed": self.state == AlarmControlPanelState.DISARMED,
            "computed": not self.calendar_event
            and self.state not in (AlarmControlPanelState.ARMED_VACATION, AlarmControlPanelState.ARMED_CUSTOM_BYPASS),
        }


class ChangeSource(StrEnum):
    CALENDAR = auto()
    MOBILE = auto()
    OCCUPANCY = auto()
    INTERNAL = auto()
    ALARM_PANEL = auto()
    BUTTON = auto()
    SUNRISE = auto()
    SUNSET = auto()
    ZOMBIFICATION = auto()
    STARTUP = auto()
