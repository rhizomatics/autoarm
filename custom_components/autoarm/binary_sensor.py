"""Binary sensor reporting whether AutoArm initialized without errors."""

from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorEntityDescription
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .autoarming import AlarmArmer, AutoArmConfigEntry
from .entity import AutoArmEntity

PARALLEL_UPDATES = 0

INITIALIZED = BinarySensorEntityDescription(
    key="initialized",
    translation_key="initialized",
    entity_category=EntityCategory.DIAGNOSTIC,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: AutoArmConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([AutoArmInitializedSensor(entry.runtime_data, entry)])


class AutoArmInitializedSensor(AutoArmEntity, BinarySensorEntity):
    def __init__(self, armer: AlarmArmer, entry: AutoArmConfigEntry) -> None:
        super().__init__(armer, entry, Platform.BINARY_SENSOR, INITIALIZED)

    @property
    def is_on(self) -> bool:
        tracker = self.armer.app_health_tracker
        return tracker.initialized and not tracker.initialization_errors

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return dict(self.armer.app_health_tracker.initialization_errors)
