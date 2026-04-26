from __future__ import annotations

import itertools
from functools import lru_cache

from leduc_cfr.cfr.trainer import StrategyProfile
from leduc_cfr.poker.leduc import CARDS, LeducState


def _expected_value(state: LeducState, profile: StrategyProfile) -> float:
    if state.terminal:
        return state.utility(0)
    legal = state.legal_actions()
    probs = profile.action_probs(state.info_set_key(), legal)
    return sum(probs[action] * _expected_value(state.apply(action), profile) for action in legal)


def expected_game_value(profile: StrategyProfile) -> float:
    deals = list(itertools.permutations(CARDS, 3))
    return sum(_expected_value(LeducState(deal=deal), profile) for deal in deals) / len(deals)


def full_information_best_response_values(profile: StrategyProfile) -> tuple[float, float]:
    """Return a diagnostic upper bound, not exact imperfect-information exploitability.

    The game tree stores all chance cards in the state, so this best response can
    condition on hidden cards. It is useful as a regression/evaluation signal but
    intentionally named as an upper bound.
    """

    deals = list(itertools.permutations(CARDS, 3))

    @lru_cache(maxsize=None)
    def br_value(state: LeducState, br_player: int) -> float:
        if state.terminal:
            return state.utility(br_player)
        legal = state.legal_actions()
        if state.current_player == br_player:
            return max(br_value(state.apply(action), br_player) for action in legal)
        probs = profile.action_probs(state.info_set_key(), legal)
        return sum(probs[action] * br_value(state.apply(action), br_player) for action in legal)

    p0 = sum(br_value(LeducState(deal=deal), 0) for deal in deals) / len(deals)
    p1 = sum(br_value(LeducState(deal=deal), 1) for deal in deals) / len(deals)
    return p0, p1


def nash_gap_upper_bound(profile: StrategyProfile) -> float:
    p0, p1 = full_information_best_response_values(profile)
    return (p0 + p1) / 2
