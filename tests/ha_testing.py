"""Home Assistant's test helpers, from whichever package provides them for the Home Assistant
installed: pytest-homeassistant (`pytest_homeassistant`), published by Home Assistant itself from
2026.11, or pytest-homeassistant-custom-component before that. Remove once the oldest supported
Home Assistant has the first, importing from `pytest_homeassistant` directly (same model as
supernotify, hq-private#85)."""

try:
    from pytest_homeassistant.common import (  # type: ignore[import-not-found,unused-ignore]
        AsyncMock,
        MockConfigEntry,
        async_fire_time_changed,
    )
    from pytest_homeassistant.components.recorder.common import (  # type: ignore[import-not-found,unused-ignore]
        async_wait_recording_done,
    )
    from pytest_homeassistant.typing import (  # type: ignore[import-not-found,unused-ignore]
        WebSocketGenerator,
    )
except ImportError:
    from pytest_homeassistant_custom_component.common import (  # type: ignore[import-untyped,unused-ignore]
        AsyncMock,
        MockConfigEntry,
        async_fire_time_changed,
    )
    from pytest_homeassistant_custom_component.components.recorder.common import (  # type: ignore[import-untyped,unused-ignore]
        async_wait_recording_done,
    )
    from pytest_homeassistant_custom_component.typing import (  # type: ignore[import-untyped,unused-ignore]
        WebSocketGenerator,
    )

__all__ = [
    "AsyncMock",
    "MockConfigEntry",
    "WebSocketGenerator",
    "async_fire_time_changed",
    "async_wait_recording_done",
]
