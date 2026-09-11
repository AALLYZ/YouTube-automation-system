import { useState } from "react";
import { api } from "../lib/api";
import { ChannelSelect, useChannels } from "../lib/channels";
import { Badge, ErrorBox, Spinner, useAsync } from "../lib/ui";

type Tab = "generate" | "link";

export default function Topics() {
  const { channels, selected, choose } = useChannels();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("generate");
  const [linkUrl, setLinkUrl] = useState("");

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

  const tabBtn = (id: Tab, label: string) => (
    <button
      className={`border-b-2 px-3 py-2 text-sm font-medium transition ${
        tab === id
          ? "border-brand-500 text-brand-700"
          : "border-transparent text-slate-400 hover:text-slate-600"
      }`}
      onClick={() => setTab(id)}
    >
      {label}
    </button>
  );

  async function runLink() {
    const url = linkUrl.trim();
    if (!url || !selected) return;
    await run(() => api.post(`/channels/${selected}/topics:from_link`, { url, count: 6 }));
    setLinkUrl("");
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <ChannelSelect channels={channels} selected={selected} onChange={choose} />
      </div>

      <div className="flex gap-1 border-b border-slate-200">
        {tabBtn("generate", "✨ Generate")}
        {tabBtn("link", "🔗 From Any Link")}
      </div>

      {tab === "generate" && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <button
              className="btn-primary"
              disabled={!selected || busy}
              onClick={() => run(() => api.post(`/channels/${selected}/topics:generate`, { count: 8 }))}
            >
              Generate 8
            </button>
            <button
              className="btn-ghost"
              disabled={!selected || busy}
              title="Pull what's currently trending on YouTube and rewrite it into original, channel-specific topic ideas — no copied titles, descriptions, or wording."
              onClick={() =>
                run(() =>
                  api.post(`/channels/${selected}/topics:from_trending`, {
                    region_code: "US",
                    max_results: 10,
                    count: 6,
                  })
                )
              }
            >
              🔥 From YouTube Trending
            </button>
          </div>
          <p className="text-xs text-slate-400">
            "From YouTube Trending" only uses trending videos as a subject signal — every
            generated topic is written fresh by AI, so nothing is copied from the original video.
          </p>
        </div>
      )}

      {tab === "link" && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <input
              className="input flex-1"
              placeholder="Paste any article, blog post, or video page URL…"
              value={linkUrl}
              onChange={(e) => setLinkUrl(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && runLink()}
              disabled={!selected || busy}
            />
            <button
              className="btn-primary shrink-0"
              disabled={!selected || !linkUrl.trim() || busy}
              onClick={runLink}
            >
              Extract &amp; Generate
            </button>
          </div>
          <p className="text-xs text-slate-400">
            We fetch the page and extract its text as a subject signal only — the AI is
            instructed never to quote or closely paraphrase it, so every generated topic (and the
            script written from it later) is original content, not a rewrite of the source page.
          </p>
        </div>
      )}

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
                      {t.source === "youtube_trending" && (
                        <span
                          className="badge mt-1 w-fit whitespace-nowrap bg-orange-50 text-orange-700 ring-orange-200"
                          title={`Inspired by trending: ${(t.source_ref?.trending_videos || [])
                            .map((v: any) => v.title)
                            .join(", ")}`}
                        >
                          🔥 trending-inspired
                        </span>
                      )}
                      {t.source === "web_link" && (
                        <span
                          className="badge mt-1 w-fit whitespace-nowrap bg-sky-50 text-sky-700 ring-sky-200"
                          title={`Inspired by: ${t.source_ref?.title || t.source_ref?.url || ""}`}
                        >
                          🔗 {t.source_ref?.domain || "link"}-inspired
                        </span>
                      )}
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
