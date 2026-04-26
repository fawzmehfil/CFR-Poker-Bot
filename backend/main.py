from __future__ import annotations

import random
import uuid
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from leduc_cfr.cfr.trainer import CFRTrainer, StrategyProfile
from leduc_cfr.eval.metrics import heuristic_policy, random_policy
from leduc_cfr.holdem.engine import Action as HoldemAction
from leduc_cfr.holdem.engine import HoldemState, fresh_holdem_state, heuristic_action as holdem_heuristic_action
from leduc_cfr.neural.policy import NeuralPolicy
from leduc_cfr.poker.leduc import Action, fresh_state

DATA_PATH = Path("data/cfr_strategy.json")
POLICY_PATH = Path("data/policy.pt")
BotMode = Literal["random", "heuristic", "cfr", "neural"]


class ActRequest(BaseModel):
    action: Action


class HoldemActRequest(BaseModel):
    action: HoldemAction


class NewGameRequest(BaseModel):
    bot_mode: BotMode = "cfr"


class GameSession:
    def __init__(self, profile: StrategyProfile, bot_mode: BotMode, neural_policy: NeuralPolicy | None = None) -> None:
        self.profile = profile
        self.bot_mode = bot_mode if bot_mode != "neural" or neural_policy is not None else "cfr"
        self.neural_policy = neural_policy
        self.rng = random.Random()
        self.state = fresh_state()
        self._bot_until_human()

    def view(self) -> dict:
        view = self.state.public_view(human_player=0)
        view["session_id"] = self.session_id
        view["bot_mode"] = self.bot_mode
        return view

    def act(self, action: Action) -> dict:
        if self.state.terminal:
            raise ValueError("Game is already over")
        if self.state.current_player != 0:
            raise ValueError("It is not the human player's turn")
        self.state = self.state.apply(action)
        self._bot_until_human()
        return self.view()

    def _bot_until_human(self) -> None:
        while not self.state.terminal and self.state.current_player == 1:
            legal = self.state.legal_actions()
            action = self._bot_action()
            self.state = self.state.apply(action)

    def _bot_action(self) -> Action:
        if self.bot_mode == "random":
            return random_policy(self.state, 1, self.rng)
        if self.bot_mode == "heuristic":
            return heuristic_policy(self.state, 1, self.rng)
        if self.bot_mode == "neural" and self.neural_policy is not None:
            return self.neural_policy.sample_action(self.state, 1, self.rng)
        return self.profile.sample_action(self.state.info_set_key(1), self.state.legal_actions(), self.rng)


class HoldemSession:
    def __init__(self) -> None:
        self.rng = random.Random()
        self.state: HoldemState = fresh_holdem_state(self.rng)
        self._bot_until_human()

    def view(self) -> dict:
        view = self.state.public_view(human_player=0)
        view["session_id"] = self.session_id
        view["mode"] = "holdem"
        return view

    def act(self, action: HoldemAction) -> dict:
        if self.state.terminal:
            raise ValueError("Game is already over")
        if self.state.current_player != 0:
            raise ValueError("It is not the human player's turn")
        self.state = self.state.apply(action)
        self._bot_until_human()
        return self.view()

    def _bot_until_human(self) -> None:
        while not self.state.terminal and self.state.current_player == 1:
            action = holdem_heuristic_action(self.state, 1, self.rng)
            self.state = self.state.apply(action)


def load_profile() -> StrategyProfile:
    if DATA_PATH.exists():
        return StrategyProfile.load(DATA_PATH)
    trainer = CFRTrainer(cfr_plus=True)
    trainer.train(500)
    profile = trainer.profile()
    profile.save(DATA_PATH)
    return profile


def load_neural_policy() -> NeuralPolicy | None:
    if not POLICY_PATH.exists():
        return None
    try:
        return NeuralPolicy.load(POLICY_PATH)
    except Exception:
        return None


app = FastAPI(title="Leduc CFR Poker Bot")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PROFILE = load_profile()
NEURAL_POLICY = load_neural_policy()
SESSIONS: dict[str, GameSession] = {}
HOLDEM_SESSIONS: dict[str, HoldemSession] = {}


@app.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "strategy_infosets": len(PROFILE.strategies),
        "bot_modes": ["random", "heuristic", "cfr", "neural"],
        "modes": ["leduc", "holdem"],
        "neural_available": NEURAL_POLICY is not None,
    }


@app.post("/api/new-game")
def new_game(req: NewGameRequest | None = None) -> dict:
    bot_mode = req.bot_mode if req is not None else "cfr"
    session = GameSession(PROFILE, bot_mode=bot_mode, neural_policy=NEURAL_POLICY)
    session.session_id = str(uuid.uuid4())
    SESSIONS[session.session_id] = session
    return session.view()


@app.post("/api/game/{session_id}/act")
def act(session_id: str, req: ActRequest) -> dict:
    session = SESSIONS.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Unknown session")
    try:
        return session.act(req.action)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/holdem/new-game")
def new_holdem_game() -> dict:
    session = HoldemSession()
    session.session_id = str(uuid.uuid4())
    HOLDEM_SESSIONS[session.session_id] = session
    return session.view()


@app.post("/api/holdem/game/{session_id}/act")
def holdem_act(session_id: str, req: HoldemActRequest) -> dict:
    session = HOLDEM_SESSIONS.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Unknown Hold'em session")
    try:
        return session.act(req.action)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
