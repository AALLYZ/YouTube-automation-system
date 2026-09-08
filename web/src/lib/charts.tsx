/** Dependency-free inline-SVG charts (CSP-safe). */

type Seg = { label: string; value: number; color: string };

export function Donut({
  segments,
  size = 132,
  thickness = 16,
  centerLabel,
  centerSub,
}: {
  segments: Seg[];
  size?: number;
  thickness?: number;
  centerLabel?: string;
  centerSub?: string;
}) {
  const total = segments.reduce((s, x) => s + x.value, 0);
  const r = (size - thickness) / 2;
  const c = 2 * Math.PI * r;
  let offset = 0;

  return (
    <div className="flex items-center gap-4">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="shrink-0">
        <g transform={`translate(${size / 2} ${size / 2}) rotate(-90)`}>
          <circle r={r} fill="none" stroke="#eef0f6" strokeWidth={thickness} />
          {total > 0 &&
            segments
              .filter((s) => s.value > 0)
              .map((s, i) => {
                const len = (s.value / total) * c;
                const dash = `${len} ${c - len}`;
                const el = (
                  <circle
                    key={i}
                    r={r}
                    fill="none"
                    stroke={s.color}
                    strokeWidth={thickness}
                    strokeDasharray={dash}
                    strokeDashoffset={-offset}
                    strokeLinecap="butt"
                    className="animate-ring"
                    style={{ ["--circ" as any]: `${c}` }}
                  />
                );
                offset += len;
                return el;
              })}
        </g>
        <text
          x="50%"
          y="47%"
          textAnchor="middle"
          className="fill-slate-800"
          style={{ fontSize: 22, fontWeight: 700 }}
        >
          {centerLabel ?? total}
        </text>
        {centerSub && (
          <text
            x="50%"
            y="62%"
            textAnchor="middle"
            className="fill-slate-400"
            style={{ fontSize: 10, letterSpacing: 0.5 }}
          >
            {centerSub}
          </text>
        )}
      </svg>
      <ul className="space-y-1.5 text-sm">
        {segments.map((s) => (
          <li key={s.label} className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: s.color }} />
            <span className="text-slate-500">{s.label}</span>
            <span className="ml-auto font-semibold tabular-nums text-slate-700">{s.value}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function GaugeBar({
  value,
  max,
  unit = "",
  goodBelow = 0.7,
  warnBelow = 0.9,
}: {
  value: number;
  max: number;
  unit?: string;
  goodBelow?: number;
  warnBelow?: number;
}) {
  const pct = max > 0 ? Math.min(1, value / max) : 0;
  const color =
    pct < goodBelow
      ? "from-emerald-400 to-emerald-500"
      : pct < warnBelow
      ? "from-amber-400 to-amber-500"
      : "from-rose-400 to-rose-500";
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between text-sm">
        <span className="font-semibold tabular-nums text-slate-800">
          {value.toLocaleString()}
          {unit}
        </span>
        <span className="text-xs text-slate-400">/ {max.toLocaleString()}</span>
      </div>
      <div className="h-2.5 w-full overflow-hidden rounded-full bg-slate-100">
        <div
          className={`animate-bar h-full rounded-full bg-gradient-to-r ${color}`}
          style={{ width: `${Math.max(pct * 100, 2)}%` }}
        />
      </div>
    </div>
  );
}

export function ProgressBar({ pct, tone = "brand" }: { pct: number; tone?: string }) {
  const grad: Record<string, string> = {
    brand: "from-brand-400 to-brand-600",
    emerald: "from-emerald-400 to-emerald-500",
    rose: "from-rose-400 to-rose-500",
    amber: "from-amber-400 to-amber-500",
  };
  return (
    <div className="h-1.5 w-24 overflow-hidden rounded-full bg-slate-100">
      <div
        className={`animate-bar h-full rounded-full bg-gradient-to-r ${grad[tone] || grad.brand}`}
        style={{ width: `${Math.max(0, Math.min(100, pct))}%` }}
      />
    </div>
  );
}

export function Sparkbars({ data, color = "#6366f1" }: { data: number[]; color?: string }) {
  const max = Math.max(1, ...data);
  return (
    <div className="flex h-8 items-end gap-0.5">
      {data.map((v, i) => (
        <div
          key={i}
          className="w-1.5 rounded-sm"
          style={{ height: `${(v / max) * 100}%`, background: color, opacity: 0.35 + (0.65 * (i + 1)) / data.length }}
        />
      ))}
    </div>
  );
}

const STAGES = [
  "TOPIC", "RESEARCH", "SCRIPT", "SCRIPT_QA", "VOICE", "VISUALS", "SUBTITLES",
  "TIMELINE", "RENDER", "THUMBNAIL", "METADATA", "FINAL_QA", "APPROVAL_GATE",
  "UPLOAD", "NOTIFY", "COMPLETE",
];

export function StageStrip({
  steps,
  current,
  status,
}: {
  steps: Record<string, string>;
  current?: string;
  status?: string;
}) {
  return (
    <div className="flex gap-[3px]" title={`${current || ""} · ${status || ""}`}>
      {STAGES.map((s) => {
        const st = steps[s];
        let cls = "bg-slate-200";
        if (st === "SUCCEEDED") cls = "bg-emerald-400";
        else if (st === "FAILED") cls = "bg-rose-400";
        else if (st === "RUNNING") cls = "bg-sky-400 animate-pulse";
        else if (s === current && status === "WAITING_APPROVAL") cls = "bg-amber-400";
        return <span key={s} className={`h-1.5 flex-1 rounded-full ${cls}`} />;
      })}
    </div>
  );
}
