import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { Donut, GaugeBar, Sparkbars, StageStrip } from "../lib/charts";
import { Icon, IconName } from "../lib/icons";
import { Badge, ErrorBox, Spinner, ago, money, useAsync } from "../lib/ui";

const TILES: {
  key: string;
  label: string;
  icon: IconName;
  grad: string;
  get: (d: any) => string | number;
  sub: (d: any) => string;
}[] = [
  {
    key: "channels", label: "Channels", icon: "youtube",
    grad: "from-brand-500 to-violet-500",
    get: (d) => d.channels.total, sub: (d) => `${d.channels.automation} automated`,
  },
  {
    key: "jobs", label: "Jobs run", icon: "automation",
    grad: "from-sky-500 to-cyan-500",
    get: (d) => d.jobs.total, sub: (d) => `${d.jobs.running} running · ${d.jobs.failed} failed`,
  },
  {
    key: "videos", label: "Videos ready", icon: "film",
    grad: "from-emerald-500 to-teal-500",
    get: (d) => d.videos.ready, sub: (d) => `${d.videos.rendering} rendering`,
  },
  {
    key: "published", label: "Published", icon: "spark",
    grad: "from-fuchsia-500 to-pink-500",
    get: (d) => d.youtube.published, sub: (d) => `${d.youtube.uploads_total} uploads`,
  },
];

