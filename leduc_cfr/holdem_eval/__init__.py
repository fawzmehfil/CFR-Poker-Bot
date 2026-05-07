from __future__ import annotations

from dataclasses import dataclass
import math
import random
import statistics
from typing import Any, Callable, Protocol

from leduc_cfr.holdem.engine import BIG_BLIND, Action, HoldemState, evaluate_hand, fresh_holdem_state, heuristic_action


class ActBot(Protocol):
    def act(self, state: HoldemState, player: int, rng: random.Random) -> Action: ...


BotPolicy = Callable[[HoldemState, int, random.Random], Action]
BotLike = BotPolicy | ActBot


@dataclass(frozen=True)
class BotSpec:
    name: str
    policy: BotLike


@dataclass(frozen=True)
class UtilitySummary:
    count: int
    total: float
    mean: float
    variance: float
    standard_error: float
    confidence_interval: tuple[float, float]

    def to_dict(self) -> dict[str, float | int | list[float]]:
        return {
            "count": self.count,
            "total": self.total,
            "mean": self.mean,
            "variance": self.variance,
            "standard_error": self.standard_error,
            "confidence_interval": list(self.confidence_interval),
        }


@dataclass(frozen=True)
class EvalMetrics:
    total_hands: int
    total_chips: int
    bb_per_100: float
    ev_per_hand: float
    win_rate: float
    loss_rate: float
    draw_rate: float
    fold_frequency: float
    call_frequency: float
    raise_frequency: float
    aggression_frequency: float
    showdown_win_rate: float
    non_showdown_winnings: int
    confidence_interval: tuple[float, float]
    standard_error: float
    variance: float

    def to_dict(self) -> dict[str, float | int | list[float]]:
        return {
            "total_hands": self.total_hands,
            "total_chips": self.total_chips,
            "bb_per_100": self.bb_per_100,
            "ev_per_hand": self.ev_per_hand,
            "win_rate": self.win_rate,
            "loss_rate": self.loss_rate,
            "draw_rate": self.draw_rate,
            "fold_frequency": self.fold_frequency,
            "call_frequency": self.call_frequency,
            "raise_frequency": self.raise_frequency,
            "aggression_frequency": self.aggression_frequency,
            "showdown_win_rate": self.showdown_win_rate,
            "non_showdown_winnings": self.non_showdown_winnings,
            "confidence_interval": list(self.confidence_interval),
            "standard_error": self.standard_error,
            "variance": self.variance,
        }


@dataclass(frozen=True)
class MatchResult:
    bot_a: str
    bot_b: str
    hands_requested: int
    seed: int
    duplicate: bool
    metrics: EvalMetrics
    bot_metrics: dict[str, EvalMetrics]
    hand_histories: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "bot_a": self.bot_a,
            "bot_b": self.bot_b,
            "hands_requested": self.hands_requested,
            "seed": self.seed,
            "duplicate": self.duplicate,
            "metrics": self.metrics.to_dict(),
            "bot_metrics": {name: metrics.to_dict() for name, metrics in self.bot_metrics.items()},
            "hand_histories": self.hand_histories,
        }


def legal_random_bot(state: HoldemState, player: int, rng: random.Random) -> Action:
    del player
    return rng.choice(state.legal_actions())


def check_call_bot(state: HoldemState, player: int, rng: random.Random) -> Action:
    del player, rng
    legal = state.legal_actions()
    if "check" in legal:
        return "check"
    if "call" in legal:
        return "call"
    if "fold" in legal:
        return "fold"
    return legal[0]


def tight_aggressive_bot(state: HoldemState, player: int, rng: random.Random) -> Action:
    legal = state.legal_actions()
    action = heuristic_action(state, player, rng)
    if action in legal:
        return action
    return check_call_bot(state, player, rng)


BUILTIN_BOTS: dict[str, BotSpec] = {
    "random": BotSpec("random", legal_random_bot),
    "check_call": BotSpec("check_call", check_call_bot),
    "heuristic": BotSpec("heuristic", tight_aggressive_bot),
}


def confidence_interval(mean: float, standard_error: float, z: float = 1.96) -> tuple[float, float]:
    half_width = z * standard_error
    return (mean - half_width, mean + half_width)


def summarize_utilities(values: list[int | float]) -> UtilitySummary:
    count = len(values)
    total = float(sum(values))
    mean = total / count if count else 0.0
    variance = statistics.variance(values) if count > 1 else 0.0
    standard_error = math.sqrt(variance / count) if count else 0.0
    return UtilitySummary(
        count=count,
        total=total,
        mean=mean,
        variance=variance,
        standard_error=standard_error,
        confidence_interval=confidence_interval(mean, standard_error),
    )


