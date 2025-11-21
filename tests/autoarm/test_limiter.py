import time

from custom_components.autoarm.autoarming import Limiter


def test_first_call_doesnt_trigger() -> None:
    limiter = Limiter(3)
    assert not limiter.triggered()


def test_multiple_calls_trigger() -> None:
    limiter = Limiter(3, max_calls=2)
    assert not limiter.triggered()
    assert not limiter.triggered()
    assert limiter.triggered()


def test_window_works_trigger() -> None:
    limiter = Limiter(3, max_calls=2)
    assert not limiter.triggered()
    assert not limiter.triggered()
    assert limiter.triggered()
    time.sleep(4)
    assert not limiter.triggered()
    assert len(limiter.calls) == 1
