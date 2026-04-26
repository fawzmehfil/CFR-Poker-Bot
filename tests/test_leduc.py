from leduc_cfr.poker.leduc import LeducState


def play_to_showdown(deal=("K1", "Q1", "J1")):
    state = LeducState(deal=deal)
    state = state.apply("k").apply("k")
    return state.apply("k").apply("k")


def test_initial_state_legal_actions_and_accounting():
    state = LeducState(deal=("K1", "Q1", "J1"))
    assert state.legal_actions() == ("k", "b")
    assert state.current_player == 0
    assert state.pot == 2
    assert state.contributions == (1, 1)
    assert state.to_call() == 0


def test_check_check_advances_to_public_round():
    state = LeducState(deal=("K1", "Q1", "J1"))
    state = state.apply("k").apply("k")
    assert state.round_index == 1
    assert state.current_player == 0
    assert state.public_card == "J1"
    assert state.visible_public() == "J1"
    assert state.contributions == (1, 1)
    assert not state.terminal


def test_bet_call_advances_to_public_round():
    state = LeducState(deal=("K1", "Q1", "J1"))
    state = state.apply("b").apply("c")
    assert state.round_index == 1
    assert state.current_player == 0
    assert state.pot == 6
    assert state.contributions == (3, 3)
    assert state.round_bets == (0, 0)
    assert state.legal_actions() == ("k", "b")


def test_bet_call_showdown_utility_is_zero_sum():
    state = LeducState(deal=("K1", "Q1", "J1"))
    state = state.apply("b").apply("c")
    state = state.apply("b").apply("c")
    assert state.terminal
    assert state.utility(0) == -state.utility(1)


def test_bet_fold_ends_hand_and_awards_pot_to_other_player():
    state = LeducState(deal=("K1", "Q1", "J1"))
    state = state.apply("b").apply("f")
    assert state.terminal
    assert state.legal_actions() == ()
    assert state.folded_player == 1
    assert state.pot == 4
    assert state.utility(0) == 1
    assert state.utility(1) == -1


def test_showdown_winner_gets_correct_utility():
    state = play_to_showdown(deal=("K1", "Q1", "J1"))
    assert state.terminal
    assert state.showdown_winner() == 0
    assert state.utility(0) == 1
    assert state.utility(1) == -1


def test_pair_beats_high_card():
    state = play_to_showdown(deal=("K1", "Q1", "Q2"))
    assert state.showdown_winner() == 1
    assert state.utility(1) == 1


def test_higher_rank_wins_when_no_pair():
    state = play_to_showdown(deal=("K1", "Q1", "J1"))
    assert state.showdown_winner() == 0
    assert state.utility(0) == 1


def test_info_set_key_hides_opponent_card():
    king_vs_queen = LeducState(deal=("K1", "Q1", "J1"))
    king_vs_jack = LeducState(deal=("K1", "J1", "J2"))
    assert king_vs_queen.info_set_key(player=0) == king_vs_jack.info_set_key(player=0)
    assert "Q" not in king_vs_queen.info_set_key(player=0)


def test_terminal_states_have_no_legal_actions():
    folded = LeducState(deal=("K1", "Q1", "J1")).apply("b").apply("f")
    showdown = play_to_showdown(deal=("K1", "Q1", "J1"))
    assert folded.legal_actions() == ()
    assert showdown.legal_actions() == ()


def test_public_view_reveals_opponent_card_only_at_terminal():
    state = LeducState(deal=("K1", "Q1", "J1"))
    assert state.public_view(human_player=0)["opponent_card"] is None

    terminal = state.apply("b").apply("f")
    assert terminal.public_view(human_player=0)["opponent_card"] == "Q"
