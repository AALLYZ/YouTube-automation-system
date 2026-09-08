import { Navigate, Route, Routes } from "react-router-dom";
import { useAuth } from "./lib/auth";
import Layout from "./components/Layout";
import Login from "./pages/Login";
import Overview from "./pages/Overview";
import Automation from "./pages/Automation";
import Topics from "./pages/Topics";
import Scripts from "./pages/Scripts";
import Videos from "./pages/Videos";
import YouTube from "./pages/YouTube";
import Notifications from "./pages/Notifications";
import Logs from "./pages/Logs";
import Settings from "./pages/Settings";
import Setup from "./pages/Setup";

export default function App() {
  const { user, loading } = useAuth();

  if (loading) return <div className="p-10 text-slate-400">Loading…</div>;
  if (!user) return <Login />;

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Overview />} />
        <Route path="/automation" element={<Automation />} />
        <Route path="/topics" element={<Topics />} />
        <Route path="/scripts" element={<Scripts />} />
        <Route path="/videos" element={<Videos />} />
        <Route path="/youtube" element={<YouTube />} />
        <Route path="/notifications" element={<Notifications />} />
        <Route path="/logs" element={<Logs />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/setup" element={<Setup />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
