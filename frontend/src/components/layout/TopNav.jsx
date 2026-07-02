import { NavLink, Link } from "react-router-dom";
import { Command } from "lucide-react";

const links = [
  { to: "/", label: "Live", testId: "nav-live", end: true },
  { to: "/time-machine", label: "Time Machine", testId: "nav-time-machine" },
  { to: "/players", label: "Players", testId: "nav-players" },
  { to: "/about", label: "About", testId: "nav-about" },
];

export default function TopNav() {
  return (
    <header
      data-testid="top-nav"
      className="fixed top-0 inset-x-0 z-40 glass border-b border-border/40"
    >
      <div className="max-w-[1400px] mx-auto px-6 h-16 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2" data-testid="nav-logo">
          <div className="h-6 w-6 rounded-sm bg-amber-soft border border-amber-soft flex items-center justify-center">
            <span className="rating-num text-[11px] font-semibold" style={{ color: 'hsl(var(--primary))' }}>PW</span>
          </div>
          <span className="font-editorial text-lg tracking-tight">PitchWise</span>
          <span className="text-dim text-[11px] uppercase tracking-widest ml-2 hidden sm:inline">
            Cricket, explained
          </span>
        </Link>

        <nav className="hidden md:flex items-center gap-1">
          {links.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.end}
              data-testid={l.testId}
              className={({ isActive }) =>
                `px-3 py-1.5 text-sm rounded-md transition-colors ${
                  isActive
                    ? "text-foreground bg-secondary"
                    : "text-muted-foreground hover:text-foreground hover:bg-secondary/60"
                }`
              }
            >
              {l.label}
            </NavLink>
          ))}
        </nav>

        <button
          data-testid="ask-pitchwise-btn"
          className="flex items-center gap-2 px-3 py-1.5 rounded-md border border-border/60 text-sm text-muted-foreground hover:text-foreground hover:border-amber-soft transition-colors"
          onClick={() => { /* stub — wired in later milestone */ }}
        >
          <span className="hidden sm:inline">Ask PitchWise</span>
          <span className="text-dim rating-num text-[11px] flex items-center gap-0.5">
            <Command className="w-3 h-3" /> K
          </span>
        </button>
      </div>
    </header>
  );
}