def evaluate_match(
    bot_a: BotSpec,
    bot_b: BotSpec,
    *,
    hands: int = 1000,
    seed: int = 7,
    duplicate: bool = True,
    store_histories: bool = True,
) -> MatchResult:
    hero_utilities: list[int] = []
    histories: list[dict[str, Any]] = []
    bot_utilities = {bot_a.name: [], bot_b.name: []}
    bot_action_counts = {
        bot_a.name: _empty_action_counts(),
        bot_b.name: _empty_action_counts(),
    }
    bot_showdowns = {
        bot_a.name: {"count": 0, "wins": 0.0},
        bot_b.name: {"count": 0, "wins": 0.0},
    }
    bot_non_showdown = {bot_a.name: 0, bot_b.name: 0}
    hero_action_counts = _empty_action_counts()
    hero_showdowns = {"count": 0, "wins": 0.0}
    hero_non_showdown = 0

    for group in range(hands):
        hand_seed = seed + group
        seatings = [(bot_a, bot_b, 0)]
        if duplicate:
            seatings.append((bot_b, bot_a, 1))
        for duplicate_index, (seat0_bot, seat1_bot, hero_seat) in enumerate(seatings):
            hand_index = len(hero_utilities)
            played = _play_hand(
                seat_bots=(seat0_bot, seat1_bot),
                hand_seed=hand_seed,
                decision_seed=_decision_seed(seed, group, duplicate_index),
                duplicate_group=group,
                duplicate_index=duplicate_index,
                hand_index=hand_index,
            )
            hero_utility = played["terminal_result"]["utilities"][str(hero_seat)]
            hero_utilities.append(hero_utility)
            if played["showdown_hands"]:
                hero_showdowns["count"] += 1
                if played["winner"] is None:
                    hero_showdowns["wins"] += 0.5
                elif played["winner"] == hero_seat:
                    hero_showdowns["wins"] += 1.0
            if played["folded_player"] is not None:
                hero_non_showdown += hero_utility
            for decision in played["bot_decisions"]:
                if decision["player"] == hero_seat:
                    _record_action(hero_action_counts, decision["action"])
            if store_histories:
                histories.append(played)

            for seat, bot in enumerate((seat0_bot, seat1_bot)):
                utility = played["terminal_result"]["utilities"][str(seat)]
                bot_utilities[bot.name].append(utility)
                if played["winner"] is None and played["showdown_hands"]:
                    bot_showdowns[bot.name]["count"] += 1
                    bot_showdowns[bot.name]["wins"] += 0.5
                elif played["winner"] == seat and played["showdown_hands"]:
                    bot_showdowns[bot.name]["count"] += 1
                    bot_showdowns[bot.name]["wins"] += 1.0
                elif played["winner"] is not None and played["showdown_hands"]:
                    bot_showdowns[bot.name]["count"] += 1
                if played["folded_player"] is not None:
                    bot_non_showdown[bot.name] += utility

            for decision in played["bot_decisions"]:
                _record_action(bot_action_counts[decision["bot"]], decision["action"])

    bot_metrics = {
        name: _metrics_from_parts(values, bot_action_counts[name], bot_showdowns[name], bot_non_showdown[name])
        for name, values in bot_utilities.items()
    }
    metrics = _metrics_from_parts(
        hero_utilities,
        hero_action_counts,
        hero_showdowns,
        hero_non_showdown,
    )
    return MatchResult(
        bot_a=bot_a.name,
        bot_b=bot_b.name,
        hands_requested=hands,
        seed=seed,
        duplicate=duplicate,
        metrics=metrics,
        bot_metrics=bot_metrics,
        hand_histories=histories,
    )


