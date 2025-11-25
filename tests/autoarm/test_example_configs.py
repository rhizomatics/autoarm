import pathlib
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from homeassistant import config as hass_config
from homeassistant.components.calendar import CalendarEntity
from homeassistant.config import (
    load_yaml_config_file,
)
from homeassistant.const import SERVICE_RELOAD
from homeassistant.core import HomeAssistant, State
from homeassistant.setup import async_setup_component

from custom_components.autoarm.const import DOMAIN

EXAMPLES_ROOT = Path("examples")

examples: list[Path] = list(EXAMPLES_ROOT.iterdir())


@pytest.mark.parametrize("config_name", examples, ids=lambda v: v.stem)
@pytest.mark.parametrize(argnames="reload", argvalues=[True, False], ids=["reload", "no-reload"])
async def test_examples(hass: HomeAssistant, config_name: str, reload: bool, local_calendar: CalendarEntity) -> None:  # noqa: ARG001
    config: dict[Any, Any] = await hass.async_add_executor_job(load_yaml_config_file, str(config_name))

    assert await async_setup_component(hass, DOMAIN, config)
    await hass.async_block_till_done()
    autoarm_state: State | None = hass.states.get("autoarm.configured")
    assert autoarm_state is not None
    assert autoarm_state.state
    assert autoarm_state.attributes["alarm_panel"] == "alarm_panel.testing"
    autoarm_init = hass.states.get("autoarm.initialization")
    assert autoarm_init is not None
    assert autoarm_init.state == "valid"

    if reload:
        config_path = pathlib.Path(__file__).parent.joinpath("fixtures", "empty_config.yaml").absolute()

        with patch.object(hass_config, "YAML_CONFIG_FILE", config_path):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_RELOAD,
                {},
                blocking=True,
            )
            await hass.async_block_till_done()
        autoarm_state = hass.states.get("autoarm.configured")
        assert autoarm_state is not None
        assert autoarm_state.attributes["alarm_panel"] == "alarm_panel.minimal"
        autoarm_init = hass.states.get("autoarm.initialization")
        assert autoarm_init is not None
        assert autoarm_init.state == "valid"
