import { NavLink, Link } from "react-router-dom";
import { Command, Play, Clock3, Users, Info } from "lucide-react";

const links = [
  { to: "/", label: "Live", testId: "nav-live", end: true, icon: Play },
  { to: "/time-machine", label: "Time Machine", testId: "nav-time-machine", icon: Clock3, mobileShort: "Machine" },
  { to: "/players", label: "Players", testId: "nav-players", icon: Users },
  { to: "/about", label: "About", testId: "nav-about", icon: Info },
];

export default function TopNav() {
  return (
    <>
      <header
        data-testid="top-nav"
        className="fixed top-0 inset-x-0 z-40 glass border-b border-border/40"
      >
        <div className="max-w-[1400px] mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2" data-testid="nav-logo">
            <div className="h-6 w-6 rounded-sm bg-amber-soft border border-amber-soft flex items-center justify-center">
              <span className="rating-num text-[11px] font-semibold" style={{ color: 'hsl(var(--primary))' }}>PW</span>
            </div>
            <span className="font-editorial text-lg tracking-tight">PitchWise</span>
            <span className="text-dim text-[11px] uppercase tracking-widest ml-2 hidden lg:inline">
              Cricket, explained
            </span>
          </Link>

          <nav className="hidden md:flex items-center gap-1" aria-label="Primary">
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
            aria-label="Ask PitchWise (coming soon)"
            title="Coming soon"
            disabled
            className="flex items-center gap-2 px-3 py-1.5 rounded-md border border-border/60 text-sm text-muted-foreground/70 cursor-not-allowed opacity-70"
          >
            <span className="hidden sm:inline">Ask PitchWise</span>
            <span className="hidden md:inline text-[10px] uppercase tracking-widest text-dim">Soon</span>
            <span className="text-dim rating-num text-[11px] flex items-center gap-0.5">
              <Command className="w-3 h-3" aria-hidden="true" /> K
            </span>
          </button>
        </div>
      </header>

      {/* Mobile bottom nav — thumb-reachable, primary navigation on phones */}
      <nav
        data-testid="bottom-nav"
        aria-label="Primary mobile"
        className="fixed bottom-0 inset-x-0 z-40 glass border-t border-border/40 md:hidden"
      >
        <ul className="grid grid-cols-4 h-16">
          {links.map((l) => (
            <li key={l.to} className="contents">
              <NavLink
                to={l.to}
                end={l.end}
                data-testid={`bottom-${l.testId}`}
                className={({ isActive }) =>
                  `flex flex-col items-center justify-center gap-1 text-[10px] uppercase tracking-widest transition-colors ${
                    isActive
                      ? "text-foreground"
                      : "text-muted-foreground hover:text-foreground"
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    <l.icon className="w-4 h-4" aria-hidden="true"
                      style={isActive ? { color: "hsl(var(--primary))" } : {}} />
                    <span>{l.mobileShort || l.label}</span>
                  </>
                )}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
    </>
  );
}
