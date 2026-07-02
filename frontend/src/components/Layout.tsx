import { Link, NavLink, Outlet } from "react-router-dom";
import { Camera, Settings as SettingsIcon, LayoutGrid } from "lucide-react";
import { cn } from "../lib/cn";

const nav = [
  { to: "/", label: "Dashboard", icon: LayoutGrid },
  { to: "/settings", label: "Settings", icon: SettingsIcon },
];

export default function Layout() {
  return (
    <div className="min-h-screen flex flex-col">
      <header className="border-b border-ink-200 bg-white">
        <div className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2 text-ink-900 font-semibold tracking-tight">
            <Camera className="h-5 w-5" />
            <span>Python Lure</span>
          </Link>
          <nav className="flex items-center gap-1">
            {nav.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                end={to === "/"}
                className={({ isActive }) =>
                  cn(
                    "inline-flex items-center gap-2 px-3 py-1.5 rounded-md text-sm transition-colors",
                    isActive ? "bg-ink-900 text-white" : "text-ink-700 hover:bg-ink-100"
                  )
                }
              >
                <Icon className="h-4 w-4" />
                {label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main className="flex-1 max-w-7xl w-full mx-auto px-6 py-8">
        <Outlet />
      </main>
    </div>
  );
}
