"""Shared test setup, as the core's: keys' state in the test's folder, and key ripening
(UN-RFC 0025) scaled down, so posting does not wait for real proofs."""
import pytest

from unseenet.core import ripening


@pytest.fixture(autouse=True)
def state_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("UNSEENET_STATE_DIR", str(tmp_path / "keys"))


@pytest.fixture(autouse=True)
def fast_ripening():
    ripening.scale_for_tests(16, rules=False)
    yield
    ripening.scale_for_tests(0)
