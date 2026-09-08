import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../lib/auth";

const NAV = [
  ["/", "Overview"],
  ["/automation", "Automation"],
  ["/topics", "Topics"],
  ["/scripts", "Scripts"],
  ["/videos", "Videos"],
  ["/youtube", "YouTube"],
  ["/notifications", "Notifications"],
  ["/logs", "Logs"],
  ["/settings", "Settings"],
  ["/setup", "Setup Wizard"],
];

export default function Layout() {
  const { user, logout } = useAuth();
  return (
    <div className="flex min-h-screen">
      <aside className="w-56 shrink-0 border-r border-slate-200 bg-white">
        <div className="px-4 py-4 text-sm font-bold tracking-tight text-brand-700">
          ▶ YT Automation
        </div>
        <nav className="flex flex-col gap-0.5 px-2">
          {NAV.map(([to, label]) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                `rounded-md px-3 py-2 text-sm ${
                  isActive
                    ? "bg-brand-50 font-medium text-brand-700"
                    : "text-slate-600 hover:bg-slate-100"
                }`
              }
            >
              {label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <div className="flex flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3">
          <div className="text-sm text-slate-400">Admin dashboard</div>
          <div className="flex items-center gap-3 text-sm">
            <span className="text-slate-500">{user?.email}</span>
            <button className="btn-ghost" onClick={logout}>
              Sign out
            </button>
          </div>
        </header>
        <main className="flex-1 p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
