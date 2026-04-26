from fastapi.testclient import TestClient

from backend.main import app


def test_backend_new_game_and_health():
    client = TestClient(app)
    health = client.get("/health")
    assert health.status_code == 200
    assert "cfr" in health.json()["bot_modes"]
    game = client.post("/api/new-game")
    assert game.status_code == 200
    body = game.json()
    assert body["session_id"]
    assert body["private_card"] in {"J", "Q", "K"}
    assert body["bot_mode"] == "cfr"


def test_backend_supports_bot_mode_selection():
    client = TestClient(app)
    game = client.post("/api/new-game", json={"bot_mode": "heuristic"})
    assert game.status_code == 200
    assert game.json()["bot_mode"] == "heuristic"
