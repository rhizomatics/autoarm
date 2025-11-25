from __future__ import annotations

import logging
from functools import partial
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.template import Template
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, ConditionVariables

if TYPE_CHECKING:

    from homeassistant.helpers.condition import ConditionCheckerType

from homeassistant.helpers import condition as condition

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.typing import ConfigType


_LOGGER = logging.getLogger(__name__)


class HomeAssistantAPI:
    def __init__(self, hass: HomeAssistant | None = None) -> None:
        self._hass = hass

    def raise_issue(
        self,
        issue_id: str,
        issue_key: str,
        issue_map: dict[str, str],
        severity: ir.IssueSeverity = ir.IssueSeverity.WARNING,
        learn_more_url: str = "https://supernotify.rhizomatics.org.uk",
        is_fixable: bool = False,
    ) -> None:
        if not self._hass:
            return
        ir.async_create_issue(
            self._hass,
            DOMAIN,
            issue_id,
            translation_key=issue_key,
            translation_placeholders=issue_map,
            severity=severity,
            learn_more_url=learn_more_url,
            is_fixable=is_fixable,
        )

    async def build_condition(
        self,
        condition_config: ConfigType,
        strict: bool = False,
        validate: bool = False,
    ) -> ConditionCheckerType | None:
        if self._hass is None:
            raise ValueError("HomeAssistant not available")
        condition_variables = ConditionVariables()
        try:
            if validate:
                condition_config = await condition.async_validate_condition_config(self._hass, condition_config)
            if strict:
                force_strict_template_mode(condition_config, undo=False)

            test = await condition.async_from_config(self._hass, condition_config)
            if test is None:
                raise ValueError(f"Invalid condition {condition_config}")
            test(self._hass, condition_variables.as_dict())
            return test
        except Exception as e:
            _LOGGER.exception("SUPERNOTIFY Condition eval failed: %s", e)
            raise
        finally:
            if strict:
                force_strict_template_mode(condition_config, undo=False)

    def evaluate_condition(
        self,
        condition: ConditionCheckerType,
        condition_variables: ConditionVariables | None = None,
    ) -> bool | None:
        if self._hass is None:
            raise ValueError("HomeAssistant not available")
        try:
            return condition(self._hass, condition_variables.as_dict() if condition_variables else None)
        except Exception as e:
            _LOGGER.error("SUPERNOTIFY Condition eval failed: %s", e)
            raise


def force_strict_template_mode(condition: ConfigType, undo: bool = False) -> None:
    class TemplateWrapper:
        def __init__(self, obj: Template) -> None:
            self._obj = obj

        def __getattr__(self, name: str) -> Any:
            if name == "async_render_to_info":
                return partial(self._obj.async_render_to_info, strict=True)
            return getattr(self._obj, name)

        def __setattr__(self, name: str, value: Any) -> None:
            super().__setattr__(name, value)

    def wrap_template(cond: ConfigType, undo: bool) -> None:
        for key, val in cond.items():
            if not undo and isinstance(val, Template) and hasattr(val, "_env"):
                cond[key] = TemplateWrapper(val)
            elif undo and isinstance(val, TemplateWrapper):
                cond[key] = val._obj
            elif isinstance(val, dict):
                wrap_template(val, undo)

    if condition is not None:
        wrap_template(condition, undo)
