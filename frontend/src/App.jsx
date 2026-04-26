import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { RotateCcw, Spade } from "lucide-react";
import "./styles.css";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";
const LABELS = { k: "Check", b: "Bet", c: "Call", r: "Raise", f: "Fold" };
const HOLDEM_LABELS = { fold: "Fold", check: "Check", call: "Call", bet: "Bet", raise: "Raise" };

function Card({ label, hidden = false }) {
  return <div className={`card ${hidden ? "hidden" : ""}`}>{hidden ? "?" : label}</div>;
}

function App() {
  const [mode, setMode] = useState("leduc");
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
      setError(String(err.message || err));
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
      setError(String(err.message || err));
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
      return game.current_player === 0 ? "Your turn" : "Bot thinking";
    }
    if (game.terminal) {
      if (game.utility > 0) return `You win ${game.utility} chips`;
      if (game.utility < 0) return `Bot wins ${Math.abs(game.utility)} chips`;
      return "Hand ends in a draw";
    }
    return game.current_player === 0 ? "Your turn" : "Bot thinking";
  }, [game]);

  return (
    <main>
      <section className="table">
        <header>
          <div className="brand">
            <Spade size={24} />
            <div>
              <h1>{mode === "holdem" ? "Texas Hold'em" : "Leduc CFR Poker"}</h1>
              <p>{mode === "holdem" ? "Playable fixed-limit demo vs heuristic bot" : "Play vs a tabular CFR+ bot"}</p>
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

        {mode === "holdem" ? (
          <div className="felt holdemFelt">
            <div className="player bot">
              <span>Bot {game ? `(${game.stacks?.[1] ?? 0})` : ""}</span>
              <div className="cardsRow">
                {(game?.bot_cards || ["?", "?"]).map((card, index) => (
                  <Card key={index} label={card} hidden={card === "?"} />
                ))}
              </div>
            </div>

            <div className="board holdemBoard">
              <div className="pot">Pot {game?.pot ?? 0}</div>
              <div className="cardsRow boardCards">
                {Array.from({ length: 5 }).map((_, index) => {
                  const label = game?.board?.[index] || "";
                  return <Card key={index} label={label || "Board"} hidden={!label} />;
                })}
              </div>
              <div className="status">{status}</div>
            </div>

            <div className="player human">
              <span>You {game ? `(${game.stacks?.[0] ?? 0})` : ""}</span>
              <div className="cardsRow">
                {(game?.hero_cards || ["?", "?"]).map((card, index) => (
                  <Card key={index} label={card} />
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="felt">
            <div className="player bot">
              <span>Bot</span>
              <Card label={game?.opponent_card || "?"} hidden={!game?.opponent_card} />
            </div>

            <div className="board">
              <div className="pot">Pot {game?.pot ?? 0}</div>
              <Card label={game?.public_card || "Public"} hidden={!game?.public_card} />
              <div className="status">{status}</div>
            </div>

            <div className="player human">
              <span>You</span>
              <Card label={game?.private_card || "?"} />
            </div>
          </div>
        )}

        <div className="controls">
          {(game?.legal_actions || []).map((action) => (
            <button key={action} onClick={() => act(action)} disabled={loading || game?.terminal}>
              {mode === "holdem" ? HOLDEM_LABELS[action] : LABELS[action]}
            </button>
          ))}
          {game?.terminal && (
            <button className="primary" onClick={() => newGame()} disabled={loading}>
              New Hand
            </button>
          )}
        </div>

        <div className="meta">
          <span>{mode === "holdem" ? `Street ${game?.street || "preflop"}` : `Round ${game ? game.round + 1 : 1}`}</span>
          <span>To call {game?.to_call ?? 0}</span>
          <span>History {(game?.history || ["", ""]).join(" / ") || "-"}</span>
        </div>

        {error && <div className="error">{error}</div>}
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
