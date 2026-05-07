from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app
from leduc_cfr.holdem.engine import Card, HoldemState, deck, evaluate_hand, fresh_holdem_state


def C(value: str) -> Card:
    return Card.parse(value)


def test_hand_evaluator_orders_major_categories():
    high_card = evaluate_hand([C("As"), C("Kd"), C("9h"), C("7c"), C("3s")])
    pair = evaluate_hand([C("As"), C("Ad"), C("9h"), C("7c"), C("3s")])
    two_pair = evaluate_hand([C("As"), C("Ad"), C("9h"), C("9c"), C("3s")])
    trips = evaluate_hand([C("As"), C("Ad"), C("Ah"), C("9c"), C("3s")])
    straight = evaluate_hand([C("As"), C("Kd"), C("Qh"), C("Jc"), C("Ts")])
    flush = evaluate_hand([C("As"), C("Ks"), C("9s"), C("7s"), C("3s")])
    full_house = evaluate_hand([C("As"), C("Ad"), C("Ah"), C("9c"), C("9s")])
    quads = evaluate_hand([C("As"), C("Ad"), C("Ah"), C("Ac"), C("9s")])
    straight_flush = evaluate_hand([C("As"), C("Ks"), C("Qs"), C("Js"), C("Ts")])

    assert high_card < pair < two_pair < trips < straight < flush < full_house < quads < straight_flush


def test_wheel_straight_is_recognized():
    assert evaluate_hand([C("As"), C("2d"), C("3h"), C("4c"), C("5s")]) == (4, (5,))


def test_deck_has_52_unique_cards():
    cards = deck()

    assert len(cards) == 52
    assert len({str(card) for card in cards}) == 52


def test_seeded_deals_are_deterministic():
    first = fresh_holdem_state(seed=17)
    second = fresh_holdem_state(seed=17)
    other = fresh_holdem_state(seed=18)

    assert first.hole_cards == second.hole_cards
    assert first.deck_cards == second.deck_cards
    assert (first.hole_cards, first.deck_cards) != (other.hole_cards, other.deck_cards)


def test_shared_lcg_seeded_deals_are_deterministic_for_rust_parity():
    first = fresh_holdem_state(seed=17, shuffle_algorithm="lcg")
    second = fresh_holdem_state(seed=17, shuffle_algorithm="lcg")
    other = fresh_holdem_state(seed=18, shuffle_algorithm="lcg")

    assert first.hole_cards == second.hole_cards
    assert first.deck_cards == second.deck_cards
    assert (first.hole_cards, first.deck_cards) != (other.hole_cards, other.deck_cards)


def test_button_posts_small_blind_and_acts_preflop():
    state = fresh_holdem_state(seed=1, button=0)

    assert state.button == 0
    assert state.small_blind_player == 0
    assert state.big_blind_player == 1
    assert state.current_player == 0
    assert state.stacks == (99, 98)
    assert state.contributions == (1, 2)
    assert state.legal_actions() == ("fold", "call", "raise", "all-in")


def test_button_one_posts_small_blind_and_acts_preflop():
    state = fresh_holdem_state(seed=1, button=1)

    assert state.button == 1
    assert state.small_blind_player == 1
    assert state.big_blind_player == 0
    assert state.current_player == 1
    assert state.stacks == (98, 99)
    assert state.contributions == (2, 1)
    assert state.to_call(1) == 1


def test_call_check_advances_to_flop():
    state = HoldemState(
        deck_cards=(C("2c"), C("3c"), C("4c"), C("5d"), C("6d")),
        hole_cards=((C("As"), C("Kd")), (C("Qh"), C("Jh"))),
    )

    state = state.apply("call")
    assert state.street == "preflop"
    state = state.apply("check")
    assert state.street == "flop"
    assert state.current_player == 1
    assert [str(card) for card in state.board] == ["2c", "3c", "4c"]


def test_postflop_bet_call_advances_turn_with_pot_accounting():
    state = HoldemState(
        deck_cards=(C("2c"), C("3c"), C("4c"), C("5d"), C("6d"), C("7s"), C("8s")),
        hole_cards=((C("As"), C("Kd")), (C("Qh"), C("Jh"))),
    )

    state = state.apply("call").apply("check")
    assert state.street == "flop"
    assert state.current_player == 1

    state = state.apply("bet")
    assert state.contributions == (2, 4)
    assert state.to_call(0) == 2
    state = state.apply("call")

    assert state.street == "turn"
    assert state.board == (C("2c"), C("3c"), C("4c"), C("5d"))
    assert state.contributions == (4, 4)
    assert state.pot == 8


