import { createContext, useContext, useEffect, useState } from "react";
import { Link, Route, Routes, useLocation } from "react-router-dom";
import {
  BarChart3,
  ClipboardCheck,
  Activity,
  Stethoscope,
  Eye,
  Files,
  Map as MapIcon,
  Moon,
  Plus,
  Sun,
} from "lucide-react";
import { Dashboard } from "@/pages/Dashboard";
import { Decisions } from "@/pages/Decisions";
import { Report } from "@/pages/Report";
import { CaseFilePage } from "@/pages/CaseFile";
import { Watchlist } from "@/pages/Watchlist";
import { Stats } from "@/pages/Stats";
import { Impact } from "@/pages/Impact";
import { Replay } from "@/pages/Replay";
import { Diagnostics } from "@/pages/Diagnostics";
import { useEngineData } from "@/lib/useEngineData";
import { useTheme } from "@/lib/theme";
import { useLanguage } from "@/lib/i18n";

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
  icon: typeof MapIcon;
}

const PRIMARY_TABS: NavItem[] = [
  { to: "/", label: "Map", icon: MapIcon },
  { to: "/ledger", label: "Ledger", icon: Files },
  { to: "/watch", label: "Watch", icon: Eye },
  { to: "/stats", label: "Stats", icon: BarChart3 },
  { to: "/impact", label: "Impact", icon: BarChart3 },
  { to: "/replay", label: "Replay", icon: Activity },
  { to: "/diagnostics", label: "System", icon: Stethoscope },
];

const ACTION_TABS: NavItem[] = [
  { to: "/report", label: "Report", icon: Plus },
  { to: "/decisions", label: "Decisions", icon: ClipboardCheck },
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
      className="flex size-10 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-surface-2 hover:text-foreground"
    >
      {theme === "light" ? <Moon className="size-4" /> : <Sun className="size-4" />}
    </button>
  );
}

function LanguageToggle() {
  const { language, setLanguage, t } = useLanguage();
  return (
    <button
      type="button"
      onClick={() => setLanguage(language === "en" ? "am" : "en")}
      aria-label={`Switch language to ${language === "en" ? "Amharic" : "English"}`}
      className="min-h-10 rounded-lg px-2.5 text-xs font-semibold text-muted-foreground transition-colors hover:bg-surface-2 hover:text-foreground"
    >
      {t("switchLanguage")}
    </button>
  );
}

function Masthead({ pending, online }: { pending: number; online: boolean | null }) {
  const location = useLocation();
  const { t } = useLanguage();
  return (
    <header className="sticky top-0 z-40 border-b border-border bg-surface-1/90 backdrop-blur-lg">
      <div className="mx-auto flex min-h-16 max-w-7xl items-center gap-5 px-4 sm:px-6">
        <Link to="/" className="group flex shrink-0 items-center gap-2.5" aria-label="Tebaki home">
          <span className="flex size-9 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-sm shadow-primary/20">
            <GuardianMark className="size-5 transition-transform duration-200 group-hover:rotate-45" />
          </span>
          <span>
            <span className="block text-[15px] font-extrabold leading-none tracking-[0.08em]">TEBAKI</span>
            <span className="mt-1 hidden text-[10px] font-medium leading-none text-muted-foreground xl:block">
              {t("guardian")}
            </span>
          </span>
        </Link>

        <nav className="hidden items-center gap-1 rounded-xl bg-surface-2 p-1 md:flex" aria-label="Primary">
          {PRIMARY_TABS.map((tab) => {
            const active = isTabActive(location.pathname, tab.to);
            const Icon = tab.icon;
            return (
              <Link
                key={tab.to}
                to={tab.to}
                aria-current={active ? "page" : undefined}
                className={
                  "flex min-h-9 items-center gap-2 rounded-lg px-3 text-sm font-medium transition-colors " +
                  (active
                    ? "bg-surface-1 text-foreground shadow-sm"
                    : "text-muted-foreground hover:bg-surface-1/60 hover:text-foreground")
                }
              >
                <Icon className="size-4" aria-hidden="true" />
                {t(tab.label.toLowerCase())}
              </Link>
            );
          })}
        </nav>

        <div className="ml-auto flex items-center gap-1.5">
            <span className="mr-2 hidden items-center gap-1.5 md:flex" title={online === false ? "The guardian's engine is unreachable" : "The engine is reachable"}>
              {online === false ? (
                <span className="inline-flex size-2 rounded-full bg-border" aria-hidden="true" />
              ) : (
                <span className="relative flex size-2" aria-hidden="true">
                  <span className="absolute inline-flex h-full w-full motion-safe:animate-ping rounded-full bg-primary opacity-60" />
                  <span className="relative inline-flex size-2 rounded-full bg-primary" />
                </span>
              )}
              <span className="text-[11px] font-semibold text-muted-foreground">
                {online === false ? "Engine offline" : "Agent online"}
              </span>
            </span>
            <Link
              to="/decisions"
              className={
                "relative hidden min-h-10 items-center gap-2 rounded-lg px-3 text-sm font-semibold transition-colors sm:flex " +
                (isTabActive(location.pathname, "/decisions")
                  ? "bg-accent text-accent-foreground"
                  : "text-muted-foreground hover:bg-surface-2 hover:text-foreground")
              }
            >
              <ClipboardCheck className="size-4" aria-hidden="true" />
              {t("decisions")}
              {pending > 0 && (
                <span className="num flex min-w-5 items-center justify-center rounded-full bg-status-pending px-1 text-[10px] font-bold text-white">
                  {pending}
                </span>
              )}
            </Link>
            <Link
              to="/report"
              className="hidden min-h-10 items-center gap-2 rounded-lg bg-primary px-3.5 text-sm font-bold text-primary-foreground shadow-sm shadow-primary/20 transition-colors hover:bg-primary/90 sm:flex"
            >
              <Plus className="size-4" aria-hidden="true" />
              {t("report")}
            </Link>
            <ThemeToggle />
            <LanguageToggle />
        </div>
      </div>
    </header>
  );
}

