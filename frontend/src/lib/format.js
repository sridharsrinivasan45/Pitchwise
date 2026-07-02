// Small formatting helpers used across PitchWise UI

export function formatOver(over, ball) {
  // over is 0-indexed internally; display as 1-indexed
  return `${(over ?? 0) + 1}.${ball ?? 1}`;
}

export function formatDelta(delta) {
  if (delta == null || delta === 0) return "—";
  const sign = delta > 0 ? "+" : "";
  return `${sign}${delta.toFixed(2)}`;
}

export function deltaColorClass(delta) {
  if (delta == null || Math.abs(delta) < 0.01) return "text-dim";
  return delta > 0 ? "text-positive" : "text-negative";
}

export function ratingTone(rating) {
  if (rating == null) return "dim";
  if (rating >= 8.5) return "hot";
  if (rating >= 7.0) return "warm";
  if (rating >= 5.0) return "neutral";
  return "cold";
}

export function shortTeam(teamShort) {
  if (!teamShort || !Array.isArray(teamShort)) return "";
  return teamShort.join(" v ");
}

export function momentTypeLabel(type) {
  const map = {
    match_turning_point: "Match-turning point",
    wicket_key: "Key wicket",
    boundary_streak: "Boundary streak",
    milestone: "Milestone",
  };
  return map[type] || "Moment";
}
