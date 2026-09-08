import { useCallback, useEffect, useState } from "react";

export function useAsync<T>(fn: () => Promise<T>, deps: any[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const run = useCallback(() => {
    setLoading(true);
    setError(null);
    fn()
      .then(setData)
      .catch((e) => setError(e.message || String(e)))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    run();
  }, [run]);

  return { data, error, loading, reload: run };
}

const OK = "bg-emerald-50 text-emerald-700 ring-emerald-200";
const RUN = "bg-sky-50 text-sky-700 ring-sky-200";
const WARN = "bg-amber-50 text-amber-700 ring-amber-200";
const BAD = "bg-rose-50 text-rose-700 ring-rose-200";
const MUTE = "bg-slate-100 text-slate-500 ring-slate-200";

const TONE: Record<string, string> = {
  COMPLETED: OK, SUCCEEDED: OK, ready: OK, uploaded: OK, published: OK,
  sent: OK, delivered: OK, read: OK, connected: OK,
  RUNNING: RUN, uploading: RUN,
  QUEUED: MUTE, PENDING: MUTE, queued: MUTE, SKIPPED: MUTE, CANCELLED: MUTE, INFO: MUTE,
  "not connected": MUTE, draft: MUTE, pending: MUTE,
  WAITING_APPROVAL: WARN, scheduled: WARN, WARNING: WARN,
  FAILED: BAD, failed: BAD, ERROR: BAD,
};

const DOT: Record<string, string> = {
  [OK]: "bg-emerald-500", [RUN]: "bg-sky-500", [WARN]: "bg-amber-500",
  [BAD]: "bg-rose-500", [MUTE]: "bg-slate-400",
};

export function Badge({ value, dot }: { value: string | number | null | undefined; dot?: boolean }) {
  const v = String(value ?? "—");
  const tone = TONE[v] || MUTE;
  return (
    <span className={`badge ${tone}`}>
      {dot && <span className={`h-1.5 w-1.5 rounded-full ${DOT[tone]}`} />}
      {v}
    </span>
  );
}

export function Spinner() {
  return (
    <div className="flex items-center gap-2 p-6 text-sm text-slate-400">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-200 border-t-brand-500" />
      Loading…
    </div>
  );
}

export function ErrorBox({ msg }: { msg: string }) {
  return (
    <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
      ⚠ {msg}
    </div>
  );
}

export function ago(iso?: string | null) {
  if (!iso) return "—";
  // backend serialises naive UTC timestamps without a suffix — treat as UTC
  const norm = /[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : iso + "Z";
  const d = new Date(norm);
  const s = Math.round((Date.now() - d.getTime()) / 1000);
  if (s < 0) return "just now";
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  if (s < 86400) return `${Math.round(s / 3600)}h ago`;
  return d.toLocaleDateString();
}

export function money(v?: number | null) {
  return `$${(v ?? 0).toFixed(v && v < 1 ? 4 : 2)}`;
}
