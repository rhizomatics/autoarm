import pathlib
from pathlib import Path
from typing import Any

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

examples: list[Path] = [p for p in EXAMPLES_ROOT.iterdir() if p.is_file() and p.name.endswith(".yaml")]


@pytest.mark.parametrize("config_name", examples, ids=lambda v: v.stem)
@pytest.mark.parametrize(argnames="reload", argvalues=[True, False], ids=["reload", "no-reload"])
async def test_examples(hass: HomeAssistant, config_name: str, reload: bool,
                        local_calendar: CalendarEntity,  # noqa: ARG001
                        monkeypatch: pytest.MonkeyPatch) -> None:
    config: dict[Any, Any] = await hass.async_add_executor_job(load_yaml_config_file, str(config_name))

    for domain in config:
        assert await async_setup_component(hass, domain, config)

    await hass.async_block_till_done()
    autoarm_state: State | None = hass.states.get("autoarm.configured")
    assert autoarm_state is not None
    assert autoarm_state.state
    assert autoarm_state.attributes["alarm_panel"] == "alarm_panel.testing"
    autoarm_init = hass.states.get("autoarm.initialization")
    assert autoarm_init is not None
    assert autoarm_init.state == "valid"
    hass.bus.async_fire("mobile_app_notification_action", {"action": "ALARM_PANEL_DISARM"})
    await hass.async_block_till_done()
    assert hass.states.get("alarm_control_panel.testing").state == "disarmed"

    if reload:
        config_path = pathlib.Path(__file__).parent.joinpath("fixtures", "empty_config.yaml").absolute()

        with monkeypatch.context() as m:
            m.setattr(hass_config, "YAML_CONFIG_FILE", str(config_path))
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
