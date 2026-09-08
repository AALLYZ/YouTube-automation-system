import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { Badge, Spinner, useAsync } from "../lib/ui";

type Step = { n: number; title: string; done: boolean; detail: string; to?: string };

export default function Setup() {
  const ov = useAsync(() => api.get("/overview"), []);
  const ch = useAsync(() => api.get<any[]>("/channels"), []);
  const first = ch.data?.[0];
  const yt = useAsync(
    () => (first ? api.get(`/youtube/status?channel_id=${first.id}`) : Promise.resolve(null)),
    [first?.id]
  );

  if (ov.loading || ch.loading) return <Spinner />;
  const p = ov.data.providers;
  const stub = (v: string) => v === "stub" || v === "console";

  const steps: Step[] = [
    { n: 1, title: "Admin account", done: true, detail: "Signed in as admin." },
    {
      n: 2,
      title: "Create a channel",
      done: (ch.data?.length ?? 0) > 0,
      detail: `${ch.data?.length ?? 0} channel(s) configured.`,
      to: "/settings",
    },
    {
      n: 3,
      title: "AI provider",
      done: !stub(p.ai),
      detail: `AI_PROVIDER=${p.ai}${stub(p.ai) ? " (stub — set anthropic/openai + key)" : ""}`,
    },
    {
      n: 4,
      title: "Research provider",
      done: !stub(p.research),
      detail: `RESEARCH_PROVIDER=${p.research}`,
    },
    { n: 5, title: "Voice provider", done: !stub(p.voice), detail: `VOICE_PROVIDER=${p.voice}` },
    {
      n: 6,
      title: "Images & stock",
      done: !stub(p.image) || !stub(p.stock),
      detail: `IMAGE_PROVIDER=${p.image}, STOCK_PROVIDER=${p.stock}`,
    },
    {
      n: 7,
      title: "YouTube OAuth",
      done: !!yt.data?.connected,
      detail: yt.data?.connected
        ? `Connected to ${yt.data.youtube_channel_title || "channel"}`
        : yt.data?.configured
        ? "OAuth configured — connect a channel"
        : "Set GOOGLE_CLIENT_ID/SECRET + YOUTUBE_PROVIDER=google",
      to: "/youtube",
    },
    {
      n: 8,
      title: "WhatsApp notifications",
      done: !stub(p.notifier),
      detail: `NOTIFIER_PROVIDER=${p.notifier}`,
      to: "/notifications",
    },
    {
      n: 9,
      title: "Scheduler",
      done: ov.data.automation.scheduler_enabled,
      detail: ov.data.automation.scheduler_enabled
        ? "SCHEDULER_ENABLED=true"
        : "Set SCHEDULER_ENABLED=true and enable automation per channel",
      to: "/automation",
    },
    {
      n: 10,
      title: "Test run",
      done: (ov.data.jobs.total ?? 0) > 0,
      detail: `${ov.data.jobs.total} job(s) created so far.`,
      to: "/automation",
    },
    {
      n: 11,
      title: "Go live",
      done:
        !!yt.data?.connected &&
        ov.data.automation.scheduler_enabled &&
        (ch.data?.length ?? 0) > 0,
      detail: "Channel + YouTube + scheduler all set → automation runs daily.",
    },
  ];

  return (
    <div className="space-y-4">      <p className="text-sm text-slate-500">
        The pipeline runs fully offline on stub providers. Swap in real providers via environment
        variables, then reconnect below.
      </p>
      <ol className="space-y-2">
        {steps.map((s) => (
          <li key={s.n} className="card flex items-start gap-3">
            <div
              className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                s.done ? "bg-green-100 text-green-700" : "bg-slate-100 text-slate-400"
              }`}
            >
              {s.done ? "✓" : s.n}
            </div>
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <span className="font-medium">{s.title}</span>
                <Badge value={s.done ? "ready" : "pending"} />
              </div>
              <div className="text-sm text-slate-500">{s.detail}</div>
            </div>
            {s.to && (
              <Link to={s.to} className="text-sm text-brand-600 hover:underline">
                Open →
              </Link>
            )}
          </li>
        ))}
      </ol>
    </div>
  );
}
