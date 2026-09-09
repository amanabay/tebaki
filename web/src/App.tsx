import { createContext, useContext, useEffect, useState } from "react";
import { Link, NavLink, Route, Routes, useLocation } from "react-router-dom";
import { Moon, Sun } from "lucide-react";
import { Dashboard } from "@/pages/Dashboard";
import { Decisions } from "@/pages/Decisions";
import { Report } from "@/pages/Report";
import { CaseFilePage } from "@/pages/CaseFile";
import { Watchlist } from "@/pages/Watchlist";
import { Stats } from "@/pages/Stats";
import { useEngineData } from "@/lib/useEngineData";
import { useTheme } from "@/lib/theme";

function GuardianMark({ className = "size-5" }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden="true">
      <path d="M16 5 L27 16 L16 27 L5 16 Z" fill="none" stroke="currentColor" strokeWidth="2" />
      <circle cx="16" cy="16" r="4" fill="currentColor" />
      <circle cx="16" cy="16" r="1.6" fill="var(--background)" />
    </svg>
  );
}

interface NavItem {
  to: string;
  label: string;
}

const PRIMARY_TABS: NavItem[] = [
  { to: "/", label: "Map" },
  { to: "/ledger", label: "Ledger" },
  { to: "/watch", label: "Watch" },
  { to: "/stats", label: "Stats" },
];

const ACTION_TABS: NavItem[] = [
  { to: "/report", label: "Report" },
  { to: "/decisions", label: "Decisions" },
];

function isTabActive(pathname: string, to: string): boolean {
  if (to === "/") return pathname === "/" ;
  if (to === "/ledger") return pathname.startsWith("/ledger") || pathname.startsWith("/case");
  return pathname.startsWith(to);
}

function ThemeToggle() {
  const { theme, toggle } = useTheme();
  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={theme === "light" ? "Switch to dark mode" : "Switch to light mode"}
      className="flex size-8 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-surface-2 hover:text-foreground"
    >
      {theme === "light" ? <Moon className="size-4" /> : <Sun className="size-4" />}
    </button>
  );
}

