import os
import os.path
from pathlib import Path
from typing import Any

import pytest
from homeassistant.config import (
    load_yaml_config_file,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.autoarm.const import DOMAIN

EXAMPLES_ROOT = Path("examples")

examples = os.listdir(EXAMPLES_ROOT)


@pytest.mark.parametrize("config_name", examples)
async def test_examples(hass: HomeAssistant, config_name) -> None:
    config: dict[Any, Any] = await hass.async_add_executor_job(load_yaml_config_file, EXAMPLES_ROOT / config_name)

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()
    autoarm_state = hass.states.get("autoarm.configured")
    assert autoarm_state.state
    assert autoarm_state.attributes["auto_arm"]
    assert autoarm_state.attributes["alarm_panel"] == "alarm_panel.testing"
