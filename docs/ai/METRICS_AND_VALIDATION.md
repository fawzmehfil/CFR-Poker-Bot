# Metrics And Validation

## Latest Verified Metrics

| Metric | Value |
|---|---:|
| Current tests | 33 passed |
| Prior Leduc/Rust baseline tests | 27 passed |
| Infosets | 288 |
| Expected game value P0 | ~-0.0856 |
| Nash-gap proxy | ~1.9819 |
| CFR vs random avg utility | ~0.7994 |
| CFR vs heuristic avg utility | ~0.0578 |
| Rust CFR traversals/sec | ~31K |
| Python CFR traversals/sec | ~8.3K |
| Rust CFR speedup | ~3.8x |
| Neural KL divergence | ~0.1129 |
| Neural cross-entropy | ~0.3724 |
| Rust random hands/sec | ~15M-23M |
| Rust state transitions/sec | ~145M |
| Rust simulation speedup | ~265x-370x |

## Metric Meanings

- `infosets`: number of tabular Leduc information sets in the exported strategy.
- `expected_game_value_p0`: exact expected value for player 0 when both seats use the saved average strategy.
- `nash_gap_upper_bound`: full-information best-response diagnostic proxy; not exact exploitability.
- `avg_utility`: mean chip utility over simulated head-to-head hands.
- `win_rate`: fraction of simulated hands with positive utility.
- `confidence interval`: multi-seed 95% interval for matchup statistic; overlapping intervals weaken improvement claims.
- `KL divergence`: neural imitation divergence from CFR action distribution.
- `cross entropy`: supervised action-distribution loss against CFR targets.
- `traversals/sec`: CFR root traversals per second.
- `hands/sec`: simulated random hands per second in benchmark/evaluation path.

## Validation Commands

### Python tests

```bash
.venv/bin/python -m pytest
```

### Rust tests

```bash
cd engine && cargo test
```

### Train CFR

```bash
.venv/bin/python scripts/train_cfr.py
.venv/bin/python scripts/train_cfr.py --engine rust --selection best_gap
.venv/bin/python scripts/train_cfr.py --engine python
```

### Train neural

```bash
.venv/bin/python scripts/train_policy.py
```

### Evaluate

```bash
.venv/bin/python scripts/evaluate.py --engine auto
.venv/bin/python scripts/evaluate.py --engine python
.venv/bin/python scripts/evaluate.py --engine rust
```

### Rust benchmark

```bash
cd engine && cargo run --release --bin bench
```

### Rust CFR

```bash
cd engine && cargo run --release --bin train_cfr -- --iterations 1000 --seed 0 --out ../data/cfr_strategy_rust.json
```

### Frontend

```bash
npm run build --prefix frontend
npm run dev --prefix frontend
```

### Backend

```bash
uvicorn backend.main:app --reload
```

## What To Run After Changes

- Game rule change: `pytest`, `cargo test`, train/evaluate if Leduc behavior changed.
- CFR change: `pytest`, `scripts/train_cfr.py`, `scripts/evaluate.py`, compare metrics.
- Rust change: `cargo test`, Rust benchmark, Rust CFR train, evaluate.
- Neural change: `pytest`, `scripts/train_policy.py`, evaluate.
- Backend/frontend change: `pytest`, `npm run build --prefix frontend`, manual Play vs Bot smoke test.

## Reporting Template

```text
Changed files:
Commands run:
Tests:
Metrics:
Regressions/anomalies:
Should default behavior change? yes/no
```

## Rules

- Never fabricate results.
- If a metric worsens, report it directly.
- If confidence intervals overlap, do not claim a real improvement.
- Keep raw files in `data/` as metric source of truth.
- Do not treat the proxy gap as exact exploitability.
