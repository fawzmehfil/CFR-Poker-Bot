from leduc_cfr.poker.leduc import LeducState


def test_check_check_advances_to_public_round():
    state = LeducState(deal=("K1", "Q1", "J1"))
    state = state.apply("k").apply("k")
    assert state.round_index == 1
    assert state.current_player == 0
    assert state.public_card == "J1"


def test_bet_call_showdown_utility_is_zero_sum():
    state = LeducState(deal=("K1", "Q1", "J1"))
    state = state.apply("b").apply("c")
    state = state.apply("b").apply("c")
    assert state.terminal
    assert state.utility(0) == -state.utility(1)


def test_fold_awards_pot_to_other_player():
    state = LeducState(deal=("K1", "Q1", "J1"))
    state = state.apply("b").apply("f")
    assert state.terminal
    assert state.utility(0) == 1
    assert state.utility(1) == -1

