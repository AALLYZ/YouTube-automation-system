import { FormEvent, useState } from "react";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { Badge, ErrorBox, Spinner, useAsync } from "../lib/ui";

const ROLES = ["admin", "editor", "viewer"];

export default function Users() {
  const { user } = useAuth();
  const users = useAsync(() => api.get<any[]>("/admin/users"), []);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("editor");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (user?.role !== "admin") {
    return <ErrorBox msg="Admin role required to manage users." />;
  }

  async function act(fn: () => Promise<any>) {
    setErr(null);
    setBusy(true);
    try {
      await fn();
      users.reload();
    } catch (e: any) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function create(e: FormEvent) {
    e.preventDefault();
    await act(async () => {
      await api.post("/admin/users", { email, password, role });
      setEmail("");
      setPassword("");
      setRole("editor");
    });
  }

  return (
    <div className="space-y-5">
      {err && <ErrorBox msg={err} />}

      <form onSubmit={create} className="card flex flex-wrap items-end gap-3">
        <div className="min-w-[14rem] flex-1">
          <div className="mb-1 text-xs font-medium text-slate-500">Email</div>
          <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </div>
        <div className="min-w-[10rem] flex-1">
          <div className="mb-1 text-xs font-medium text-slate-500">Temporary password</div>
          <input
            className="input"
            type="text"
            value={password}
            minLength={8}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>
        <div>
          <div className="mb-1 text-xs font-medium text-slate-500">Role</div>
          <select className="input" value={role} onChange={(e) => setRole(e.target.value)}>
            {ROLES.map((r) => (
              <option key={r}>{r}</option>
            ))}
          </select>
        </div>
        <button className="btn-primary" disabled={busy}>
          Add user
        </button>
      </form>

      <div className="card-flush">
        <div className="section-title px-5 pt-4">Team</div>
        {users.loading ? (
          <Spinner />
        ) : users.error ? (
          <div className="p-4"><ErrorBox msg={users.error} /></div>
        ) : (
          <table className="mt-2 w-full">
            <thead>
              <tr>
                <th className="th">Email</th>
                <th className="th">Role</th>
                <th className="th">Status</th>
                <th className="th">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.data!.map((u) => (
                <tr key={u.id} className={u.is_active ? "" : "opacity-50"}>
                  <td className="td">
                    {u.email}
                    {u.id === user!.id && <span className="ml-1 text-xs text-slate-400">(you)</span>}
                  </td>
                  <td className="td">
                    <select
                      className="rounded-md border border-slate-200 bg-white px-1.5 py-0.5 text-xs"
                      value={u.role}
                      disabled={busy}
                      onChange={(e) => act(() => api.patch(`/admin/users/${u.id}`, { role: e.target.value }))}
                    >
                      {ROLES.map((r) => (
                        <option key={r}>{r}</option>
                      ))}
                    </select>
                  </td>
                  <td className="td">
                    <Badge value={u.is_active ? "active" : "disabled"} dot />
                  </td>
                  <td className="td">
                    {u.id !== user!.id && (
                      <button
                        className="btn-ghost !px-2 !py-1"
                        disabled={busy}
                        onClick={() => act(() => api.patch(`/admin/users/${u.id}`, { is_active: !u.is_active }))}
                      >
                        {u.is_active ? "Deactivate" : "Reactivate"}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      <p className="text-xs text-slate-400">
        Share the temporary password with the new user — they can change it via “Forgot password?”.
      </p>
    </div>
  );
}
