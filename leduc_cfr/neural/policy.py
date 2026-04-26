from __future__ import annotations

import itertools
from pathlib import Path
import random

import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from leduc_cfr.cfr.trainer import StrategyProfile
from leduc_cfr.poker.leduc import Action, CARDS, LeducState, RANKS, rank

ACTION_ORDER = ("k", "b", "c", "r", "f")
RANK_ORDER = ("J", "Q", "K", "-")
INPUT_DIM = 22


def encode_infoset(key: str) -> list[float]:
    player_s, private, public, round_s, history = key.split("|")
    vec: list[float] = []
    vec.extend([1.0 if player_s == f"p{i}" else 0.0 for i in range(2)])
    vec.extend([1.0 if private == r else 0.0 for r in RANK_ORDER[:3]])
    vec.extend([1.0 if public == r else 0.0 for r in RANK_ORDER])
    vec.append(float(round_s[-1]))
    vec.extend([0.0, 0.0, 0.0])
    for token in ACTION_ORDER:
        vec.append(history.count(token) / 4.0)
    vec.extend([0.0] * (INPUT_DIM - len(vec)))
    return vec


def encode_state(state: LeducState, player: int) -> list[float]:
    private = rank(state.private_cards[player])
    public = rank(state.public_card) if state.round_index == 1 else "-"
    history_text = "".join(state.history[0]) + "/" + "".join(state.history[1])
    vec: list[float] = []
    vec.extend([1.0 if player == i else 0.0 for i in range(2)])
    vec.extend([1.0 if private == card_rank else 0.0 for card_rank in RANKS])
    vec.extend([1.0 if public == card_rank else 0.0 for card_rank in RANK_ORDER])
    vec.extend([1.0 if state.round_index == street else 0.0 for street in (0, 1)])
    vec.append(state.pot / 20.0)
    vec.append(state.to_call(player) / 8.0)
    vec.append(state.raises_this_round / 2.0)
    for action in ACTION_ORDER:
        vec.append(history_text.count(action) / 4.0)
    vec.extend([len(state.history[0]) / 4.0, len(state.history[1]) / 4.0, 1.0])
    if len(vec) != INPUT_DIM:
        raise ValueError(f"Expected {INPUT_DIM} features, got {len(vec)}")
    return vec


def build_policy_dataset(profile: StrategyProfile) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    examples: dict[str, tuple[list[float], list[float], list[float]]] = {}

    def visit(state: LeducState) -> None:
        if state.terminal:
            return
        player = state.current_player
        key = state.info_set_key(player)
        probs = profile.strategies.get(key)
        if probs is not None and key not in examples:
            examples[key] = (
                encode_state(state, player),
                [float(probs.get(action, 0.0)) for action in ACTION_ORDER],
                [1.0 if action in probs else 0.0 for action in ACTION_ORDER],
            )
        for action in state.legal_actions():
            visit(state.apply(action))

    for deal in itertools.permutations(CARDS, 3):
        visit(LeducState(deal=deal))

    xs, ys, masks = zip(*examples.values())
    return (
        torch.tensor(xs, dtype=torch.float32),
        torch.tensor(ys, dtype=torch.float32),
        torch.tensor(masks, dtype=torch.float32),
    )


class PolicyNet(nn.Module):
    def __init__(self, input_dim: int = INPUT_DIM, hidden_dim: int = 96) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, len(ACTION_ORDER)),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class NeuralPolicy:
    def __init__(self, model: PolicyNet) -> None:
        self.model = model
        self.model.eval()

    @classmethod
    def load(cls, path: str | Path) -> "NeuralPolicy":
        data = torch.load(path, map_location="cpu", weights_only=False)
        model = PolicyNet(input_dim=int(data["input_dim"]))
        model.load_state_dict(data["model_state"])
        return cls(model)

    def action_probs(self, state: LeducState, player: int) -> dict[Action, float]:
        legal = state.legal_actions()
        mask = torch.tensor([[1.0 if action in legal else 0.0 for action in ACTION_ORDER]], dtype=torch.float32)
        x = torch.tensor([encode_state(state, player)], dtype=torch.float32)
        with torch.no_grad():
            logits = self.model(x).masked_fill(mask == 0, -1e9)
            probs = torch.softmax(logits, dim=-1)[0].tolist()
        return {action: float(probs[index]) for index, action in enumerate(ACTION_ORDER) if action in legal}

    def sample_action(self, state: LeducState, player: int, rng: random.Random) -> Action:
        probs = self.action_probs(state, player)
        roll = rng.random()
        acc = 0.0
        last = next(iter(probs))
        for action, prob in probs.items():
            acc += prob
            if roll <= acc:
                return action
            last = action
        return last


def train_policy_from_strategy(
    profile: StrategyProfile,
    epochs: int = 50,
    batch_size: int = 64,
    learning_rate: float = 1e-3,
    out_path: str | Path | None = None,
) -> dict[str, float | list[dict[str, float]]]:
    x, y, mask = build_policy_dataset(profile)
    dataset = TensorDataset(x, y, mask)
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    model = PolicyNet(input_dim=x.shape[1])
    opt = torch.optim.AdamW(model.parameters(), lr=learning_rate)
    loss_fn = nn.KLDivLoss(reduction="batchmean")
    last_loss = 0.0
    history: list[dict[str, float]] = []

    for epoch in range(1, epochs + 1):
        epoch_losses = []
        for xb, yb, mb in loader:
            logits = model(xb).masked_fill(mb == 0, -1e9)
            log_probs = torch.log_softmax(logits, dim=-1)
            loss = loss_fn(log_probs, yb)
            opt.zero_grad()
            loss.backward()
            opt.step()
            last_loss = float(loss.detach())
            epoch_losses.append(last_loss)
        history.append({"epoch": float(epoch), "kl_divergence": sum(epoch_losses) / len(epoch_losses)})

    with torch.no_grad():
        logits = model(x).masked_fill(mask == 0, -1e9)
        log_probs = torch.log_softmax(logits, dim=-1)
        final_kl = float(loss_fn(log_probs, y).detach())
        cross_entropy = float((-(y * log_probs).sum(dim=1)).mean().detach())

    if out_path:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "model_state": model.state_dict(),
                "input_dim": x.shape[1],
                "actions": ACTION_ORDER,
                "kl_divergence": final_kl,
                "cross_entropy": cross_entropy,
            },
            out_path,
        )
    return {
        "loss": final_kl,
        "kl_divergence": final_kl,
        "cross_entropy": cross_entropy,
        "examples": float(x.shape[0]),
        "epochs": float(epochs),
        "history": history,
    }
