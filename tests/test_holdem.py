from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app
from leduc_cfr.holdem.engine import Card, HoldemState, evaluate_hand


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


def test_call_check_advances_to_flop():
    state = HoldemState(
        deck_cards=(C("2c"), C("3c"), C("4c"), C("5d"), C("6d")),
        hole_cards=((C("As"), C("Kd")), (C("Qh"), C("Jh"))),
    )

    state = state.apply("call")
    assert state.street == "preflop"
    state = state.apply("check")
    assert state.street == "flop"
    assert [str(card) for card in state.board] == ["2c", "3c", "4c"]


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
    assert state.utility(0) == 10
    assert state.utility(1) == -10


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
