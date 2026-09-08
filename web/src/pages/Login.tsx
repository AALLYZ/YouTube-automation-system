import { FormEvent, useEffect, useState } from "react";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";

type Mode = "signin" | "register" | "forgot" | "reset";

export default function Login() {
  const { login, register } = useAuth();

  const resetToken = new URLSearchParams(window.location.search).get("token");
  const [mode, setMode] = useState<Mode>(
    resetToken || window.location.pathname.includes("reset-password") ? "reset" : "signin"
  );
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [password2, setPassword2] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [canRegister, setCanRegister] = useState(false);

  useEffect(() => {
    api
      .get<{ registration_enabled: boolean }>("/auth/config")
      .then((c) => setCanRegister(c.registration_enabled))
      .catch(() => {});
  }, []);

  function go(m: Mode) {
    setMode(m);
    setErr(null);
    setNotice(null);
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setErr(null);
    setNotice(null);
    setBusy(true);
    try {
      if (mode === "signin") {
        await login(email, password);
      } else if (mode === "register") {
        if (password !== password2) throw new Error("Passwords do not match");
        if (password.length < 8) throw new Error("Password must be at least 8 characters");
        await register(email, password);
      } else if (mode === "forgot") {
        const r = await api.post<{ message: string; reset_token?: string }>("/auth/forgot-password", {
          email,
        });
        setNotice(
          r.reset_token
            ? `${r.message}\n\nDev token (no email configured):\n${r.reset_token}`
            : r.message
        );
      } else if (mode === "reset") {
        if (password !== password2) throw new Error("Passwords do not match");
        await api.post("/auth/reset-password", { token: resetToken, password });
        setNotice("Password updated. Sign in with your new password.");
        setMode("signin");
        setPassword("");
        setPassword2("");
      }
    } catch (e: any) {
      setErr(e.message || "Something went wrong");
    } finally {
      setBusy(false);
    }
  }

  const titles: Record<Mode, string> = {
    signin: "Sign in",
    register: "Create your account",
    forgot: "Reset your password",
    reset: "Choose a new password",
  };
  const cta: Record<Mode, string> = {
    signin: "Sign in",
    register: "Create account",
    forgot: "Send reset link",
    reset: "Update password",
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden p-4">
      <div className="absolute inset-0 bg-gradient-to-br from-[#1e1b4b] via-[#3730a3] to-[#7e22ce]" />
      <div className="absolute inset-0 opacity-40 [background:radial-gradient(40rem_40rem_at_20%_-10%,rgba(168,85,247,.55),transparent),radial-gradient(36rem_36rem_at_100%_100%,rgba(236,72,153,.4),transparent)]" />

      <div className="relative w-full max-w-sm">
        <div className="mb-5 flex items-center gap-2 text-white">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-white/15 text-lg">▶</span>
          <span className="text-lg font-bold tracking-tight">YouTube Automation</span>
        </div>

        <form
          onSubmit={submit}
          className="space-y-4 rounded-2xl border border-white/60 bg-white/95 p-6 shadow-2xl backdrop-blur"
        >
          <div>
            <h1 className="text-lg font-semibold text-slate-800">{titles[mode]}</h1>
            <p className="mt-0.5 text-sm text-slate-500">
              {mode === "signin" && "Welcome back to the admin dashboard."}
              {mode === "register" && "Set up access to the automation dashboard."}
              {mode === "forgot" && "We'll issue a reset link valid for 30 minutes."}
              {mode === "reset" && "Enter a new password for your account."}
            </p>
          </div>

          {err && <div className="rounded-lg bg-rose-50 p-2.5 text-sm text-rose-700">⚠ {err}</div>}
          {notice && (
            <div className="whitespace-pre-wrap break-words rounded-lg bg-emerald-50 p-2.5 text-sm text-emerald-800">
              {notice}
            </div>
          )}
          {mode === "register" && !canRegister && (
            <div className="rounded-lg bg-amber-50 p-2.5 text-sm text-amber-800">
              Sign-up is invite-only. Ask an administrator to enable open registration
              (<code className="text-xs">AUTH_ALLOW_REGISTRATION=true</code>) or to create your account.
            </div>
          )}

          {mode !== "reset" && (
            <label className="block text-sm">
              <span className="mb-1 block font-medium text-slate-600">Email</span>
              <input
                className="input"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </label>
          )}

          {mode !== "forgot" && (
            <label className="block text-sm">
              <span className="mb-1 block font-medium text-slate-600">
                {mode === "reset" ? "New password" : "Password"}
              </span>
              <input
                className="input"
                type="password"
                autoComplete={mode === "signin" ? "current-password" : "new-password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={mode === "signin" ? undefined : 8}
              />
            </label>
          )}

          {(mode === "register" || mode === "reset") && (
            <label className="block text-sm">
              <span className="mb-1 block font-medium text-slate-600">Confirm password</span>
              <input
                className="input"
                type="password"
                autoComplete="new-password"
                value={password2}
                onChange={(e) => setPassword2(e.target.value)}
                required
              />
            </label>
          )}

          <button className="btn-primary w-full justify-center py-2" disabled={busy}>
            {busy ? "…" : cta[mode]}
          </button>

          <div className="flex items-center justify-between pt-1 text-xs">
            {mode === "signin" ? (
              <>
                <button type="button" className="text-brand-600 hover:underline" onClick={() => go("forgot")}>
                  Forgot password?
                </button>
                <button type="button" className="text-brand-600 hover:underline" onClick={() => go("register")}>
                  Create an account
                </button>
              </>
            ) : (
              <button type="button" className="text-slate-500 hover:underline" onClick={() => go("signin")}>
                ← Back to sign in
              </button>
            )}
          </div>
        </form>

        <p className="mt-4 text-center text-xs text-white/50">
          Self-hosted · registration {canRegister ? "open" : "invite-only"}
        </p>
      </div>
    </div>
  );
}
