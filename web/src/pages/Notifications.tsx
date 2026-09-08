import { useState } from "react";
import { api } from "../lib/api";
import { ChannelSelect, useChannels } from "../lib/channels";
import { Badge, ErrorBox, Spinner, ago, useAsync } from "../lib/ui";

const EVENTS = ["job_started", "video_ready", "published", "error"];

export default function Notifications() {
  const { channels, selected, choose } = useChannels();
  const [event, setEvent] = useState("video_ready");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const list = useAsync(() => api.get<any[]>("/notifications"), []);

  async function sendTest() {
    setBusy(true);
    setErr(null);
    try {
      await api.post("/notifications/test", { channel_id: selected, event });
      list.reload();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">      {err && <ErrorBox msg={err} />}

      <div className="card flex flex-wrap items-end gap-3">
        <div>
          <div className="mb-1 text-xs font-medium text-slate-500">Channel</div>
          <ChannelSelect channels={channels} selected={selected} onChange={choose} />
        </div>
        <div>
          <div className="mb-1 text-xs font-medium text-slate-500">Event</div>
          <select className="input" value={event} onChange={(e) => setEvent(e.target.value)}>
            {EVENTS.map((e) => (
              <option key={e}>{e}</option>
            ))}
          </select>
        </div>
        <button className="btn-primary" disabled={!selected || busy} onClick={sendTest}>
          Send test
        </button>
      </div>

      <div className="card">
        {list.loading ? (
          <Spinner />
        ) : list.error ? (
          <ErrorBox msg={list.error} />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr>
                  <th className="th">Event</th>
                  <th className="th">Status</th>
                  <th className="th">Provider</th>
                  <th className="th">Recipient</th>
                  <th className="th">Body</th>
                  <th className="th">When</th>
                </tr>
              </thead>
              <tbody>
                {list.data!.map((n) => (
                  <tr key={n.id}>
                    <td className="td">{n.event}</td>
                    <td className="td">
                      <Badge value={n.status} />
                    </td>
                    <td className="td">{n.provider}</td>
                    <td className="td">{n.recipient || "—"}</td>
                    <td className="td max-w-sm whitespace-pre-wrap text-xs text-slate-500">
                      {n.body}
                      {n.error && <div className="text-red-500">⚠ {n.error}</div>}
                    </td>
                    <td className="td">{ago(n.created_at)}</td>
                  </tr>
                ))}
                {list.data!.length === 0 && (
                  <tr>
                    <td className="td text-slate-400" colSpan={6}>
                      No notifications yet.
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
