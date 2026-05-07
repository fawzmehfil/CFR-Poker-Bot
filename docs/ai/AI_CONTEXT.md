# AI Continuation Context: CFR-Poker-Bot

## One-Line Definition

CFR-Poker-Bot is a high-performance imperfect-information poker AI system using tabular CFR/CFR+, neural policy imitation, Rust-accelerated traversal/simulation, FastAPI, and React.

## Positioning

- **Leduc Poker is the research/game-theory core.** CFR, metrics, neural imitation, and Rust traversal are centered on Leduc.
- **Texas Hold'em is a separate playable demo mode.** It is heuristic/abstraction-based and must not be described as CFR-solved.
- Core thesis: poker bots need both strategy quality and systems throughput. CFR provides game-theoretic learning, neural imitation compresses learned policies, and Rust accelerates simulation/traversal.
- Target readers: AI/ML systems engineers, game AI researchers, startup engineers, and portfolio reviewers.

## Current Capabilities

- Python Leduc engine.
- Rust Leduc engine.
- Full Rust CFR traversal binary.
- Python CFR fallback.
- CFR/CFR+ training.
- Checkpoint selection modes: `best_gap`, `best_heuristic`, `balanced`.
- PyTorch neural policy imitation from CFR average strategies.
- Evaluation with EV, matchup metrics, confidence intervals, and diagnostic nash-gap proxy.
- Rust-accelerated evaluation/simulation benchmark path.
- FastAPI backend.
- React Play vs Bot UI.
- Leduc bot modes: `random`, `heuristic`, `cfr`, `neural`.
- Current branch also includes a separate heads-up Texas Hold'em playable demo with heuristic bot.

## Latest Verified Metrics

Source of truth: `data/eval.json`, `data/cfr_metrics.json`, `data/cfr_metrics_engine_compare.json`, `data/policy_metrics.json`, latest test/build runs.

| Metric | Value |
|---|---:|
| Current Python tests | 33 passed |
| Prior Leduc/Rust baseline tests | 27 passed |
| Leduc infosets | 288 |
| Expected game value P0 | ~-0.0856 |
| Best-gap nash-gap proxy | ~1.9819 |
| CFR vs random avg utility | ~0.7994 |
| CFR vs heuristic avg utility | ~0.0578 |
| Rust CFR traversals/sec | ~31K |
| Python CFR traversals/sec | ~8.3K |
| Rust CFR speedup | ~3.8x |
| Neural KL divergence to CFR | ~0.1129 |
| Neural cross-entropy | ~0.3724 |
| Rust random hands/sec | ~15M-23M depending benchmark path |
| Rust state transitions/sec | ~145M |
| Rust simulation speedup | ~265x-370x |

## Important Interpretations

- `nash_gap_upper_bound` is a diagnostic proxy based on full-information best response; it is **not exact exploitability**.
- The neural model imitates CFR. It is not an independent RL solver.
- Rust per-step Python/Rust FFI hot-path calls were slower due to call overhead.
- Full Rust CFR traversal is the correct fast training path.
- Python fallback must remain available.
- Hold'em is playable, but not solved. Do not attach CFR claims to it.

## Hard Rules For Future AI Sessions

- Do not rebuild the repo from scratch.
- Do not remove or replace Leduc CFR.
- Do not remove Python fallback.
- Do not fabricate metrics.
- Do not claim Hold'em is solved by CFR.
- Do not claim neural beats CFR unless evaluation proves it.
- Always run tests after meaningful changes.
- Prefer one phase per prompt.
- Keep changes minimal and verifiable.
- Preserve existing API behavior unless explicitly changing it with tests.
