from __future__ import annotations

import ctypes
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from leduc_cfr.poker.leduc import Action, LeducState

CARD_TO_INDEX = {"J1": 0, "J2": 1, "Q1": 2, "Q2": 3, "K1": 4, "K2": 5}
RANK_LABELS = ("J", "Q", "K", "-")
ACTION_TO_CODE = {"k": 0, "b": 1, "c": 2, "r": 3, "f": 4}
CODE_TO_ACTION = {value: key for key, value in ACTION_TO_CODE.items()}
EMPTY_ACTION = 7


class EngineOps(Protocol):
    name: str

    def initial_state(self, deal: tuple[str, str, str]): ...

    def is_terminal(self, state) -> bool: ...

    def current_player(self, state) -> int: ...

    def legal_actions(self, state) -> tuple[Action, ...]: ...

    def apply_action(self, state, action: Action): ...

    def utility(self, state, player: int) -> float: ...

    def info_set_key(self, state, player: int) -> str: ...


class PythonEngineOps:
    name = "python"

    def initial_state(self, deal: tuple[str, str, str]) -> LeducState:
        return LeducState(deal=deal)

    def is_terminal(self, state: LeducState) -> bool:
        return state.terminal

    def current_player(self, state: LeducState) -> int:
        return state.current_player

    @lru_cache(maxsize=None)
    def legal_actions(self, state: LeducState) -> tuple[Action, ...]:
        return state.legal_actions()

    @lru_cache(maxsize=None)
    def apply_action(self, state: LeducState, action: Action) -> LeducState:
        return state.apply(action)

    def utility(self, state: LeducState, player: int) -> float:
        return state.utility(player)

    @lru_cache(maxsize=None)
    def info_set_key(self, state: LeducState, player: int) -> str:
        return state.info_set_key(player)


class RustEngineOps:
    name = "rust"

    def __init__(self) -> None:
        self.lib = ctypes.CDLL(str(_find_or_build_library()))
        self.lib.leduc_initial_state.argtypes = [ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint8]
        self.lib.leduc_initial_state.restype = ctypes.c_uint64
        self.lib.leduc_is_terminal.argtypes = [ctypes.c_uint64]
        self.lib.leduc_is_terminal.restype = ctypes.c_uint8
        self.lib.leduc_current_player.argtypes = [ctypes.c_uint64]
        self.lib.leduc_current_player.restype = ctypes.c_uint8
        self.lib.leduc_legal_actions.argtypes = [ctypes.c_uint64]
        self.lib.leduc_legal_actions.restype = ctypes.c_uint32
        self.lib.leduc_apply_action.argtypes = [ctypes.c_uint64, ctypes.c_uint8]
        self.lib.leduc_apply_action.restype = ctypes.c_uint64
        self.lib.leduc_utility.argtypes = [ctypes.c_uint64, ctypes.c_uint8]
        self.lib.leduc_utility.restype = ctypes.c_double
        self.lib.leduc_infoset_parts.argtypes = [ctypes.c_uint64, ctypes.c_uint8]
        self.lib.leduc_infoset_parts.restype = ctypes.c_uint64

    def initial_state(self, deal: tuple[str, str, str]) -> int:
        return int(self.lib.leduc_initial_state(*(CARD_TO_INDEX[card] for card in deal)))

    def is_terminal(self, state: int) -> bool:
        return bool(self.lib.leduc_is_terminal(state))

    def current_player(self, state: int) -> int:
        return int(self.lib.leduc_current_player(state))

    @lru_cache(maxsize=None)
    def legal_actions(self, state: int) -> tuple[Action, ...]:
        packed = int(self.lib.leduc_legal_actions(state))
        count = packed & 0xFF
        return tuple(CODE_TO_ACTION[(packed >> (8 * (idx + 1))) & 0xFF] for idx in range(count))  # type: ignore[return-value]

    @lru_cache(maxsize=None)
    def apply_action(self, state: int, action: Action) -> int:
        return int(self.lib.leduc_apply_action(state, ACTION_TO_CODE[action]))

    def utility(self, state: int, player: int) -> float:
        return float(self.lib.leduc_utility(state, player))

    @lru_cache(maxsize=None)
    def info_set_key(self, state: int, player: int) -> str:
        parts = int(self.lib.leduc_infoset_parts(state, player))
        private = parts & 0b111
        public = (parts >> 3) & 0b111
        round_index = (parts >> 6) & 0b1
        h0_len = (parts >> 7) & 0b111
        h1_len = (parts >> 10) & 0b111
        shift = 13
        histories = []
        for length in (h0_len, h1_len):
            actions = []
            for idx in range(4):
                code = (parts >> (shift + 3 * idx)) & 0b111
                if idx < length and code != EMPTY_ACTION:
                    actions.append(CODE_TO_ACTION[code])
            histories.append("".join(actions) or "-")
            shift += 12
        return f"p{player}|{RANK_LABELS[private]}|{RANK_LABELS[public]}|r{round_index}|{histories[0]}/{histories[1]}"


def engine_ops(name: str = "python") -> EngineOps:
    if name == "python":
        return PythonEngineOps()
    if name == "rust":
        return RustEngineOps()
    if name == "auto":
        try:
            return RustEngineOps()
        except Exception:
            return PythonEngineOps()
    raise ValueError(f"Unknown CFR engine: {name}")


def rust_trace_matches_python() -> bool:
    rust = RustEngineOps()
    py = PythonEngineOps()
    actions: tuple[Action, ...] = ("b", "f")
    rust_state = rust.initial_state(("K1", "Q1", "J1"))
    py_state = py.initial_state(("K1", "Q1", "J1"))
    for action in actions:
        if rust.legal_actions(rust_state) != py.legal_actions(py_state):
            return False
        rust_state = rust.apply_action(rust_state, action)
        py_state = py.apply_action(py_state, action)
    return (
        rust.is_terminal(rust_state) == py.is_terminal(py_state)
        and rust.current_player(rust_state) == py.current_player(py_state)
        and rust.legal_actions(rust_state) == py.legal_actions(py_state)
        and rust.utility(rust_state, 0) == py.utility(py_state, 0)
    )


def _find_or_build_library() -> Path:
    root = Path(__file__).resolve().parents[2]
    engine_dir = root / "engine"
    candidates = [
        engine_dir / "target" / "release" / "libleduc_engine.dylib",
        engine_dir / "target" / "release" / "libleduc_engine.so",
        engine_dir / "target" / "release" / "leduc_engine.dll",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    subprocess.run(["cargo", "build", "--release"], cwd=engine_dir, check=True, capture_output=True, text=True)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise RuntimeError("Rust CFR engine library was not built")
