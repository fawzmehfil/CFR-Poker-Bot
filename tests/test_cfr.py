from leduc_cfr.cfr.trainer import CFRTrainer


def test_cfr_smoke_produces_infosets_and_probabilities():
    trainer = CFRTrainer(cfr_plus=True)
    trainer.train(2)
    profile = trainer.profile()
    assert profile.strategies
    for probs in profile.strategies.values():
        assert abs(sum(probs.values()) - 1.0) < 1e-6

