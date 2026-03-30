"""Integration tests for auth, PvP, and tooling API routes."""

import json
import os
import sys

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import auth
import main


client = TestClient(main.app)


class TestMagicLinkAuth:
    def test_magic_link_login_flow(self):
        requested = client.post(
            "/api/auth/magic-link/request",
            json={"email": "student@example.com", "display_name": "Student"},
        )
        assert requested.status_code == 200
        payload = requested.json()
        assert payload["sent"] is True
        assert payload["magic_link_token"]

        verified = client.post(
            "/api/auth/magic-link/verify",
            json={"token": payload["magic_link_token"]},
        )
        assert verified.status_code == 200
        access_token = verified.json()["access_token"]

        me = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert me.status_code == 200
        assert me.json()["user"]["email"] == "student@example.com"

        logout = client.post(
            "/api/auth/logout",
            json={},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert logout.status_code == 200

        after_logout = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert after_logout.status_code == 401

    def test_google_login_flow(self, monkeypatch):
        monkeypatch.setattr(
            auth,
            "_verify_google_identity_token",
            lambda token: {
                "email": "coach@example.com",
                "name": "Coach",
                "sub": "google-subject-1",
                "iss": "accounts.google.com",
            },
        )

        resp = client.post("/api/auth/google", json={"id_token": "fake"})
        assert resp.status_code == 200
        assert resp.json()["user"]["provider"] == "google"

    def test_magic_link_token_cannot_be_reused(self):
        requested = client.post(
            "/api/auth/magic-link/request",
            json={"email": "reuse@example.com", "display_name": "Reuse"},
        )
        token = requested.json()["magic_link_token"]

        first = client.post("/api/auth/magic-link/verify", json={"token": token})
        assert first.status_code == 200

        second = client.post("/api/auth/magic-link/verify", json={"token": token})
        assert second.status_code == 400

    def test_auth_me_requires_token(self):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401


class TestPvP:
    def test_create_join_and_play_pvp_game(self):
        created = client.post(
            "/api/pvp/create",
            json={"player_name": "Alice", "preferred_color": "white"},
        )
        assert created.status_code == 200
        create_payload = created.json()
        game_id = create_payload["state"]["game_id"]
        white_token = create_payload["player_token"]
        join_code = create_payload["state"]["join_code"]
        assert create_payload["state"]["waiting_for_opponent"] is True

        joined = client.post(
            "/api/pvp/join",
            json={"join_code": join_code, "player_name": "Bob"},
        )
        assert joined.status_code == 200
        black_token = joined.json()["player_token"]
        assert joined.json()["state"]["players"]["white"] == "Alice"
        assert joined.json()["state"]["players"]["black"] == "Bob"

        state = client.get(f"/api/pvp/{game_id}/state", params={"player_token": white_token})
        assert state.status_code == 200
        assert state.json()["player_color"] == "white"
        assert "e2e4" in state.json()["legal_moves"]

        move = client.post(
            f"/api/pvp/{game_id}/move",
            json={
                "player_token": white_token,
                "from_sq": "e2",
                "to_sq": "e4",
            },
        )
        assert move.status_code == 200
        assert move.json()["move_history"] == ["e2e4"]

        wrong_turn = client.post(
            f"/api/pvp/{game_id}/move",
            json={
                "player_token": white_token,
                "from_sq": "d2",
                "to_sq": "d4",
            },
        )
        assert wrong_turn.status_code == 400

        black_state = client.get(f"/api/pvp/{game_id}/state", params={"player_token": black_token})
        assert black_state.status_code == 200
        assert black_state.json()["player_color"] == "black"
        assert "e7e5" in black_state.json()["legal_moves"]

    def test_join_full_room_rejected(self):
        created = client.post(
            "/api/pvp/create",
            json={"player_name": "Alice", "preferred_color": "white"},
        )
        join_code = created.json()["state"]["join_code"]

        first_join = client.post(
            "/api/pvp/join",
            json={"join_code": join_code, "player_name": "Bob"},
        )
        assert first_join.status_code == 200

        second_join = client.post(
            "/api/pvp/join",
            json={"join_code": join_code, "player_name": "Carol"},
        )
        assert second_join.status_code == 400

    def test_invalid_pvp_move_token_rejected(self):
        created = client.post(
            "/api/pvp/create",
            json={"player_name": "Alice", "preferred_color": "white"},
        )
        game_id = created.json()["state"]["game_id"]
        join_code = created.json()["state"]["join_code"]

        joined = client.post(
            "/api/pvp/join",
            json={"join_code": join_code, "player_name": "Bob"},
        )
        assert joined.status_code == 200

        bad_move = client.post(
            f"/api/pvp/{game_id}/move",
            json={
                "player_token": "invalid-token",
                "from_sq": "e2",
                "to_sq": "e4",
            },
        )
        assert bad_move.status_code == 400


class TestToolingEndpoints:
    def test_run_benchmarks_endpoint(self, monkeypatch, tmp_path):
        monkeypatch.setattr(main, "BENCHMARK_LATEST", tmp_path / "latest.json")
        monkeypatch.setattr(main, "BENCHMARK_HISTORY", tmp_path / "history.jsonl")

        resp = client.post(
            "/api/tooling/benchmarks/run",
            json={"engine_ids": ["v0"], "persist": True},
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["engine_ids"] == ["v0"]
        assert payload["results"][0]["engine_id"] == "v0"
        assert (tmp_path / "latest.json").exists()

    def test_run_benchmarks_with_no_implemented_engines(self, monkeypatch):
        monkeypatch.setattr(main, "_implemented_engine_ids", lambda: [])
        resp = client.post("/api/tooling/benchmarks/run", json={"persist": False})
        assert resp.status_code == 400

    def test_build_openings_endpoint(self, monkeypatch, tmp_path):
        monkeypatch.setattr(main, "OPENING_JSON_PATH", tmp_path / "openings.json")
        monkeypatch.setattr(main, "OPENING_BIN_PATH", tmp_path / "openings.bin")
        monkeypatch.setattr(main, "OPENING_GENERATED_JSON_PATH", tmp_path / "openings.generated.json")
        monkeypatch.setattr(main, "OPENING_GENERATED_BIN_PATH", tmp_path / "openings.generated.bin")

        resp = client.post(
            "/api/tooling/openings/build",
            json={
                "pgn_text": (
                    "[Event \"Game\"]\n"
                    "[Site \"?\"]\n"
                    "[Date \"2026.03.28\"]\n"
                    "[Round \"-\"]\n"
                    "[White \"A\"]\n"
                    "[Black \"B\"]\n"
                    "[Result \"*\"]\n"
                    "[WhiteElo \"2000\"]\n"
                    "[BlackElo \"2000\"]\n\n"
                    "1. e4 e5 2. Nf3 *\n"
                ),
                "max_plies": 4,
                "min_elo": 1800,
                "activate": False,
            },
        )
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["games_used"] == 1
        assert payload["polyglot_entries"] >= 2
        assert (tmp_path / "openings.generated.json").exists()
        assert (tmp_path / "openings.generated.bin").exists()

    def test_build_openings_requires_pgn_text(self):
        resp = client.post(
            "/api/tooling/openings/build",
            json={"pgn_text": "   "},
        )
        assert resp.status_code == 400