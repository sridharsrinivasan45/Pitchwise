"""Backend tests for WhySheet 404 fix (iteration_7)."""
import os
import re
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://ball-genius.preview.emergentagent.com").rstrip("/")
BALL_ID_RE = re.compile(r"^\d+-i\d+-o\d+\.\d+$")


@pytest.fixture(scope="module")
def s():
    return requests.Session()


def _pick_historical_match_id(s):
    r = s.get(f"{BASE_URL}/api/matches?limit=20", timeout=30)
    assert r.status_code == 200, r.text
    matches = r.json()
    # Prefer non-featured historical
    for m in matches:
        if not m.get("featured") and m.get("ball_count", 0) > 30:
            return m["match_id"]
    return matches[0]["match_id"]


def test_matches_list(s):
    r = s.get(f"{BASE_URL}/api/matches?limit=5", timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list) and len(data) > 0


@pytest.mark.parametrize("match_id", ["1535465", "1359487"])
def test_state_ball_id_format(s, match_id):
    r = s.get(f"{BASE_URL}/api/matches/{match_id}/state", timeout=30)
    assert r.status_code == 200, r.text
    state = r.json()
    latest = state.get("latest_ball_id")
    assert latest, f"latest_ball_id missing: {state}"
    assert BALL_ID_RE.match(latest), f"latest_ball_id wrong format: {latest}"
    momentum = state.get("momentum", [])
    assert len(momentum) > 0
    last_mom = momentum[-1]["ball_id"]
    assert BALL_ID_RE.match(last_mom), f"momentum ball_id wrong format: {last_mom}"
    assert last_mom == latest, f"momentum last != latest_ball_id ({last_mom} vs {latest})"


@pytest.mark.parametrize("match_id", ["1535465", "1359487"])
def test_rating_breakdown_with_and_without_ball(s, match_id):
    # Get state to fetch a real player_id and latest_ball_id
    st = s.get(f"{BASE_URL}/api/matches/{match_id}/state", timeout=30).json()
    assert st["top_impact"], "No top_impact players"
    player_id = st["top_impact"][0]["player_id"]
    latest_ball_id = st["latest_ball_id"]

    # With valid at_ball_id
    r = s.get(f"{BASE_URL}/api/ratings/{match_id}/{player_id}",
              params={"at_ball_id": latest_ball_id}, timeout=30)
    assert r.status_code == 200, f"Failed for valid ball: {r.status_code} {r.text}"
    data = r.json()
    assert data["player_id"] == player_id
    assert "player_name" in data
    assert "components" in data
    assert "final_rating" in data

    # Without at_ball_id (latest)
    r2 = s.get(f"{BASE_URL}/api/ratings/{match_id}/{player_id}", timeout=30)
    assert r2.status_code == 200
    assert r2.json()["final_rating"] is not None

    # Nonsense at_ball_id — should fall back to latest, NOT 404
    r3 = s.get(f"{BASE_URL}/api/ratings/{match_id}/{player_id}",
               params={"at_ball_id": "xxxxx"}, timeout=30)
    assert r3.status_code == 200, f"Fallback failed: {r3.status_code} {r3.text}"
    assert r3.json()["player_id"] == player_id


def test_historical_match_state_renders(s):
    match_id = "1535465"
    r = s.get(f"{BASE_URL}/api/matches/{match_id}/state", timeout=30)
    assert r.status_code == 200
    st = r.json()
    assert st.get("momentum") and len(st["momentum"]) > 0
    assert st.get("top_impact") and len(st["top_impact"]) > 0
