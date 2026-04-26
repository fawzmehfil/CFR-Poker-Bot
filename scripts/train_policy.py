from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
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
    parser.add_argument("--metrics", default="data/policy_metrics.json")
    args = parser.parse_args()

    profile = StrategyProfile.load(args.strategy)
    metrics = train_policy_from_strategy(profile, epochs=args.epochs, out_path=args.out)
    payload = {
        "timestamp": datetime.now(UTC).isoformat(),
        "strategy": args.strategy,
        "policy_path": args.out,
        **metrics,
    }
    Path(args.metrics).parent.mkdir(parents=True, exist_ok=True)
    Path(args.metrics).write_text(json.dumps(payload, indent=2))
    print(
        "saved neural policy to "
        f"{args.out}; kl={metrics['kl_divergence']:.6f}; "
        f"cross_entropy={metrics['cross_entropy']:.6f}; examples={int(metrics['examples'])}"
    )


if __name__ == "__main__":
    main()
