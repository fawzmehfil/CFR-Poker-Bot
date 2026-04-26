from fastapi.testclient import TestClient

from backend.main import app


def test_backend_new_game_and_health():
    client = TestClient(app)
    health = client.get("/health")
    assert health.status_code == 200
    game = client.post("/api/new-game")
    assert game.status_code == 200
    body = game.json()
    assert body["session_id"]
    assert body["private_card"] in {"J", "Q", "K"}
