from __future__ import annotations

import random
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from leduc_cfr.cfr.trainer import CFRTrainer, StrategyProfile
from leduc_cfr.poker.leduc import Action, fresh_state

DATA_PATH = Path("data/cfr_strategy.json")


class ActRequest(BaseModel):
    action: Action


class GameSession:
    def __init__(self, profile: StrategyProfile) -> None:
        self.profile = profile
        self.rng = random.Random()
        self.state = fresh_state()
        self._bot_until_human()

    def view(self) -> dict:
        view = self.state.public_view(human_player=0)
        view["session_id"] = self.session_id
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
            action = self.profile.sample_action(self.state.info_set_key(1), legal, self.rng)
            self.state = self.state.apply(action)


def load_profile() -> StrategyProfile:
    if DATA_PATH.exists():
        return StrategyProfile.load(DATA_PATH)
    trainer = CFRTrainer(cfr_plus=True)
    trainer.train(500)
    profile = trainer.profile()
    profile.save(DATA_PATH)
    return profile


app = FastAPI(title="Leduc CFR Poker Bot")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PROFILE = load_profile()
SESSIONS: dict[str, GameSession] = {}


@app.get("/health")
def health() -> dict:
    return {"ok": True, "strategy_infosets": len(PROFILE.strategies)}


@app.post("/api/new-game")
def new_game() -> dict:
    session = GameSession(PROFILE)
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

