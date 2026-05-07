# Architecture Map

## Repository Layout

```text
backend/              FastAPI game API
frontend/             React Play vs Bot UI
leduc_cfr/poker/      Python Leduc rules engine
leduc_cfr/cfr/        Python CFR trainer and engine abstraction
leduc_cfr/eval/       EV, matchup, proxy-gap, Rust benchmark integration
leduc_cfr/neural/     PyTorch policy imitation
leduc_cfr/holdem/     Separate playable heads-up Hold'em demo engine
engine/               Rust Leduc engine, benchmark, CFR traversal
scripts/              Train/evaluate entrypoints
tests/                Unit/API/smoke tests
data/                 Generated strategies, metrics, plots, models
```

## Major Modules

- `leduc_cfr/poker/leduc.py`: Python Leduc game state, legal actions, betting transitions, terminal utility, public views, infoset keys.
- `leduc_cfr/cfr/trainer.py`: Python CFR/CFR+ trainer, regret matching, average strategy extraction, Python/Rust engine selection fallback.
- `leduc_cfr/cfr/engine.py`: Python/Rust engine abstraction for state operations. Per-action FFI exists but is not the preferred fast training path.
- `leduc_cfr/eval/metrics.py`: exact EV over Leduc deals, head-to-head matchups, confidence intervals, full-information nash-gap proxy.
- `leduc_cfr/eval/rust_engine.py`: optional Rust evaluation/simulation bridge.
- `leduc_cfr/neural/policy.py`: PyTorch dataset encoding, policy model, neural policy loader/sampler.
- `leduc_cfr/holdem/engine.py`: separate 2-player Hold'em demo engine, evaluator, fixed-limit betting, heuristic bot.
- `engine/src/lib.rs`: Rust Leduc rules engine and C ABI helpers.
- `engine/src/bin/bench.rs`: Rust benchmark and Python comparison.
- `engine/src/bin/train_cfr.rs`: full Rust CFR traversal binary.
- `backend/main.py`: FastAPI Leduc and Hold'em game endpoints.
- `frontend/src/App.jsx`: React UI with Leduc/Hold'em mode toggle.
- `scripts/train_cfr.py`: CFR training orchestration. Rust is default for `--selection best_gap` under `--engine auto`.
- `scripts/train_policy.py`: CFR-to-neural imitation training.
- `scripts/evaluate.py`: evaluation JSON/plot generation.

## Data Flow

### Training

```text
scripts/train_cfr.py
  -> Rust CFR binary or Python CFR fallback
  -> data/cfr_strategy.json
  -> scripts/evaluate.py
```

### Neural

```text
data/cfr_strategy.json
  -> scripts/train_policy.py
  -> data/policy.pt + data/policy_metrics.json
```

### App

```text
React UI
  -> FastAPI endpoints
  -> bot policy
  -> Leduc/Hold'em state transition
  -> public response
```

### Rust

```text
Rust Leduc engine
  -> benchmark/evaluation/full CFR traversal
  -> JSON strategy + metrics artifacts
```

## Engine Modes

- CFR training default: `--engine auto --selection best_gap` uses full Rust CFR traversal.
- Python training fallback: `--engine python`.
- Explicit Rust training: `--engine rust`.
- Evaluation: `--engine auto`, `--engine python`, `--engine rust`.

## Strategy/Bot Modes

- `random`: uniform legal-action sampling.
- `heuristic`: rule-based Leduc or Hold'em policy.
- `cfr`: tabular average strategy from `data/cfr_strategy.json`.
- `neural`: PyTorch imitation policy, falling back to CFR if unavailable.

## Where To Change Things

- Leduc rules: `leduc_cfr/poker/leduc.py` and `engine/src/lib.rs`.
- Python CFR: `leduc_cfr/cfr/trainer.py`.
- Rust CFR: `engine/src/bin/train_cfr.rs`.
- Evaluation: `leduc_cfr/eval/metrics.py`, `leduc_cfr/eval/rust_engine.py`, `scripts/evaluate.py`.
- Neural policy: `leduc_cfr/neural/policy.py`, `scripts/train_policy.py`.
- Backend API: `backend/main.py`.
- UI: `frontend/src/App.jsx`, `frontend/src/styles.css`.
- Hold'em demo: `leduc_cfr/holdem/`, Hold'em backend routes, UI mode toggle, `tests/test_holdem.py`.
