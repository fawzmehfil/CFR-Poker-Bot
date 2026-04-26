from leduc_cfr.cfr.trainer import CFRTrainer
from leduc_cfr.neural.policy import INPUT_DIM, build_policy_dataset, train_policy_from_strategy


def test_policy_dataset_uses_state_features_and_cfr_targets():
    trainer = CFRTrainer(cfr_plus=True)
    trainer.train(2)
    profile = trainer.profile()

    x, y, mask = build_policy_dataset(profile)

    assert x.shape[0] == y.shape[0] == mask.shape[0]
    assert x.shape[1] == INPUT_DIM
    assert y.shape[1] == mask.shape[1] == 5


def test_policy_training_reports_kl_and_cross_entropy():
    trainer = CFRTrainer(cfr_plus=True)
    trainer.train(2)
    metrics = train_policy_from_strategy(trainer.profile(), epochs=1)

    assert metrics["examples"] > 0
    assert metrics["kl_divergence"] >= 0
    assert metrics["cross_entropy"] >= 0
