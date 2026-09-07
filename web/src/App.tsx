import { useEffect, useState } from "react";
import { Link, Route, Routes, useLocation } from "react-router-dom";
import { Dashboard } from "@/pages/Dashboard";
import { Decisions } from "@/pages/Decisions";
import { Report } from "@/pages/Report";
import { api } from "@/lib/api";

function GuardianMark({ className = "size-5" }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden="true">
      <path
        d="M16 5 L27 16 L16 27 L5 16 Z"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
      />
      <circle cx="16" cy="16" r="4" fill="currentColor" />
      <circle cx="16" cy="16" r="1.6" fill="var(--background)" />
    </svg>
  );
}

function Masthead() {
  const location = useLocation();
  const [pending, setPending] = useState<number | null>(null);
  const [online, setOnline] = useState(true);

  useEffect(() => {
    let alive = true;
    const load = () =>
      api
        .listDecisions()
        .then((cards) => {
          if (!alive) return;
          setPending(cards.length);
          setOnline(true);
        })
        .catch(() => {
          if (!alive) return;
          setPending(null);
          setOnline(false);
        });
    load();
    const t = setInterval(load, 8000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, [location.pathname]);

  const links = [
    { to: "/", label: "Ledger" },
    { to: "/report", label: "Report" },
    { to: "/decisions", label: "Decisions" },
  ];

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background/95 backdrop-blur-sm">
      {/* the sodium line */}
      <div className="h-0.5 bg-primary" />
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-3">
        <Link to="/" className="group flex items-baseline gap-3">
          <GuardianMark className="size-5 shrink-0 self-center text-primary transition-transform group-hover:rotate-45" />
          <span className="text-lg font-bold tracking-[0.08em]">TEBAKI</span>
          <span className="font-ethiopic text-lg leading-none text-primary">ጠባቂ</span>
          <span className="micro-label hidden sm:inline">the city's guardian</span>
        </Link>
        <nav className="flex items-center gap-1">
          {links.map((l) => {
            const active = location.pathname === l.to;
            return (
              <Link
                key={l.to}
                to={l.to}
                className={
                  "relative rounded-md px-3 py-1.5 text-sm transition-colors " +
                  (active
                    ? "bg-surface-2 text-foreground"
                    : "text-muted-foreground hover:text-foreground")
                }
              >
                {l.label}
                {l.to === "/decisions" && pending !== null && pending > 0 && (
                  <span className="num absolute -top-1.5 -right-1.5 flex size-4.5 items-center justify-center rounded-full bg-primary text-[10px] font-bold text-primary-foreground">
                    {pending}
                  </span>
                )}
              </Link>
            );
          })}
          <span className="ml-3 hidden items-center gap-1.5 md:flex">
            {online ? (
              <>
                <span className="relative flex size-2">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-60" />
                  <span className="relative inline-flex size-2 rounded-full bg-primary" />
                </span>
                <span className="micro-label">on watch</span>
              </>
            ) : (
              <>
                <span className="inline-flex size-2 rounded-full bg-border" />
                <span className="micro-label">off watch</span>
              </>
            )}
          </span>
        </nav>
      </div>
    </header>
  );
}

function NotFound() {
  return (
    <div className="mx-auto max-w-md py-20 text-center">
      <GuardianMark className="mx-auto size-10 text-primary" />
      <h2 className="mt-4 text-xl font-semibold">Nothing on watch here.</h2>
      <p className="mt-2 text-sm text-muted-foreground">
        This page doesn't exist — the guardian keeps to the ledger, the report desk, and the
        decision queue.
      </p>
      <Link to="/" className="mt-4 inline-block text-sm text-primary underline-offset-4 hover:underline">
        Back to the ledger
      </Link>
    </div>
  );
}

export default function App() {
  return (
    <div className="min-h-dvh bg-background">
      <Masthead />
      <main className="mx-auto max-w-6xl px-4 py-6">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/report" element={<Report />} />
          <Route path="/decisions" element={<Decisions />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
      <footer className="mt-12 border-t border-border py-6">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-2 px-4">
          <span className="micro-label">
            Tebaki ጠባቂ — files, tracks &amp; escalates so you don't have to
          </span>
          <span className="micro-label num">any city is a pull request</span>
        </div>
      </footer>
    </div>
  );
}
