from __future__ import annotations

from dataclasses import dataclass, field
import itertools
import random
from collections import Counter
from typing import Literal

Action = Literal["fold", "check", "call", "bet", "raise"]
Street = Literal["preflop", "flop", "turn", "river", "showdown"]

RANKS = "23456789TJQKA"
SUITS = "cdhs"
RANK_VALUE = {rank: index + 2 for index, rank in enumerate(RANKS)}
STARTING_STACK = 100
SMALL_BLIND = 1
BIG_BLIND = 2
MAX_RAISES_PER_STREET = 1


@dataclass(frozen=True, order=True)
class Card:
    rank: str
    suit: str

    def __str__(self) -> str:
        return f"{self.rank}{self.suit}"

    @classmethod
    def parse(cls, value: str) -> "Card":
        if len(value) != 2 or value[0] not in RANKS or value[1] not in SUITS:
            raise ValueError(f"Invalid card: {value}")
        return cls(value[0], value[1])


def deck() -> list[Card]:
    return [Card(rank, suit) for rank in RANKS for suit in SUITS]


def _straight_high(values: set[int]) -> int | None:
    wheel_values = set(values)
    if 14 in wheel_values:
        wheel_values.add(1)
    for high in range(14, 4, -1):
        if all(value in wheel_values for value in range(high - 4, high + 1)):
            return high
    return None


def evaluate_hand(cards: list[Card] | tuple[Card, ...]) -> tuple[int, tuple[int, ...]]:
    if len(cards) < 5:
        raise ValueError("Hold'em hand evaluation requires at least five cards")

    best: tuple[int, tuple[int, ...]] | None = None
    for combo in itertools.combinations(cards, 5):
        ranks = sorted((RANK_VALUE[card.rank] for card in combo), reverse=True)
        counts = Counter(ranks)
        groups = sorted(((count, rank) for rank, count in counts.items()), reverse=True)
        flush = len({card.suit for card in combo}) == 1
        straight = _straight_high(set(ranks))

        if flush and straight:
            score = (8, (straight,))
        elif groups[0][0] == 4:
            quad = groups[0][1]
            kicker = max(rank for rank in ranks if rank != quad)
            score = (7, (quad, kicker))
        elif groups[0][0] == 3 and groups[1][0] == 2:
            score = (6, (groups[0][1], groups[1][1]))
        elif flush:
            score = (5, tuple(ranks))
        elif straight:
            score = (4, (straight,))
        elif groups[0][0] == 3:
            trip = groups[0][1]
            kickers = tuple(rank for rank in ranks if rank != trip)
            score = (3, (trip, *kickers))
        elif groups[0][0] == 2 and groups[1][0] == 2:
            pairs = sorted((rank for count, rank in groups if count == 2), reverse=True)
            kicker = max(rank for rank in ranks if rank not in pairs)
            score = (2, (pairs[0], pairs[1], kicker))
        elif groups[0][0] == 2:
            pair = groups[0][1]
            kickers = tuple(rank for rank in ranks if rank != pair)
            score = (1, (pair, *kickers))
        else:
            score = (0, tuple(ranks))

        if best is None or score > best:
            best = score
    return best or (0, ())


