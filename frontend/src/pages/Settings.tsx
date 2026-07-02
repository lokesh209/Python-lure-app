import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  FolderOpen,
  Save,
  Sparkles,
} from "lucide-react";
import { api } from "../lib/api";
import type { SettingsPatch } from "../lib/types";
import { HiPerGatorCard } from "../components/HiPerGatorCard";
import "../lib/pywebview";

export default function Settings() {
  const qc = useQueryClient();
  const settings = useQuery({ queryKey: ["settings"], queryFn: api.settings });
  const health = useQuery({ queryKey: ["health"], queryFn: api.health });

  const save = useMutation({
    mutationFn: (body: SettingsPatch) => api.patchSettings(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["settings"] });
      qc.invalidateQueries({ queryKey: ["health"] });
      qc.invalidateQueries({ queryKey: ["hpg-status"] });
    },
  });

  // --- Local form state, hydrated from server ---
  const [gatorlink, setGatorlink] = useState("");
  const [dataRoot, setDataRoot] = useState("");
  const [confThreshold, setConfThreshold] = useState(0.05);
  const [detector, setDetector] = useState("hipergator");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [advanced, setAdvanced] = useState({
    ssh_alias: "",
    remote_base: "",
    conda_env: "",
    account: "",
    qos: "",
    partition: "",
    gres: "",
    mem: "8gb",
    email: "",
    poll_sec: 20,
  });

  useEffect(() => {
    const s = settings.data;
    if (!s) return;
    setGatorlink(s.gatorlink ?? "");
    setDataRoot(s.data_root);
    setConfThreshold(s.conf_threshold);
    setDetector(s.detector || "hipergator");
    setAdvanced({
      ssh_alias: s.hipergator.ssh_alias,
      remote_base: s.hipergator.remote_base,
      conda_env: s.hipergator.conda_env,
      account: s.hipergator.account,
      qos: s.hipergator.qos,
      partition: s.hipergator.partition,
      gres: s.hipergator.gres,
      mem: s.hipergator.mem,
      email: s.hipergator.email,
      poll_sec: s.hipergator.poll_sec,
    });
  }, [settings.data]);

  const pickDataRoot = async () => {
    const pick = window.pywebview?.api?.pick_folder;
    if (!pick) {
      alert("Native folder picker is only available in the desktop app.");
      return;
    }
    const chosen = await pick(dataRoot || "/Volumes");
    if (chosen) setDataRoot(chosen);
  };

  const onSave = () => {
    const body: SettingsPatch = {};
    const s = settings.data;
    if (!s) return;
    if (gatorlink && gatorlink !== (s.gatorlink ?? "")) body.gatorlink = gatorlink;
    if (dataRoot !== s.data_root) body.data_root = dataRoot;
    if (confThreshold !== s.conf_threshold) body.conf_threshold = confThreshold;
    if (detector !== s.detector) body.detector = detector;

    if (showAdvanced) {
      const a = advanced; const h = s.hipergator;
      if (a.ssh_alias !== h.ssh_alias) body.hipergator_ssh_alias = a.ssh_alias;
      // If user typed gatorlink, those override the path advanced fields.
      if (!body.gatorlink) {
        if (a.remote_base !== h.remote_base) body.hipergator_remote_base = a.remote_base;
        if (a.conda_env !== h.conda_env) body.hipergator_conda_env = a.conda_env;
        if (a.email !== h.email) body.hipergator_email = a.email;
      }
      if (a.account !== h.account) body.hipergator_account = a.account;
      if (a.qos !== h.qos) body.hipergator_qos = a.qos;
      if (a.partition !== h.partition) body.hipergator_partition = a.partition;
      if (a.gres !== h.gres) body.hipergator_gres = a.gres;
      if (a.mem !== h.mem) body.hipergator_mem = a.mem;
      if (a.poll_sec !== h.poll_sec) body.hipergator_poll_sec = a.poll_sec;
    }

    save.mutate(body);
  };

  const dirty = (() => {
    const s = settings.data;
    if (!s) return false;
    if (gatorlink && gatorlink !== (s.gatorlink ?? "")) return true;
    if (dataRoot !== s.data_root) return true;
    if (confThreshold !== s.conf_threshold) return true;
    if (detector !== s.detector) return true;
    if (showAdvanced) {
      const a = advanced; const h = s.hipergator;
      if (a.ssh_alias !== h.ssh_alias) return true;
      if (a.remote_base !== h.remote_base) return true;
      if (a.conda_env !== h.conda_env) return true;
      if (a.account !== h.account) return true;
      if (a.qos !== h.qos) return true;
      if (a.partition !== h.partition) return true;
      if (a.gres !== h.gres) return true;
      if (a.mem !== h.mem) return true;
      if (a.email !== h.email) return true;
      if (a.poll_sec !== h.poll_sec) return true;
    }
    return false;
  })();

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="text-sm text-ink-500 mt-1">
          Set this up once. Field workers only need to fill in their GatorLink.
        </p>
      </div>

      <HiPerGatorCard />

      <div className="card p-5 space-y-5">
        <div>
          <h2 className="font-semibold">Your GatorLink</h2>
          <p className="text-xs text-ink-500 mt-0.5">
            We use this to find your folder on HiPerGator. Just your username,
            no <code>@ufl.edu</code>.
          </p>
          <div className="mt-2 flex gap-2 items-center">
            <input
              className="input flex-1 font-mono"
              placeholder="e.g. makinenilokesh"
              value={gatorlink}
              onChange={(e) => setGatorlink(e.target.value.trim())}
              autoComplete="off"
            />
            {settings.data?.is_configured && (
              <span className="badge bg-emerald-100 text-emerald-800 inline-flex items-center gap-1">
                <CheckCircle2 className="h-3.5 w-3.5" /> Configured
              </span>
            )}
          </div>
          {gatorlink && (
            <div className="mt-2 rounded-md bg-emerald-50 border border-emerald-200 px-3 py-2 text-xs text-emerald-900 flex items-start gap-2">
              <Sparkles className="h-3.5 w-3.5 mt-0.5 shrink-0" />
              <span>
                Will use <code>/blue/ramccleery/{gatorlink}/lure_runs</code>{" "}
                and email job notifications to <code>{gatorlink}@ufl.edu</code>.
              </span>
            </div>
          )}
        </div>

        <div>
          <h2 className="font-semibold">Where to store images on this Mac</h2>
          <p className="text-xs text-ink-500 mt-0.5">
            All ingested project folders live here. Pick anywhere with enough
            space — an external drive works fine.
          </p>
          <div className="mt-2 flex gap-2">
            <button className="btn-primary shrink-0" onClick={pickDataRoot}>
              <FolderOpen className="h-4 w-4" />
              Pick folder…
            </button>
            <input
              className="input font-mono text-xs"
              value={dataRoot}
              onChange={(e) => setDataRoot(e.target.value)}
            />
          </div>
        </div>

        <div>
          <h2 className="font-semibold">Inference Backend</h2>
          <p className="text-xs text-ink-500 mt-0.5">
            Choose where to run the AI model. HiPerGator is the supercomputer (very fast, requires internet). Local runs directly on your Mac (slower, no internet needed).
          </p>
          <div className="mt-2">
            <select
              className="input text-sm w-full max-w-[200px]"
              value={detector}
              onChange={(e) => setDetector(e.target.value)}
            >
              <option value="hipergator">HiPerGator Cluster</option>
              <option value="local">Local MacBook</option>
              <option value="mock">Mock (Testing only)</option>
            </select>
          </div>
          {detector === "local" && (
            <div className="mt-2 rounded-md bg-amber-50 border border-amber-200 px-3 py-2 text-xs text-amber-900">
              <span className="font-semibold">Warning:</span> Local detection can take 30-45 minutes for a full SD card and your fans will spin up. Only use this if HiPerGator is down or heavily congested!
            </div>
          )}
        </div>

        <div>
          <h2 className="font-semibold">Detection threshold</h2>
          <p className="text-xs text-ink-500 mt-0.5">
            Skip images where MegaDetector's best score is below this. Lower
            = more false positives to review; higher = some real animals
            missed. Lab default is 0.05.
          </p>
          <div className="mt-2 flex items-center gap-3">
            <input
              type="range" min={0.01} max={0.5} step={0.01}
              value={confThreshold}
              onChange={(e) => setConfThreshold(parseFloat(e.target.value))}
              className="flex-1"
            />
            <code className="text-sm w-14 text-right">
              {(confThreshold * 100).toFixed(0)}%
            </code>
          </div>
        </div>

        <button
          type="button"
          className="text-xs text-ink-500 inline-flex items-center gap-1 hover:text-ink-800"
          onClick={() => setShowAdvanced((v) => !v)}
        >
          {showAdvanced ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
          {showAdvanced ? "Hide advanced" : "Show advanced (lab admin only)"}
        </button>

        {showAdvanced && (
          <div className="rounded-md border border-ink-200 bg-ink-50 p-4 space-y-3 text-sm">
            <div className="text-xs text-ink-500 mb-2">
              These are lab-wide values. Don't change unless McCleery has
              asked you to.
            </div>
            <AdvancedRow label="SSH host alias"
              value={advanced.ssh_alias}
              onChange={(v) => setAdvanced((a) => ({ ...a, ssh_alias: v }))} />
            <AdvancedRow label="Remote base path"
              value={advanced.remote_base}
              onChange={(v) => setAdvanced((a) => ({ ...a, remote_base: v }))} />
            <AdvancedRow label="Conda env"
              value={advanced.conda_env}
              onChange={(v) => setAdvanced((a) => ({ ...a, conda_env: v }))} />
            <AdvancedRow label="Email"
              value={advanced.email}
              onChange={(v) => setAdvanced((a) => ({ ...a, email: v }))} />
            <div className="grid grid-cols-2 gap-3">
              <AdvancedRow label="Account"
                value={advanced.account}
                onChange={(v) => setAdvanced((a) => ({ ...a, account: v }))} />
              <AdvancedRow label="QOS"
                value={advanced.qos}
                onChange={(v) => setAdvanced((a) => ({ ...a, qos: v }))} />
              <AdvancedRow label="Partition"
                value={advanced.partition}
                onChange={(v) => setAdvanced((a) => ({ ...a, partition: v }))} />
              <AdvancedRow label="GRES (GPU)"
                value={advanced.gres}
                onChange={(v) => setAdvanced((a) => ({ ...a, gres: v }))} />
              <AdvancedRow label="Memory (RAM)"
                value={advanced.mem}
                onChange={(v) => setAdvanced((a) => ({ ...a, mem: v }))} />
            </div>
          </div>
        )}

        <div className="flex items-center justify-between pt-3 border-t border-ink-100">
          <div className="text-xs text-ink-400">
            Backend: {health.data?.ok ? "Connected" : "—"}
          </div>
          <div className="flex items-center gap-2">
            {save.isSuccess && !dirty && (
              <span className="text-xs text-emerald-700 inline-flex items-center gap-1">
                <CheckCircle2 className="h-3.5 w-3.5" /> Saved
              </span>
            )}
            {save.error && (
              <span className="text-xs text-red-700">
                {(save.error as Error).message}
              </span>
            )}
            <button
              className="btn-primary"
              onClick={onSave}
              disabled={!dirty || save.isPending}
            >
              <Save className="h-4 w-4" />
              {save.isPending ? "Saving…" : "Save"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function AdvancedRow({
  label, value, onChange,
}: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-wide text-ink-500">{label}</div>
      <input
        className="input font-mono text-xs mt-1"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}
