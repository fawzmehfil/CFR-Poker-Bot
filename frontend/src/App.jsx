import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { RotateCcw, Spade } from "lucide-react";
import "./styles.css";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";
const LABELS = { k: "Check", b: "Bet", c: "Call", r: "Raise", f: "Fold" };
const HOLDEM_LABELS = { fold: "Fold", check: "Check", call: "Call", bet: "Bet", raise: "Raise", "all-in": "All-in" };
const STREET_LABELS = { preflop: "Preflop", flop: "Flop", turn: "Turn", river: "River", showdown: "Showdown" };
const SUITS = {
  h: { symbol: "♥", name: "heart" },
  d: { symbol: "♦", name: "diamond" },
  c: { symbol: "♣", name: "club" },
  s: { symbol: "♠", name: "spade" },
};
const RANKS = { T: "10" };

function parseCard(label = "") {
  if (label.length < 2) return { rank: label, suit: null };
  const suitKey = label.at(-1);
  const suit = SUITS[suitKey];
  if (!suit) return { rank: label, suit: null };
  return { rank: RANKS[label.slice(0, -1)] || label.slice(0, -1), suit };
}

function Card({ label, hidden = false, placeholder = "Board" }) {
  const card = parseCard(label);
  const isRed = card.suit?.name === "heart" || card.suit?.name === "diamond";

  if (hidden) {
    return (
      <div className="card hidden">
        <span>{label || "?"}</span>
      </div>
    );
  }

  if (!label) {
    return <div className="card empty">{placeholder}</div>;
  }

  return (
    <div className={`card ${isRed ? "red" : "black"}`}>
      <span className="rank">{card.rank}</span>
      {card.suit && <span className="suit">{card.suit.symbol}</span>}
    </div>
  );
}

function Chips({ amount, muted = false }) {
  return (
    <div className={`chipStack ${muted ? "muted" : ""}`} aria-label={`${amount} chips`}>
      <span className="chipIcon" />
      <strong>{amount}</strong>
    </div>
  );
}

function PlayerSeat({ name, stack, cards, hiddenCards = false, className = "", note }) {
  return (
    <div className={`playerSeat ${className}`}>
      <div className="seatCards">
        {cards.map((card, index) => (
          <Card key={`${card || "hidden"}-${index}`} label={card} hidden={hiddenCards || card === "?"} />
        ))}
      </div>
      <div className="seatPlate">
        <span>{name}</span>
        {stack !== undefined && <strong>{stack}</strong>}
        {note && <small>{note}</small>}
      </div>
    </div>
  );
}

function actionLabel(mode, action) {
  return mode === "holdem" ? HOLDEM_LABELS[action] || action : LABELS[action] || action;
}

