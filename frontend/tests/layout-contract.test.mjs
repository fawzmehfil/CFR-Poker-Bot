import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";

const app = readFileSync(new URL("../src/App.jsx", import.meta.url), "utf8");
const css = readFileSync(new URL("../src/styles.css", import.meta.url), "utf8");

test("table layout keeps the board centered with the pot beside it", () => {
  assert.match(app, /className="boardZone"/);
  assert.match(app, /className="boardRail"/);
  assert.match(css, /\.boardZone\s*{[\s\S]*grid-template-columns:\s*minmax\(0,\s*1fr\)\s+auto\s+minmax\(0,\s*1fr\)/);
  assert.match(css, /\.sidePot\s*{[\s\S]*justify-self:\s*start/);
});

test("side pot column stays vertically aligned instead of tapering", () => {
  const sidePotRule = css.match(/\.sidePot\s*{[\s\S]*?\n}/)?.[0] || "";
  const sidePotToCallRule = css.match(/\.sidePot \.toCall\s*{[\s\S]*?\n}/)?.[0] || "";
  const potEmphasisRule = css.match(/\.potEmphasis\s*{[\s\S]*?\n}/)?.[0] || "";

  assert.match(sidePotRule, /inline-size:\s*clamp\(/);
  assert.match(sidePotRule, /justify-items:\s*stretch/);
  assert.match(potEmphasisRule, /inline-size:\s*100%/);
  assert.match(sidePotToCallRule, /inline-size:\s*100%/);
});

test("action buttons keep their action color on hover", () => {
  const actionHoverRule = css.match(/\.actionButton:hover:not\(:disabled\)\s*{[\s\S]*?\n}/)?.[0] || "";

  assert.match(actionHoverRule, /background:\s*var\(--button-bg\)/);
  assert.doesNotMatch(actionHoverRule, /rgba\(255,\s*255,\s*255,\s*0\.12\)/);
  assert.match(actionHoverRule, /filter:\s*brightness\(1\.04\)/);
});

test("new hand buttons keep their base fill on hover", () => {
  const newHandHoverRule = css.match(/\.newHandButton:hover:not\(:disabled\)\s*{[\s\S]*?\n}/)?.[0] || "";

  assert.match(app, /className="iconButton newHandButton"/);
  assert.match(app, /className="primary newHandButton"/);
  assert.match(newHandHoverRule, /background:\s*var\(--button-bg\)/);
  assert.doesNotMatch(newHandHoverRule, /rgba\(255,\s*255,\s*255,\s*0\.12\)/);
  assert.match(newHandHoverRule, /filter:\s*brightness\(1\.04\)/);
});

test("chip bet animations share the exact center endpoint", () => {
  const chipMoverRule = css.match(/\.chipMover\s*{[\s\S]*?\n}/)?.[0] || "";
  const heroRule = css.match(/\.chipMover\.fromHero\s*{[\s\S]*?\n}/)?.[0] || "";
  const botRule = css.match(/\.chipMover\.fromBot\s*{[\s\S]*?\n}/)?.[0] || "";

  assert.match(chipMoverRule, /top:\s*50%/);
  assert.doesNotMatch(heroRule, /bottom:/);
  assert.doesNotMatch(botRule, /top:\s*\d/);
  assert.match(heroRule, /animation:\s*chipToPotCenter/);
  assert.match(botRule, /animation:\s*chipToPotCenter/);
  assert.match(css, /@keyframes chipToPotCenter[\s\S]*to\s*{[\s\S]*translate\(-50%,\s*-50%\)/);
});

test("action feedback is a side toast instead of a center-screen banner", () => {
  const bannerRule = css.match(/\.actionBanner\s*{[\s\S]*?\n}/)?.[0] || "";

  assert.doesNotMatch(bannerRule, /left:\s*50%/);
  assert.doesNotMatch(bannerRule, /top:\s*47%/);
  assert.match(bannerRule, /right:\s*clamp\(/);
});

test("main poker shell is constrained to one viewport", () => {
  assert.match(css, /\.table\s*{[\s\S]*height:\s*min\(/);
  assert.match(css, /\.felt\s*{[\s\S]*min-height:\s*0/);
  assert.doesNotMatch(css, /\.felt\s*{[\s\S]*?min-height:\s*700px/);
});

test("felt surface does not render a center watermark", () => {
  assert.doesNotMatch(app, /className="feltLogo"/);
  assert.doesNotMatch(app, />CFR Poker</);
  assert.doesNotMatch(css, /\.feltLogo/);
});
