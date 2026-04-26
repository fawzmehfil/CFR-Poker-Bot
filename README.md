# CFR Poker Engine

Tabular Counterfactual Regret Minimization for Leduc Poker with neural policy approximation, FastAPI/React gameplay, and high-performance Rust simulation/training.

## Overview

Poker is an imperfect-information game: players must act under hidden information, stochastic outcomes, and strategic deception. Unlike perfect-information games such as chess, the value of an action depends on private cards, public history, and the distribution of strategies an opponent may be using.

This project implements a complete research-engineering stack around **Leduc Poker**, a compact benchmark game commonly used for studying imperfect-information algorithms. Leduc is small enough for tabular methods and exhaustive game-tree evaluation, but still contains the essential poker structure: private cards, a public card, betting rounds, folds, showdowns, information sets, and mixed strategies.

The core solver uses **Counterfactual Regret Minimization (CFR/CFR+)** to learn average strategies over information sets. Around that solver, the repo includes evaluation tooling, a PyTorch policy imitation model, a playable FastAPI + React app, and a Rust engine that supports both high-throughput simulation benchmarks and full CFR traversal for Leduc.

## Architecture

```text
                    +-----------------------------+
                    |       Evaluation Scripts     |
                    |  EV, proxy gap, matchups     |
                    +--------------+--------------+
                                   |
+------------------+      +--------v---------+      +------------------+
| Python Leduc     | ---> | CFR / CFR+       | ---> | Strategy Profile |
| game engine      |      | trainer          |      | JSON artifacts   |
+------------------+      +--------+---------+      +---------+--------+
                                    |                          |
                                    v                          v
                           +----------------+        +------------------+
                           | PyTorch policy |        | FastAPI backend  |
                           | approximation  |        | bot selection    |
                           +----------------+        +---------+--------+
                                                               |
                                                               v
                                                    +------------------+
                                                    | React Play vs Bot|
                                                    +------------------+

+------------------+       +------------------------------+
| Rust engine      | ----> | Full CFR traversal + rollout  |
| performance layer|       | Python fallback remains safe  |
+------------------+       +------------------------------+
```

Main components:

- `leduc_cfr/poker`: Python Leduc engine with legal actions, betting transitions, terminal utilities, and information-set keys.
- `leduc_cfr/cfr`: Tabular CFR/CFR+ trainer with regret matching and average strategy extraction.
- `leduc_cfr/eval`: Expected value, diagnostic nash-gap proxy, seeded head-to-head matchups, confidence intervals, and optional Rust benchmark integration.
- `leduc_cfr/neural`: PyTorch MLP trained to imitate the CFR average strategy.
- `backend`: FastAPI service for playable bot sessions with random, heuristic, CFR, and neural modes.
- `frontend`: React UI for Play vs Bot.
- `engine`: Rust Leduc engine, benchmark binary, and full CFR traversal trainer. The Python trainer remains available as a fallback and comparison implementation.

## Core Algorithms

### Counterfactual Regret Minimization

CFR iteratively traverses the game tree and updates regret values at each information set. An information set groups states that are indistinguishable to the acting player, such as having the same private card, public card, betting round, and action history.

At each information set:

1. **Regret matching** converts positive cumulative regrets into a mixed strategy.
2. The game tree is recursively evaluated under current reach probabilities.
3. Counterfactual regrets are accumulated for actions that would have improved value.
4. The average strategy is accumulated over visits and used as the final policy.

The implementation supports both standard CFR and CFR+, with CFR+ clipping cumulative regrets at zero.

### Neural Policy Approximation

The neural model is trained by supervised imitation of the CFR average strategy. Each training example encodes:

- acting player
- private card
- public card including hidden state
- betting round
- pot size
- amount to call
- raise count
- compressed action history

The target is the CFR average action distribution for that information set. This model is an approximation of the tabular strategy, not an independent solver.

## Performance & Metrics