export default function Overview() {
  const ov = useAsync(() => api.get("/overview"));
  const jobs = useAsync(() => api.get<any[]>("/jobs"));

  if (ov.loading) return <Spinner />;
  if (ov.error) return <ErrorBox msg={ov.error} />;
  const d = ov.data!;

  const s = d.jobs.by_status || {};
  const segs = [
    { label: "Completed", value: s.COMPLETED || 0, color: "#10b981" },
    { label: "Running", value: s.RUNNING || 0, color: "#0ea5e9" },
    { label: "Waiting", value: s.WAITING_APPROVAL || 0, color: "#f59e0b" },
    { label: "Failed", value: s.FAILED || 0, color: "#f43f5e" },
    { label: "Queued", value: (s.QUEUED || 0) + (s.CANCELLED || 0), color: "#cbd5e1" },
  ];

  const recent = (jobs.data || []).slice(0, 6);
  const costBars = recent.map((j) => j.total_cost_usd || 0).reverse();

  return (
    <div className="space-y-6">
      {/* hero */}
      <div className="card-flush relative">
        <div className="absolute inset-0 bg-gradient-to-br from-brand-600 via-violet-600 to-fuchsia-600" />
        <div className="absolute inset-0 opacity-30 [background:radial-gradient(20rem_20rem_at_90%_-30%,white,transparent)]" />
        <div className="relative flex flex-wrap items-center justify-between gap-4 p-6 text-white">
          <div>
            <div className="text-xs font-medium uppercase tracking-widest text-white/70">
              Pipeline status
            </div>
            <div className="mt-1 text-2xl font-bold">
              {d.jobs.running > 0
                ? `${d.jobs.running} job${d.jobs.running > 1 ? "s" : ""} in flight`
                : d.jobs.waiting_approval > 0
                ? `${d.jobs.waiting_approval} awaiting approval`
                : "Idle — ready to run"}
            </div>
            <div className="mt-1 text-sm text-white/80">
              {money(d.cost.today_usd)} spent today · {money(d.cost.all_time_usd)} all-time
            </div>
          </div>
          <div className="flex gap-2">
            <Link to="/automation" className="rounded-lg bg-white px-4 py-2 text-sm font-semibold text-brand-700 shadow hover:bg-white/90">
              New job
            </Link>
            <button className="rounded-lg bg-white/15 px-4 py-2 text-sm font-semibold text-white ring-1 ring-white/25 hover:bg-white/25" onClick={() => { ov.reload(); jobs.reload(); }}>
              Refresh
            </button>
          </div>
        </div>
      </div>

      {/* stat tiles */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {TILES.map((t) => {
          const I = Icon[t.icon];
          return (
            <div key={t.key} className="card flex items-center gap-4">
              <div className={`grid h-12 w-12 shrink-0 place-items-center rounded-xl bg-gradient-to-br ${t.grad} text-white shadow-lg`}>
                <I className="h-6 w-6" />
              </div>
              <div className="min-w-0">
                <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                  {t.label}
                </div>
                <div className="text-2xl font-bold text-slate-800">{t.get(d)}</div>
                <div className="truncate text-xs text-slate-400">{t.sub(d)}</div>
              </div>
            </div>
          );
        })}
      </div>

      {/* charts row */}
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="card">
          <div className="section-title mb-3">Jobs by status</div>
          <Donut segments={segs} centerLabel={d.jobs.total} centerSub="TOTAL" />
        </div>

        <div className="card space-y-4">
          <div>
            <div className="section-title mb-2 flex items-center gap-2">
              <Icon.gauge className="h-4 w-4 text-slate-400" /> YouTube quota today
            </div>
            <GaugeBar value={d.youtube.quota_used_today} max={d.youtube.quota_daily_limit} />
          </div>
          <div>
            <div className="section-title mb-2 flex items-center gap-2">
              <Icon.bell className="h-4 w-4 text-slate-400" /> Notifications
            </div>
            <GaugeBar
              value={d.notifications.failed}
              max={Math.max(1, d.notifications.total)}
              goodBelow={0.01}
              warnBelow={0.2}
            />
            <div className="mt-1 text-xs text-slate-400">
              {d.notifications.total} sent · {d.notifications.failed} failed
            </div>
          </div>
        </div>

        <div className="card">
          <div className="section-title mb-2 flex items-center gap-2">
            <Icon.dollar className="h-4 w-4 text-slate-400" /> Cost — last {costBars.length} jobs
          </div>
          <Sparkbars data={costBars.length ? costBars : [0]} />
          <div className="mt-3 flex items-center justify-between text-xs text-slate-400">
            <span>today {money(d.cost.today_usd)}</span>
            <span>avg {money(recent.length ? recent.reduce((a: number, j: any) => a + (j.total_cost_usd || 0), 0) / recent.length : 0)}</span>
          </div>
        </div>
      </div>

      {/* recent jobs */}
      <div className="card-flush">
        <div className="flex items-center justify-between px-5 pt-4">
          <div className="section-title">Recent jobs</div>
          <Link to="/automation" className="text-sm font-medium text-brand-600 hover:underline">
            All jobs →
          </Link>
        </div>
        <table className="mt-2 w-full">
          <thead>
            <tr>
              <th className="th">Job</th>
              <th className="th">Status</th>
              <th className="th w-[38%]">Pipeline</th>
              <th className="th">Cost</th>
              <th className="th">When</th>
            </tr>
          </thead>
          <tbody>
            {recent.map((j) => {
              const steps = Object.fromEntries((j.steps || []).map((x: any) => [x.stage, x.status]));
              return (
                <tr key={j.public_id}>
                  <td className="td font-mono text-xs">
                    {j.public_id}
                    {j.test_run && <span className="ml-1 rounded bg-slate-100 px-1 text-[10px] text-slate-400">test</span>}
                  </td>
                  <td className="td"><Badge value={j.status} dot /></td>
                  <td className="td">
                    <StageStrip steps={steps} current={j.current_stage} status={j.status} />
                    <div className="mt-1 text-[11px] text-slate-400">
                      {j.current_stage} · {j.progress_pct}%
                    </div>
                  </td>
                  <td className="td tabular-nums">{money(j.total_cost_usd)}</td>
                  <td className="td text-slate-500">{ago(j.started_at || j.created_at)}</td>
                </tr>
              );
            })}
            {recent.length === 0 && (
              <tr>
                <td className="td text-slate-400" colSpan={5}>
                  No jobs yet — <Link to="/automation" className="text-brand-600">start one</Link>.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* providers */}
      <div className="card">
        <div className="section-title mb-3">Providers &amp; automation</div>
        <div className="flex flex-wrap gap-2">
          {Object.entries(d.providers).map(([k, v]) => (
            <span
              key={k}
              className={`badge ${
                v === "stub" || v === "console"
                  ? "bg-slate-100 text-slate-500 ring-slate-200"
                  : "bg-emerald-50 text-emerald-700 ring-emerald-200"
              }`}
            >
              {k}: <b className="font-semibold">{String(v)}</b>
            </span>
          ))}
          <span className={`badge ${d.automation.scheduler_enabled ? "bg-emerald-50 text-emerald-700 ring-emerald-200" : "bg-slate-100 text-slate-500 ring-slate-200"}`}>
            scheduler: <b>{d.automation.scheduler_enabled ? "on" : "off"}</b>
          </span>
        </div>
      </div>
    </div>
  );
}