def _play_hand(
    *,
    seat_bots: tuple[BotSpec, BotSpec],
    hand_seed: int,
    decision_seed: int,
    duplicate_group: int,
    duplicate_index: int,
    hand_index: int,
) -> dict[str, Any]:
    rng = random.Random(decision_seed)
    state = fresh_holdem_state(seed=hand_seed, shuffle_algorithm="lcg")
    initial_hole_cards = [[str(card) for card in state.hole_cards[player]] for player in range(2)]
    actions: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    pot_sizes = [state.pot]
    stack_snapshots = [list(state.stacks)]

    while not state.terminal:
        player = state.current_player
        bot = seat_bots[player]
        legal = state.legal_actions()
        action = _bot_action(bot, state, player, rng)
        if action not in legal:
            raise ValueError(f"Bot {bot.name} produced illegal action {action}; legal={legal}")
        before = state
        after = state.apply(action)
        decision = {
            "decision_index": len(decisions),
            "bot": bot.name,
            "player": player,
            "street": before.street,
            "legal_actions": list(legal),
            "action": action,
            "to_call": before.to_call(player),
            "pot_before": before.pot,
            "stacks_before": list(before.stacks),
        }
        decisions.append(decision)
        actions.append(
            {
                **decision,
                "pot_after": after.pot,
                "stacks_after": list(after.stacks),
                "board_after": [str(card) for card in after.board],
            }
        )
        pot_sizes.append(after.pot)
        stack_snapshots.append(list(after.stacks))
        state = after

    winner = _winner(state)
    showdown_hands = _showdown_hands(state)
    utilities = {str(player): state.utility(player) for player in range(2)}
    return {
        "seed": hand_seed,
        "decision_seed": decision_seed,
        "duplicate_group": duplicate_group,
        "duplicate_index": duplicate_index,
        "hand_index": hand_index,
        "seat_bots": {"0": seat_bots[0].name, "1": seat_bots[1].name},
        "hole_cards": {"0": initial_hole_cards[0], "1": initial_hole_cards[1]},
        "board": [str(card) for card in state.board],
        "actions": actions,
        "pot_sizes": pot_sizes,
        "stacks": stack_snapshots,
        "terminal_result": {
            "pot": state.pot,
            "final_stacks": list(state.final_stacks()),
            "utilities": utilities,
            "folded_player": state.folded_player,
        },
        "winner": winner,
        "folded_player": state.folded_player,
        "showdown_hands": showdown_hands,
        "bot_decisions": decisions,
    }


def _bot_action(bot: BotSpec, state: HoldemState, player: int, rng: random.Random) -> Action:
    policy = bot.policy
    if hasattr(policy, "act"):
        return policy.act(state, player, rng)  # type: ignore[union-attr]
    return policy(state, player, rng)  # type: ignore[operator]


def _winner(state: HoldemState) -> int | None:
    if state.folded_player is not None:
        return 1 - state.folded_player
    return state.showdown_winner()


def _showdown_hands(state: HoldemState) -> dict[str, Any]:
    if state.folded_player is not None or len(state.board) != 5:
        return {}
    return {
        str(player): {
            "cards": [str(card) for card in state.hole_cards[player] + state.board],
            "score": list(evaluate_hand(state.hole_cards[player] + state.board)),
        }
        for player in range(2)
    }


def _decision_seed(seed: int, group: int, duplicate_index: int) -> int:
    return seed * 1_000_003 + group * 17 + duplicate_index


def _empty_action_counts() -> dict[str, int]:
    return {"decisions": 0, "fold": 0, "call": 0, "raise": 0, "aggressive": 0}


def _record_action(counts: dict[str, int], action: str) -> None:
    counts["decisions"] += 1
    if action == "fold":
        counts["fold"] += 1
    elif action == "call":
        counts["call"] += 1
    elif action in ("bet", "raise", "all-in"):
        counts["raise"] += 1
        counts["aggressive"] += 1


def _metrics_from_parts(
    utilities: list[int],
    action_counts: dict[str, int],
    showdown_counts: dict[str, float],
    non_showdown_winnings: int,
) -> EvalMetrics:
    summary = summarize_utilities(utilities)
    wins = sum(1 for value in utilities if value > 0)
    losses = sum(1 for value in utilities if value < 0)
    draws = sum(1 for value in utilities if value == 0)
    decisions = action_counts["decisions"]
    total_hands = len(utilities)
    return EvalMetrics(
        total_hands=total_hands,
        total_chips=int(sum(utilities)),
        bb_per_100=(summary.mean / BIG_BLIND * 100) if total_hands else 0.0,
        ev_per_hand=summary.mean,
        win_rate=wins / total_hands if total_hands else 0.0,
        loss_rate=losses / total_hands if total_hands else 0.0,
        draw_rate=draws / total_hands if total_hands else 0.0,
        fold_frequency=action_counts["fold"] / decisions if decisions else 0.0,
        call_frequency=action_counts["call"] / decisions if decisions else 0.0,
        raise_frequency=action_counts["raise"] / decisions if decisions else 0.0,
        aggression_frequency=action_counts["aggressive"] / decisions if decisions else 0.0,
        showdown_win_rate=showdown_counts["wins"] / showdown_counts["count"] if showdown_counts["count"] else 0.0,
        non_showdown_winnings=non_showdown_winnings,
        confidence_interval=summary.confidence_interval,
        standard_error=summary.standard_error,
        variance=summary.variance,
    )


__all__ = [
    "BUILTIN_BOTS",
    "BotLike",
    "BotPolicy",
    "BotSpec",
    "EvalMetrics",
    "MatchResult",
    "UtilitySummary",
    "check_call_bot",
    "confidence_interval",
    "evaluate_match",
    "legal_random_bot",
    "summarize_utilities",
    "tight_aggressive_bot",
]
