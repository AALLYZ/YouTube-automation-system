import { useState } from "react";
import { api } from "../lib/api";
import { StageStrip } from "../lib/charts";
import { ChannelSelect, useChannels } from "../lib/channels";
import { Badge, ErrorBox, Spinner, ago, money, useAsync } from "../lib/ui";

export default function Automation() {
  const { channels, selected, choose } = useChannels();
  const [mode, setMode] = useState("AUTO");
  const [testRun, setTestRun] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const jobs = useAsync(() => api.get<any[]>("/jobs"), []);
  const sched = useAsync(() => api.get("/scheduler/status"), []);

  async function act(fn: () => Promise<any>, key: string) {
    setBusy(key);
    setErr(null);
    try {
      await fn();
      jobs.reload();
      sched.reload();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-6">
      {err && <ErrorBox msg={err} />}

      <div className="card space-y-3">
        <h2 className="section-title">Start a job</h2>
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <div className="mb-1 text-xs font-medium text-slate-500">Channel</div>
            <ChannelSelect channels={channels} selected={selected} onChange={choose} />
          </div>
          <div>
            <div className="mb-1 text-xs font-medium text-slate-500">Mode</div>
            <select className="input" value={mode} onChange={(e) => setMode(e.target.value)}>
              <option>AUTO</option>
              <option>APPROVAL_REQUIRED</option>
              <option>MANUAL</option>
            </select>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={testRun} onChange={(e) => setTestRun(e.target.checked)} />
            Test run (no publish)
          </label>
          <button
            className="btn-primary"
            disabled={!selected || busy === "create"}
            onClick={() =>
              act(
                () => api.post("/jobs", { channel_id: selected, mode, test_run: testRun }),
                "create"
              )
            }
          >
            {busy === "create" ? "Running…" : "Create & run"}
          </button>
        </div>
      </div>

      <div className="card">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="font-semibold">Scheduler</h2>
          <button
            className="btn-ghost"
            disabled={busy === "tick"}
            onClick={() => act(() => api.post("/scheduler/run"), "tick")}
          >
            Run scheduler tick
          </button>
        </div>
        {sched.data && (
          <div className="text-sm text-slate-500">
            Scheduler {sched.data.enabled ? "enabled" : "disabled"} · async workers{" "}
            {sched.data.jobs_async ? "on" : "off"} · {sched.data.recent_runs.length} recent run(s)
          </div>
        )}
      </div>

      <div className="card">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="font-semibold">Jobs</h2>
          <button className="btn-ghost" onClick={jobs.reload}>
            Refresh
          </button>
        </div>
        {jobs.loading ? (
          <Spinner />
        ) : jobs.error ? (
          <ErrorBox msg={jobs.error} />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr>
                  <th className="th">Job</th>
                  <th className="th">Status</th>
                  <th className="th w-[32%]">Pipeline</th>
                  <th className="th">Cost</th>
                  <th className="th">Created</th>
                  <th className="th">Actions</th>
                </tr>
              </thead>
              <tbody>
                {jobs.data!.map((j) => {
                  const steps = Object.fromEntries((j.steps || []).map((x: any) => [x.stage, x.status]));
                  return (
                  <tr key={j.public_id}>
                    <td className="td font-mono text-xs">
                      {j.public_id}
                      {j.test_run && <span className="ml-1 rounded bg-slate-100 px-1 text-[10px] text-slate-400">test</span>}
                    </td>
                    <td className="td">
                      <Badge value={j.status} dot />
                    </td>
                    <td className="td">
                      <StageStrip steps={steps} current={j.current_stage} status={j.status} />
                      <div className="mt-1 text-[11px] text-slate-400">{j.current_stage} · {j.progress_pct}%</div>
                    </td>
                    <td className="td tabular-nums">{money(j.total_cost_usd)}</td>
                    <td className="td text-slate-500">{ago(j.started_at || j.created_at)}</td>
                    <td className="td">
                      <div className="flex gap-1">
                        {j.status === "WAITING_APPROVAL" && (
                          <>
                            <button
                              className="btn-primary !px-2 !py-1"
                              onClick={() => act(() => api.post(`/jobs/${j.public_id}:approve`), j.public_id)}
                            >
                              Approve
                            </button>
                            <button
                              className="btn-ghost !px-2 !py-1"
                              onClick={() => act(() => api.post(`/jobs/${j.public_id}:reject`), j.public_id)}
                            >
                              Reject
                            </button>
                          </>
                        )}
                        {j.status === "FAILED" && (
                          <button
                            className="btn-ghost !px-2 !py-1"
                            onClick={() => act(() => api.post(`/jobs/${j.public_id}:retry`), j.public_id)}
                          >
                            Retry
                          </button>
                        )}
                        {["QUEUED", "RUNNING", "WAITING_APPROVAL"].includes(j.status) && (
                          <button
                            className="btn-ghost !px-2 !py-1"
                            onClick={() => act(() => api.post(`/jobs/${j.public_id}:cancel`), j.public_id)}
                          >
                            Cancel
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
