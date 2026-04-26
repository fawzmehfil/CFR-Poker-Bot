from __future__ import annotations

from dataclasses import dataclass, field
import random
from typing import Literal

Action = Literal["k", "b", "c", "r", "f"]

RANKS = ("J", "Q", "K")
CARDS = ("J1", "J2", "Q1", "Q2", "K1", "K2")
ANTE = 1
BET_SIZES = (2, 4)
MAX_RAISES = 2


def rank(card: str) -> str:
    return card[0]


def random_deal(rng: random.Random | None = None) -> tuple[str, str, str]:
    rng = rng or random
    cards = list(CARDS)
    rng.shuffle(cards)
    return cards[0], cards[1], cards[2]


def fresh_state(deal: tuple[str, str, str] | None = None) -> "LeducState":
    return LeducState(deal=deal or random_deal())


@dataclass(frozen=True)
class LeducState:
    deal: tuple[str, str, str]
    round_index: int = 0
    current_player: int = 0
    contributions: tuple[int, int] = (ANTE, ANTE)
    round_bets: tuple[int, int] = (0, 0)
    raises_this_round: int = 0
    history: tuple[tuple[Action, ...], tuple[Action, ...]] = field(default_factory=lambda: ((), ()))
    terminal: bool = False
    folded_player: int | None = None

    def __post_init__(self) -> None:
        if len(self.deal) != 3 or len(set(self.deal)) != 3 or any(card not in CARDS for card in self.deal):
            raise ValueError(f"Deal must contain three unique Leduc cards from the deck: {self.deal}")
        if self.round_index not in (0, 1):
            raise ValueError(f"round_index must be 0 or 1: {self.round_index}")
        if self.current_player not in (0, 1):
            raise ValueError(f"current_player must be 0 or 1: {self.current_player}")
        if len(self.contributions) != 2 or len(self.round_bets) != 2:
            raise ValueError("contributions and round_bets must have one entry per player")
        if any(value < 0 for value in (*self.contributions, *self.round_bets)):
            raise ValueError("contributions and round_bets cannot be negative")
        if self.raises_this_round < 0 or self.raises_this_round > MAX_RAISES:
            raise ValueError(f"raises_this_round must be between 0 and {MAX_RAISES}")
        if len(self.history) != 2:
            raise ValueError("history must have one action tuple per betting round")
        if self.folded_player is not None and self.folded_player not in (0, 1):
            raise ValueError(f"folded_player must be 0, 1, or None: {self.folded_player}")
        if self.folded_player is not None and not self.terminal:
            raise ValueError("A folded hand must be terminal")

    @property
    def private_cards(self) -> tuple[str, str]:
        return self.deal[0], self.deal[1]

    @property
    def public_card(self) -> str:
        return self.deal[2]

    @property
    def pot(self) -> int:
        return self.contributions[0] + self.contributions[1]

    def visible_public(self) -> str | None:
        return self.public_card if self.round_index == 1 or self.terminal else None

    def to_call(self, player: int | None = None) -> int:
        player = self.current_player if player is None else player
        return max(self.round_bets) - self.round_bets[player]

    def legal_actions(self) -> tuple[Action, ...]:
        if self.terminal:
            return ()
        if self.to_call() > 0:
            actions: list[Action] = ["f", "c"]
            if self.raises_this_round < MAX_RAISES:
                actions.append("r")
            return tuple(actions)
        actions = ["k"]
        if self.raises_this_round < MAX_RAISES:
            actions.append("b")
        return tuple(actions)

    def apply(self, action: Action) -> "LeducState":
        if action not in self.legal_actions():
            raise ValueError(f"Illegal action {action}; legal={self.legal_actions()}")

        hist = [list(self.history[0]), list(self.history[1])]
        hist[self.round_index].append(action)
        history = (tuple(hist[0]), tuple(hist[1]))

        if action == "f":
            return self._replace(history=history, terminal=True, folded_player=self.current_player)

        contributions = list(self.contributions)
        round_bets = list(self.round_bets)
        raises = self.raises_this_round

        if action == "c":
            call = self.to_call()
            contributions[self.current_player] += call
            round_bets[self.current_player] += call
            return self._after_closed_betting(tuple(contributions), history)

        if action in ("b", "r"):
            amount = self.to_call() + BET_SIZES[self.round_index]
            contributions[self.current_player] += amount
            round_bets[self.current_player] += amount
            raises += 1
            return self._replace(
                contributions=tuple(contributions),
                round_bets=tuple(round_bets),
                raises_this_round=raises,
                current_player=1 - self.current_player,
                history=history,
            )

        if action == "k":
            if len(history[self.round_index]) >= 2 and history[self.round_index][-2:] == ("k", "k"):
                return self._after_closed_betting(self.contributions, history)
            return self._replace(current_player=1 - self.current_player, history=history)

        raise AssertionError(action)

    def _after_closed_betting(
        self, contributions: tuple[int, int], history: tuple[tuple[Action, ...], tuple[Action, ...]]
    ) -> "LeducState":
        if self.round_index == 0:
            return self._replace(
                round_index=1,
                current_player=0,
                contributions=contributions,
                round_bets=(0, 0),
                raises_this_round=0,
                history=history,
            )
        return self._replace(contributions=contributions, history=history, terminal=True)

    def utility(self, player: int) -> float:
        if not self.terminal:
            raise ValueError("Utility is only defined for terminal states")
        if self.folded_player is not None:
            winner = 1 - self.folded_player
        else:
            winner = self.showdown_winner()
        if winner is None:
            return self.pot / 2 - self.contributions[player]
        if winner == player:
            return self.pot - self.contributions[player]
        return -float(self.contributions[player])

    def showdown_winner(self) -> int | None:
        p0, p1 = self.private_cards
        public = rank(self.public_card)
        pair0 = rank(p0) == public
        pair1 = rank(p1) == public
        if pair0 != pair1:
            return 0 if pair0 else 1
        if RANKS.index(rank(p0)) == RANKS.index(rank(p1)):
            return None
        return 0 if RANKS.index(rank(p0)) > RANKS.index(rank(p1)) else 1

    def info_set_key(self, player: int | None = None) -> str:
        player = self.current_player if player is None else player
        private = rank(self.private_cards[player])
        public = rank(self.public_card) if self.round_index == 1 else "-"
        h0 = "".join(self.history[0]) or "-"
        h1 = "".join(self.history[1]) or "-"
        return f"p{player}|{private}|{public}|r{self.round_index}|{h0}/{h1}"

    def public_view(self, human_player: int = 0) -> dict:
        opponent = 1 - human_player
        return {
            "round": self.round_index,
            "current_player": self.current_player,
            "pot": self.pot,
            "to_call": self.to_call() if not self.terminal else 0,
            "legal_actions": self.legal_actions(),
            "private_card": rank(self.private_cards[human_player]),
            "opponent_card": rank(self.private_cards[opponent]) if self.terminal else None,
            "public_card": rank(self.public_card) if self.round_index == 1 or self.terminal else None,
            "history": ["".join(self.history[0]), "".join(self.history[1])],
            "terminal": self.terminal,
            "winner": self.showdown_winner() if self.terminal and self.folded_player is None else (
                None if not self.terminal else 1 - self.folded_player
            ),
            "utility": self.utility(human_player) if self.terminal else None,
        }

    def _replace(self, **kwargs) -> "LeducState":
        data = {
            "deal": self.deal,
            "round_index": self.round_index,
            "current_player": self.current_player,
            "contributions": self.contributions,
            "round_bets": self.round_bets,
            "raises_this_round": self.raises_this_round,
            "history": self.history,
            "terminal": self.terminal,
            "folded_player": self.folded_player,
        }
        data.update(kwargs)
        return LeducState(**data)
