export const HOLDEM_LABELS = {
  fold: "Fold",
  check: "Check",
  call: "Call",
  bet: "Bet",
  raise: "Raise",
  "all-in": "All-in",
};

export const LEDUC_LABELS = { k: "Check", b: "Bet", c: "Call", r: "Raise", f: "Fold" };

export const STREET_LABELS = {
  preflop: "Preflop",
  flop: "Flop",
  turn: "Turn",
  river: "River",
  showdown: "Showdown",
};

const ACTION_VERBS = {
  fold: "folds",
  check: "checks",
  call: "calls",
  bet: "bets",
  raise: "raises to",
  "all-in": "moves all-in",
  f: "folds",
  k: "checks",
  c: "calls",
  b: "bets",
  r: "raises",
};

const YOU_ACTION_VERBS = {
  fold: "fold",
  check: "check",
  call: "call",
  bet: "bet",
  raise: "raise to",
  "all-in": "move all-in",
  f: "fold",
  k: "check",
  c: "call",
  b: "bet",
  r: "raise",
};

const BANNER_LABELS = {
  fold: "FOLD",
  check: "CHECK",
  call: "CALL",
  bet: "BET",
  raise: "RAISE",
  "all-in": "ALL-IN",
  f: "FOLD",
  k: "CHECK",
  c: "CALL",
  b: "BET",
  r: "RAISE",
};

const RANK_VALUES = {
  2: 2,
  3: 3,
  4: 4,
  5: 5,
  6: 6,
  7: 7,
  8: 8,
  9: 9,
  T: 10,
  J: 11,
  Q: 12,
  K: 13,
  A: 14,
};

const RANK_NAMES = {
  14: "Aces",
  13: "Kings",
  12: "Queens",
  11: "Jacks",
  10: "Tens",
  9: "Nines",
  8: "Eights",
  7: "Sevens",
  6: "Sixes",
  5: "Fives",
  4: "Fours",
  3: "Threes",
  2: "Twos",
};

const HAND_CATEGORIES = {
  8: "Straight Flush",
  7: "Four of a Kind",
  6: "Full House",
  5: "Flush",
  4: "Straight",
  3: "Three of a Kind",
  2: "Two Pair",
  1: "Pair",
  0: "High Card",
};

export function actionTone(action) {
  if (action === "f" || action === "fold") return "danger";
  if (action === "r" || action === "raise" || action === "bet" || action === "b") return "raise";
  if (action === "all-in") return "allIn";
  if (action === "check" || action === "k") return "check";
  return "call";
}

export function actionLabel(mode, action) {
  return mode === "holdem" ? HOLDEM_LABELS[action] || action : LEDUC_LABELS[action] || action;
}

export function buildActionTimeline(mode, history = []) {
  if (mode === "holdem") {
    return groupEvents(
      history
        .filter(Boolean)
        .map((token, index) => parseHoldemToken(token, index))
        .filter(Boolean),
    );
  }

  const events = history.flatMap((roundHistory, roundIndex) => {
    const actions = String(roundHistory || "").split("").filter(Boolean);
    return actions.map((action, actionIndex) => {
      const street = `Round ${roundIndex + 1}`;
      const actor = actionIndex % 2 === 0 ? "You" : "Bot";
      return {
        id: `${roundIndex}-${actionIndex}-${actor}-${action}`,
        actor,
        label: actionVerb(action, actor, mode),
        amount: null,
        tone: actionTone(action),
        street,
      };
    });
  });
  return groupEvents(events);
}

export function getLatestActionBanner(mode, previousGame, nextGame) {
  if (mode !== "holdem") {
    return getLatestLeducActionBanner(previousGame?.history || [], nextGame?.history || []);
  }

  const previousLength = previousGame?.history?.length || 0;
  const nextHistory = nextGame?.history || [];
  if (!nextHistory.length || nextHistory.length <= previousLength) return null;

  const timeline = buildActionTimeline(mode, nextHistory);
  const latest = timeline.flatMap((group) => group.events).at(-1);
  if (!latest) return null;

  const rawAction = mode === "holdem" ? String(nextHistory.at(-1)).split(":")[2] : String(nextHistory.at(-1)).at(-1);
  return {
    actor: latest.actor,
    text: BANNER_LABELS[rawAction] || latest.label.toUpperCase(),
    amount: latest.amount,
    tone: latest.tone,
  };
}

function getLatestLeducActionBanner(previousHistory, nextHistory) {
  for (let roundIndex = 0; roundIndex < nextHistory.length; roundIndex += 1) {
    const previousRound = String(previousHistory[roundIndex] || "");
    const nextRound = String(nextHistory[roundIndex] || "");
    if (nextRound.length <= previousRound.length) continue;

    const actionIndex = nextRound.length - 1;
    const action = nextRound.at(-1);
    const actor = actionIndex % 2 === 0 ? "You" : "Bot";
    return {
      actor,
      text: BANNER_LABELS[action] || actionLabel("leduc", action).toUpperCase(),
      amount: null,
      tone: actionTone(action),
    };
  }

  return null;
}

export function buildBoardRevealPlan(cards = []) {
  return Array.from({ length: 5 }, (_, index) => {
    const label = cards[index] || "";
    return {
      label,
      isVisible: Boolean(label),
      delayMs: index * 120,
    };
  });
}

