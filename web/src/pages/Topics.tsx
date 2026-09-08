import { useState } from "react";
import { api } from "../lib/api";
import { ChannelSelect, useChannels } from "../lib/channels";
import { Badge, ErrorBox, Spinner, useAsync } from "../lib/ui";

export default function Topics() {
  const { channels, selected, choose } = useChannels();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const topics = useAsync(
    () => (selected ? api.get<any[]>(`/channels/${selected}/topics`) : Promise.resolve([])),
    [selected]
  );

  async function run(fn: () => Promise<any>) {
    setBusy(true);
    setErr(null);
    try {
      await fn();
      topics.reload();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">        <div className="flex items-center gap-2">
          <ChannelSelect channels={channels} selected={selected} onChange={choose} />
          <button
            className="btn-primary"
            disabled={!selected || busy}
            onClick={() => run(() => api.post(`/channels/${selected}/topics:generate`, { count: 8 }))}
          >
            Generate 8
          </button>
        </div>
      </div>
      {err && <ErrorBox msg={err} />}

      <div className="card">
        {topics.loading ? (
          <Spinner />
        ) : topics.error ? (
          <ErrorBox msg={topics.error} />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr>
                  <th className="th">Score</th>
                  <th className="th">Title</th>
                  <th className="th">Status</th>
                  <th className="th">Actions</th>
                </tr>
              </thead>
              <tbody>
                {topics.data!.map((t) => (
                  <tr key={t.id}>
                    <td className="td font-semibold">{t.total_score.toFixed(0)}</td>
                    <td className="td">
                      <div>{t.title}</div>
                      <div className="text-xs text-slate-400">{t.angle}</div>
                    </td>
                    <td className="td">
                      <Badge value={t.status} />
                    </td>
                    <td className="td">
                      {t.status === "GENERATED" && (
                        <div className="flex gap-1">
                          <button
                            className="btn-ghost !px-2 !py-1"
                            onClick={() => run(() => api.post(`/topics/${t.id}:approve`))}
                          >
                            Approve
                          </button>
                          <button
                            className="btn-ghost !px-2 !py-1"
                            onClick={() => run(() => api.post(`/topics/${t.id}:reject`, { reason: "" }))}
                          >
                            Reject
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
                {topics.data!.length === 0 && (
                  <tr>
                    <td className="td text-slate-400" colSpan={4}>
                      No topics — generate some.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
