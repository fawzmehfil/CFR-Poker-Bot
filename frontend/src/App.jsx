import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { Check, Clock3, Coins, History, Loader2, RotateCcw, Sparkles, Spade, TrendingUp, X, Zap } from "lucide-react";
import {
  STREET_LABELS,
  actionLabel,
  actionTone,
  buildActionTimeline,
  buildBoardRevealPlan,
  describeShowdown,
  getLatestActionBanner,
} from "./uiState.js";
import "./styles.css";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";
const ACTION_DELAY_MS = 220;
const BOT_REVEAL_DELAY_MS = 440;
const NEW_HAND_DELAY_MS = 260;
const BANNER_MS = 1180;
const CHIP_ANIMATION_MS = 980;

const SUITS = {
  h: { symbol: "♥", name: "heart" },
  d: { symbol: "♦", name: "diamond" },
  c: { symbol: "♣", name: "club" },
  s: { symbol: "♠", name: "spade" },
};
const RANKS = { T: "10" };

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function parseCard(label = "") {
  if (label.length < 2) return { rank: label, suit: null };
  const suitKey = label.at(-1);
  const suit = SUITS[suitKey];
  if (!suit) return { rank: label, suit: null };
  return { rank: RANKS[label.slice(0, -1)] || label.slice(0, -1), suit };
}

function Card({ label, hidden = false, placeholder = "Board", revealDelay = 0, interactive = false, className = "" }) {
  const card = parseCard(label);
  const isRed = card.suit?.name === "heart" || card.suit?.name === "diamond";
  const style = { "--reveal-delay": `${revealDelay}ms` };

  if (hidden) {
    return (
      <div className={`card hidden ${className}`} style={style} aria-label="Hidden card">
        <span className="cardBackMark">{label || "?"}</span>
      </div>
    );
  }

  if (!label) {
    return (
      <div className={`card empty ${className}`} style={style} aria-label={`${placeholder} card slot`}>
        <span>{placeholder}</span>
      </div>
    );
  }

  return (
    <div
      className={`card revealed ${isRed ? "red" : "black"} ${interactive ? "interactive" : ""} ${className}`}
      style={style}
      aria-label={`${card.rank} of ${card.suit?.name || "unknown suit"}s`}
    >
      <span className="corner top">{card.rank}</span>
      {card.suit && <span className="suit">{card.suit.symbol}</span>}
      <span className="corner bottom">{card.rank}</span>
    </div>
  );
}

function Chips({ amount, muted = false, large = false }) {
  return (
    <div className={`chipStack ${muted ? "muted" : ""} ${large ? "large" : ""}`} aria-label={`${amount} chips`}>
      <span className="chipIcon" />
      <strong>{amount}</strong>
    </div>
  );
}

function PotColumn({ pot = 0, toCall = 0 }) {
  return (
    <div className="potColumn sidePot">
      <span className="metricLabel">Pot</span>
      <div key={pot} className="potEmphasis">
        <Chips amount={pot} large />
      </div>
      <div className="toCall">
        To call <strong>{toCall}</strong>
      </div>
    </div>
  );
}

function ActionIcon({ action }) {
  const normalized = action === "f" ? "fold" : action === "k" ? "check" : action === "r" ? "raise" : action;
  const Icon =
    normalized === "fold"
      ? X
      : normalized === "check"
        ? Check
        : normalized === "raise" || normalized === "bet" || normalized === "b"
          ? TrendingUp
          : normalized === "all-in"
            ? Zap
            : Coins;
  return <Icon size={18} strokeWidth={2.4} aria-hidden="true" />;
}

function PlayerSeat({
  name,
  stack,
  cards,
  hiddenCards = false,
  className = "",
  note,
  active = false,
  thinking = false,
  winner = false,
  cardDelayBase = 0,
}) {
  return (
    <div className={`playerSeat ${className} ${active ? "active" : ""} ${thinking ? "thinking" : ""} ${winner ? "winner" : ""}`}>
      <div className="seatHalo" />
      <div className="seatCards">
        {cards.map((card, index) => (
          <Card
            key={`${card || "hidden"}-${index}`}
            label={card}
            hidden={hiddenCards || card === "?"}
            interactive={name === "You"}
            revealDelay={cardDelayBase + index * 90}
          />
        ))}
      </div>
      <div className="seatPlate">
        <span>{name}</span>
        {stack !== undefined && (
          <strong key={stack} className="stackAmount">
            {stack}
          </strong>
        )}
        {note && <small>{note}</small>}
        {thinking && (
          <em>
            <Clock3 size={12} aria-hidden="true" />
            Thinking
          </em>
        )}
      </div>
    </div>
  );
}

