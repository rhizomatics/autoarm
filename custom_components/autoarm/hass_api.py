from __future__ import annotations

import logging
from functools import partial
from typing import TYPE_CHECKING, Any, cast

from homeassistant.components.alarm_control_panel.const import AlarmControlPanelState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConditionError, ConditionErrorContainer
from homeassistant.helpers import condition as condition
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.template import Template
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, ConditionVariables

if TYPE_CHECKING:
    from collections.abc import Callable

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
        learn_more_url: str = "https://autoarm.rhizomatics.org.uk",
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
        self, condition_config: list[ConfigType], strict: bool = False, validate: bool = False, name: str = DOMAIN
    ) -> Callable | None:
        if self._hass is None:
            raise ValueError("HomeAssistant not available")
        capturing_logger: ConditionErrorLoggingAdaptor = ConditionErrorLoggingAdaptor(_LOGGER)
        condition_variables: ConditionVariables = ConditionVariables(False, False, AlarmControlPanelState.PENDING, {})
        cond_list: list[ConfigType]
        try:
            if validate:
                cond_list = cast(
                    "list[ConfigType]", await condition.async_validate_conditions_config(self._hass, condition_config)
                )
            else:
                cond_list = condition_config
        except Exception as e:
            _LOGGER.exception("AUTOARM Condition validation failed: %s", e)
            raise
        try:
            if strict:
                force_strict_template_mode(cond_list, undo=False)

            test: Callable = await condition.async_conditions_from_config(
                self._hass, cond_list, cast("logging.Logger", capturing_logger), name
            )
            if test is None:
                raise ValueError(f"Invalid condition {condition_config}")
            test({DOMAIN: condition_variables.as_dict()})
            if strict and capturing_logger.condition_errors:
                for exception in capturing_logger.condition_errors:
                    _LOGGER.warning("AUTOARM Invalid condition %s:%s", condition_config, exception)
                raise capturing_logger.condition_errors[0]
            return test
        except Exception as e:
            _LOGGER.exception("AUTOARM Condition eval failed: %s", e)
            raise
        finally:
            if strict:
                force_strict_template_mode(condition_config, undo=True)

    def evaluate_condition(
        self,
        condition: Callable,
        condition_variables: ConditionVariables | None = None,
    ) -> bool | None:
        if self._hass is None:
            raise ValueError("HomeAssistant not available")
        try:
            return condition({DOMAIN: condition_variables.as_dict()} if condition_variables else None)
        except Exception as e:
            _LOGGER.error("AUTOARM Condition eval failed: %s", e)
            raise


class ConditionErrorLoggingAdaptor(logging.LoggerAdapter):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.condition_errors: list[ConditionError] = []

    def capture(self, args: Any) -> None:
        if args and isinstance(args, (list, tuple)):
            for arg in args:
                if isinstance(arg, ConditionErrorContainer):
                    self.condition_errors.extend(arg.errors)
                elif isinstance(arg, ConditionError):
                    self.condition_errors.append(arg)

    def error(self, msg: Any, *args: object, **kwargs: Any) -> None:
        self.capture(args)
        self.logger.error(msg, args, kwargs)

    def warning(self, msg: Any, *args: Any, **kwargs: Any) -> None:
        self.capture(args)
        self.logger.warning(msg, args, kwargs)


def force_strict_template_mode(conditions: list[ConfigType], undo: bool = False) -> None:
    class TemplateWrapper:
        def __init__(self, obj: Template) -> None:
            self._obj = obj

        def __getattr__(self, name: str) -> Any:
            if name == "async_render_to_info":
                return partial(self._obj.async_render_to_info, strict=True)
            return getattr(self._obj, name)

        def __setattr__(self, name: str, value: Any) -> None:
            super().__setattr__(name, value)

    def wrap_template(cond: ConfigType, undo: bool) -> ConfigType:
        for key, val in cond.items():
            if not undo and isinstance(val, Template) and hasattr(val, "_env"):
                cond[key] = TemplateWrapper(val)
            elif undo and isinstance(val, TemplateWrapper):
                cond[key] = val._obj
            elif isinstance(val, dict):
                wrap_template(val, undo)
        return cond

    if conditions is not None:
        conditions = [wrap_template(condition, undo) for condition in conditions]
