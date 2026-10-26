"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  createContext,
  useContext,
  useEffect,
  useState,
  ReactNode,
} from "react";
import {
  LayoutDashboard,
  Bot,
  Factory,
  CalendarRange,
  Package,
  Library,
  Settings,
  PanelLeftClose,
  PanelLeftOpen,
  Moon,
  Sun,
  Bell,
  ChevronRight,
  Layers,
  ExternalLink,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { api, query, Scope, Dashboard, Health, Answer } from "@/lib/api";
const nav = [
  ["dashboard", "Dashboard", LayoutDashboard],
  ["ai-expert", "AI Production Expert", Bot],
  ["production", "Production Monitoring", Factory],
  ["planning", "Production Planning", CalendarRange],
  ["inventory", "Inventory Management", Package],
  ["knowledge", "Knowledge Base", Library],
  ["settings", "Settings", Settings],
] as const;
type Message = { role: "user" | "assistant"; text: string; answer?: Answer };
type State = {
  scope: Scope;
  setScope: (s: Scope) => void;
  data?: Dashboard;
  health?: Health;
  loading: boolean;
  error: string;
  messages: Message[];
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  refresh: () => void;
};
const Context = createContext<State | null>(null);
export function useWorkspace() {
  const c = useContext(Context);
  if (!c) throw new Error("Workspace context missing.");
  return c;
}
export default function Workspace({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(false);
  const [mobile, setMobile] = useState(false);
  const [dark, setDark] = useState(false);
  const [ready, setReady] = useState(false);
  const [scope, setScope] = useState<Scope>({
    start: "",
    end: "",
    machine: "",
    product: "",
    shift: "All",
    source: "reviewed",
  });
  const [options, setOptions] = useState<{
    machines: string[];
    products: string[];
  }>({ machines: [], products: [] });
  const [data, setData] = useState<Dashboard>();
  const [health, setHealth] = useState<Health>();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [version, setVersion] = useState(0);
  const [messages, setMessages] = useState<Message[]>([]);
  useEffect(() => {
    const isDark = localStorage.getItem("manufacturing-theme") === "dark";
    setDark(isDark);
    document.documentElement.classList.toggle("dark", isDark);
    const q = new URLSearchParams(window.location.search);
    setScope((s) => ({
      ...s,
      source: q.get("source") === "demo" ? "demo" : "reviewed",
    }));
    setReady(true);
    api<Health>("/health")
      .then(setHealth)
      .catch(() => {});
  }, []);
  // Route navigation owns the machine on detail pages. Query strings preserve
  // the same scope when moving between regular workspace sections.
  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    const machine = pathname.startsWith("/production/")
      ? pathname.split("/")[2]
      : q.get("machine") || "";
    setScope((previous) =>
      previous.machine === machine ? previous : { ...previous, machine },
    );
  }, [pathname]);
  useEffect(() => {
    if (!ready) return;
    let active = true;
    api<{ dates: string[]; machines: string[]; products: string[] }>(
      "/production/options?source=" + scope.source,
    )
      .then((o) => {
        if (!active) return;
        setOptions(o);
        setScope((s) => {
          if (s.start && s.end) return s;
          const saved = new URLSearchParams(window.location.search);
          const q =
            (saved.get("source") || "reviewed") === s.source
              ? saved
              : new URLSearchParams();
          const end =
            q.get("end") ||
            o.dates.at(-1) ||
            new Date().toISOString().slice(0, 10);
          const start = new Date(end + "T12:00:00");
          start.setDate(start.getDate() - 6);
          return {
            ...s,
            end,
            start: q.get("start") || start.toISOString().slice(0, 10),
            machine: pathname.startsWith("/production/")
              ? pathname.split("/")[2]
              : q.get("machine") || "",
            product: q.get("product") || "",
            shift: (q.get("shift") as Scope["shift"]) || "All",
          };
        });
      })
      .catch((e) => {
        setError(String(e.message));
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [scope.source, ready, version]);
  useEffect(() => {
    if (!scope.start || !scope.end) return;
    let active = true;
    setLoading(true);
    setError("");
    setData(undefined);
    api<Dashboard>("/dashboard/summary?" + query(scope))
      .then((d) => {
        if (active) setData(d);
      })
      .catch((e) => {
        if (active) setError(e.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    window.history.replaceState(null, "", pathname + "?" + query(scope));
    return () => {
      active = false;
    };
  }, [scope, version, pathname]);
  const section = pathname.split("/")[1] || "dashboard";
  const title =
    nav.find(([route]) => route === section)?.[1] || "Machine details";
  function theme() {
    const value = !dark;
    setDark(value);
    document.documentElement.classList.toggle("dark", value);
    localStorage.setItem("manufacturing-theme", value ? "dark" : "light");
  }
  return (
    <Context.Provider
      value={{
        scope,
        setScope,
        data,
        health,
        loading,
        error,
        messages,
        setMessages,
        refresh: () => setVersion((v) => v + 1),
      }}
    >
      <div className="min-h-screen">
        <aside
          className={`${mobile ? "flex" : "hidden"} lg:flex fixed inset-y-0 left-0 z-40 flex-col bg-[#10263e] text-[#c5d4e4] transition-[width] ${collapsed ? "w-20" : "w-64"}`}
        >
          <Link
            href={"/dashboard?" + query(scope)}
            className="flex items-center gap-3 border-b border-white/10 p-6 text-white"
          >
            <span className="rounded-lg bg-[#31597d] p-2">
              <Layers size={21} />
            </span>
            {!collapsed && (
              <span>
                <strong className="block text-[15px]">Manufacturing AI</strong>
                <small className="text-[10px] uppercase tracking-[2px] text-slate-400">
                  Operations workspace
                </small>
              </span>
            )}
          </Link>
          <div className="flex-1 space-y-1 p-3 pt-7">
            {!collapsed && (
              <p className="px-3 pb-3 text-[10px] tracking-[2px] text-slate-400">
                WORKSPACE
              </p>
            )}
            {nav.map(([route, label, Icon]) => (
              <Link
                key={route}
                title={label}
                href={"/" + route + "?" + query(scope)}
                onClick={() => setMobile(false)}
                className={`flex min-h-11 items-center gap-3 rounded-lg px-3 py-3 text-[13px] ${section === route ? "bg-[#285277] text-white" : "hover:bg-white/5 hover:text-white"}`}
              >
                <Icon size={18} />
                {!collapsed && label}
              </Link>
            ))}
          </div>
          {!collapsed && (
            <div className="m-4 rounded-lg border border-white/10 p-4 text-xs leading-6 text-slate-400">
              Local development
              <br />
              <span className="text-slate-200">
                Historical data · Human decisions
              </span>
            </div>
          )}
          <Button
            variant="ghost"
            className="m-3 text-slate-300 hover:bg-white/10 hover:text-white"
            aria-label="Collapse sidebar"
            onClick={() => setCollapsed((v) => !v)}
          >
            {collapsed ? (
              <PanelLeftOpen size={18} />
            ) : (
              <>
                <PanelLeftClose size={18} />
                <span className="ml-2 text-xs">Collapse navigation</span>
              </>
            )}
          </Button>
        </aside>
        {mobile && (
          <button
            aria-label="Close mobile navigation"
            className="fixed inset-0 z-30 bg-black/40 lg:hidden"
            onClick={() => setMobile(false)}
          />
        )}
        <div className={`${collapsed ? "lg:ml-20" : "lg:ml-64"}`}>
          <header className="flex h-[76px] items-center justify-between gap-3 border-b border-border bg-card px-5 md:px-9">
            <div className="flex items-center gap-3 text-xs muted">
              <Button
                className="lg:hidden"
                variant="ghost"
                size="icon"
                aria-label="Open navigation"
                onClick={() => setMobile((v) => !v)}
              >
                <PanelLeftOpen size={18} />
              </Button>
              <span className="hidden md:inline">Operations</span>
              <ChevronRight size={13} />
              <span className="font-medium text-foreground">{title}</span>
            </div>
            <div className="flex items-center gap-3">
              <Badge variant="outline" className="hidden sm:inline-flex">
                Local workspace
              </Badge>
              <Button
                variant="ghost"
                size="icon"
                aria-label="Toggle theme"
                onClick={theme}
              >
                {dark ? <Sun size={18} /> : <Moon size={18} />}
              </Button>
              <Button
                variant="ghost"
                size="icon"
                aria-label="Notifications not connected"
                title="Notifications are not connected"
                onClick={() =>
                  window.alert(
                    "Notifications are a placeholder; no notification service is connected.",
                  )
                }
              >
                <Bell size={18} />
              </Button>
              <span
                className="grid size-8 place-items-center rounded-full bg-secondary text-xs font-semibold"
                title="Local user placeholder; authentication not implemented"
              >
                M
              </span>
            </div>
          </header>
          <main className="mx-auto max-w-[1640px] space-y-6 p-5 md:p-9">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <div className="eyebrow mb-2">
                  Separator manufacturing / Slitting operations
                </div>
                <h1>{title}</h1>
                <p className="mt-1 text-sm muted">
                  A clear view of production, evidence and operating
                  assumptions.
                </p>
              </div>
              <a
                href="http://127.0.0.1:8502/"
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-2 text-xs muted"
              >
                <ExternalLink size={13} />
                Streamlit fallback
              </a>
            </div>
            <section
              className="panel grid grid-cols-2 gap-4 xl:grid-cols-6"
              aria-label="Production filters"
            >
              <div>
                <label htmlFor="data-source">Data source</label>
                <select
                  id="data-source"
                  value={scope.source}
                  onChange={(e) => {
                    const next = {
                      ...scope,
                      source: e.target.value as Scope["source"],
                      start: "",
                      end: "",
                      machine: "",
                      product: "",
                    };
                    setScope(next);
                    if (pathname.startsWith("/production/"))
                      router.push("/production?" + query(next));
                  }}
                >
                  <option value="reviewed">Reviewed history</option>
                  <option value="demo">Synthetic demo</option>
                </select>
              </div>
              <div>
                <label htmlFor="start">From</label>
                <Input
                  id="start"
                  type="date"
                  value={scope.start}
                  onChange={(e) =>
                    setScope({ ...scope, start: e.target.value })
                  }
                />
              </div>
              <div>
                <label htmlFor="end">Through</label>
                <Input
                  id="end"
                  type="date"
                  value={scope.end}
                  onChange={(e) => setScope({ ...scope, end: e.target.value })}
                />
              </div>
              <div>
                <label htmlFor="machine">Machine</label>
                <select
                  id="machine"
                  value={scope.machine}
                  onChange={(e) => {
                    const next = { ...scope, machine: e.target.value };
                    if (pathname.startsWith("/production/")) {
                      router.push(
                        (next.machine
                          ? "/production/" + next.machine
                          : "/production") +
                          "?" +
                          query(next),
                      );
                    } else setScope(next);
                  }}
                >
                  <option value="">All machines</option>
                  {options.machines.map((m) => (
                    <option key={m}>{m}</option>
                  ))}
                </select>
              </div>
              <div>
                <label htmlFor="shift">Shift</label>
                <select
                  id="shift"
                  value={scope.shift}
                  onChange={(e) =>
                    setScope({
                      ...scope,
                      shift: e.target.value as Scope["shift"],
                    })
                  }
                >
                  <option value="All">All recorded shifts</option>
                  <option value="Day">Day</option>
                  <option value="Night">Night</option>
                </select>
              </div>
              <div>
                <label htmlFor="product">Product</label>
                <select
                  id="product"
                  value={scope.product}
                  onChange={(e) =>
                    setScope({ ...scope, product: e.target.value })
                  }
                >
                  <option value="">All specifications</option>
                  {options.products.map((p) => (
                    <option key={p}>{p}</option>
                  ))}
                </select>
              </div>
            </section>
            {scope.source === "demo" && (
              <div className="note font-semibold">
                SYNTHETIC DEMONSTRATION — all production in this mode is
                artificial, not company records.
              </div>
            )}
            {error && (
              <div
                role="alert"
                className="panel flex items-center justify-between border-destructive text-sm"
              >
                <span>{error}</span>
                <Button
                  variant="outline"
                  onClick={() => setVersion((v) => v + 1)}
                >
                  Retry
                </Button>
              </div>
            )}
            <div className="flex flex-wrap items-center gap-3 text-xs">
              <strong>
                {scope.start} — {scope.end}
              </strong>
              <span>
                {scope.shift === "All"
                  ? "All recorded shifts"
                  : scope.shift + " shift"}
              </span>
              <span>· Up to 30 calendar dates</span>
              {[7, 30].map((days) => (
                <Button
                  key={days}
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    const start = new Date(scope.end + "T12:00:00");
                    start.setDate(start.getDate() - days + 1);
                    setScope({
                      ...scope,
                      start: start.toISOString().slice(0, 10),
                    });
                  }}
                >
                  Last {days} days
                </Button>
              ))}
            </div>
            {children}
            <footer className="border-t border-border pt-5 text-[11px] muted">
              Manufacturing AI · Local development · No MES connection or
              production authentication · Latest reviewed date:{" "}
              {data?.last_recorded_date || "unavailable"}
            </footer>
          </main>
        </div>
      </div>
    </Context.Provider>
  );
}