The numbers below are from the current generated artifacts in `data/`. Exact metrics are labeled as such; the nash-gap value is a diagnostic proxy based on full-information best response, not exact exploitability.

### CFR Metrics

| Metric | Value | Notes |
|---|---:|---|
| Information sets | 288 | Tabular Leduc infosets |
| Expected value P0 | -0.0856 | Exact EV when both seats use saved average strategy |
| Nash gap upper bound proxy | 1.9819 | Full-information diagnostic proxy |
| CFR vs random avg utility | 0.7994 | 5,000 simulated hands |
| CFR vs random win rate | 0.4662 | 95% CI: [0.4475, 0.4849] |
| CFR vs heuristic avg utility | 0.0578 | 5,000 simulated hands |
| CFR vs heuristic win rate | 0.3776 | 95% CI: [0.3559, 0.3993] |

### Neural Metrics

| Metric | Value | Notes |
|---|---:|---|
| Training examples | 288 | One per CFR information set |
| KL divergence to CFR policy | 0.1129 | Supervised imitation loss |
| Cross-entropy | 0.3724 | Against CFR average strategy |
| Neural vs CFR avg utility | -0.0660 | Slightly negative, expected for approximation |
| Neural vs random avg utility | 0.8194 | 5,000 simulated hands |
| Neural vs heuristic avg utility | 0.0044 | Near break-even with wide CI |

### Rust Performance

| Metric | Value |
|---|---:|
| Python CFR traversals/sec | 8,298 |
| Rust CFR traversals/sec | 31,954 |
| Rust CFR training speedup | ~3.8x |
| Python random hands/sec | 62,684 |
| Rust random hands/sec | 23,198,402 |
| Speedup factor | 370.08x |
| Rust terminal rollouts/sec | 24,459,895 |
| Rust state transitions/sec | ~145M |
| Correctness comparison | Passed against Python trace |

## Benchmark Summary

The CFR strategy has learned useful poker behavior in Leduc: it strongly outperforms a random policy by average utility, while performance against the heuristic baseline is positive but noisy. The nash-gap value is best interpreted as a convergence diagnostic rather than exact exploitability.

The neural policy approximates the CFR average strategy with low KL divergence, but it is not a replacement for CFR. Its head-to-head result against CFR is slightly negative, which is expected for an imitation model trained on a small tabular policy.

The Rust engine demonstrates the systems value of separating high-throughput game traversal from the Python research stack. The benchmark reaches roughly 23.2M random hands/sec and about 145M state transitions/sec while matching deterministic Python traces for legal actions, terminal states, and utility. Full Rust CFR traversal now matches the Python best-gap strategy quality while running about 3.8x faster on this workload. Python remains the fallback via `--engine python`.

Checkpoint selection matters. `best_gap` favors the lowest diagnostic exploitability proxy; `best_heuristic` favors exploitative performance against the rule-based baseline; `balanced` trades off gap, random-policy utility, and heuristic-policy utility. The default path uses Rust CFR for `best_gap` because that mode matches Python quality with better throughput.

## Usage

### Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm install --prefix frontend
```

### Tests

```bash
.venv/bin/python -m pytest
```

### Train CFR

```bash
.venv/bin/python scripts/train_cfr.py
```

Useful presets and selection modes:

```bash
.venv/bin/python scripts/train_cfr.py --preset quick
.venv/bin/python scripts/train_cfr.py --preset strong --selection best_gap
.venv/bin/python scripts/train_cfr.py --preset strong --selection balanced
.venv/bin/python scripts/train_cfr.py --engine python --selection best_gap
.venv/bin/python scripts/train_cfr.py --engine rust --selection best_heuristic
```

### Train Neural Policy

```bash
.venv/bin/python scripts/train_policy.py
```

Outputs:

```text
data/policy.pt
data/policy_metrics.json
```

### Evaluation

```bash
.venv/bin/python scripts/evaluate.py --engine auto
.venv/bin/python scripts/evaluate.py --engine python
.venv/bin/python scripts/evaluate.py --engine rust
```

Outputs:

```text
data/eval.json
data/eval.png
data/rust_benchmark.json
data/performance_summary.md
```

### Run the App

Terminal 1:

```bash
uvicorn backend.main:app --reload
```

Terminal 2:

```bash
npm run dev --prefix frontend
```

Open the Vite URL, usually `http://localhost:5173`.

