from __future__ import annotations

import itertools
import random
from functools import lru_cache
from typing import Callable

from leduc_cfr.cfr.trainer import StrategyProfile
from leduc_cfr.poker.leduc import Action, CARDS, LeducState, RANKS, rank, random_deal


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


BotPolicy = Callable[[LeducState, int, random.Random], Action]


def random_policy(state: LeducState, player: int, rng: random.Random) -> Action:
    del player
    return rng.choice(state.legal_actions())


def heuristic_policy(state: LeducState, player: int, rng: random.Random) -> Action:
    del rng
    legal = state.legal_actions()
    private_rank = rank(state.private_cards[player])
    public_rank = rank(state.public_card) if state.round_index == 1 else None
    has_pair = public_rank == private_rank
    is_high_card = RANKS.index(private_rank) == len(RANKS) - 1
    is_low_card = RANKS.index(private_rank) == 0

    if state.to_call(player) == 0:
        if "b" in legal and (has_pair or (state.round_index == 0 and is_high_card)):
            return "b"
        return "k"

    if "r" in legal and has_pair:
        return "r"
    if "c" in legal and (has_pair or is_high_card or state.to_call(player) <= 2):
        return "c"
    if "f" in legal and is_low_card:
        return "f"
    return "c" if "c" in legal else legal[0]


def strategy_profile_policy(profile: StrategyProfile) -> BotPolicy:
    def policy(state: LeducState, player: int, rng: random.Random) -> Action:
        return profile.sample_action(state.info_set_key(player), state.legal_actions(), rng)

    return policy


def play_hand(
    profile: StrategyProfile,
    opponent_policy: BotPolicy,
    cfr_player: int,
    rng: random.Random,
) -> float:
    state = LeducState(deal=random_deal(rng))
    while not state.terminal:
        legal = state.legal_actions()
        if state.current_player == cfr_player:
            action = profile.sample_action(state.info_set_key(cfr_player), legal, rng)
        else:
            action = opponent_policy(state, state.current_player, rng)
        state = state.apply(action)
    return state.utility(cfr_player)


def play_policy_hand(
    agent_policy: BotPolicy,
    opponent_policy: BotPolicy,
    agent_player: int,
    rng: random.Random,
) -> float:
    state = LeducState(deal=random_deal(rng))
    while not state.terminal:
        if state.current_player == agent_player:
            action = agent_policy(state, state.current_player, rng)
        else:
            action = opponent_policy(state, state.current_player, rng)
        state = state.apply(action)
    return state.utility(agent_player)


def head_to_head(
    profile: StrategyProfile,
    opponent_policy: BotPolicy,
    hands: int = 1000,
    seed: int = 7,
) -> dict[str, float | int]:
    rng = random.Random(seed)
    utilities = []
    wins = 0
    losses = 0
    draws = 0

    for hand_index in range(hands):
        utility = play_hand(profile, opponent_policy, cfr_player=hand_index % 2, rng=rng)
        utilities.append(utility)
        if utility > 0:
            wins += 1
        elif utility < 0:
            losses += 1
        else:
            draws += 1

    return {
        "hands": hands,
        "win_rate": wins / hands if hands else 0.0,
        "loss_rate": losses / hands if hands else 0.0,
        "draw_rate": draws / hands if hands else 0.0,
        "avg_utility": sum(utilities) / hands if hands else 0.0,
    }


def policy_head_to_head(
    agent_policy: BotPolicy,
    opponent_policy: BotPolicy,
    hands: int = 1000,
    seed: int = 7,
) -> dict[str, float | int]:
    rng = random.Random(seed)
    utilities = []
    wins = 0
    losses = 0
    draws = 0

    for hand_index in range(hands):
        utility = play_policy_hand(agent_policy, opponent_policy, agent_player=hand_index % 2, rng=rng)
        utilities.append(utility)
        if utility > 0:
            wins += 1
        elif utility < 0:
            losses += 1
        else:
            draws += 1

    return {
        "hands": hands,
        "win_rate": wins / hands if hands else 0.0,
        "loss_rate": losses / hands if hands else 0.0,
        "draw_rate": draws / hands if hands else 0.0,
        "avg_utility": sum(utilities) / hands if hands else 0.0,
    }
