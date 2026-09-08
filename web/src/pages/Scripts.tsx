import { useState } from "react";
import { api } from "../lib/api";
import { ChannelSelect, useChannels } from "../lib/channels";
import { Badge, ErrorBox, useAsync } from "../lib/ui";

export default function Scripts() {
  const { channels, selected, choose } = useChannels();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [open, setOpen] = useState<number | null>(null);

  const topics = useAsync(
    () => (selected ? api.get<any[]>(`/channels/${selected}/topics`) : Promise.resolve([])),
    [selected]
  );

  async function draft(topicId: number) {
    setBusy(true);
    setErr(null);
    try {
      const res = await api.post(`/channels/${selected}/scripts:draft`, {
        topic_id: topicId,
        test_run: true,
      });
      setOpen(res.script.id);
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  const script = useAsync(
    () => (open ? api.get(`/scripts/${open}`) : Promise.resolve(null)),
    [open]
  );

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Scripts</h1>
        <ChannelSelect channels={channels} selected={selected} onChange={choose} />
      </div>
      {err && <ErrorBox msg={err} />}

      <div className="card">
        <h2 className="mb-2 font-semibold">Draft from a topic</h2>
        <div className="space-y-1">
          {(topics.data || []).map((t) => (
            <div key={t.id} className="flex items-center justify-between border-t border-slate-100 py-2 text-sm">
              <span>{t.title}</span>
              <button className="btn-ghost !px-2 !py-1" disabled={busy} onClick={() => draft(t.id)}>
                Draft script
              </button>
            </div>
          ))}
          {(topics.data || []).length === 0 && (
            <div className="text-sm text-slate-400">Generate topics first.</div>
          )}
        </div>
      </div>

      {script.data && (
        <div className="card space-y-3">
          <div className="flex items-center gap-2">
            <h2 className="font-semibold">Script #{script.data.id}</h2>
            <Badge value={script.data.status} />
            <span className="text-sm text-slate-400">
              QA {script.data.qa_score ?? "—"} · v{script.data.current_version} ·{" "}
              {script.data.target_duration_sec}s target
            </span>
          </div>
          <div className="space-y-2">
            {script.data.scenes.map((s: any) => (
              <div key={s.scene_index} className="rounded border border-slate-100 p-2 text-sm">
                <div className="text-xs font-medium text-slate-400">
                  Scene {s.scene_index} · {s.visual_type} · {s.planned_duration_sec}s
                </div>
                <div>{s.narration}</div>
                <div className="mt-1 text-xs text-slate-400">🎬 {s.visual_prompt}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
