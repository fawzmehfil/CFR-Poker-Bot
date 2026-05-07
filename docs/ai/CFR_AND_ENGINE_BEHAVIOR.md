# CFR And Engine Behavior

## Leduc Poker In This Repo

- Two-player Leduc with one private card per player.
- Public card appears after the first betting round.
- Betting rounds support checks, bets, calls, raises, and folds.
- Terminal states are fold or showdown.
- Utility is chip utility relative to each player's contribution.
- Infosets hide the opponent private card.

## CFR Behavior

- Traverses the full Leduc game tree over all card deals.
- Uses regret matching: positive cumulative regrets become the current mixed strategy; if no positive regrets exist, strategy is uniform over legal actions.
- Accumulates average strategy using player reach probability.
- Uses reach probabilities for both players and counterfactual regret weighting.
- Terminal utility orientation is from player 0 in traversal; regret signs are flipped for player 1 updates.
- CFR+ mode clips cumulative regrets at zero.
- Average strategies are exported in JSON schema:

```json
{
  "strategies": {
    "infoset-key": { "k": 0.5, "b": 0.5 }
  }
}
```

## Infoset Key Behavior

Includes:

- acting player id
- acting player's private rank
- public rank or hidden marker
- betting round
- public action history by round

Must not include:

- opponent private card
- full hidden deal identity
- future public card before it is revealed

Opponent-card leakage invalidates imperfect-information training.

## Checkpoint Selection

- `best_gap`: chooses lowest diagnostic nash-gap proxy. Best for equilibrium-style reporting.
- `best_heuristic`: chooses highest CFR-vs-heuristic average utility. More exploitative.
- `balanced`: weighted tradeoff over low gap, high random utility, and high heuristic utility.

Important tradeoff: lower proxy gap can reduce exploitative utility against a specific heuristic. Do not present one mode as universally superior.

## Rust Behavior

- Rust simulator is very fast for batched work.
- Rust evaluation acceleration works and validates deterministic traces against Python.
- Per-action Python/Rust FFI calls were slower due to binding overhead.
- Full Rust CFR traversal is faster and matches Python best-gap strategy quality.
- Current default: Rust CFR for best-gap training via `--engine auto`.
- Python CFR fallback remains available via `--engine python`.
- Do not make Rust mandatory for all workflows.

## Neural Behavior

- Supervised imitation from the CFR average strategy.
- Features encode private/public card, acting player, round/street, pot, to-call amount, raise count, and compressed action history.
- Model outputs an action distribution over legal actions.
- It should be described as policy compression/imitation, not independent RL or a solver.

## UI/Game Behavior

- Leduc bot card is hidden during an active hand.
- Leduc bot card is revealed only at terminal/showdown.
- Hold'em bot hole cards are hidden during an active hand and revealed only at terminal.
- Backend returns only legal actions for the human turn.
- Existing Leduc endpoints must continue to work.

## Common Mistakes To Avoid

- Including opponent private card in an infoset.
- Changing terminal utility sign without tests.
- Breaking strategy JSON schema.
- Silently changing metric definitions.
- Replacing Leduc with Hold'em.
- Making Rust mandatory without fallback.
- Claiming exact exploitability when metric is a proxy.
- Claiming Hold'em is solved by CFR.
- Claiming neural beats CFR without evaluation.
