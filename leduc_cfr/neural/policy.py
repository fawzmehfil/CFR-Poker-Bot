from __future__ import annotations

from pathlib import Path

import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from leduc_cfr.cfr.trainer import StrategyProfile

ACTION_ORDER = ("k", "b", "c", "r", "f")
RANK_ORDER = ("J", "Q", "K", "-")


def encode_infoset(key: str) -> list[float]:
    player_s, private, public, round_s, history = key.split("|")
    vec: list[float] = []
    vec.extend([1.0 if player_s == f"p{i}" else 0.0 for i in range(2)])
    vec.extend([1.0 if private == r else 0.0 for r in RANK_ORDER[:3]])
    vec.extend([1.0 if public == r else 0.0 for r in RANK_ORDER])
    vec.append(float(round_s[-1]))
    for token in ACTION_ORDER:
        vec.append(history.count(token) / 4.0)
    return vec


class PolicyNet(nn.Module):
    def __init__(self, input_dim: int = 15, hidden_dim: int = 64) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, len(ACTION_ORDER)),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


def train_policy_from_strategy(
    profile: StrategyProfile,
    epochs: int = 50,
    batch_size: int = 64,
    learning_rate: float = 1e-3,
    out_path: str | Path | None = None,
) -> dict[str, float]:
    xs = []
    ys = []
    masks = []
    for key, probs in profile.strategies.items():
        xs.append(encode_infoset(key))
        ys.append([float(probs.get(action, 0.0)) for action in ACTION_ORDER])
        masks.append([1.0 if action in probs else 0.0 for action in ACTION_ORDER])

    x = torch.tensor(xs, dtype=torch.float32)
    y = torch.tensor(ys, dtype=torch.float32)
    mask = torch.tensor(masks, dtype=torch.float32)
    dataset = TensorDataset(x, y, mask)
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    model = PolicyNet(input_dim=x.shape[1])
    opt = torch.optim.AdamW(model.parameters(), lr=learning_rate)
    loss_fn = nn.KLDivLoss(reduction="batchmean")
    last_loss = 0.0

    for _ in range(epochs):
        for xb, yb, mb in loader:
            logits = model(xb).masked_fill(mb == 0, -1e9)
            log_probs = torch.log_softmax(logits, dim=-1)
            loss = loss_fn(log_probs, yb)
            opt.zero_grad()
            loss.backward()
            opt.step()
            last_loss = float(loss.detach())

    if out_path:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "model_state": model.state_dict(),
                "input_dim": x.shape[1],
                "actions": ACTION_ORDER,
                "loss": last_loss,
            },
            out_path,
        )
    return {"loss": last_loss, "examples": float(len(xs))}

