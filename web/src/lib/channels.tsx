import { useEffect, useState } from "react";
import { api } from "./api";

export type Channel = {
  id: number;
  name: string;
  slug: string;
  niche: string;
  video_length_min: number;
  is_active: boolean;
  settings?: any;
};

const KEY = "ytauto_channel";

export function useChannels() {
  const [channels, setChannels] = useState<Channel[]>([]);
  const [selected, setSelected] = useState<number | null>(() => {
    const v = Number(localStorage.getItem(KEY));
    return v || null;
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .get<Channel[]>("/channels")
      .then((cs) => {
        setChannels(cs);
        setSelected((cur) => cur ?? cs[0]?.id ?? null);
      })
      .finally(() => setLoading(false));
  }, []);

  function choose(id: number) {
    setSelected(id);
    try {
      localStorage.setItem(KEY, String(id));
    } catch {
      /* ignore */
    }
  }

  return { channels, selected, choose, loading };
}

export function ChannelSelect({
  channels,
  selected,
  onChange,
}: {
  channels: Channel[];
  selected: number | null;
  onChange: (id: number) => void;
}) {
  return (
    <select
      className="input max-w-xs"
      value={selected ?? ""}
      onChange={(e) => onChange(Number(e.target.value))}
    >
      {channels.map((c) => (
        <option key={c.id} value={c.id}>
          {c.name}
        </option>
      ))}
    </select>
  );
}
