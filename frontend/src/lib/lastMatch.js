/**
 * Last-viewed-match persistence.
 *
 * Persists the most recently opened match so revisiting `/` can resume where
 * the user left off. Deliberately localStorage-only (anonymous MVP, no auth).
 * We also cache a lightweight preview (teams, date, curation title) so the
 * empty-state "Continue" button can render without an extra API round-trip.
 */
const KEY = "pitchwise:lastMatch:v1";

export function readLastMatch() {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (!parsed?.match_id) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function saveLastMatch(match) {
  if (!match?.match_id) return;
  try {
    const preview = {
      match_id: match.match_id,
      teams: match.teams || [],
      team_short: match.team_short || [],
      season: match.season || "",
      date: match.date || "",
      venue: match.venue || "",
      curation_title: match.curation_title || null,
      result_summary: match.result_summary || null,
      saved_at: new Date().toISOString(),
    };
    localStorage.setItem(KEY, JSON.stringify(preview));
  } catch {
    /* storage disabled — silent */
  }
}

export function clearLastMatch() {
  try { localStorage.removeItem(KEY); } catch { /* ignore */ }
}