@dataclass(frozen=True)
class HoldemState:
    deck_cards: tuple[Card, ...]
    hole_cards: tuple[tuple[Card, Card], tuple[Card, Card]]
    board: tuple[Card, ...] = ()
    street: Street = "preflop"
    current_player: int = 0
    stacks: tuple[int, int] = (STARTING_STACK - SMALL_BLIND, STARTING_STACK - BIG_BLIND)
    contributions: tuple[int, int] = (SMALL_BLIND, BIG_BLIND)
    street_bets: tuple[int, int] = (SMALL_BLIND, BIG_BLIND)
    acted: tuple[bool, bool] = (False, False)
    raises_this_street: int = 0
    terminal: bool = False
    folded_player: int | None = None
    history: tuple[str, ...] = field(default_factory=tuple)

    @property
    def pot(self) -> int:
        return sum(self.contributions)

    def to_call(self, player: int | None = None) -> int:
        player = self.current_player if player is None else player
        return max(self.street_bets) - self.street_bets[player]

    def legal_actions(self) -> tuple[Action, ...]:
        if self.terminal:
            return ()
        if self.to_call() > 0:
            actions: list[Action] = ["fold", "call"]
            if self.raises_this_street < MAX_RAISES_PER_STREET and self.stacks[self.current_player] > self.to_call():
                actions.append("raise")
            return tuple(actions)
        actions = ["check"]
        if self.raises_this_street < MAX_RAISES_PER_STREET and self.stacks[self.current_player] > 0:
            actions.append("bet")
        return tuple(actions)

    def apply(self, action: Action) -> "HoldemState":
        if action not in self.legal_actions():
            raise ValueError(f"Illegal action {action}; legal={self.legal_actions()}")
        if action == "fold":
            return self._replace(
                terminal=True,
                folded_player=self.current_player,
                history=self.history + (self._history_token(action),),
            )

        next_state = self
        if action in ("call", "bet", "raise"):
            amount = self.to_call(self.current_player)
            if action in ("bet", "raise"):
                amount += self.bet_size()
            next_state = self._commit(amount, action)
        elif action == "check":
            next_state = self._mark_acted(action)

        if next_state._street_closed():
            return next_state._advance_street()
        return next_state._replace(current_player=1 - self.current_player)

    def bet_size(self) -> int:
        return 2 if self.street in ("preflop", "flop") else 4

    def showdown_winner(self) -> int | None:
        score0 = evaluate_hand(list(self.hole_cards[0] + self.board))
        score1 = evaluate_hand(list(self.hole_cards[1] + self.board))
        if score0 == score1:
            return None
        return 0 if score0 > score1 else 1

    def utility(self, player: int) -> int:
        if not self.terminal:
            raise ValueError("Utility is only defined for terminal states")
        if self.folded_player is not None:
            winner = 1 - self.folded_player
        else:
            winner = self.showdown_winner()
        if winner is None:
            return self.pot // 2 - self.contributions[player]
        if winner == player:
            return self.pot - self.contributions[player]
        return -self.contributions[player]

    def public_view(self, human_player: int = 0) -> dict:
        terminal = self.terminal
        bot_cards = [str(card) for card in self.hole_cards[1]] if terminal else ["?", "?"]
        result = None
        if terminal:
            utility = self.utility(human_player)
            if utility > 0:
                result = f"You win {utility} chips"
            elif utility < 0:
                result = f"Bot wins {abs(utility)} chips"
            else:
                result = "Hand ends in a draw"
        return {
            "hero_cards": [str(card) for card in self.hole_cards[human_player]],
            "bot_cards": bot_cards,
            "board": [str(card) for card in self.board],
            "pot": self.pot,
            "stacks": list(self.stacks),
            "street": self.street,
            "current_player": self.current_player,
            "legal_actions": list(self.legal_actions()) if self.current_player == human_player else [],
            "to_call": self.to_call(human_player) if not terminal else 0,
            "terminal": terminal,
            "result": result,
            "utility": self.utility(human_player) if terminal else 0,
            "history": list(self.history),
        }

    def _commit(self, amount: int, action: Action) -> "HoldemState":
        player = self.current_player
        amount = min(amount, self.stacks[player])
        stacks = list(self.stacks)
        contributions = list(self.contributions)
        street_bets = list(self.street_bets)
        acted = [False, False] if action in ("bet", "raise") else list(self.acted)
        stacks[player] -= amount
        contributions[player] += amount
        street_bets[player] += amount
        acted[player] = True
        raises = self.raises_this_street + (1 if action in ("bet", "raise") else 0)
        return self._replace(
            stacks=tuple(stacks),
            contributions=tuple(contributions),
            street_bets=tuple(street_bets),
            acted=tuple(acted),
            raises_this_street=raises,
            history=self.history + (self._history_token(action),),
        )

    def _mark_acted(self, action: Action) -> "HoldemState":
        acted = list(self.acted)
        acted[self.current_player] = True
        return self._replace(acted=tuple(acted), history=self.history + (self._history_token(action),))

    def _street_closed(self) -> bool:
        return self.street_bets[0] == self.street_bets[1] and all(self.acted)

    def _advance_street(self) -> "HoldemState":
        if self.street == "river":
            return self._replace(terminal=True, street="showdown")
        if self.street == "preflop":
            board = self.deck_cards[:3]
            remaining = self.deck_cards[3:]
            street: Street = "flop"
        elif self.street == "flop":
            board = self.board + (self.deck_cards[0],)
            remaining = self.deck_cards[1:]
            street = "turn"
        else:
            board = self.board + (self.deck_cards[0],)
            remaining = self.deck_cards[1:]
            street = "river"
        return self._replace(
            deck_cards=remaining,
            board=board,
            street=street,
            current_player=0,
            street_bets=(0, 0),
            acted=(False, False),
            raises_this_street=0,
        )

    def _history_token(self, action: Action) -> str:
        return f"{self.street}:{self.current_player}:{action}"

    def _replace(self, **kwargs) -> "HoldemState":
        values = self.__dict__.copy()
        values.update(kwargs)
        return HoldemState(**values)