function Masthead({ pending, online }: { pending: number; online: boolean | null }) {
  const location = useLocation();
  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background/95 backdrop-blur-sm">
      {/* the amber line */}
      <div className="h-0.5 bg-primary" aria-hidden="true" />
      <div className="mx-auto max-w-6xl items-center px-4 py-3">
        <div className="flex items-center justify-between gap-4">
          <Link to="/" className="group flex items-baseline gap-3" aria-label="Tebaki home">
            <GuardianMark className="size-5 shrink-0 self-center text-primary transition-transform group-hover:rotate-45" />
            <span className="font-serif text-lg font-bold tracking-[0.08em]">TEBAKI</span>
            <span lang="am" className="font-ethiopic text-lg leading-none text-primary">
              ጠባቂ
            </span>
            <span className="micro-label hidden sm:inline">the city's guardian</span>
          </Link>
          <div className="flex items-center gap-1">
            <span className="mr-2 hidden items-center gap-1.5 md:flex" title={online === false ? "The guardian's engine is unreachable" : "The engine is reachable"}>
              {online === false ? (
                <span className="inline-flex size-2 rounded-full bg-border" aria-hidden="true" />
              ) : (
                <span className="relative flex size-2" aria-hidden="true">
                  <span className="absolute inline-flex h-full w-full motion-safe:animate-ping rounded-full bg-primary opacity-60" />
                  <span className="relative inline-flex size-2 rounded-full bg-primary" />
                </span>
              )}
              <span className="micro-label">{online === false ? "off watch" : "on watch"}</span>
            </span>
            <ThemeToggle />
          </div>
        </div>
        {/* file-folder tabs */}
        <nav className="mt-2 flex items-end gap-0" aria-label="Primary">
          {PRIMARY_TABS.map((tab) => {
            const active = isTabActive(location.pathname, tab.to);
            return (
              <Link
                key={tab.to}
                to={tab.to}
                aria-current={active ? "page" : undefined}
                className={
                  "-mb-3 rounded-t-md border border-b-0 px-3.5 py-1.5 text-sm transition-colors " +
                  (active
                    ? "border-border bg-surface-1 font-medium text-foreground"
                    : "border-transparent text-muted-foreground hover:bg-surface-2/60 hover:text-foreground")
                }
              >
                {tab.label}
              </Link>
            );
          })}
          <div className="flex-1 border-b border-border" aria-hidden="true" />
          {ACTION_TABS.map((tab) => {
            const active = isTabActive(location.pathname, tab.to);
            return (
              <Link
                key={tab.to}
                to={tab.to}
                aria-current={active ? "page" : undefined}
                className={
                  "relative -mb-3 flex items-center gap-2 rounded-t-md border border-b-0 px-3.5 py-1.5 text-sm transition-colors " +
                  (active
                    ? "border-border bg-surface-1 font-medium text-foreground"
                    : "border-transparent text-muted-foreground hover:bg-surface-2/60 hover:text-foreground")
                }
              >
                {tab.label}
                {tab.to === "/decisions" && pending > 0 && (
                  <span className="num flex min-w-4.5 items-center justify-center rounded-full bg-primary px-1 text-[10px] font-bold text-primary-foreground">
                    {pending}
                  </span>
                )}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}

function MobileBar({ pending }: { pending: number }) {
  const tabs = [...PRIMARY_TABS, ...ACTION_TABS];
  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-40 border-t border-border bg-background/95 backdrop-blur-sm md:hidden"
      aria-label="Primary"
    >
      <div className="grid grid-cols-6">
        {tabs.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            className={({ isActive }) =>
              "flex flex-col items-center gap-0.5 py-2 text-[11px] " +
              (isActive ? "text-primary" : "text-muted-foreground")
            }
          >
            <span className="relative">
              {tab.label}
              {tab.to === "/decisions" && pending > 0 && (
                <span className="num absolute -top-1.5 -right-2 flex size-4 items-center justify-center rounded-full bg-primary text-[9px] font-bold text-primary-foreground">
                  {pending}
                </span>
              )}
            </span>
          </NavLink>
        ))}
      </div>
    </nav>
  );
}

function NotFound() {
  return (
    <div className="mx-auto max-w-md py-20 text-center">
      <GuardianMark className="mx-auto size-10 text-primary" />
      <h1 className="mt-4 font-serif text-2xl font-semibold">Nothing on file here.</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        This page doesn't exist — the archive keeps to the map, the ledger, the watchlist, and
        the decision desk.
      </p>
      <Link to="/" className="mt-4 inline-block text-sm text-primary underline-offset-4 hover:underline">
        Back to the map
      </Link>
    </div>
  );
}

interface AppData {
  pending: number;
  online: boolean | null;
}

const AppContext = createContext<AppData>({ pending: 0, online: null });
export const useAppData = () => useContext(AppContext);

export default function App() {
  const engine = useEngineData();
  const pending = engine.decisions.length;
  // announce decision arrivals politely
  const [announced, setAnnounced] = useState(0);
  useEffect(() => {
    if (pending > announced) {
      setAnnounced(pending);
    } else {
      setAnnounced(pending);
    }
  }, [pending, announced]);

  return (
    <AppContext.Provider value={{ pending, online: engine.online }}>
      <div className="flex min-h-dvh flex-col bg-background">
        <Masthead pending={pending} online={engine.online} />
        {/* polite live region: new decision cards announce themselves */}
        <div role="status" aria-live="polite" className="sr-only">
          {pending > 0
            ? `${pending} filing decision${pending === 1 ? "" : "s"} waiting for approval`
            : ""}
        </div>
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 pt-6 pb-24 md:pb-8">
          <Routes>
            <Route path="/" element={<Dashboard data={engine} />} />
            <Route path="/ledger" element={<Dashboard data={engine} initialView="ledger" />} />
            <Route path="/report" element={<Report />} />
            <Route path="/decisions" element={<Decisions data={engine} />} />
            <Route path="/case/:complaintId" element={<CaseFilePage />} />
            <Route path="/watch" element={<Watchlist data={engine} />} />
            <Route path="/stats" element={<Stats data={engine} />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </main>
        <footer className="mt-12 border-t border-border py-6 pb-20 md:pb-6">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-2 px-4">
            <span className="micro-label">
              Tebaki <span lang="am">ጠባቂ</span> — files, tracks &amp; escalates so you don't have
              to
            </span>
            <span className="micro-label num">any city is a pull request</span>
          </div>
        </footer>
        <MobileBar pending={pending} />
      </div>
    </AppContext.Provider>
  );
}
