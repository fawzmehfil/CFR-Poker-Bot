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


def test_holdem_backend_rejects_illegal_action_cleanly():
    client = TestClient(app)
    game = client.post("/api/holdem/new-game").json()

    response = client.post(f"/api/holdem/game/{game['session_id']}/act", json={"action": "check"})

    assert response.status_code == 400
    assert "Illegal action" in response.json()["detail"]


def test_holdem_backend_legal_user_flow_never_gets_stuck_on_bot_turn():
    client = TestClient(app)
    game = client.post("/api/holdem/new-game").json()

    for _ in range(12):
        assert game["terminal"] or game["current_player"] == 0
        if game["terminal"]:
            break
        assert game["legal_actions"]
        preferred = "call" if "call" in game["legal_actions"] else game["legal_actions"][0]
        response = client.post(f"/api/holdem/game/{game['session_id']}/act", json={"action": preferred})
        assert response.status_code == 200
        game = response.json()

    assert game["terminal"] or game["current_player"] == 0
