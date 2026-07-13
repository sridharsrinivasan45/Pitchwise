"""Backend regression tests for Live-page refactor (iter 9).

Focus:
  - Matches list works (needed for frontend match resolution)
  - Match by id endpoint + moments + skip-to-death work for arbitrary match ids
  - No hardcoded Rinku narration for over-19 sixes on non-Rinku matches
  - Career rating regressions for Kohli/Bumrah
"""
import os
import json
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://ball-genius.preview.emergentagent.com").rstrip("/")


@pytest.fixture(scope="module")
def match_ids():
    r = requests.get(f"{BASE_URL}/api/matches?limit=5", timeout=20)
    assert r.status_code == 200
    data = r.json()
    matches = data["matches"] if isinstance(data, dict) else data
    assert len(matches) >= 2
    return [m["match_id"] for m in matches]


def test_matches_list_ok():
    r = requests.get(f"{BASE_URL}/api/matches?limit=5", timeout=20)
    assert r.status_code == 200
    data = r.json()
    matches = data["matches"] if isinstance(data, dict) else data
    assert isinstance(matches, list) and len(matches) > 0
    m = matches[0]
    for k in ("match_id", "teams", "team_short", "date", "venue"):
        assert k in m, f"missing key {k}"


def test_match_detail_endpoints(match_ids):
    mid = match_ids[0]
    m = requests.get(f"{BASE_URL}/api/matches/{mid}", timeout=20)
    assert m.status_code == 200, m.text
    body = m.json()
    assert body["match_id"] == mid

    mm = requests.get(f"{BASE_URL}/api/matches/{mid}/moments?limit=12", timeout=20)
    assert mm.status_code == 200
    assert isinstance(mm.json() if isinstance(mm.json(), list) else mm.json().get("moments", []), (list, dict))

    sk = requests.get(f"{BASE_URL}/api/matches/{mid}/skip_to_death", timeout=20)
    assert sk.status_code in (200, 404)


def test_narration_no_rinku_hardcoding():
    """The old hardcoded 'SIX at O20 ... Rinku' branch must be gone. Read the file directly."""
    path = "/app/backend/routes/stream.py"
    with open(path) as f:
        src = f.read()
    assert "Rinku" not in src, "stream.py must not hardcode Rinku narration"
    # And no over==19 hardcoded string branch
    assert "over'] == 19" not in src and "over']==19" not in src


def test_kohli_career_rating():
    r = requests.get(f"{BASE_URL}/api/players?search=Kohli", timeout=30)
    assert r.status_code == 200
    data = r.json()
    players = data["players"] if isinstance(data, dict) else data
    kohli = next((p for p in players if "V Kohli" == p.get("name") or "V Kohli" == p.get("player_name")), None)
    assert kohli, "V Kohli should be findable"
    rating = kohli.get("career_rating")
    assert rating is not None
    assert 6.3 <= rating <= 6.9, f"Kohli career_rating ~6.6 expected, got {rating}"


def test_bumrah_career_rating():
    r = requests.get(f"{BASE_URL}/api/players?search=Bumrah", timeout=30)
    assert r.status_code == 200
    data = r.json()
    players = data["players"] if isinstance(data, dict) else data
    bumrah = next((p for p in players if "Bumrah" in (p.get("name") or p.get("player_name") or "")), None)
    assert bumrah, "Bumrah should be findable"
    rating = bumrah.get("career_rating")
    assert rating is not None
    assert 8.2 <= rating <= 8.8, f"Bumrah career_rating ~8.5 expected, got {rating}"


def test_player_detail_has_career_avg_rating():
    r = requests.get(f"{BASE_URL}/api/players?search=Kohli", timeout=30)
    players = r.json()
    players = players["players"] if isinstance(players, dict) else players
    kohli = next(p for p in players if "V Kohli" == (p.get("name") or p.get("player_name")))
    pid = kohli["player_id"]
    d = requests.get(f"{BASE_URL}/api/players/{pid}", timeout=30)
    assert d.status_code == 200
    body = d.json()
    career = body.get("career") or {}
    assert career.get("avg_rating") is not None
