import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, AlertCircle, Loader2, Smartphone, KeyRound, X } from "lucide-react";
import { api } from "../lib/api";
import { cn } from "../lib/cn";

type AuthEvent = { kind: "info" | "duo" | "ok" | "error"; message: string };

export function HiPerGatorCard() {
  const qc = useQueryClient();
  const status = useQuery({
    queryKey: ["hpg-status"],
    queryFn: api.hpgStatus,
    refetchInterval: 30_000,
  });

  const [open, setOpen] = useState(false);

  const forget = useMutation({
    mutationFn: api.hpgForget,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["hpg-status"] }),
  });

  const disconnect = useMutation({
    mutationFn: api.hpgDisconnect,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["hpg-status"] }),
  });

  const s = status.data;
  const tone =
    s?.status === "ok" ? "emerald" :
    s?.status === "expired" ? "amber" :
    s?.status === "no_config" ? "red" : "ink";

  return (
    <div className="card p-5 space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold">HiPerGator</h2>
          <p className="text-xs text-ink-500 mt-0.5">
            Used to run MegaDetector on UF's GPU cluster.
          </p>
        </div>
        <span className={cn(
          "badge inline-flex items-center gap-1.5",
          tone === "emerald" && "bg-emerald-100 text-emerald-800",
          tone === "amber" && "bg-amber-100 text-amber-800",
          tone === "red" && "bg-red-100 text-red-800",
          tone === "ink" && "bg-ink-100 text-ink-700",
        )}>
          {s?.status === "ok" ? <CheckCircle2 className="h-3.5 w-3.5" /> :
           s?.status === "expired" ? <AlertCircle className="h-3.5 w-3.5" /> :
           <AlertCircle className="h-3.5 w-3.5" />}
          {s?.status === "ok" ? "Connected" :
           s?.status === "expired" ? "Needs auth" :
           s?.status === "no_config" ? "Not configured" : "…"}
        </span>
      </div>

      {s?.message && (
        <div className="text-xs text-ink-500">{s.message}</div>
      )}

      <div className="flex flex-wrap gap-2">
        <button
          className="btn-primary"
          onClick={() => setOpen(true)}
          disabled={s?.status === "no_config"}
        >
          <KeyRound className="h-4 w-4" />
          {s?.status === "ok" ? "Re-authenticate" : "Authenticate"}
        </button>
        {s?.status === "ok" && (
          <button
            className="btn-ghost"
            onClick={() => disconnect.mutate()}
            disabled={disconnect.isPending}
            title="Close the active SSH connection"
          >
            Disconnect
          </button>
        )}
        {s?.has_saved_password && (
          <button
            className="btn-ghost text-red-600 hover:text-red-700 hover:bg-red-50"
            onClick={() => forget.mutate()}
            disabled={forget.isPending}
            title="Remove the saved GatorLink password from your Keychain"
          >
            Forget password
          </button>
        )}
      </div>

      {s?.status === "no_config" && (
        <div className="rounded-md bg-red-50 border border-red-200 p-3 text-xs text-red-800 leading-relaxed">
          Your <code>~/.ssh/config</code> is missing a <code>{"hpg"}</code> host
          entry. See <code>docs/lab_admin_setup.md</code> for setup
          instructions.
        </div>
      )}

      {open && (
        <AuthModal
          onClose={() => {
            setOpen(false);
            qc.invalidateQueries({ queryKey: ["hpg-status"] });
          }}
          hasSavedPassword={!!s?.has_saved_password}
        />
      )}
    </div>
  );
}

