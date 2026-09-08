import { useEffect, useState } from "react";
import { api, authedBlobUrl } from "../lib/api";
import { Badge, ErrorBox, Spinner, money, useAsync } from "../lib/ui";

const HAS_VIDEO = [
  "RENDER", "THUMBNAIL", "METADATA", "FINAL_QA", "APPROVAL_GATE", "UPLOAD", "NOTIFY", "COMPLETE",
];

function VideoCard({ job }: { job: any }) {
  const [url, setUrl] = useState<string | null>(null);
  const [err, setErr] = useState(false);

  useEffect(() => {
    let revoke: string | null = null;
    authedBlobUrl(`/jobs/${job.public_id}/video`)
      .then((u) => {
        revoke = u;
        setUrl(u);
      })
      .catch(() => setErr(true));
    return () => {
      if (revoke) URL.revokeObjectURL(revoke);
    };
  }, [job.public_id]);

  return (
    <div className="card space-y-2">
      <div className="flex items-center justify-between">
        <span className="font-mono text-xs">{job.public_id}</span>
        <Badge value={job.status} />
      </div>
      {url ? (
        <video className="aspect-video w-full rounded bg-black" controls src={url} />
      ) : err ? (
        <div className="aspect-video w-full rounded bg-slate-100 p-4 text-xs text-slate-400">
          Video not available yet.
        </div>
      ) : (
        <div className="aspect-video w-full animate-pulse rounded bg-slate-100" />
      )}
      <div className="flex items-center justify-between text-xs text-slate-500">
        <span>{job.current_stage}</span>
        <span>{money(job.total_cost_usd)}</span>
      </div>
    </div>
  );
}

export default function Videos() {
  const jobs = useAsync(() => api.get<any[]>("/jobs"), []);
  if (jobs.loading) return <Spinner />;
  if (jobs.error) return <ErrorBox msg={jobs.error} />;

  const withVideo = jobs.data!.filter((j) => HAS_VIDEO.includes(j.current_stage));

  return (
    <div className="space-y-4">      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {withVideo.map((j) => (
          <VideoCard key={j.public_id} job={j} />
        ))}
        {withVideo.length === 0 && (
          <div className="text-sm text-slate-400">No rendered videos yet.</div>
        )}
      </div>
    </div>
  );
}
