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

const TONE: Record<string, string> = {
  COMPLETED: "bg-green-100 text-green-700",
  RUNNING: "bg-blue-100 text-blue-700",
  QUEUED: "bg-slate-100 text-slate-600",
  WAITING_APPROVAL: "bg-amber-100 text-amber-700",
  FAILED: "bg-red-100 text-red-700",
  CANCELLED: "bg-slate-200 text-slate-500",
  SUCCEEDED: "bg-green-100 text-green-700",
  PENDING: "bg-slate-100 text-slate-600",
  SKIPPED: "bg-slate-100 text-slate-400",
  sent: "bg-green-100 text-green-700",
  delivered: "bg-green-100 text-green-700",
  read: "bg-green-100 text-green-700",
  queued: "bg-slate-100 text-slate-600",
  failed: "bg-red-100 text-red-700",
  ready: "bg-green-100 text-green-700",
  uploaded: "bg-green-100 text-green-700",
  published: "bg-green-100 text-green-700",
  scheduled: "bg-amber-100 text-amber-700",
  ERROR: "bg-red-100 text-red-700",
  WARNING: "bg-amber-100 text-amber-700",
  INFO: "bg-slate-100 text-slate-600",
};

export function Badge({ value }: { value: string | number | null | undefined }) {
  const v = String(value ?? "—");
  return <span className={`badge ${TONE[v] || "bg-slate-100 text-slate-600"}`}>{v}</span>;
}

export function Spinner() {
  return <div className="p-6 text-sm text-slate-400">Loading…</div>;
}

export function ErrorBox({ msg }: { msg: string }) {
  return (
    <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{msg}</div>
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
