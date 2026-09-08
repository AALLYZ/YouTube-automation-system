import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { Icon, IconName } from "../lib/icons";

const NAV: [string, string, IconName][] = [
  ["/", "Overview", "overview"],
  ["/automation", "Automation", "automation"],
  ["/topics", "Topics", "topics"],
  ["/scripts", "Scripts", "scripts"],
  ["/videos", "Videos", "videos"],
  ["/youtube", "YouTube", "youtube"],
  ["/notifications", "Notifications", "bell"],
  ["/logs", "Logs", "logs"],
  ["/settings", "Settings", "settings"],
  ["/setup", "Setup Wizard", "wizard"],
];

const TITLES: Record<string, string> = Object.fromEntries(NAV.map(([p, l]) => [p, l]));

export default function Layout() {
  const { user, logout } = useAuth();
  const { pathname } = useLocation();
  const title = TITLES[pathname] || "Dashboard";

  return (
    <div className="flex min-h-screen">
      <aside className="relative w-60 shrink-0 overflow-hidden text-slate-300">
        <div className="absolute inset-0 bg-gradient-to-b from-[#1e1b4b] via-[#312e81] to-[#4c1d95]" />
        <div className="absolute inset-0 opacity-40 [background:radial-gradient(30rem_20rem_at_-20%_0%,rgba(139,92,246,.6),transparent)]" />
        <div className="relative flex h-full flex-col">
          <div className="flex items-center gap-2 px-5 py-5">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-white/10 text-lg">▶</span>
            <span className="text-sm font-bold tracking-tight text-white">YT Automation</span>
          </div>
          <nav className="flex flex-1 flex-col gap-1 px-3">
            {NAV.map(([to, label, ic]) => {
              const I = Icon[ic];
              return (
                <NavLink
                  key={to}
                  to={to}
                  end={to === "/"}
                  className={({ isActive }) =>
                    `group flex items-center gap-3 rounded-xl px-3 py-2 text-sm transition ${
                      isActive
                        ? "bg-white/15 font-semibold text-white shadow-inner ring-1 ring-white/10"
                        : "text-slate-300/80 hover:bg-white/10 hover:text-white"
                    }`
                  }
                >
                  <I className="h-[18px] w-[18px] opacity-90" />
                  {label}
                </NavLink>
              );
            })}
          </nav>
          <div className="px-5 py-4 text-[11px] text-slate-400/70">v0.1.0 · all systems go</div>
        </div>
      </aside>

      <div className="flex flex-1 flex-col">
        <header className="sticky top-0 z-10 flex items-center justify-between border-b border-white/60 bg-white/70 px-6 py-3 backdrop-blur-md">
          <h1 className="text-lg font-semibold text-slate-800">{title}</h1>
          <div className="flex items-center gap-3 text-sm">
            <span className="hidden text-slate-500 sm:inline">{user?.email}</span>
            <span className="grid h-8 w-8 place-items-center rounded-full bg-gradient-to-br from-brand-500 to-fuchsia-500 text-xs font-bold text-white">
              {(user?.email?.[0] || "?").toUpperCase()}
            </span>
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
