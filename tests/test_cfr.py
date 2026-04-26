from leduc_cfr.cfr.trainer import CFRTrainer, InfoSet
from leduc_cfr.eval.metrics import nash_gap_upper_bound
from leduc_cfr.poker.leduc import LeducState


def test_cfr_smoke_produces_infosets_and_probabilities():
    trainer = CFRTrainer(cfr_plus=True)
    trainer.train(2)
    profile = trainer.profile()
    assert profile.strategies
    for probs in profile.strategies.values():
        assert abs(sum(probs.values()) - 1.0) < 1e-6


def test_regret_matching_uses_positive_regrets_only():
    info = InfoSet(regret_sum={"k": -2.0, "b": 6.0})
    strategy = info.strategy(("k", "b"))

    assert strategy == {"k": 0.0, "b": 1.0}


def test_regret_matching_falls_back_to_uniform_when_no_positive_regret():
    info = InfoSet(regret_sum={"f": -1.0, "c": 0.0, "r": -3.0})
    strategy = info.strategy(("f", "c", "r"))

    assert strategy == {"f": 1 / 3, "c": 1 / 3, "r": 1 / 3}


def test_average_strategy_normalizes_accumulated_reach_weights():
    info = InfoSet(strategy_sum={"k": 3.0, "b": 1.0})
    avg = info.average_strategy()

    assert avg == {"b": 0.25, "k": 0.75}
    assert abs(sum(avg.values()) - 1.0) < 1e-9


def test_terminal_utility_sign_from_each_player_perspective():
    folded = LeducState(deal=("K1", "Q1", "J1")).apply("b").apply("f")
    showdown = (
        LeducState(deal=("K1", "Q1", "J1"))
        .apply("k")
        .apply("k")
        .apply("k")
        .apply("k")
    )

    assert folded.utility(0) == -folded.utility(1)
    assert showdown.utility(0) == -showdown.utility(1)


def test_cfr_plus_keeps_regrets_non_negative():
    trainer = CFRTrainer(cfr_plus=True)
    trainer.train(3)

    assert all(regret >= 0 for info in trainer.info_sets.values() for regret in info.regret_sum.values())


def test_convergence_proxy_improves_with_more_iterations():
    early = CFRTrainer(cfr_plus=True)
    early.train(1)
    later = CFRTrainer(cfr_plus=True)
    later.train(20)

    assert nash_gap_upper_bound(later.profile()) < nash_gap_upper_bound(early.profile())
