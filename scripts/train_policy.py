from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from leduc_cfr.cfr.trainer import StrategyProfile
from leduc_cfr.neural.policy import train_policy_from_strategy


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", default="data/cfr_strategy.json")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--out", default="data/policy.pt")
    args = parser.parse_args()

    profile = StrategyProfile.load(args.strategy)
    metrics = train_policy_from_strategy(profile, epochs=args.epochs, out_path=args.out)
    print(f"saved neural policy to {args.out}; loss={metrics['loss']:.6f}; examples={int(metrics['examples'])}")


if __name__ == "__main__":
    main()
