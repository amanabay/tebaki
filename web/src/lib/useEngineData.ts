import { useCallback, useEffect, useRef, useState } from "react";
import {
  api,
  type ActivityEvent,
  type LedgerRow,
  type MapData,
  type ScoreboardRow,
  type DecisionCard,
} from "@/lib/api";

export interface EngineData {
  ledger: LedgerRow[];
  scoreboard: ScoreboardRow[];
  activity: ActivityEvent[];
  mapData: MapData | null;
  decisions: DecisionCard[];
  /** null = still loading the first fetch; false = fetch failed */
  online: boolean | null;
  refresh: () => void;
}

/**
 * One shared engine-data poller for the whole app. Polls every 8s while the
 * tab is visible, backs off to 60s while hidden or after failures. All pages
 * read from this single source — no per-component intervals.
 */
export function useEngineData(): EngineData {
  const [ledger, setLedger] = useState<LedgerRow[]>([]);
  const [scoreboard, setScoreboard] = useState<ScoreboardRow[]>([]);
  const [activity, setActivity] = useState<ActivityEvent[]>([]);
  const [mapData, setMapData] = useState<MapData | null>(null);
  const [decisions, setDecisions] = useState<DecisionCard[]>([]);
  const [online, setOnline] = useState<boolean | null>(null);
  const [loaded, setLoaded] = useState(false);
  const failures = useRef(0);
  const inflight = useRef(false);

  const refresh = useCallback(async () => {
    if (inflight.current) return;
    inflight.current = true;
    try {
      const [l, s, a, m, d] = await Promise.all([
        api.ledger(),
        api.scoreboard(),
        api.activity(),
        api.mapData(),
        api.listDecisions(),
      ]);
      setLedger(l);
      setScoreboard(s);
      setActivity(a);
      setMapData(m);
      setDecisions(d);
      setOnline(true);
      failures.current = 0;
    } catch {
      failures.current += 1;
      setOnline(false);
    } finally {
      inflight.current = false;
      setLoaded(true);
    }
  }, []);

  useEffect(() => {
    refresh();
    let timer: ReturnType<typeof setTimeout>;
    const schedule = () => {
      const hidden = document.visibilityState === "hidden";
      const backoff = failures.current > 0 ? 60_000 : 0;
      const interval = hidden ? 60_000 : backoff || 8_000;
      timer = setTimeout(() => {
        if (document.visibilityState === "visible" || failures.current > 0) refresh();
        schedule();
      }, interval);
    };
    schedule();
    const onVisible = () => {
      if (document.visibilityState === "visible") refresh();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [refresh]);

  return {
    ledger,
    scoreboard,
    activity,
    mapData,
    decisions,
    online: loaded ? online : null,
    refresh,
  };
}

export function usePendingCount(decisions: DecisionCard[]): number {
  return decisions.length;
}
