"""M5 — Narrator (evidence-grounded explanation layer) tests."""
import os
import re
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://ball-genius.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

DEMO_MATCHES = ["1359487", "1359542", "1082591", "1535465", "1082596"]
ARCHETYPE_EXPECT = {
    "1359487": {"miracle_chase"},
    "1359542": {"runs_thriller"},
    "1535465": {"bowling_defence"},
    "1082596": {"bowling_defence", "one_sided"},
    "1178426": {"super_over"},
}
VALID_ARCHETYPES = {
    "miracle_chase", "super_over", "runs_thriller", "wickets_thriller",
    "one_sided", "bowling_defence", "batting_masterclass", "default",
}
BANNED = ["brilliant", "shocking", "thrilling", "the theft", "momentum killer",
          "genius", "poor", "terrible"]

NUM_RE = re.compile(r"[-+]?\d+\.?\d*")


def _numbers_in(s):
    return [float(x) for x in NUM_RE.findall(s or "")]


def _numbers_in_ev(ev):
    out = set()
    def walk(x):
        if isinstance(x, dict):
            [walk(v) for v in x.values()]
        elif isinstance(x, (list, tuple)):
            [walk(v) for v in x]
        elif isinstance(x, bool):
            return
        elif isinstance(x, (int, float)):
            out.add(float(x))
    walk(ev)
    for n in list(out):
        out.add(round(n * 100, 1))
        out.add(round(n * 100, 0))
    return out


def _fetch(match_id, refresh=False, polish=True):
    r = requests.get(
        f"{API}/matches/{match_id}/narration",
        params={"refresh": int(refresh), "polish": int(polish)},
        timeout=120,
    )
    return r


# ---------- Endpoint shape ----------
@pytest.mark.parametrize("mid", DEMO_MATCHES)
def test_narration_shape(mid):
    r = _fetch(mid, polish=False)
    assert r.status_code == 200, f"{mid} → {r.status_code} {r.text[:200]}"
    d = r.json()
    assert d["match_id"] == mid
    assert "context" in d and "teams_short" in d["context"] and "winner_short" in d["context"]
    assert "result_summary" in d["context"]
    v = d["verdict"]
    assert v["archetype"] in VALID_ARCHETYPES
    assert "sentence" in v and "polished" in v and "evidence" in v
    assert d["turning_point"] is None or {"sentence","polished","evidence"} <= set(d["turning_point"])
    assert isinstance(d["players"], list)
    for p in d["players"]:
        assert {"sentence","polished","evidence"} <= set(p)


# ---------- Archetype correctness ----------
@pytest.mark.parametrize("mid,expected", list(ARCHETYPE_EXPECT.items()))
def test_archetype(mid, expected):
    r = _fetch(mid, polish=False)
    if r.status_code == 404 and mid == "1178426":
        pytest.skip("1178426 super_over match not present in DB")
    assert r.status_code == 200, f"{mid} → {r.status_code}"
    a = r.json()["verdict"]["archetype"]
    assert a in expected, f"match {mid}: expected {expected}, got {a}"


# ---------- Grounding invariant ----------
@pytest.mark.parametrize("mid", ["1359487", "1359542", "1535465"])
def test_grounding_invariant(mid):
    r = _fetch(mid, polish=True)
    assert r.status_code == 200
    d = r.json()

    def check(entry, label):
        polished = entry.get("polished") or entry.get("sentence")
        ev = entry.get("evidence") or {}
        nums = _numbers_in(polished)
        ev_nums = _numbers_in_ev(ev)
        for n in nums:
            assert any(abs(n - e) < 0.15 for e in ev_nums), (
                f"[{mid}] {label}: number {n} not in evidence for polished='{polished}'"
            )

    check(d["verdict"], "verdict")
    if d.get("turning_point"):
        check(d["turning_point"], "turning_point")
    for p in d["players"]:
        check(p, f"player {p.get('evidence',{}).get('player_id')}")


# ---------- Banned wordlist ----------
@pytest.mark.parametrize("mid", ["1359487", "1359542", "1535465"])
def test_banned_words(mid):
    r = _fetch(mid, polish=True)
    assert r.status_code == 200
    d = r.json()
    all_sents = [d["verdict"].get("polished","")]
    if d.get("turning_point"): all_sents.append(d["turning_point"].get("polished",""))
    all_sents += [p.get("polished","") for p in d["players"]]
    for s in all_sents:
        low = s.lower()
        for b in BANNED:
            # Use word-boundary matching so proper nouns like "Pooran" don't false-positive on "poor"
            assert not re.search(rf"\b{re.escape(b)}\b", low), f"[{mid}] banned word '{b}' in: {s}"


# ---------- Cache behavior ----------
def test_cache_and_refresh():
    mid = "1359487"
    r1 = _fetch(mid, polish=True)
    assert r1.status_code == 200
    r2 = _fetch(mid, polish=True)
    assert r2.status_code == 200
    assert r1.json() == r2.json(), "second call should be cache-identical"
    r3 = _fetch(mid, refresh=True, polish=False)
    assert r3.status_code == 200
    assert r3.json()["verdict"]["polished"] == r3.json()["verdict"]["sentence"], "refresh polish=0 identity"


# ---------- Matches list left-join ----------
def test_matches_list_has_verdict_archetype():
    r = requests.get(f"{API}/matches", params={"limit": 30}, timeout=60)
    assert r.status_code == 200
    matches = r.json()["matches"]
    assert len(matches) > 0
    for m in matches:
        assert "verdict" in m
        assert "archetype" in m

def test_featured_has_cached_verdict():
    r = requests.get(f"{API}/matches", params={"featured": "true", "limit": 30}, timeout=60)
    assert r.status_code == 200
    matches = r.json()["matches"]
    # After we've hit /narration on 1359487, at least it should have a verdict cached
    m1 = next((m for m in matches if m["match_id"] == "1359487"), None)
    if m1:
        assert m1["verdict"], f"1359487 has no cached verdict on list: {m1}"
        assert m1["archetype"] == "miracle_chase"


# ---------- 1359487 specific content ----------
def test_1359487_content():
    r = _fetch("1359487", polish=False)
    assert r.status_code == 200
    d = r.json()
    v = d["verdict"]
    assert v["archetype"] == "miracle_chase"
    s = v["sentence"]
    assert "KKR" in s
    assert "1.2%" in s or "1.1%" in s or "1.3%" in s, f"expected ~1.2% in {s}"


def test_1359542_1_run():
    r = _fetch("1359542", polish=False)
    assert r.status_code == 200
    s = r.json()["verdict"]["sentence"]
    assert "1 run" in s or "1-run" in s


def test_1535465_bowling():
    r = _fetch("1535465", polish=False)
    assert r.status_code == 200
    d = r.json()
    assert d["verdict"]["archetype"] == "bowling_defence"
    s = d["verdict"]["sentence"].lower()
    assert "rcb" in s
    assert "bowling" in s or "bowlers" in s