export function describeShowdown(game) {
  if (!game?.terminal) return null;

  const utility = Number(game.utility || 0);
  const winnerName = utility > 0 ? "You" : utility < 0 ? "Bot" : "Split pot";
  const tone = utility > 0 ? "win" : utility < 0 ? "loss" : "draw";
  const winnerCards = utility >= 0 ? game.hero_cards : game.bot_cards;
  const winningHand = describeBestHand([...(winnerCards || []), ...(game.board || [])]);

  return {
    winnerName,
    winningHand,
    outcome: game.result || (tone === "draw" ? "Hand ends in a draw" : `${winnerName} wins`),
    tone,
  };
}

function parseHoldemToken(token, index) {
  const [streetKey, player, action, amountText] = String(token).split(":");
  if (!streetKey || !player || !action) return null;
  const amount = Number(amountText || 0);
  const street = STREET_LABELS[streetKey] || streetKey;
  const actor = player === "p0" ? "You" : "Bot";
  return {
    id: `${streetKey}-${index}-${player}-${action}-${amount}`,
    actor,
    label: actionVerb(action, actor, "holdem"),
    amount: amount > 0 ? amount : null,
    tone: actionTone(action),
    street,
  };
}

function actionVerb(action, actor, mode) {
  const verbs = actor === "You" ? YOU_ACTION_VERBS : ACTION_VERBS;
  return verbs[action] || actionLabel(mode, action).toLowerCase();
}

function groupEvents(events) {
  const groups = [];
  for (const event of events) {
    const lastGroup = groups.at(-1);
    if (lastGroup?.street === event.street) {
      lastGroup.events.push(event);
    } else {
      groups.push({ street: event.street, events: [event] });
    }
  }
  return groups;
}

function describeBestHand(cards) {
  const parsedCards = cards.map(parseCard).filter(Boolean);
  if (parsedCards.length < 5) return "Hand complete";

  const best = combinations(parsedCards, 5)
    .map(scoreFiveCards)
    .sort(compareScores)
    .at(-1);

  if (!best) return "Hand complete";
  if (best.category === 1) return `Pair of ${RANK_NAMES[best.primary]}`;
  if (best.category === 2) return `Two Pair, ${RANK_NAMES[best.primary]} and ${RANK_NAMES[best.secondary]}`;
  if (best.category === 3) return `Three of a Kind, ${RANK_NAMES[best.primary]}`;
  if (best.category === 7) return `Four of a Kind, ${RANK_NAMES[best.primary]}`;
  if (best.category === 0) return `${RANK_NAMES[best.primary].replace(/s$/, "")} High`;
  return HAND_CATEGORIES[best.category] || "Made Hand";
}

function parseCard(label) {
  if (!label || label === "?") return null;
  const rank = label.slice(0, -1);
  const suit = label.at(-1);
  const value = RANK_VALUES[rank];
  return value ? { rank, value, suit } : null;
}

function combinations(cards, size) {
  if (size === 0) return [[]];
  if (cards.length < size) return [];
  if (cards.length === size) return [cards];
  const [first, ...rest] = cards;
  return [
    ...combinations(rest, size - 1).map((combo) => [first, ...combo]),
    ...combinations(rest, size),
  ];
}

function scoreFiveCards(cards) {
  const values = cards.map((card) => card.value).sort((a, b) => b - a);
  const counts = countValues(values);
  const groups = [...counts.entries()].sort((a, b) => b[1] - a[1] || b[0] - a[0]);
  const flush = new Set(cards.map((card) => card.suit)).size === 1;
  const straightHigh = getStraightHigh(values);

  if (flush && straightHigh) return score(8, [straightHigh], straightHigh);
  if (groups[0][1] === 4) return score(7, [groups[0][0], kicker(values, [groups[0][0]])], groups[0][0]);
  if (groups[0][1] === 3 && groups[1]?.[1] === 2) return score(6, [groups[0][0], groups[1][0]], groups[0][0], groups[1][0]);
  if (flush) return score(5, values, values[0]);
  if (straightHigh) return score(4, [straightHigh], straightHigh);
  if (groups[0][1] === 3) return score(3, [groups[0][0], ...kickers(values, [groups[0][0]])], groups[0][0]);

  const pairs = groups.filter((group) => group[1] === 2).map((group) => group[0]);
  if (pairs.length >= 2) {
    const orderedPairs = pairs.sort((a, b) => b - a);
    return score(
      2,
      [orderedPairs[0], orderedPairs[1], kicker(values, orderedPairs)],
      orderedPairs[0],
      orderedPairs[1],
    );
  }
  if (pairs.length === 1) return score(1, [pairs[0], ...kickers(values, pairs)], pairs[0]);
  return score(0, values, values[0]);
}

function score(category, ranks, primary, secondary = null) {
  return { category, ranks, primary, secondary };
}

function compareScores(a, b) {
  if (a.category !== b.category) return a.category - b.category;
  const length = Math.max(a.ranks.length, b.ranks.length);
  for (let index = 0; index < length; index += 1) {
    const diff = (a.ranks[index] || 0) - (b.ranks[index] || 0);
    if (diff !== 0) return diff;
  }
  return 0;
}

function countValues(values) {
  const counts = new Map();
  for (const value of values) counts.set(value, (counts.get(value) || 0) + 1);
  return counts;
}

function getStraightHigh(values) {
  const unique = new Set(values);
  if (unique.has(14)) unique.add(1);
  for (let high = 14; high >= 5; high -= 1) {
    if ([0, 1, 2, 3, 4].every((offset) => unique.has(high - offset))) return high;
  }
  return null;
}

function kicker(values, usedValues) {
  return kickers(values, usedValues)[0] || 0;
}

function kickers(values, usedValues) {
  const used = new Set(usedValues);
  return values.filter((value) => !used.has(value));
}
