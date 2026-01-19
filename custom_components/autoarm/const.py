"""The Auto Arm integration"""

import logging
from dataclasses import dataclass
from enum import StrEnum, auto

import voluptuous as vol
from homeassistant.components.alarm_control_panel.const import AlarmControlPanelState
from homeassistant.components.calendar import CalendarEvent
from homeassistant.const import (
    CONF_ALIAS,
    CONF_CONDITIONS,
    CONF_DELAY_TIME,
    CONF_ENTITY_ID,
    CONF_SERVICE,
    STATE_HOME,
    STATE_NOT_HOME,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "autoarm"

ATTR_ACTION = "action"
ATTR_RESET = "reset"
CONF_DATA = "data"
CONF_NOTIFY = "notify"
CONF_ALARM_PANEL = "alarm_panel"
CONF_ALARM_STATES = "alarm_states"

ALARM_STATES = [k.lower() for k in AlarmControlPanelState.__members__]

NO_CAL_EVENT_MODE_AUTO = "auto"
NO_CAL_EVENT_MODE_MANUAL = "manual"
NO_CAL_EVENT_OPTIONS: list[str] = [NO_CAL_EVENT_MODE_AUTO, NO_CAL_EVENT_MODE_MANUAL, *ALARM_STATES]

NOTIFY_COMMON = "common"
NOTIFY_QUIET = "quiet"
NOTIFY_NORMAL = "normal"
NOTIFY_CATEGORIES = [NOTIFY_COMMON, NOTIFY_QUIET, NOTIFY_NORMAL]

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

CONF_CALENDAR_CONTROL = "calendar_control"
CONF_CALENDARS = "calendars"
CONF_CALENDAR_POLL_INTERVAL = "poll_interval"
CONF_CALENDAR_EVENT_STATES = "state_patterns"
CONF_CALENDAR_NO_EVENT = "no_event_mode"
CALENDAR_SCHEMA = vol.Schema({
    vol.Required(CONF_ENTITY_ID): cv.entity_id,
    vol.Optional(CONF_ALIAS): cv.string,
    vol.Optional(CONF_CALENDAR_POLL_INTERVAL, default=30): cv.positive_int,
    vol.Optional(CONF_CALENDAR_EVENT_STATES, default=DEFAULT_CALENDAR_MAPPINGS): {
        vol.In(ALARM_STATES): vol.All(cv.ensure_list, [cv.string])
    },
})
CALENDAR_CONTROL_SCHEMA = vol.Schema({
    vol.Optional(CONF_CALENDAR_NO_EVENT, default=NO_CAL_EVENT_MODE_AUTO): vol.All(vol.Lower, vol.In(NO_CAL_EVENT_OPTIONS)),
    vol.Optional(CONF_CALENDARS, default=[]): vol.All(cv.ensure_list, [CALENDAR_SCHEMA]),
})

CONF_TRANSITIONS = "transitions"
TRANSITION_SCHEMA = vol.Schema({vol.Optional(CONF_ALIAS): cv.string, vol.Required(CONF_CONDITIONS): cv.CONDITIONS_SCHEMA})

CONF_BUTTONS = "buttons"
BUTTON_OPTIONS = [ATTR_RESET, *ALARM_STATES]
BUTTON_SCHEMA = vol.Schema({
    vol.Optional(CONF_ALIAS): cv.string,
    vol.Optional(CONF_DELAY_TIME): vol.All(cv.time_period, cv.positive_timedelta),
    vol.Required(CONF_ENTITY_ID): vol.All(cv.ensure_list, [cv.entity_id]),
})

CONF_RATE_LIMIT = "rate_limit"
CONF_RATE_LIMIT_CALLS = "max_calls"
CONF_RATE_LIMIT_PERIOD = "period"
RATE_LIMIT_SCHEMA = vol.Schema({
    vol.Optional(CONF_RATE_LIMIT_PERIOD, default=60): vol.All(cv.time_period, cv.positive_timedelta),
    vol.Optional(CONF_RATE_LIMIT_CALLS, default=6): cv.positive_int,
})

CONF_OCCUPANCY = "occupancy"
CONF_DAY = "day"
CONF_NIGHT = "night"
CONF_OCCUPANCY_DEFAULT = "default_state"
OCCUPANCY_SCHEMA = vol.Schema({
    vol.Required(CONF_ENTITY_ID, default=[]): vol.All(cv.ensure_list, [cv.entity_id]),
    vol.Optional(CONF_OCCUPANCY_DEFAULT, default={CONF_DAY: AlarmControlPanelState.ARMED_HOME}): {
        vol.In([CONF_DAY, CONF_NIGHT]): vol.In(ALARM_STATES)
    },
    vol.Optional(CONF_DELAY_TIME): {vol.In([STATE_HOME, STATE_NOT_HOME]): vol.All(cv.time_period, cv.positive_timedelta)},
})

CONF_DIURNAL = "diurnal"
CONF_SUNRISE = "sunrise"
CONF_EARLIEST = "earliest"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema({
            vol.Required(CONF_ALARM_PANEL): vol.Schema({
                vol.Optional(CONF_ALIAS): cv.string,
                vol.Required(CONF_ENTITY_ID): cv.entity_id,
            }),
            vol.Optional(CONF_DIURNAL): vol.Schema({
                vol.Optional(CONF_SUNRISE): vol.Schema({vol.Optional(CONF_EARLIEST): cv.time})
            }),
            vol.Optional(CONF_TRANSITIONS): {vol.In(ALARM_STATES): TRANSITION_SCHEMA},
            vol.Optional(CONF_CALENDAR_CONTROL): CALENDAR_CONTROL_SCHEMA,
            vol.Optional(CONF_BUTTONS): {vol.In(BUTTON_OPTIONS): BUTTON_SCHEMA},
            vol.Optional(CONF_OCCUPANCY, default={}): OCCUPANCY_SCHEMA,
            vol.Optional(CONF_NOTIFY, default={}): NOTIFY_SCHEMA,
            vol.Optional(CONF_RATE_LIMIT, default={}): RATE_LIMIT_SCHEMA,
        })
    },
    extra=vol.ALLOW_EXTRA,  # validation fails without this by trying to include all of HASS config
)

