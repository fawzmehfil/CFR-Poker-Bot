from leduc_cfr.cfr.trainer import CFRTrainer
from leduc_cfr.eval.metrics import head_to_head, heuristic_policy, policy_head_to_head, random_policy, strategy_profile_policy


def test_head_to_head_reports_real_rates_and_utility():
    trainer = CFRTrainer(cfr_plus=True)
    trainer.train(2)
    profile = trainer.profile()

    metrics = head_to_head(profile, random_policy, hands=20, seed=11)

    assert metrics["hands"] == 20
    assert 0 <= metrics["win_rate"] <= 1
    assert 0 <= metrics["loss_rate"] <= 1
    assert 0 <= metrics["draw_rate"] <= 1
    assert abs(metrics["win_rate"] + metrics["loss_rate"] + metrics["draw_rate"] - 1) < 1e-9
    assert isinstance(metrics["avg_utility"], float)


def test_heuristic_head_to_head_is_seeded_and_reproducible():
    trainer = CFRTrainer(cfr_plus=True)
    trainer.train(2)
    profile = trainer.profile()

    first = head_to_head(profile, heuristic_policy, hands=20, seed=5)
    second = head_to_head(profile, heuristic_policy, hands=20, seed=5)

    assert first == second


def test_policy_head_to_head_supports_profile_policy():
    trainer = CFRTrainer(cfr_plus=True)
    trainer.train(2)
    profile = trainer.profile()

    metrics = policy_head_to_head(strategy_profile_policy(profile), random_policy, hands=20, seed=3)

    assert metrics["hands"] == 20
    assert 0 <= metrics["win_rate"] <= 1
