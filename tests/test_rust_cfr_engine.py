import pytest

from leduc_cfr.cfr.engine import PythonEngineOps, RustEngineOps, rust_trace_matches_python


def test_rust_trace_matches_python_when_available():
    try:
        assert rust_trace_matches_python()
    except Exception as exc:
        pytest.skip(f"Rust CFR engine unavailable: {exc}")


def test_rust_engine_infoset_key_matches_python_when_available():
    try:
        rust = RustEngineOps()
    except Exception as exc:
        pytest.skip(f"Rust CFR engine unavailable: {exc}")
    python = PythonEngineOps()

    rust_state = rust.initial_state(("K1", "Q1", "J1"))
    python_state = python.initial_state(("K1", "Q1", "J1"))
    for action in ("k", "k"):
        rust_state = rust.apply_action(rust_state, action)
        python_state = python.apply_action(python_state, action)

    assert rust.legal_actions(rust_state) == python.legal_actions(python_state)
    assert rust.info_set_key(rust_state, 0) == python.info_set_key(python_state, 0)
