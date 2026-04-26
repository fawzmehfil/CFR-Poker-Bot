from __future__ import annotations

from dataclasses import dataclass, field
import itertools
import json
import random
from pathlib import Path

from leduc_cfr.cfr.engine import EngineOps, engine_ops
from leduc_cfr.poker.leduc import CARDS, Action, LeducState


@dataclass
class InfoSet:
    regret_sum: dict[Action, float] = field(default_factory=dict)
    strategy_sum: dict[Action, float] = field(default_factory=dict)

    def strategy(self, legal_actions: tuple[Action, ...]) -> dict[Action, float]:
        positives = {a: max(0.0, self.regret_sum.get(a, 0.0)) for a in legal_actions}
        total = sum(positives.values())
        if total <= 0:
            return {a: 1.0 / len(legal_actions) for a in legal_actions}
        return {a: positives[a] / total for a in legal_actions}

    def average_strategy(self) -> dict[Action, float]:
        total = sum(max(0.0, v) for v in self.strategy_sum.values())
        if total <= 0:
            actions = sorted(self.strategy_sum) or ["k", "b"]
            return {a: 1.0 / len(actions) for a in actions}
        return {a: max(0.0, v) / total for a, v in sorted(self.strategy_sum.items())}


@dataclass
class StrategyProfile:
    strategies: dict[str, dict[Action, float]]

    def action_probs(self, key: str, legal_actions: tuple[Action, ...]) -> dict[Action, float]:
        raw = self.strategies.get(key)
        if not raw:
            return {a: 1.0 / len(legal_actions) for a in legal_actions}
        filtered = {a: max(0.0, raw.get(a, 0.0)) for a in legal_actions}
        total = sum(filtered.values())
        if total <= 0:
            return {a: 1.0 / len(legal_actions) for a in legal_actions}
        return {a: filtered[a] / total for a in legal_actions}

    def sample_action(
        self, key: str, legal_actions: tuple[Action, ...], rng: random.Random | None = None
    ) -> Action:
        rng = rng or random
        probs = self.action_probs(key, legal_actions)
        roll = rng.random()
        acc = 0.0
        last = legal_actions[-1]
        for action, prob in probs.items():
            acc += prob
            if roll <= acc:
                return action
            last = action
        return last

    def save(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps({"strategies": self.strategies}, indent=2, sort_keys=True))

    @classmethod
    def load(cls, path: str | Path) -> "StrategyProfile":
        data = json.loads(Path(path).read_text())
        return cls(strategies=data["strategies"])


class CFRTrainer:
    def __init__(self, cfr_plus: bool = False, engine: str = "python") -> None:
        self.info_sets: dict[str, InfoSet] = {}
        self.cfr_plus = cfr_plus
        self.iterations = 0
        self.deals = list(itertools.permutations(CARDS, 3))
        self.ops: EngineOps = engine_ops(engine)
        self.engine = self.ops.name

    def train(self, iterations: int) -> list[float]:
        utilities: list[float] = []
        for _ in range(iterations):
            total = 0.0
            for deal in self.deals:
                total += self._cfr(self.ops.initial_state(deal), reach0=1.0, reach1=1.0)
            self.iterations += 1
            utilities.append(total / len(self.deals))
        return utilities

    def profile(self) -> StrategyProfile:
        return StrategyProfile({key: info.average_strategy() for key, info in sorted(self.info_sets.items())})

    def _cfr(self, state: LeducState, reach0: float, reach1: float) -> float:
        if self.ops.is_terminal(state):
            return self.ops.utility(state, 0)

        player = self.ops.current_player(state)
        legal = self.ops.legal_actions(state)
        key = self.ops.info_set_key(state, player)
        info = self.info_sets.setdefault(key, InfoSet())
        strategy = info.strategy(legal)

        reach = reach0 if player == 0 else reach1
        for action in legal:
            info.strategy_sum[action] = info.strategy_sum.get(action, 0.0) + reach * strategy[action]

        child_values: dict[Action, float] = {}
        node_value = 0.0
        for action in legal:
            next_state = self.ops.apply_action(state, action)
            if player == 0:
                child_values[action] = self._cfr(next_state, reach0 * strategy[action], reach1)
            else:
                child_values[action] = self._cfr(next_state, reach0, reach1 * strategy[action])
            node_value += strategy[action] * child_values[action]

        for action in legal:
            if player == 0:
                regret = child_values[action] - node_value
                weighted = reach1 * regret
            else:
                regret = node_value - child_values[action]
                weighted = reach0 * regret
            updated = info.regret_sum.get(action, 0.0) + weighted
            info.regret_sum[action] = max(0.0, updated) if self.cfr_plus else updated

        return node_value
