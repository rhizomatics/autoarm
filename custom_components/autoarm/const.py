"""The Auto Arm integration"""

import logging

import voluptuous as vol
from homeassistant.const import CONF_ICON, CONF_SERVICE
from homeassistant.helpers import config_validation as cv

DOMAIN = "autoarm"

CONF_ACTIONS = "actions"
CONF_ACTION = "action"
CONF_ACTION_TEMPLATE = "action_template"
CONF_TITLE_TEMPLATE = "title_template"
CONF_DATA = "data"
CONF_TITLE = "title"
CONF_URI = "uri"
CONF_NOTIFY = "notify"
CONF_ALARM_PANEL = "alarm_panel"
CONF_AUTO_ARM = "auto_arm"
CONF_SLEEP_START = "sleep_start"
CONF_SLEEP_END = "sleep_end"
CONF_SUNRISE_CUTOFF = "sunrise_cutoff"
CONF_ARM_AWAY_DELAY = "arm_away_delay"
CONF_BUTTON_ENTITY_RESET = "reset_button"
CONF_BUTTON_ENTITY_AWAY = "away_button"
CONF_BUTTON_ENTITY_DISARM = "disarm_button"
CONF_OCCUPANTS = "occupants"
CONF_THROTTLE_SECONDS = "throttle_seconds"
CONF_THROTTLE_CALLS = "throttle_calls"

NOTIFY_COMMON = "common"
NOTIFY_QUIET = "quiet"
NOTIFY_NORMAL = "normal"
NOTIFY_CATEGORIES = [NOTIFY_COMMON, NOTIFY_QUIET, NOTIFY_NORMAL]

_LOGGER = logging.getLogger(__name__)

PUSH_ACTION_SCHEMA = vol.Schema(
    {
        vol.Exclusive(CONF_ACTION, CONF_ACTION_TEMPLATE): cv.string,
        vol.Exclusive(CONF_TITLE, CONF_TITLE_TEMPLATE): cv.string,
        vol.Optional(CONF_URI): cv.url,
        vol.Optional(CONF_ICON): cv.string,
    },
    extra=vol.ALLOW_EXTRA,
)

NOTIFY_DEF_SCHEMA = vol.Schema({vol.Optional(CONF_SERVICE): cv.service, vol.Optional(CONF_DATA): dict})

NOTIFY_SCHEMA = vol.Schema({
    vol.Optional(NOTIFY_COMMON): {vol.Required(CONF_SERVICE): cv.service, vol.Optional(CONF_DATA): dict},
    vol.Optional(NOTIFY_QUIET): NOTIFY_DEF_SCHEMA,
    vol.Optional(NOTIFY_NORMAL): NOTIFY_DEF_SCHEMA,
})

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema({
            vol.Required(CONF_ALARM_PANEL): cv.entity_id,
            vol.Optional(CONF_AUTO_ARM, default=True): cv.boolean,  # type: ignore
            vol.Optional(CONF_SLEEP_START): cv.time,
            vol.Optional(CONF_SLEEP_END): cv.time,
            vol.Optional(CONF_SUNRISE_CUTOFF): cv.time,
            vol.Optional(CONF_ARM_AWAY_DELAY, default=180): cv.positive_int,  # type: ignore
            vol.Optional(CONF_BUTTON_ENTITY_RESET): cv.entity_id,
            vol.Optional(CONF_BUTTON_ENTITY_AWAY): cv.entity_id,
            vol.Optional(CONF_BUTTON_ENTITY_DISARM): cv.entity_id,
            vol.Optional(CONF_OCCUPANTS, default=[]): vol.All(cv.ensure_list, [cv.entity_id]),  # type: ignore
            vol.Optional(CONF_ACTIONS, default=[]): vol.All(cv.ensure_list, [PUSH_ACTION_SCHEMA]),  # type: ignore
            vol.Optional(CONF_NOTIFY, default={}): NOTIFY_SCHEMA,  # type: ignore
            vol.Optional(CONF_THROTTLE_SECONDS, default=60): cv.positive_int,  # type: ignore
            vol.Optional(CONF_THROTTLE_CALLS, default=6): cv.positive_int,  # type: ignore
        })
    },
    extra=vol.ALLOW_EXTRA,
)
