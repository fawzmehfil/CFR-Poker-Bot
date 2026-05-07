# Roadmap And Prompting Guide

## Completed Phases

1. Runnable Leduc CFR baseline.
2. Game/UI correctness fixes.
3. Stronger Leduc engine tests.
4. Evaluation metrics and confidence intervals.
5. Neural policy imitation.
6. Standalone Rust engine.
7. Rust evaluation acceleration.
8. Rust hot-path FFI experiment; slower due to per-call overhead.
9. Full Rust CFR traversal.
10. Rust CFR default for best-gap training with Python fallback.
11. Separate heads-up Texas Hold'em playable demo with heuristic bot.

## Current Product Direction

- High-performance imperfect-information game AI system.
- Leduc = rigorous CFR research core.
- Hold'em = playable demo, separate from the CFR claims.

## Next Recommended Phase

Dashboard and polish phase:

- show training/evaluation metrics in UI
- expose strategy explorer for Leduc infosets
- show run comparison and Rust/Python benchmark summaries
- keep all displayed metrics sourced from `data/`

## Hold'em Phase Status

Current branch has a first playable mode:

- `leduc_cfr/holdem/`
- fixed-limit 2-player engine
- hand evaluator
- heuristic bot
- backend routes
- React mode toggle
- tests in `tests/test_holdem.py`

Non-goals remain:

- do not solve Hold'em with CFR
- do not replace Leduc
- do not remove Rust/Python CFR paths

Future Hold'em improvements:

- stronger heuristic/abstraction policy
- clearer showdown explanations
- better betting UX
- manual browser smoke tests

## Future Phases

- Dashboard polish.
- Strategy explorer.
- Stronger exact exploitability or imperfect-information best response.
- Richer neural model and validation split.
- More Rust CFR selection/reporting metadata.
- Hold'em heuristic improvements.
- In-process Rust bindings for traversal once correctness and performance justify it.

## Prompt-Writing Rules

- One phase per prompt.
- Always include current defaults and relevant metrics.
- Always define non-goals.
- Always require tests.
- Require exact changed files and metrics.
- Never ask to rebuild from scratch.
- Separate research core from playable demo.

## Reusable Prompt Preamble

```text
You are continuing CFR-Poker-Bot. Do not rebuild. Use docs/ai/* as source of truth.
Preserve Leduc CFR, Rust/Python fallbacks, and existing tests. Do not fabricate metrics.
Report changed files, commands, tests, and metrics after each phase.
```

## Good Next Prompt

```text
Proceed to dashboard polish only.
Use existing data artifacts; do not fake metrics.
Add a metrics dashboard, strategy explorer, and Rust/Python benchmark summary.
Do not change Leduc rules, CFR logic, or Hold'em rules.
Run .venv/bin/python -m pytest and npm run build --prefix frontend.
Report changed files, commands, tests, and any metric files read.
```
