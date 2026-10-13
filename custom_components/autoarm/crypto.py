"""Keeps the alarm panel code out of plain sight in the config entry

The key is derived from this Home Assistant's instance id, which is stored alongside the config entry, so this
is obfuscation, to stop the code being read off a screen, a backup listing or a shared file, and no protection
against someone with the whole of the `.storage` directory
"""

import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken
from homeassistant.core import HomeAssistant
from homeassistant.helpers import instance_id

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def _cipher(hass: HomeAssistant) -> Fernet:
    key: bytes = hashlib.sha256(f"{DOMAIN}:{await instance_id.async_get(hass)}".encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


async def async_encrypt(hass: HomeAssistant, text: str) -> str:
    return (await _cipher(hass)).encrypt(text.encode()).decode()


async def async_decrypt(hass: HomeAssistant, token: str) -> str | None:
    """None if it can't be read, as when the config entry has come from another Home Assistant"""
    try:
        return (await _cipher(hass)).decrypt(token.encode()).decode()
    except InvalidToken:
        _LOGGER.warning("AUTOARM Unable to read the stored alarm panel code, set it again in the options")
        return None