function MobileBar({ pending }: { pending: number }) {
  const tabs = [...PRIMARY_TABS, ...ACTION_TABS];
  const { t } = useLanguage();
  const location = useLocation();
  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-40 border-t border-border bg-surface-1/95 px-2 pb-[env(safe-area-inset-bottom)] backdrop-blur-lg md:hidden"
      aria-label="Primary"
    >
      <div className="grid grid-cols-9">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          return <Link
            key={tab.to}
            to={tab.to}
            aria-current={isTabActive(location.pathname, tab.to) ? "page" : undefined}
            className={
              "relative flex min-h-16 flex-col items-center justify-center gap-1 rounded-xl text-[10px] font-semibold transition-colors " +
              (isTabActive(location.pathname, tab.to)
                ? "text-primary"
                : "text-muted-foreground hover:bg-surface-2 hover:text-foreground")
            }
          >
            <span className={"relative " + (tab.to === "/report" ? "rounded-lg bg-primary p-1.5 text-primary-foreground" : "")}>
              <Icon className="size-5" aria-hidden="true" />
              {tab.to === "/decisions" && pending > 0 && (
                <span className="num absolute -right-2 -top-2 flex size-4 items-center justify-center rounded-full bg-status-pending text-[9px] font-bold text-white">
                  {pending}
                </span>
              )}
            </span>
            {t(tab.label.toLowerCase())}
          </Link>;
        })}
      </div>
    </nav>
  );
}

function NotFound() {
  return (
    <div className="mx-auto max-w-md py-20 text-center">
      <GuardianMark className="mx-auto size-10 text-primary" />
      <h1 className="mt-4 text-2xl font-bold tracking-tight">We couldn't find that page.</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        The link may be out of date, or the case may have moved.
      </p>
      <Link to="/" className="mt-4 inline-block text-sm text-primary underline-offset-4 hover:underline">
        Return to overview
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
  const { t } = useLanguage();
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
        <a
          href="#main-content"
          className="fixed left-4 top-2 z-50 -translate-y-20 rounded-lg bg-primary px-4 py-2 text-sm font-bold text-primary-foreground focus:translate-y-0"
        >
          Skip to content
        </a>
        <Masthead pending={pending} online={engine.online} />
        {/* polite live region: new decision cards announce themselves */}
        <div role="status" aria-live="polite" className="sr-only">
          {pending > 0
            ? `${pending} filing decision${pending === 1 ? "" : "s"} waiting for approval`
            : ""}
        </div>
        <main id="main-content" className="mx-auto w-full max-w-7xl flex-1 px-4 pb-24 pt-6 sm:px-6 md:pb-8 md:pt-8">
          <Routes>
            <Route path="/" element={<Dashboard data={engine} />} />
            <Route path="/ledger" element={<Dashboard data={engine} initialView="ledger" />} />
            <Route path="/report" element={<Report />} />
            <Route path="/decisions" element={<Decisions data={engine} />} />
            <Route path="/case/:complaintId" element={<CaseFilePage />} />
            <Route path="/watch" element={<Watchlist data={engine} />} />
            <Route path="/stats" element={<Stats data={engine} />} />
            <Route path="/impact" element={<Impact />} />
            <Route path="/replay" element={<Replay />} />
            <Route path="/diagnostics" element={<Diagnostics />} />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </main>
        <footer className="mt-12 border-t border-border py-6 pb-20 md:pb-6">
          <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-2 px-4 sm:px-6">
            <span className="micro-label">
              Tebaki — {t("footer")}
            </span>
            <span className="text-xs text-muted-foreground">Built for accountable city services.</span>
          </div>
        </footer>
        <MobileBar pending={pending} />
      </div>
    </AppContext.Provider>
  );
}