def fresh_holdem_state(rng: random.Random | None = None) -> HoldemState:
    rng = rng or random.Random()
    cards = deck()
    rng.shuffle(cards)
    hole_cards = ((cards[0], cards[2]), (cards[1], cards[3]))
    return HoldemState(deck_cards=tuple(cards[4:]), hole_cards=hole_cards)


def heuristic_action(state: HoldemState, player: int, rng: random.Random) -> Action:
    legal = state.legal_actions()
    strength = estimate_strength(state, player)
    to_call = state.to_call(player)
    pot_odds = to_call / max(1, state.pot + to_call)
    aggression = 0.15 if state.street in ("turn", "river") else 0.08

    if to_call == 0:
        if "bet" in legal and strength + aggression > 0.62:
            return "bet"
        return "check"
    if "raise" in legal and strength > 0.82 and rng.random() < 0.45:
        return "raise"
    if "call" in legal and (strength >= pot_odds + 0.18 or strength > 0.55):
        return "call"
    return "fold" if "fold" in legal else legal[0]


def estimate_strength(state: HoldemState, player: int) -> float:
    cards = list(state.hole_cards[player] + state.board)
    if len(state.board) >= 3:
        category = evaluate_hand(cards)[0]
        return min(0.98, 0.18 + category * 0.1 + _draw_bonus(cards))
    ranks = [RANK_VALUE[card.rank] for card in state.hole_cards[player]]
    suited = state.hole_cards[player][0].suit == state.hole_cards[player][1].suit
    pair = ranks[0] == ranks[1]
    high = max(ranks)
    connected = abs(ranks[0] - ranks[1]) <= 1
    score = 0.25 + (0.32 if pair else 0.0) + (high - 2) / 40
    if suited:
        score += 0.08
    if connected:
        score += 0.06
    return min(0.95, score)


def _draw_bonus(cards: list[Card]) -> float:
    suits = Counter(card.suit for card in cards)
    ranks = {RANK_VALUE[card.rank] for card in cards}
    if 14 in ranks:
        ranks.add(1)
    flush_draw = any(count >= 4 for count in suits.values())
    straight_draw = any(sum(1 for value in range(start, start + 5) if value in ranks) >= 4 for start in range(1, 11))
    return (0.08 if flush_draw else 0.0) + (0.06 if straight_draw else 0.0)
