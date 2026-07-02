import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API_BASE = `${BACKEND_URL}/api`;

export const api = axios.create({
  baseURL: API_BASE,
  timeout: 20000,
});

export async function fetchHealth() {
  const { data } = await api.get("/health");
  return data;
}

export async function fetchMatches({ featured = false, search = "", season = "", team = "", sort = "newest", limit = 50, offset = 0 } = {}) {
  const params = { featured, search, season, team, sort, limit, offset };
  const { data } = await api.get(`/matches`, { params });
  return data;
}

export async function fetchMatchFacets() {
  const { data } = await api.get(`/matches/facets`);
  return data;
}

export async function fetchPlayers({ search = "", team = "", role = "", sort = "rating", limit = 60, offset = 0 } = {}) {
  const { data } = await api.get(`/players`, { params: { search, team, role, sort, limit, offset } });
  return data;
}

export async function fetchPlayerProfile(playerId) {
  const { data } = await api.get(`/players/${playerId}`);
  return data;
}

export async function fetchSkipToDeath(matchId) {
  const { data } = await api.get(`/matches/${matchId}/skip-to-death`);
  return data;
}

export async function fetchMatch(matchId) {
  const { data } = await api.get(`/matches/${matchId}`);
  return data;
}

export async function fetchMatchState(matchId, atBall) {
  const params = atBall != null ? { at_ball: atBall } : {};
  const { data } = await api.get(`/matches/${matchId}/state`, { params });
  return data;
}

export async function fetchMoments(matchId, topN = 5) {
  const { data } = await api.get(`/matches/${matchId}/moments`, { params: { top_n: topN } });
  return data.moments;
}

export async function fetchRatingBreakdown(matchId, playerId, atBallId) {
  const params = atBallId ? { at_ball_id: atBallId } : {};
  const { data } = await api.get(`/ratings/${matchId}/${playerId}`, { params });
  return data;
}
