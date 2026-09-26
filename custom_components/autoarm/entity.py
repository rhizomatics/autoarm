"""Base entity for the AutoArm status entities."""

from homeassistant.core import Context, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity, EntityDescription

from .autoarming import AlarmArmer, AutoArmConfigEntry
from .const import DOMAIN, SIGNAL_STATUS_UPDATED


class AutoArmEntity(Entity):
    """Entity showing AutoArm's own state, updated whenever the armer publishes a change"""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, armer: AlarmArmer, entry: AutoArmConfigEntry, platform: str, description: EntityDescription) -> None:
        self.armer = armer
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        # fixed entity_id, so it doesn't vary with the system language, and matches the docs
        self.entity_id = f"{platform}.{DOMAIN}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="AutoArm",
            manufacturer="Rhizomatics",
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(async_dispatcher_connect(self.hass, SIGNAL_STATUS_UPDATED, self._on_status_updated))

    @callback
    def _on_status_updated(self, context: Context | None = None) -> None:
        # so the state change can be traced back to what caused it
        if context is not None:
            self.async_set_context(context)
        self.async_write_ha_state()