function formatHistoryToken(mode, token) {
  if (!token) return "";
  if (mode !== "holdem") return actionLabel(mode, token);
  const [street, player, action, amount] = token.split(":");
  const actor = player === "p0" ? "You" : "Bot";
  const label = actionLabel(mode, action);
  const chipText = Number(amount) > 0 ? ` ${amount}` : "";
  return `${STREET_LABELS[street] || street}: ${actor} ${label}${chipText}`;
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

function actionTone(action) {
  if (action === "f" || action === "fold") return "danger";
  if (action === "r" || action === "raise" || action === "bet" || action === "b") return "raise";
  if (action === "all-in") return "allIn";
  return "call";
}

function App() {
  const [mode, setMode] = useState("holdem");
  const [game, setGame] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function newGame(nextMode = mode) {
    setLoading(true);
    setError("");
    try {
      const path = nextMode === "holdem" ? "/api/holdem/new-game" : "/api/new-game";
      const res = await fetch(`${API}${path}`, { method: "POST" });
      if (!res.ok) throw new Error(await res.text());
      setGame(await res.json());
    } catch (err) {
      setError(formatError(err));
    } finally {
      setLoading(false);
    }
  }

  async function act(action) {
    if (!game) return;
    setLoading(true);
    setError("");
    try {
      const path =
        mode === "holdem" ? `/api/holdem/game/${game.session_id}/act` : `/api/game/${game.session_id}/act`;
      const res = await fetch(`${API}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      });
      if (!res.ok) throw new Error(await res.text());
      setGame(await res.json());
    } catch (err) {
      setError(formatError(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    newGame(mode);
  }, [mode]);

  const status = useMemo(() => {
    if (!game) return "Starting table...";
    if (mode === "holdem") {
      if (game.terminal) return game.result || "Hand complete";
      return game.current_player === 0 ? "Your decision" : "Bot thinking";
    }
    if (game.terminal) {
      if (game.utility > 0) return `You win ${game.utility} chips`;
      if (game.utility < 0) return `Bot wins ${Math.abs(game.utility)} chips`;
      return "Hand ends in a draw";
    }
    return game.current_player === 0 ? "Your decision" : "Bot thinking";
  }, [game]);

  const street = mode === "holdem" ? STREET_LABELS[game?.street] || "Preflop" : `Round ${game ? game.round + 1 : 1}`;
  const historyItems = (game?.history || []).filter(Boolean).map((item) => formatHistoryToken(mode, item));
  const legalActions = game?.legal_actions || [];
  const heroStack = game?.stacks?.[0];
  const botStack = game?.stacks?.[1];
  const isHumanTurn = Boolean(game && !game.terminal && game.current_player === 0);
  const positionText =
    mode === "holdem" && game
      ? `Button ${game.button === 0 ? "You" : "Bot"} | SB ${
          game.small_blind_player === 0 ? "You" : "Bot"
        } | BB ${game.big_blind_player === 0 ? "You" : "Bot"}`
      : game?.bot_mode
        ? `Bot mode ${game.bot_mode}`
        : "Bot ready";
  const stackText = mode === "holdem" ? `Stacks You ${heroStack ?? 0} | Bot ${botStack ?? 0}` : `Pot ${game?.pot ?? 0}`;

  return (
    <main>
      <section className="table">
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
            <button className="iconButton" title="New hand" onClick={() => newGame()} disabled={loading}>
              <RotateCcw size={20} />
            </button>
          </div>
        </header>

        <div className={`felt ${mode === "holdem" ? "holdemFelt" : "leducFelt"}`}>
          <div className="feltRail" />
          <div className="feltLogo">
            <Spade size={44} />
            <span>CFR Poker</span>
          </div>

          {mode === "holdem" ? (
            <>
              <PlayerSeat
                name="Bot"
                stack={botStack ?? 0}
                cards={game?.bot_cards || ["?", "?"]}
                className="botSeat"
                note="Opponent"
              />

              <div className="tableCenter holdemBoard">
                <div className="potColumn">
                  <span className="metricLabel">To call</span>
                  <Chips amount={game?.to_call ?? 0} muted />
                  <div className="pot">Pot {game?.pot ?? 0}</div>
                </div>
                <div className={`status ${game?.terminal ? "complete" : ""}`}>{status}</div>
                <div className="cardsRow boardCards">
                  {Array.from({ length: 5 }).map((_, index) => (
                    <Card key={index} label={game?.board?.[index] || ""} placeholder="Board" />
                  ))}
                </div>
              </div>

              <PlayerSeat
                name="You"
                stack={heroStack ?? 0}
                cards={game?.hero_cards || ["?", "?"]}
                className={`humanSeat ${isHumanTurn ? "active" : ""}`}
                note={game?.terminal ? "Hand complete" : isHumanTurn ? "Your action" : "Waiting"}
              />
            </>
          ) : (
            <>
              <PlayerSeat
                name="Bot"
                cards={[game?.opponent_card || "?"]}
                hiddenCards={!game?.opponent_card}
                className="botSeat"
                note="Reveals at showdown"
              />

              <div className="tableCenter leducBoard">
                <div className="potColumn">
                  <span className="metricLabel">To call</span>
                  <Chips amount={game?.to_call ?? 0} muted />
                  <div className="pot">Pot {game?.pot ?? 0}</div>
                </div>
                <div className={`status ${game?.terminal ? "complete" : ""}`}>{status}</div>
                <div className="cardsRow boardCards">
                  <Card label={game?.public_card || ""} placeholder="Public" />
                </div>
              </div>

              <PlayerSeat
                name="You"
                cards={[game?.private_card || "?"]}
                className={`humanSeat ${isHumanTurn ? "active" : ""}`}
                note={game?.terminal ? "Hand complete" : isHumanTurn ? "Your private card" : "Waiting"}
              />
            </>
          )}
        </div>

        <div className="playDock">
          <div className="handInfo">
            <span className="street">{street}</span>
            <span>{positionText}</span>
            <span>{stackText}</span>
          </div>

          <div className="controls">
            {legalActions.map((action) => (
              <button
                key={action}
                className={`actionButton ${actionTone(action)}`}
                onClick={() => act(action)}
                disabled={loading || game?.terminal}
              >
                {actionLabel(mode, action)}
                {action === "call" || action === "c" ? <span>{game?.to_call ?? 0}</span> : null}
              </button>
            ))}
            {game?.terminal && (
              <button className="primary" onClick={() => newGame()} disabled={loading}>
                New Hand
              </button>
            )}
            {!game?.terminal && legalActions.length === 0 && (
              <div className="waiting">{loading ? "Dealing..." : "Waiting for bot..."}</div>
            )}
          </div>
        </div>

        <div className="historyPanel" aria-label="Hand history">
          <div className="historyTitle">Hand History</div>
          {historyItems.length ? (
            <ol>
              {historyItems.slice(-8).map((item, index) => (
                <li key={`${item}-${index}`}>{item}</li>
              ))}
            </ol>
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
