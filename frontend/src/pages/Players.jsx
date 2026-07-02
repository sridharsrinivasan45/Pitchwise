import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Search, X } from "lucide-react";
import { fetchPlayers, fetchMatchFacets } from "@/lib/api";
import RatingBadge from "@/components/rating/RatingBadge";

const ROLES = [{ k: "", l: "All" }, { k: "batter", l: "Batters" }, { k: "bowler", l: "Bowlers" }, { k: "allrounder", l: "Allrounders" }];
const SORTS = [{ k: "rating", l: "Top rated" }, { k: "matches", l: "Most matches" }, { k: "name", l: "A → Z" }];

export default function Players() {
  const nav = useNavigate();
  const [players, setPlayers] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [teams, setTeams] = useState([]);
  const [search, setSearch] = useState("");
  const [team, setTeam] = useState("");
  const [role, setRole] = useState("");
  const [sort, setSort] = useState("rating");
  const [offset, setOffset] = useState(0);
  const LIMIT = 60;

  useEffect(() => { fetchMatchFacets().then((f) => setTeams(f.teams || [])); }, []);
  useEffect(() => {
    setLoading(true);
    fetchPlayers({ search, team, role, sort, limit: LIMIT, offset })
      .then((d) => { setPlayers(d.players); setTotal(d.total); })
      .finally(() => setLoading(false));
  }, [search, team, role, sort, offset]);

  const anyFilter = search || team || role || sort !== "rating";

  return (
    <div className="max-w-[1400px] mx-auto px-6 py-10" data-testid="players-page">
      <p className="text-dim text-[11px] uppercase tracking-widest mb-3">Players</p>
      <h1 className="font-editorial text-4xl md:text-5xl leading-tight mb-3">
        {total.toLocaleString()} careers, one impact scale.
      </h1>
      <p className="text-muted-foreground max-w-2xl mb-8">
        Every player rated by their real match impact — not by strike rate or averages.
      </p>

      <section className="mb-6 rounded-xl border border-border/60 bg-card/40 p-4 flex flex-wrap items-center gap-3" data-testid="players-filters">
        <div className="relative flex-1 min-w-[240px]">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-dim" />
          <input
            value={search}
            onChange={(e) => { setSearch(e.target.value); setOffset(0); }}
            placeholder="Search players..."
            data-testid="players-search"
            className="w-full bg-secondary/60 border border-border/60 rounded-md pl-9 pr-3 py-2 text-sm placeholder:text-dim focus:outline-none focus:border-amber-soft"
          />
        </div>
        <select value={team} onChange={(e) => { setTeam(e.target.value); setOffset(0); }}
          data-testid="players-filter-team"
          className="bg-secondary/60 border border-border/60 rounded-md px-3 py-2 text-sm">
          <option value="">Any team</option>
          {teams.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <div className="flex items-center gap-1">
          {ROLES.map((r) => (
            <button key={r.k} onClick={() => { setRole(r.k); setOffset(0); }}
              data-testid={`players-role-${r.k || 'all'}`}
              className={`px-2.5 py-1 rounded-md text-xs transition-colors ${
                role === r.k ? "text-foreground bg-secondary border border-amber-soft" : "text-dim hover:text-foreground"
              }`}>{r.l}</button>
          ))}
        </div>
        <div className="flex items-center gap-1 ml-auto">
          {SORTS.map((s) => (
            <button key={s.k} onClick={() => { setSort(s.k); setOffset(0); }}
              data-testid={`players-sort-${s.k}`}
              className={`px-2.5 py-1 rounded-md text-xs transition-colors ${
                sort === s.k ? "text-foreground bg-secondary border border-amber-soft" : "text-dim hover:text-foreground"
              }`}>{s.l}</button>
          ))}
        </div>
        {anyFilter && (
          <button onClick={() => { setSearch(""); setTeam(""); setRole(""); setSort("rating"); setOffset(0); }}
            data-testid="players-clear" className="flex items-center gap-1 text-xs text-dim hover:text-foreground">
            <X className="w-3 h-3" /> Clear
          </button>
        )}
      </section>

      <div className="flex items-baseline justify-between mb-4 text-sm">
        <p className="text-muted-foreground rating-num">{loading ? "loading…" : `${total.toLocaleString()} players`}</p>
        {total > LIMIT && (
          <div className="flex items-center gap-2 text-xs">
            <button onClick={() => setOffset(Math.max(0, offset - LIMIT))} disabled={offset === 0}
              data-testid="players-page-prev" className="px-2 py-1 rounded-md border border-border/60 disabled:opacity-30">← Prev</button>
            <span className="text-dim rating-num">{offset + 1}–{Math.min(offset + LIMIT, total)}</span>
            <button onClick={() => setOffset(offset + LIMIT)} disabled={offset + LIMIT >= total}
              data-testid="players-page-next" className="px-2 py-1 rounded-md border border-border/60 disabled:opacity-30">Next →</button>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3" data-testid="players-grid">
        {players.map((p) => (
          <button key={p.player_id}
            onClick={() => nav(`/players/${p.player_id}`)}
            data-testid={`player-card-${p.player_id}`}
            className="text-left rounded-lg border border-border/60 bg-card p-4 flex items-center justify-between gap-4 hover:border-amber-soft transition-colors">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-[10px] uppercase tracking-widest text-dim rating-num">{p.team_short}</span>
                <span className="text-dim">·</span>
                <span className="text-[10px] uppercase tracking-widest text-dim">{p.role}</span>
              </div>
              <p className="font-editorial text-lg leading-tight truncate">{p.display_name}</p>
              <p className="mt-1 text-xs text-dim rating-num">
                {p.matches} matches · {p.runs > 0 && `${p.runs} runs`}{p.runs > 0 && p.wickets > 0 && " · "}{p.wickets > 0 && `${p.wickets} wkts`}
              </p>
            </div>
            <RatingBadge rating={p.career_rating} delta={0} size="sm" showDelta={false} testId={`player-rating-${p.player_id}`} />
          </button>
        ))}
        {!loading && players.length === 0 && (
          <div className="col-span-full text-dim text-sm text-center py-12">
            No players found.
          </div>
        )}
      </div>
    </div>
  );
}