### Rust Benchmark

```bash
cd engine
cargo test
cargo run --release --bin bench
cargo run --release --bin train_cfr -- --iterations 1000 --selection best_gap --out ../data/cfr_strategy_rust.json
```

Outputs:

```text
data/rust_benchmark.json
data/performance_summary.md
```

## Project Structure

```text
backend/
  main.py                    FastAPI game service
engine/
  src/lib.rs                 Rust Leduc engine
  src/bin/bench.rs           Rust benchmark and Python comparison
  src/bin/train_cfr.rs       Rust CFR traversal trainer
frontend/
  src/App.jsx                React Play vs Bot UI
  src/styles.css             UI styling
leduc_cfr/
  poker/leduc.py             Python Leduc engine
  cfr/trainer.py             CFR/CFR+ solver
  eval/metrics.py            Evaluation and matchup metrics
  neural/policy.py           PyTorch policy approximation
scripts/
  train_cfr.py               CFR training and checkpoint selection
  train_policy.py            Neural imitation training
  evaluate.py                Evaluation and plots
tests/
  test_leduc.py              Game engine tests
  test_cfr.py                CFR tests
  test_eval.py               Evaluation tests
  test_policy.py             Neural dataset/training tests
  test_backend.py            API smoke tests
data/
  *.json, *.png, *.pt        Generated metrics, plots, and models
```

## Design Decisions

- **Leduc over Hold'em:** Leduc is small enough for tabular CFR and exhaustive analysis, while still representing imperfect information, betting, folds, and showdowns.
- **Tabular CFR first:** A correct tabular baseline is easier to verify and provides a reliable target for neural approximation.
- **Neural as imitation:** The PyTorch model compresses the CFR average strategy into a learned policy. It is measured against CFR and not presented as independently superior.
- **Rust as a performance layer:** Rust now handles standalone simulation benchmarks and full Leduc CFR traversal. Python remains the orchestration and fallback layer.
- **Optional Rust evaluation acceleration:** Evaluation can call the Rust benchmark path for random rollout throughput and correctness validation. Python remains the fallback and the default-safe execution path.
- **Selection is explicit:** Best-gap selection optimizes the convergence proxy; heuristic and balanced modes are available when exploitative matchup performance is the priority.
- **Proxy metrics are labeled:** The nash-gap upper bound is a diagnostic using full-information best response, not exact exploitability.

## Limitations

- The solved game is Leduc Poker, not full Texas Hold'em.
- The exploitability-style metric is a proxy, not a mathematically exact exploitability computation.
- The neural policy is supervised imitation of CFR, not reinforcement learning from self-play.
- Rust CFR traversal is standalone and file-based; it is not yet exposed as an in-process Python extension.
- Matchup results have sampling variance; confidence intervals should be considered when comparing policies.

## Future Work

- Add in-process Rust bindings for CFR traversal to remove subprocess orchestration overhead.
- Add exact imperfect-information exploitability or stronger best-response tooling.
- Scale evaluation with larger multi-seed matchup matrices.
- Improve neural architectures and validation protocols.
- Add a separate heads-up Texas Hold'em playable demo without attempting full CFR over Hold'em.

## Resume Bullets

- Built a full-stack imperfect-information poker research system with tabular CFR/CFR+, PyTorch policy imitation, seeded evaluation, FastAPI serving, and a React Play vs Bot interface.
- Implemented Rust Leduc simulation and full CFR traversal, reaching approximately 3.8x Python CFR training throughput and roughly 23.2M simulated hands/sec with deterministic correctness checks.
