import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Search, Filter, X } from "lucide-react";
import { fetchMatches, fetchMatchFacets } from "@/lib/api";

const SORT_OPTIONS = [
  { key: "newest", label: "Newest" },
  { key: "oldest", label: "Oldest" },
  { key: "impact", label: "Highest Impact" },
];

function MatchCard({ m, onClick, featured = false }) {
  return (
    <button
      onClick={onClick}
      data-testid={`match-card-${m.match_id}`}
      className={`text-left rounded-xl border p-5 transition-colors bg-card hover:border-amber-soft w-full ${
        featured ? "border-amber-soft" : "border-border/60"
      }`}
    >
      <div className="flex items-center gap-2 mb-2 flex-wrap">
        {featured && (
          <span className="text-[10px] uppercase tracking-widest px-2 py-0.5 rounded-sm bg-amber-soft border border-amber-soft"
            style={{ color: "hsl(var(--primary))" }}>
            Featured
          </span>
        )}
        <span className="rating-num text-xs text-dim">{m.season}</span>
        <span className="text-dim">·</span>
        <span className="rating-num text-xs text-dim">{m.date}</span>
        {m.has_super_over && <span className="text-[9px] uppercase tracking-widest text-dim">Super Over</span>}
        {m.has_dls && <span className="text-[9px] uppercase tracking-widest text-dim">DLS</span>}
      </div>
      <h3 className="font-editorial text-xl mb-1 leading-tight">
        {m.curation_title || `${m.team_short.join(" vs ")}`}
      </h3>
      {m.curation_hook && <p className="text-muted-foreground text-sm mb-3">{m.curation_hook}</p>}
      <div className="flex items-center justify-between text-sm mt-2">
        <span className="rating-num text-dim">{m.venue?.split(",")[0] || m.city || "—"}</span>
        <div className="flex items-center gap-2">
          {m.total_impact > 0 && (
            <span className="rating-num text-xs text-dim">
              impact <span style={{ color: "hsl(var(--primary))" }}>{m.total_impact.toFixed(1)}</span>
            </span>
          )}
          <span className="text-positive text-xs">{m.result_summary}</span>
        </div>
      </div>
    </button>
  );
}

export default function TimeMachine() {
  const nav = useNavigate();
  const [featuredList, setFeaturedList] = useState([]);
  const [matches, setMatches] = useState([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [facets, setFacets] = useState({ seasons: [], teams: [] });
  const [search, setSearch] = useState("");
  const [season, setSeason] = useState("");
  const [team, setTeam] = useState("");
  const [sort, setSort] = useState("newest");
  const [offset, setOffset] = useState(0);
  const LIMIT = 30;

  useEffect(() => {
    (async () => {
      const f = await fetchMatches({ featured: true });
      setFeaturedList(f.matches || []);
      const fa = await fetchMatchFacets();
      setFacets(fa);
    })();
  }, []);

  useEffect(() => {
    setLoading(true);
    fetchMatches({ search, season, team, sort, limit: LIMIT, offset })
      .then((d) => { setMatches(d.matches); setTotal(d.total); })
      .finally(() => setLoading(false));
  }, [search, season, team, sort, offset]);

  const clearFilters = () => { setSearch(""); setSeason(""); setTeam(""); setSort("newest"); setOffset(0); };
  const anyFilter = search || season || team || sort !== "newest";
  const openMatch = (id) => nav(`/?match_id=${id}`);

  return (
    <div className="max-w-[1400px] mx-auto px-6 py-10" data-testid="time-machine-page">
      <p className="text-dim text-[11px] uppercase tracking-widest mb-3">Time Machine</p>
      <h1 className="font-editorial text-4xl md:text-5xl leading-tight mb-3">
        {total.toLocaleString()} IPL matches. Every one, replayable.
      </h1>
      <p className="text-muted-foreground max-w-2xl mb-8">
        Search 19 seasons of ball-by-ball IPL history. Every match plays back with live-evolving ratings.
      </p>

      {/* Featured strip */}
      {featuredList.length > 0 && (
        <section className="mb-10" data-testid="featured-strip">
          <p className="text-[10px] uppercase tracking-widest text-dim mb-3">Featured</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {featuredList.map((m) => (
              <MatchCard key={m.match_id} m={m} featured onClick={() => openMatch(m.match_id)} />
            ))}
          </div>
        </section>
      )}

      {/* Filters */}
      <section className="mb-6 rounded-xl border border-border/60 bg-card/40 p-4 flex flex-wrap items-center gap-3" data-testid="filters">
        <div className="relative flex-1 min-w-[240px]">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-dim" />
          <input
            value={search}
            onChange={(e) => { setSearch(e.target.value); setOffset(0); }}
            placeholder="Search team, venue, city..."
            data-testid="matches-search"
            className="w-full bg-secondary/60 border border-border/60 rounded-md pl-9 pr-3 py-2 text-sm placeholder:text-dim focus:outline-none focus:border-amber-soft"
          />
        </div>
        <select value={season} onChange={(e) => { setSeason(e.target.value); setOffset(0); }}
          data-testid="filter-season"
          className="bg-secondary/60 border border-border/60 rounded-md px-3 py-2 text-sm">
          <option value="">All seasons</option>
          {facets.seasons.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <select value={team} onChange={(e) => { setTeam(e.target.value); setOffset(0); }}
          data-testid="filter-team"
          className="bg-secondary/60 border border-border/60 rounded-md px-3 py-2 text-sm">
          <option value="">All teams</option>
          {facets.teams.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <div className="flex items-center gap-1 ml-auto">
          <Filter className="w-3 h-3 text-dim" />
          {SORT_OPTIONS.map((o) => (
            <button key={o.key} onClick={() => { setSort(o.key); setOffset(0); }}
              data-testid={`sort-${o.key}`}
              className={`px-2.5 py-1 rounded-md text-xs transition-colors ${
                sort === o.key ? "text-foreground bg-secondary border border-amber-soft" : "text-dim hover:text-foreground"
              }`}>
              {o.label}
            </button>
          ))}
        </div>
        {anyFilter && (
          <button onClick={clearFilters} data-testid="clear-filters"
            className="flex items-center gap-1 text-xs text-dim hover:text-foreground">
            <X className="w-3 h-3" /> Clear
          </button>
        )}
      </section>

      {/* Results summary */}
      <div className="flex items-baseline justify-between mb-4">
        <p className="text-sm text-muted-foreground rating-num">
          {loading ? "loading…" : `${total.toLocaleString()} match${total === 1 ? "" : "es"}`}
        </p>
        {total > LIMIT && (
          <div className="flex items-center gap-2 text-xs">
            <button
              onClick={() => setOffset(Math.max(0, offset - LIMIT))}
              disabled={offset === 0}
              data-testid="page-prev"
              className="px-2 py-1 rounded-md border border-border/60 disabled:opacity-30">← Prev</button>
            <span className="text-dim rating-num">
              {offset + 1}–{Math.min(offset + LIMIT, total)}
            </span>
            <button
              onClick={() => setOffset(offset + LIMIT)}
              disabled={offset + LIMIT >= total}
              data-testid="page-next"
              className="px-2 py-1 rounded-md border border-border/60 disabled:opacity-30">Next →</button>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4" data-testid="matches-grid">
        {matches.map((m) => (
          <MatchCard key={m.match_id} m={m} onClick={() => openMatch(m.match_id)} />
        ))}
        {!loading && matches.length === 0 && (
          <div className="col-span-full text-dim text-sm text-center py-12">
            No matches found. Try clearing filters.
          </div>
        )}
      </div>
    </div>
  );
}