DEFAULT_TRANSITIONS: dict[str, str | list[str]] = {
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


@dataclass
class ConditionVariables:
    """Field with sub-fields added to the template context of Transition Conditions"""

    occupied: bool
    night: bool
    state: AlarmControlPanelState
    occupied_defaults: dict[str, AlarmControlPanelState]
    calendar_event: CalendarEvent | None = None
    at_home: list[str] | None = None
    not_home: list[str] | None = None

    def as_dict(self) -> ConfigType:
        """Generate the field to be exposed in the context, stringifying alarm states"""
        return {
            "daytime": not self.night,
            "occupied": self.occupied,
            "at_home": self.at_home or [],
            "not_home": self.at_home or [],
            "vacation": self.state == AlarmControlPanelState.ARMED_VACATION,
            "night": self.night,
            "bypass": self.state == AlarmControlPanelState.ARMED_CUSTOM_BYPASS,
            "manual": self.state in (AlarmControlPanelState.ARMED_VACATION, AlarmControlPanelState.ARMED_CUSTOM_BYPASS),
            "calendar_event": self.calendar_event,
            "state": str(self.state),
            "occupied_daytime_state": self.occupied_defaults.get(CONF_DAY, AlarmControlPanelState.ARMED_HOME),
            "disarmed": self.state == AlarmControlPanelState.DISARMED,
            "computed": not self.calendar_event
            and self.state not in (AlarmControlPanelState.ARMED_VACATION, AlarmControlPanelState.ARMED_CUSTOM_BYPASS),
        }


class ChangeSource(StrEnum):
    """Enumeration of all the known ways to trigger a state change"""

    CALENDAR = auto()
    MOBILE = auto()
    OCCUPANCY = auto()
    INTERNAL = auto()
    ALARM_PANEL = auto()
    BUTTON = auto()
    ACTION = auto()
    NOTIFY = auto()
    SUNRISE = auto()
    SUNSET = auto()
    ZOMBIFICATION = auto()
    STARTUP = auto()
