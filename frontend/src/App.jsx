import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { RotateCcw, Spade } from "lucide-react";
import "./styles.css";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";
const LABELS = { k: "Check", b: "Bet", c: "Call", r: "Raise", f: "Fold" };

function Card({ label, hidden = false }) {
  return <div className={`card ${hidden ? "hidden" : ""}`}>{hidden ? "?" : label}</div>;
}

function App() {
  const [game, setGame] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function newGame() {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API}/api/new-game`, { method: "POST" });
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
      const res = await fetch(`${API}/api/game/${game.session_id}/act`, {
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
    newGame();
  }, []);

  const status = useMemo(() => {
    if (!game) return "Starting table...";
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
              <h1>Leduc CFR Poker</h1>
              <p>Play vs a tabular CFR+ bot</p>
            </div>
          </div>
          <button className="iconButton" title="New hand" onClick={newGame} disabled={loading}>
            <RotateCcw size={20} />
          </button>
        </header>

        <div className="felt">
          <div className="player bot">
            <span>Bot</span>
            <Card hidden />
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

        <div className="controls">
          {(game?.legal_actions || []).map((action) => (
            <button key={action} onClick={() => act(action)} disabled={loading || game?.terminal}>
              {LABELS[action]}
            </button>
          ))}
          {game?.terminal && (
            <button className="primary" onClick={newGame} disabled={loading}>
              New Hand
            </button>
          )}
        </div>

        <div className="meta">
          <span>Round {game ? game.round + 1 : 1}</span>
          <span>To call {game?.to_call ?? 0}</span>
          <span>History {(game?.history || ["", ""]).join(" / ") || "-"}</span>
        </div>

        {error && <div className="error">{error}</div>}
      </section>
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);

