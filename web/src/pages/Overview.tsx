import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { Badge, ErrorBox, Spinner, ago, money, useAsync } from "../lib/ui";

function Stat({ label, value, sub }: { label: string; value: any; sub?: string }) {
  return (
    <div className="card">
      <div className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-slate-800">{value}</div>
      {sub && <div className="mt-0.5 text-xs text-slate-400">{sub}</div>}
    </div>
  );
}

export default function Overview() {
  const { data, error, loading, reload } = useAsync(() => api.get("/overview"));

  if (loading) return <Spinner />;
  if (error) return <ErrorBox msg={error} />;
  const d = data!;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Overview</h1>
        <button className="btn-ghost" onClick={reload}>
          Refresh
        </button>
      </div>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Stat label="Channels" value={d.channels.total} sub={`${d.channels.automation} automated`} />
        <Stat label="Jobs" value={d.jobs.total} sub={`${d.jobs.running} running · ${d.jobs.failed} failed`} />
        <Stat
          label="Videos ready"
          value={d.videos.ready}
          sub={`${d.videos.rendering} rendering`}
        />
        <Stat label="Published" value={d.youtube.published} sub={`${d.youtube.uploads_total} uploads`} />
        <Stat label="Cost today" value={money(d.cost.today_usd)} sub={`${money(d.cost.all_time_usd)} all-time`} />
        <Stat
          label="YT quota today"
          value={d.youtube.quota_used_today}
          sub={`/ ${d.youtube.quota_daily_limit}`}
        />
        <Stat label="Waiting approval" value={d.jobs.waiting_approval} />
        <Stat label="Notifications" value={d.notifications.total} sub={`${d.notifications.failed} failed`} />
      </div>

      <div className="card">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="font-semibold">Recent jobs</h2>
          <Link to="/automation" className="text-sm text-brand-600 hover:underline">
            All jobs →
          </Link>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr>
                <th className="th">Job</th>
                <th className="th">Status</th>
                <th className="th">Stage</th>
                <th className="th">Progress</th>
                <th className="th">Cost</th>
                <th className="th">Created</th>
              </tr>
            </thead>
            <tbody>
              {d.recent_jobs.map((j: any) => (
                <tr key={j.public_id}>
                  <td className="td font-mono text-xs">{j.public_id}</td>
                  <td className="td">
                    <Badge value={j.status} />
                    {j.test_run && <span className="ml-1 text-xs text-slate-400">test</span>}
                  </td>
                  <td className="td">{j.current_stage}</td>
                  <td className="td">{j.progress_pct}%</td>
                  <td className="td">{money(j.total_cost_usd)}</td>
                  <td className="td">{ago(j.created_at)}</td>
                </tr>
              ))}
              {d.recent_jobs.length === 0 && (
                <tr>
                  <td className="td text-slate-400" colSpan={6}>
                    No jobs yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card">
        <h2 className="mb-2 font-semibold">Providers</h2>
        <div className="flex flex-wrap gap-2 text-xs">
          {Object.entries(d.providers).map(([k, v]) => (
            <span key={k} className="rounded bg-slate-100 px-2 py-1">
              <span className="text-slate-400">{k}:</span> <span className="font-medium">{String(v)}</span>
            </span>
          ))}
          <span className="rounded bg-slate-100 px-2 py-1">
            <span className="text-slate-400">scheduler:</span>{" "}
            <span className="font-medium">{d.automation.scheduler_enabled ? "on" : "off"}</span>
          </span>
        </div>
      </div>
    </div>
  );
}