def test_all_in_call_runs_board_to_showdown():
    state = HoldemState(
        deck_cards=(C("2c"), C("7d"), C("9s"), C("Tc"), C("3h")),
        hole_cards=((C("As"), C("Ad")), (C("Qh"), C("Jh"))),
        stacks=(3, 98),
        contributions=(1, 2),
        street_bets=(1, 2),
    )

    state = state.apply("all-in")
    assert not state.terminal
    assert state.current_player == 1
    assert state.to_call() == 2

    state = state.apply("call")

    assert state.terminal
    assert state.street == "showdown"
    assert len(state.board) == 5
    assert state.showdown_winner() == 0
    assert state.final_stacks() == (8, 96)
    assert state.utility(0) == 4
    assert state.history == ("preflop:p0:all-in:3", "preflop:p1:call:2")


def test_fold_terminal_utility():
    state = HoldemState(
        deck_cards=(C("2c"), C("3c"), C("4c"), C("5d"), C("6d")),
        hole_cards=((C("As"), C("Kd")), (C("Qh"), C("Jh"))),
    )

    state = state.apply("fold")

    assert state.terminal
    assert state.utility(0) == -1
    assert state.utility(1) == 1


def test_showdown_winner_gets_pot_minus_contribution():
    state = HoldemState(
        deck_cards=(),
        hole_cards=((C("As"), C("Ad")), (C("Qh"), C("Jh"))),
        board=(C("2c"), C("7d"), C("9s"), C("Tc"), C("3h")),
        street="showdown",
        terminal=True,
        contributions=(10, 10),
        stacks=(90, 90),
        street_bets=(0, 0),
    )

    assert state.showdown_winner() == 0
    assert state.final_stacks() == (110, 90)
    assert state.utility(0) == 10
    assert state.utility(1) == -10


def test_showdown_returns_uncalled_all_in_overage():
    state = HoldemState(
        deck_cards=(),
        hole_cards=((C("As"), C("Kd")), (C("Qh"), C("Qd"))),
        board=(C("2c"), C("7d"), C("9s"), C("Tc"), C("3h")),
        street="showdown",
        terminal=True,
        contributions=(10, 5),
        stacks=(90, 95),
        street_bets=(0, 0),
    )

    assert state.showdown_winner() == 1
    assert state.final_stacks() == (95, 105)
    assert state.utility(0) == -5
    assert state.utility(1) == 5


def test_showdown_tie_splits_pot_with_odd_chip_to_player_zero():
    state = HoldemState(
        deck_cards=(),
        hole_cards=((C("As"), C("Kd")), (C("Ah"), C("Kc"))),
        board=(C("Qs"), C("Jd"), C("Th"), C("2c"), C("3h")),
        street="showdown",
        terminal=True,
        contributions=(5, 4),
        stacks=(95, 96),
        street_bets=(0, 0),
    )

    assert state.showdown_winner() is None
    assert state.final_stacks() == (100, 100)
    assert state.utility(0) == 0
    assert state.utility(1) == 0


def test_evaluator_uses_best_seven_card_tiebreakers():
    ace_kicker_pair = evaluate_hand([C("As"), C("Ah"), C("Kd"), C("9c"), C("7s"), C("4d"), C("2h")])
    queen_kicker_pair = evaluate_hand([C("Ac"), C("Ad"), C("Qd"), C("9h"), C("7c"), C("4s"), C("2d")])
    higher_flush = evaluate_hand([C("As"), C("Js"), C("8s"), C("5s"), C("3s"), C("Kd"), C("Qh")])
    lower_flush = evaluate_hand([C("Ks"), C("Js"), C("8s"), C("5s"), C("3s"), C("Ad"), C("Qh")])

    assert ace_kicker_pair > queen_kicker_pair
    assert higher_flush > lower_flush


def test_holdem_backend_new_game_and_action_smoke():
    client = TestClient(app)

    response = client.post("/api/holdem/new-game")
    assert response.status_code == 200
    game = response.json()
    assert len(game["hero_cards"]) == 2
    assert game["bot_cards"] == ["?", "?"]
    assert game["street"] == "preflop"
    assert game["legal_actions"]

    action_response = client.post(f"/api/holdem/game/{game['session_id']}/act", json={"action": game["legal_actions"][0]})
    assert action_response.status_code == 200
    updated = action_response.json()
    assert "board" in updated
    assert "pot" in updated
    if not updated["terminal"]:
        assert updated["bot_cards"] == ["?", "?"]
