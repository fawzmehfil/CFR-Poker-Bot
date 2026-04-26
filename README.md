# CFR Poker Bot

Minimal serious Leduc Poker CFR project:

- Tabular CFR and CFR+ trainer
- PyTorch policy approximation from CFR average strategy
- FastAPI backend
- React Play vs Bot UI
- Evaluation and plotting scripts

This repo intentionally implements Leduc Poker only. It does not attempt Texas Hold'em.

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm install --prefix frontend

python -m pytest
python scripts/train_cfr.py --iterations 1000 --cfr-plus --out data/cfr_strategy.json
python scripts/train_policy.py --strategy data/cfr_strategy.json --epochs 25 --out data/policy.pt
python scripts/evaluate.py --strategy data/cfr_strategy.json --plot data/eval.png
uvicorn backend.main:app --reload
```

In another terminal:

```bash
npm run dev --prefix frontend
```

Open the frontend URL printed by Vite, usually `http://localhost:5173`.

## Project Layout

```text
leduc_cfr/
  poker/       Leduc rules and state transitions
  cfr/         Tabular CFR/CFR+ trainer and strategy I/O
  neural/      PyTorch policy approximation
  eval/        Best-response/exploitability-style evaluation
backend/       FastAPI API and game session manager
frontend/      React Play vs Bot UI
scripts/       CLI entrypoints for training/eval
tests/         Smoke and correctness tests
```

## Useful Commands

```bash
python scripts/train_cfr.py --iterations 5000 --cfr-plus --out data/cfr_strategy.json
python scripts/evaluate.py --strategy data/cfr_strategy.json
uvicorn backend.main:app --reload
npm run dev --prefix frontend
```