function formatError(err) {
  const text = String(err?.message || err || "");
  try {
    const parsed = JSON.parse(text);
    return parsed.detail || text;
  } catch {
    return text;
  }
}

function getBetSize(game) {
  return game?.street === "turn" || game?.street === "river" ? 4 : 2;
}

function getImmediateAmount(mode, game, action) {
  if (!game) return null;
  if (action === "call" || action === "c") return game.to_call || null;
  if (action === "bet" || action === "b" || action === "raise" || action === "r") {
    return mode === "holdem" ? (game.to_call || 0) + getBetSize(game) : game.to_call || null;
  }
  if (action === "all-in") return game.stacks?.[0] || null;
  return null;
}

function buildImmediateBanner(mode, game, action) {
  return {
    actor: "You",
    text: actionLabel(mode, action).toUpperCase(),
    amount: getImmediateAmount(mode, game, action),
    tone: actionTone(action),
  };
}

function App() {
  const [mode, setMode] = useState("holdem");
  const [game, setGame] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [phase, setPhase] = useState("idle");
  const [actionBanner, setActionBanner] = useState(null);
  const [chipBurst, setChipBurst] = useState(null);
  const requestIdRef = useRef(0);
  const bannerTimerRef = useRef(null);
  const chipTimerRef = useRef(null);

  function showActionBanner(banner) {
    if (!banner) return;
    clearTimeout(bannerTimerRef.current);
    setActionBanner({ ...banner, id: `${Date.now()}-${banner.actor}-${banner.text}` });
    bannerTimerRef.current = setTimeout(() => setActionBanner(null), BANNER_MS);
  }

  function triggerChipBurst(banner) {
    if (!banner?.amount) return;
    clearTimeout(chipTimerRef.current);
    setChipBurst({ ...banner, id: `${Date.now()}-${banner.actor}-${banner.amount}` });
    chipTimerRef.current = setTimeout(() => setChipBurst(null), CHIP_ANIMATION_MS);
  }

  async function newGame(nextMode = mode) {
    const requestId = requestIdRef.current + 1;
    requestIdRef.current = requestId;
    setLoading(true);
    setPhase("dealing");
    setError("");
    setGame(null);
    setActionBanner(null);

    try {
      await sleep(NEW_HAND_DELAY_MS);
      const path = nextMode === "holdem" ? "/api/holdem/new-game" : "/api/new-game";
      const res = await fetch(`${API}${path}`, { method: "POST" });
      if (!res.ok) throw new Error(await res.text());
      const nextGame = await res.json();
      if (requestIdRef.current !== requestId) return;
      setPhase("reveal");
      setGame(nextGame);
      await sleep(ACTION_DELAY_MS);
    } catch (err) {
      if (requestIdRef.current === requestId) setError(formatError(err));
    } finally {
      if (requestIdRef.current === requestId) {
        setPhase("idle");
        setLoading(false);
      }
    }
  }

  async function act(action) {
    if (!game || loading) return;
    const requestId = requestIdRef.current + 1;
    const previousGame = game;
    const immediateBanner = buildImmediateBanner(mode, game, action);
    requestIdRef.current = requestId;
    showActionBanner(immediateBanner);
    triggerChipBurst(immediateBanner);
    setLoading(true);
    setPhase("player-action");
    setError("");

    try {
      await sleep(ACTION_DELAY_MS);
      if (requestIdRef.current !== requestId) return;
      setPhase("bot-thinking");
      const path =
        mode === "holdem" ? `/api/holdem/game/${game.session_id}/act` : `/api/game/${game.session_id}/act`;
      const res = await fetch(`${API}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });
      if (!res.ok) throw new Error(await res.text());
      const nextGame = await res.json();
      if (requestIdRef.current !== requestId) return;
      await sleep(BOT_REVEAL_DELAY_MS);
      const responseBanner = getLatestActionBanner(mode, previousGame, nextGame) || immediateBanner;
      showActionBanner(responseBanner);
      triggerChipBurst(responseBanner);
      setPhase("reveal");
      setGame(nextGame);
      await sleep(ACTION_DELAY_MS);
    } catch (err) {
      if (requestIdRef.current === requestId) setError(formatError(err));
    } finally {
      if (requestIdRef.current === requestId) {
        setPhase("idle");
        setLoading(false);
      }
    }
  }

  useEffect(() => {
    newGame(mode);
  }, [mode]);

  useEffect(() => {
    return () => {
      clearTimeout(bannerTimerRef.current);
      clearTimeout(chipTimerRef.current);
    };
  }, []);

  const displayStacks = mode === "holdem" && game?.terminal && game.final_stacks ? game.final_stacks : game?.stacks;
  const heroStack = displayStacks?.[0];
  const botStack = displayStacks?.[1];
  const isBotThinking = phase === "bot-thinking" || Boolean(game && !game.terminal && game.current_player === 1);
  const isHumanTurn = Boolean(game && !game.terminal && game.current_player === 0 && !loading);
  const showdown = mode === "holdem" ? describeShowdown(game) : null;
  const timeline = useMemo(() => buildActionTimeline(mode, game?.history || []), [mode, game?.history]);
  const boardPlan = useMemo(() => buildBoardRevealPlan(game?.board || []), [game?.board]);
  const betSize = getBetSize(game);
  const street = mode === "holdem" ? STREET_LABELS[game?.street] || "Preflop" : `Round ${game ? game.round + 1 : 1}`;
  const positionText =
    mode === "holdem" && game
      ? `Button ${game.button === 0 ? "You" : "Bot"} | SB ${
          game.small_blind_player === 0 ? "You" : "Bot"
        } | BB ${game.big_blind_player === 0 ? "You" : "Bot"}`
      : game?.bot_mode
        ? `Bot mode ${game.bot_mode}`
        : "Bot ready";
  const stackText = mode === "holdem" ? `Stacks You ${heroStack ?? 0} | Bot ${botStack ?? 0}` : `Pot ${game?.pot ?? 0}`;
  const status = useMemo(() => {
    if (phase === "dealing" || !game) return "Shuffling and dealing...";
    if (phase === "player-action") return "Action locked in";
    if (isBotThinking) return "Bot thinking...";
    if (game.terminal) {
      if (mode === "holdem") return showdown?.outcome || "Hand complete";
      if (game.utility > 0) return `You win ${game.utility} chips`;
      if (game.utility < 0) return `Bot wins ${Math.abs(game.utility)} chips`;
      return "Hand ends in a draw";
    }
    return game.current_player === 0 ? "Your decision" : "Bot thinking...";
  }, [game, isBotThinking, mode, phase, showdown]);

  return (
    <main className={`appShell phase-${phase}`}>
      <section className="table" aria-live="polite">
        <header>
          <div className="brand">
            <Spade size={24} />
            <div>
              <h1>{mode === "holdem" ? "Texas Hold'em" : "Leduc CFR Poker"}</h1>
              <p>{mode === "holdem" ? "Heads-up Hold'em vs heuristic bot" : "Compact CFR+ training table"}</p>
            </div>
          </div>
          <div className="headerActions">
            <div className="modeToggle" aria-label="Game mode">
              <button className={mode === "leduc" ? "selected" : ""} onClick={() => setMode("leduc")} disabled={loading}>
                Leduc CFR
              </button>
              <button
                className={mode === "holdem" ? "selected" : ""}
                onClick={() => setMode("holdem")}
                disabled={loading}
              >
                Texas Hold'em
              </button>
            </div>
            <button className="iconButton newHandButton" title="New hand" onClick={() => newGame()} disabled={loading}>
              {phase === "dealing" ? <Loader2 size={20} className="spin" /> : <RotateCcw size={20} />}
            </button>
          </div>
        </header>

        <div className={`felt ${mode === "holdem" ? "holdemFelt" : "leducFelt"}`}>
          <div className="feltRail" />

          {chipBurst && (
            <div key={chipBurst.id} className={`chipMover ${chipBurst.actor === "You" ? "fromHero" : "fromBot"}`}>
              <span className="chipIcon" />
              <strong>{chipBurst.amount}</strong>
            </div>
          )}

          {actionBanner && (
            <div key={actionBanner.id} className={`actionBanner ${actionBanner.tone}`}>
              <span>{actionBanner.actor}</span>
              <strong>{actionBanner.text}</strong>
              {actionBanner.amount ? <em>{actionBanner.amount}</em> : null}
            </div>
          )}

          {mode === "holdem" ? (
            <>
              <PlayerSeat
                name="Bot"
                stack={botStack ?? 0}
                cards={game?.bot_cards || ["?", "?"]}
                hiddenCards={!game?.terminal}
                className="botSeat"
                note={isBotThinking ? "Reading the line" : game?.terminal ? "Cards shown" : "Opponent"}
                active={isBotThinking}
                thinking={isBotThinking}
                winner={showdown?.winnerName === "Bot"}
              />

              <div className="tableCenter holdemBoard">
                <div className="centerTopline">
                  <div className="streetPill">
                    <span>{street}</span>
                    {phase === "reveal" ? <Sparkles size={14} aria-hidden="true" /> : null}
                  </div>
                  <div className={`status ${game?.terminal ? "complete" : ""} ${isBotThinking ? "thinking" : ""}`}>
                    {status}
                  </div>
                </div>
                <div className="boardZone">
                  <div className="boardRail">
                    <div className="cardsRow boardCards" aria-label="Board cards">
                      {boardPlan.map((card, index) => (
                        <Card
                          key={`${index}-${card.label || "empty"}`}
                          label={card.label}
                          placeholder="Board"
                          revealDelay={card.delayMs}
                        />
                      ))}
                    </div>
                  </div>
                  <PotColumn pot={game?.pot ?? 0} toCall={game?.to_call ?? 0} />
                </div>
                {showdown && (
                  <div className={`showdownPanel ${showdown.tone}`}>
                    <Sparkles size={16} aria-hidden="true" />
                    <strong>{showdown.winningHand}</strong>
                    <span>{showdown.outcome}</span>
                  </div>
                )}
              </div>

              <PlayerSeat
                name="You"
                stack={heroStack ?? 0}
                cards={game?.hero_cards || ["?", "?"]}
                className="humanSeat"
                note={game?.terminal ? "Hand complete" : isHumanTurn ? "Your action" : "Waiting"}
                active={isHumanTurn}
                winner={showdown?.winnerName === "You"}
                cardDelayBase={90}
              />
            </>
          ) : (
            <>
              <PlayerSeat
                name="Bot"
                cards={[game?.opponent_card || "?"]}
                hiddenCards={!game?.opponent_card}
                className="botSeat"
                note={isBotThinking ? "Thinking" : "Reveals at showdown"}
                active={isBotThinking}
                thinking={isBotThinking}
              />

              <div className="tableCenter leducBoard">
                <div className="centerTopline">
                  <div className="streetPill">
                    <span>{street}</span>
                  </div>
                  <div className={`status ${game?.terminal ? "complete" : ""} ${isBotThinking ? "thinking" : ""}`}>
                    {status}
                  </div>
                </div>
                <div className="boardZone">
                  <div className="boardRail">
                    <div className="cardsRow boardCards">
                      <Card label={game?.public_card || ""} placeholder="Public" revealDelay={120} />
                    </div>
                  </div>
                  <PotColumn pot={game?.pot ?? 0} toCall={game?.to_call ?? 0} />
                </div>
              </div>

              <PlayerSeat
                name="You"
                cards={[game?.private_card || "?"]}
                className="humanSeat"
                note={game?.terminal ? "Hand complete" : isHumanTurn ? "Your private card" : "Waiting"}
                active={isHumanTurn}
              />
            </>
          )}
        </div>

        <div className="playDock">
          <div className="handInfo">
            <span className="street">{street}</span>
            <span>{positionText}</span>
            <span>{stackText}</span>
            {mode === "holdem" && <span>Limit bet {betSize}</span>}
          </div>

          <div className="controlGroup">
            {mode === "holdem" && !game?.terminal && (
              <div className="betSizing" aria-label="Bet sizing">
                <span>Raise structure</span>
                <strong>{betSize} chips</strong>
                <small>{game?.street === "turn" || game?.street === "river" ? "big bet street" : "small bet street"}</small>
              </div>
            )}
            <div className="controls">
              {(game?.legal_actions || []).map((action) => {
                const amount = getImmediateAmount(mode, game, action);
                const label = actionLabel(mode, action);
                return (
                  <button
                    key={action}
                    className={`actionButton ${actionTone(action)}`}
                    onClick={() => act(action)}
                    disabled={loading || game?.terminal}
                    aria-label={amount ? `${label} ${amount} chips` : label}
                  >
                    <ActionIcon action={action} />
                    <span className="actionText">
                      <span className="actionLabel">{label}</span>
                      {amount ? <span className="buttonAmount">{amount}</span> : null}
                    </span>
                  </button>
                );
              })}
              {game?.terminal && (
                <button className="primary newHandButton" onClick={() => newGame()} disabled={loading}>
                  <RotateCcw size={18} aria-hidden="true" />
                  New Hand
                </button>
              )}
              {!game?.terminal && (game?.legal_actions || []).length === 0 && (
                <div className="waiting">{loading ? "Dealing..." : "Waiting for bot..."}</div>
              )}
            </div>
          </div>
        </div>

        <div className="historyPanel" aria-label="Hand history">
          <div className="historyTitle">
            <History size={15} aria-hidden="true" />
            <span>Action Timeline</span>
          </div>
          {timeline.length ? (
            <div className="timeline">
              {timeline.slice(-4).map((group) => (
                <section key={group.street} className="timelineStreet">
                  <h2>[{group.street.toUpperCase()}]</h2>
                  <ol>
                    {group.events.map((event) => (
                      <li key={event.id} className={event.tone}>
                        <span className="historyActor">{event.actor}</span>
                        <span>{event.label}</span>
                        {event.amount ? <strong>{event.amount}</strong> : null}
                      </li>
                    ))}
                  </ol>
                </section>
              ))}
            </div>
          ) : (
            <p>No actions yet.</p>
          )}
        </div>

        {error && <div className="error">{error}</div>}
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
