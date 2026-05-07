from __future__ import annotations

import math
import random

import pytest

from leduc_cfr.holdem.engine import Action, HoldemState
from leduc_cfr.holdem_eval import (
    BotSpec,
    check_call_bot,
    confidence_interval,
    evaluate_match,
    legal_random_bot,
    summarize_utilities,
)


def test_evaluate_match_is_deterministic_with_seeded_duplicate_hands():
    first = evaluate_match(
        BotSpec("check_call", check_call_bot),
        BotSpec("random", legal_random_bot),
        hands=8,
        seed=123,
        duplicate=True,
    )
    second = evaluate_match(
        BotSpec("check_call", check_call_bot),
        BotSpec("random", legal_random_bot),
        hands=8,
        seed=123,
        duplicate=True,
    )

    assert first.to_dict() == second.to_dict()
    assert first.metrics.total_hands == 16
    assert first.metrics.bb_per_100 == pytest.approx(first.metrics.ev_per_hand / 2 * 100)


def test_duplicate_same_policy_match_is_symmetric():
    result = evaluate_match(
        BotSpec("check_call_a", check_call_bot),
        BotSpec("check_call_b", check_call_bot),
        hands=6,
        seed=77,
        duplicate=True,
    )

    assert result.metrics.total_hands == 12
    assert result.metrics.total_chips == 0
    assert result.metrics.ev_per_hand == 0
    assert result.metrics.bb_per_100 == 0


def test_confidence_interval_and_variance_sanity():
    summary = summarize_utilities([2, -2, 4, -4])
    low, high = confidence_interval(summary.mean, summary.standard_error)

    assert summary.total == 0
    assert summary.mean == 0
    assert summary.variance == pytest.approx(40 / 3)
    assert summary.standard_error == pytest.approx(math.sqrt((40 / 3) / 4))
    assert low < summary.mean < high


def test_hand_histories_include_research_fields():
    result = evaluate_match(
        BotSpec("check_call", check_call_bot),
        BotSpec("random", legal_random_bot),
        hands=2,
        seed=9,
        duplicate=True,
    )
    history = result.hand_histories[0]

    assert {
        "seed",
        "duplicate_group",
        "hand_index",
        "hole_cards",
        "board",
        "actions",
        "pot_sizes",
        "stacks",
        "terminal_result",
        "winner",
        "showdown_hands",
        "bot_decisions",
    }.issubset(history)
    assert history["actions"]
    assert history["bot_decisions"]
    assert history["terminal_result"]["utilities"]


def test_bot_api_accepts_callable_and_act_object():
    def callable_bot(state: HoldemState, player: int, rng: random.Random) -> Action:
        del player, rng
        return "call" if "call" in state.legal_actions() else state.legal_actions()[0]

    class ObjectBot:
        def act(self, state: HoldemState, player: int, rng: random.Random) -> Action:
            del player, rng
            return "check" if "check" in state.legal_actions() else state.legal_actions()[0]

    result = evaluate_match(
        BotSpec("callable", callable_bot),
        BotSpec("object", ObjectBot()),
        hands=3,
        seed=11,
        duplicate=False,
    )

    assert result.metrics.total_hands == 3


def test_illegal_bot_action_is_rejected():
    def illegal_bot(state: HoldemState, player: int, rng: random.Random) -> Action:
        del state, player, rng
        return "raise"

    with pytest.raises(ValueError, match="illegal action"):
        evaluate_match(BotSpec("bad", illegal_bot), BotSpec("check_call", check_call_bot), hands=1, seed=1)


def test_metrics_do_not_depend_on_storing_histories():
    with_histories = evaluate_match(
        BotSpec("random", legal_random_bot),
        BotSpec("check_call", check_call_bot),
        hands=10,
        seed=5,
        duplicate=True,
        store_histories=True,
    )
    without_histories = evaluate_match(
        BotSpec("random", legal_random_bot),
        BotSpec("check_call", check_call_bot),
        hands=10,
        seed=5,
        duplicate=True,
        store_histories=False,
    )

    assert without_histories.hand_histories == []
    assert without_histories.metrics.to_dict() == with_histories.metrics.to_dict()
    assert without_histories.metrics.aggression_frequency > 0
