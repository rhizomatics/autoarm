
import pytest
from homeassistant.helpers import config_validation as cv

from custom_components.autoarm.const import DEFAULT_TRANSITIONS
from custom_components.autoarm.hass_api import HomeAssistantAPI


@pytest.mark.parametrize("schema", DEFAULT_TRANSITIONS.values(), ids=DEFAULT_TRANSITIONS.keys())
def test_default_transitions_validated(schema: str) -> None:

    condition = cv.CONDITIONS_SCHEMA(schema)
    assert condition


@pytest.mark.parametrize("schema", DEFAULT_TRANSITIONS.keys())
async def test_default_transitions_built(hass_api: HomeAssistantAPI, schema: str) -> None:

    condition = cv.CONDITIONS_SCHEMA(DEFAULT_TRANSITIONS[schema])
    checker = await hass_api.build_condition(condition, validate=True, name=schema)
    assert checker


@pytest.mark.parametrize("schema", DEFAULT_TRANSITIONS.keys())
async def test_default_transitions_evaluated(hass_api: HomeAssistantAPI, schema: str) -> None:

    condition = cv.CONDITIONS_SCHEMA(DEFAULT_TRANSITIONS[schema])
    checker = await hass_api.build_condition(condition, validate=True, name=schema)
    assert checker
    hass_api.evaluate_condition(checker)