function AuthModal({ onClose, hasSavedPassword }: { onClose: () => void; hasSavedPassword: boolean }) {
  const [password, setPassword] = useState("");
  const [events, setEvents] = useState<AuthEvent[]>([]);
  const [running, setRunning] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => () => wsRef.current?.close(), []);

  // Automatically trigger authentication if password is saved!
  useEffect(() => {
    if (hasSavedPassword) {
      start(null);
    }
  }, [hasSavedPassword]);

  const start = (pwd: string | null) => {
    setEvents([{ kind: "info", message: "Connecting…" }]);
    setRunning(true);
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${proto}//${window.location.host}/api/hipergator/auth`);
    wsRef.current = ws;
    ws.onopen = () => ws.send(JSON.stringify({ password: pwd ?? undefined }));
    ws.onmessage = (e) => {
      const evt = JSON.parse(e.data) as AuthEvent;
      setEvents((es) => [...es, evt]);
      if (evt.kind === "ok" || evt.kind === "error") setRunning(false);
    };
    ws.onerror = () => {
      setEvents((es) => [...es, { kind: "error", message: "Lost connection to backend." }]);
      setRunning(false);
    };
    ws.onclose = () => setRunning(false);
  };

  const last = events[events.length - 1];
  const succeeded = events.some((e) => e.kind === "ok");

  return (
    <div className="fixed inset-0 z-40 bg-black/40 flex items-center justify-center p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-5 space-y-4 relative">
        <button
          className="absolute top-3 right-3 text-ink-400 hover:text-ink-700"
          onClick={onClose}
        >
          <X className="h-4 w-4" />
        </button>

        <div className="flex items-center gap-2">
          <KeyRound className="h-5 w-5 text-ink-700" />
          <h3 className="font-semibold">Authenticate to HiPerGator</h3>
        </div>

        {!running && events.length === 0 && (
          <>
            <p className="text-sm text-ink-600">
              {hasSavedPassword
                ? "We'll use the GatorLink password saved in your Keychain. You'll get a Duo Push on your phone — just approve it."
                : "Enter your GatorLink password. We'll save it securely and never store it on disk. If you have SSH keys configured, you can leave this blank."}
            </p>
            {!hasSavedPassword && (
              <input
                className="input"
                type="password"
                placeholder="GatorLink password (optional if using SSH keys)"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoFocus
              />
            )}
            <div className="flex gap-2 justify-end">
              <button className="btn-ghost" onClick={onClose}>Cancel</button>
              <button
                className="btn-primary"
                onClick={() => start(hasSavedPassword ? null : password)}
              >
                Start
              </button>
            </div>
          </>
        )}

        {(running || events.length > 0) && (
          <div className="space-y-3">
            <div className="rounded-md border border-ink-200 bg-ink-50 p-3 max-h-60 overflow-y-auto space-y-1.5">
              {events.map((e, i) => (
                <EventLine key={i} evt={e} />
              ))}
              {running && !succeeded && (
                <div className="flex items-center gap-2 text-xs text-ink-500 pt-1 border-t border-ink-200 mt-1">
                  <Loader2 className="h-4 w-4 animate-spin shrink-0" />
                  <span>In progress…</span>
                </div>
              )}
            </div>

            {last?.kind === "duo" && (
              <div className="rounded-md bg-amber-50 border border-amber-200 p-3 text-sm text-amber-900 flex items-center gap-2">
                <Smartphone className="h-5 w-5 animate-pulse" />
                <span>Approve the Duo push on your phone now.</span>
              </div>
            )}

            <div className="flex justify-end">
              <button
                className={succeeded ? "btn-primary" : "btn-ghost"}
                onClick={onClose}
                disabled={running && !succeeded}
              >
                {succeeded ? "Done" : running ? "Working…" : "Close"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function EventLine({ evt }: { evt: AuthEvent }) {
  const Icon =
    evt.kind === "ok" ? CheckCircle2 :
    evt.kind === "error" ? AlertCircle :
    evt.kind === "duo" ? Smartphone :
    CheckCircle2;
  const color =
    evt.kind === "ok" ? "text-emerald-700" :
    evt.kind === "error" ? "text-red-700" :
    evt.kind === "duo" ? "text-amber-700" :
    "text-ink-500";
  return (
    <div className={cn("flex items-start gap-2 text-xs", color)}>
      <Icon className="h-3.5 w-3.5 mt-0.5 shrink-0" />
      <span>{evt.message}</span>
    </div>
  );
}
