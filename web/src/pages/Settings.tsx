import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { ChannelSelect, useChannels } from "../lib/channels";
import { ErrorBox } from "../lib/ui";

const JSON_BLOBS = [
  "topic_ai", "script_ai", "research_cfg", "voice_cfg", "visual_cfg",
  "thumbnail_cfg", "youtube_cfg", "whatsapp_cfg", "scoring_weights",
];

export default function Settings() {
  const { channels, selected, choose, loading } = useChannels();
  const [settings, setSettings] = useState<any>(null);
  const [raw, setRaw] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [newName, setNewName] = useState("");

  useEffect(() => {
    if (!selected) return;
    api.get(`/channels/${selected}/settings`).then((s) => {
      setSettings(s);
      const r: Record<string, string> = {};
      JSON_BLOBS.forEach((k) => (r[k] = JSON.stringify(s[k] ?? {}, null, 2)));
      setRaw(r);
    });
  }, [selected]);

  async function save() {
    setErr(null);
    setMsg(null);
    const body: any = {
      approval_mode: settings.approval_mode,
      automation_enabled: settings.automation_enabled,
      daily_video_limit: settings.daily_video_limit,
      publish_time: settings.publish_time,
      privacy_default: settings.privacy_default,
      allow_unverified_media: settings.allow_unverified_media,
      notify_events: settings.notify_events,
    };
    try {
      for (const k of JSON_BLOBS) body[k] = JSON.parse(raw[k] || "{}");
    } catch (e: any) {
      setErr(`Invalid JSON in a config block: ${e.message}`);
      return;
    }
    try {
      await api.put(`/channels/${selected}/settings`, body);
      setMsg("Saved.");
    } catch (e: any) {
      setErr(e.message);
    }
  }

  async function createChannel() {
    if (!newName.trim()) return;
    try {
      const c = await api.post("/channels", { name: newName, niche: "" });
      setNewName("");
      choose(c.id);
      location.reload();
    } catch (e: any) {
      setErr(e.message);
    }
  }

  if (loading) return <div className="text-slate-400">Loading…</div>;

  return (
    <div className="space-y-4">
      <ChannelSelect channels={channels} selected={selected} onChange={choose} />
      {err && <ErrorBox msg={err} />}
      {msg && <div className="rounded bg-green-50 p-2 text-sm text-green-700">{msg}</div>}

      <div className="card flex items-end gap-2">
        <div className="flex-1">
          <div className="mb-1 text-xs font-medium text-slate-500">New channel name</div>
          <input className="input" value={newName} onChange={(e) => setNewName(e.target.value)} />
        </div>
        <button className="btn-ghost" onClick={createChannel}>
          Create channel
        </button>
      </div>

      {settings && (
        <>
          <div className="card grid gap-4 md:grid-cols-2">
            <label className="text-sm">
              <span className="mb-1 block font-medium text-slate-600">Approval mode</span>
              <select
                className="input"
                value={settings.approval_mode}
                onChange={(e) => setSettings({ ...settings, approval_mode: e.target.value })}
              >
                <option>AUTO</option>
                <option>APPROVAL_REQUIRED</option>
                <option>MANUAL</option>
              </select>
            </label>
            <label className="text-sm">
              <span className="mb-1 block font-medium text-slate-600">Default privacy</span>
              <select
                className="input"
                value={settings.privacy_default}
                onChange={(e) => setSettings({ ...settings, privacy_default: e.target.value })}
              >
                <option>private</option>
                <option>unlisted</option>
                <option>public</option>
              </select>
            </label>
            <label className="text-sm">
              <span className="mb-1 block font-medium text-slate-600">Daily video limit</span>
              <input
                className="input"
                type="number"
                value={settings.daily_video_limit}
                onChange={(e) =>
                  setSettings({ ...settings, daily_video_limit: Number(e.target.value) })
                }
              />
            </label>
            <label className="text-sm">
              <span className="mb-1 block font-medium text-slate-600">Publish time (UTC HH:MM)</span>
              <input
                className="input"
                value={settings.publish_time}
                onChange={(e) => setSettings({ ...settings, publish_time: e.target.value })}
              />
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={settings.automation_enabled}
                onChange={(e) => setSettings({ ...settings, automation_enabled: e.target.checked })}
              />
              Automation enabled (scheduler)
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={settings.allow_unverified_media}
                onChange={(e) =>
                  setSettings({ ...settings, allow_unverified_media: e.target.checked })
                }
              />
              Allow unverified media
            </label>
          </div>

          <div className="card">
            <h2 className="mb-2 font-semibold">AI &amp; provider config (JSON)</h2>
            <div className="grid gap-4 md:grid-cols-2">
              {JSON_BLOBS.map((k) => (
                <label key={k} className="text-sm">
                  <span className="mb-1 block font-mono text-xs text-slate-500">{k}</span>
                  <textarea
                    className="input h-28 font-mono text-xs"
                    value={raw[k] ?? ""}
                    onChange={(e) => setRaw({ ...raw, [k]: e.target.value })}
                  />
                </label>
              ))}
            </div>
          </div>

          <button className="btn-primary" onClick={save}>
            Save settings
          </button>
        </>
      )}
    </div>
  );
}
