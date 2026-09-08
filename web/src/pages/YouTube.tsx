import { useState } from "react";
import { api } from "../lib/api";
import { ChannelSelect, useChannels } from "../lib/channels";
import { Badge, ErrorBox, Spinner, useAsync } from "../lib/ui";

export default function YouTube() {
  const { channels, selected, choose } = useChannels();
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const status = useAsync(
    () => (selected ? api.get(`/youtube/status?channel_id=${selected}`) : Promise.resolve(null)),
    [selected]
  );

  async function connect() {
    setErr(null);
    setBusy(true);
    try {
      const res = await api.get<{ authorization_url: string }>(
        `/youtube/oauth/start?channel_id=${selected}`
      );
      window.location.href = res.authorization_url;
    } catch (e: any) {
      setErr(e.message);
      setBusy(false);
    }
  }

  async function disconnect() {
    setBusy(true);
    try {
      await api.post(`/youtube/disconnect?channel_id=${selected}`);
      status.reload();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">YouTube</h1>
        <ChannelSelect channels={channels} selected={selected} onChange={choose} />
      </div>
      {err && <ErrorBox msg={err} />}

      {status.loading ? (
        <Spinner />
      ) : status.error ? (
        <ErrorBox msg={status.error} />
      ) : status.data ? (
        <div className="card space-y-3">
          <div className="flex items-center gap-2">
            <span className="font-semibold">Connection</span>
            <Badge value={status.data.connected ? "connected" : "not connected"} />
          </div>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm">
            <dt className="text-slate-400">Provider</dt>
            <dd>{status.data.provider}</dd>
            <dt className="text-slate-400">OAuth configured</dt>
            <dd>{status.data.configured ? "yes" : "no"}</dd>
            <dt className="text-slate-400">YouTube channel</dt>
            <dd>{status.data.youtube_channel_title || "—"}</dd>
            <dt className="text-slate-400">Token expires</dt>
            <dd>{status.data.token_expires_at || "—"}</dd>
            <dt className="text-slate-400">Quota today</dt>
            <dd>
              {status.data.quota_used_today} / {status.data.quota_daily_limit}
            </dd>
          </dl>
          <div className="flex gap-2">
            {status.data.connected ? (
              <button className="btn-ghost" disabled={busy} onClick={disconnect}>
                Disconnect
              </button>
            ) : (
              <button
                className="btn-primary"
                disabled={busy || !status.data.configured}
                onClick={connect}
              >
                Connect YouTube
              </button>
            )}
          </div>
          {!status.data.configured && (
            <p className="text-xs text-slate-400">
              Set GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET and YOUTUBE_PROVIDER=google to enable real
              uploads.
            </p>
          )}
        </div>
      ) : null}
    </div>
  );
}
