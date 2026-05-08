import assert from "node:assert/strict";
import { test } from "node:test";

import {
  buildActionTimeline,
  buildBoardRevealPlan,
  describeShowdown,
  getLatestActionBanner,
} from "../src/uiState.js";

test("groups Hold'em history into a color-coded street timeline", () => {
  const timeline = buildActionTimeline("holdem", [
    "preflop:p0:call:1",
    "preflop:p1:raise:4",
    "preflop:p0:call:3",
    "flop:p1:check:0",
    "flop:p0:bet:2",
  ]);

  assert.deepEqual(
    timeline.map((group) => group.street),
    ["Preflop", "Flop"],
  );
  assert.equal(timeline[0].events[0].label, "call");
  assert.deepEqual(timeline[0].events[1], {
    id: "preflop-1-p1-raise-4",
    actor: "Bot",
    label: "raises to",
    amount: 4,
    tone: "raise",
    street: "Preflop",
  });
  assert.equal(timeline[1].events[1].tone, "raise");
});

test("detects the latest action banner from new history", () => {
  const previous = {
    history: ["preflop:p0:call:1"],
  };
  const next = {
    history: ["preflop:p0:call:1", "preflop:p1:all-in:96"],
  };

  assert.deepEqual(getLatestActionBanner("holdem", previous, next), {
    actor: "Bot",
    text: "ALL-IN",
    amount: 96,
    tone: "allIn",
  });
});

test("detects the latest Leduc action when a round history string grows", () => {
  const previous = {
    history: ["", ""],
  };
  const next = {
    history: ["kk", ""],
  };

  assert.deepEqual(getLatestActionBanner("leduc", previous, next), {
    actor: "Bot",
    text: "CHECK",
    amount: null,
    tone: "check",
  });
});

test("assigns sequential reveal timing to visible board cards", () => {
  const plan = buildBoardRevealPlan(["Ah", "Kd", "Qs", "2c", "9h"]);

  assert.equal(plan.length, 5);
  assert.deepEqual(
    plan.map((card) => card.delayMs),
    [0, 120, 240, 360, 480],
  );
  assert.equal(plan[3].label, "2c");
  assert.equal(plan[4].isVisible, true);
});

test("summarizes showdown winner and winning hand text", () => {
  const summary = describeShowdown({
    terminal: true,
    hero_cards: ["Qh", "Qs"],
    bot_cards: ["Ah", "Kd"],
    board: ["2c", "7d", "9s", "Jc", "3h"],
    utility: 12,
    result: "You win 12 chips",
  });

  assert.deepEqual(summary, {
    winnerName: "You",
    winningHand: "Pair of Queens",
    outcome: "You win 12 chips",
    tone: "win",
  });
});
