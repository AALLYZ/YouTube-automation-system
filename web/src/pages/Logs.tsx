import { useState } from "react";
import { api } from "../lib/api";
import { Badge, ErrorBox, Spinner, ago, money, useAsync } from "../lib/ui";

export default function Logs() {
  const [tab, setTab] = useState<"events" | "usage">("events");
  const logs = useAsync(() => api.get<any[]>("/logs"), []);
  const usage = useAsync(() => api.get<any[]>("/usage"), []);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">        <div className="flex gap-1">
          <button
            className={tab === "events" ? "btn-primary" : "btn-ghost"}
            onClick={() => setTab("events")}
          >
            Events
          </button>
          <button
            className={tab === "usage" ? "btn-primary" : "btn-ghost"}
            onClick={() => setTab("usage")}
          >
            API usage
          </button>
        </div>
      </div>

      {tab === "events" ? (
        <div className="card">
          {logs.loading ? (
            <Spinner />
          ) : logs.error ? (
            <ErrorBox msg={logs.error} />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr>
                    <th className="th">Level</th>
                    <th className="th">Event</th>
                    <th className="th">Job</th>
                    <th className="th">Message</th>
                    <th className="th">When</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.data!.map((l) => (
                    <tr key={l.id}>
                      <td className="td">
                        <Badge value={l.level} />
                      </td>
                      <td className="td font-mono text-xs">{l.event}</td>
                      <td className="td">{l.job_id ?? "—"}</td>
                      <td className="td text-xs text-slate-500">{l.message}</td>
                      <td className="td">{ago(l.created_at)}</td>
                    </tr>
                  ))}
                  {logs.data!.length === 0 && (
                    <tr>
                      <td className="td text-slate-400" colSpan={5}>
                        No events logged yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : (
        <div className="card">
          {usage.loading ? (
            <Spinner />
          ) : usage.error ? (
            <ErrorBox msg={usage.error} />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr>
                    <th className="th">Job</th>
                    <th className="th">Stage</th>
                    <th className="th">Provider</th>
                    <th className="th">Op</th>
                    <th className="th">Tokens</th>
                    <th className="th">Units</th>
                    <th className="th">Cost</th>
                  </tr>
                </thead>
                <tbody>
                  {usage.data!.map((u) => (
                    <tr key={u.id}>
                      <td className="td font-mono text-xs">{u.job || "—"}</td>
                      <td className="td">{u.stage}</td>
                      <td className="td">{u.provider}</td>
                      <td className="td text-xs">{u.operation}</td>
                      <td className="td text-xs">
                        {u.input_tokens + u.output_tokens || "—"}
                      </td>
                      <td className="td text-xs">{u.units || "—"}</td>
                      <td className="td">{money(u.est_cost_usd)}</td>
                    </tr>
                  ))}
                  {usage.data!.length === 0 && (
                    <tr>
                      <td className="td text-slate-400" colSpan={7}>
                        No API usage recorded.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
