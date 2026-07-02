import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import {
  ArrowLeft,
  FolderInput,
  FolderOpen,
  CheckCircle2,
  AlertTriangle,
  Image as ImageIcon,
  Sparkles,
  ExternalLink,
} from "lucide-react";
import { Link } from "react-router-dom";
import { ApiError, api } from "../lib/api";
import "../lib/pywebview";

type InspectResult = Awaited<ReturnType<typeof api.inspectFolder>>;

export default function NewProject() {
  const nav = useNavigate();
  const [form, setForm] = useState({
    source: "",
    date: "",
    location: "",
    site: "",
    treatment: "",
    interval: "",
    is_sentinel: false,
  });
  const [inspect, setInspect] = useState<InspectResult | null>(null);
  const [picking, setPicking] = useState(false);

  const ingest = useMutation({
    mutationFn: () => api.ingestProject(form),
    onSuccess: (project) => nav(`/projects/${project.id}`),
  });

  const update = (k: keyof typeof form) => (v: string | boolean) =>
    setForm((f) => ({ ...f, [k]: v }));

  /** Set the source path and run inspect-folder. Auto-fills fields if the
   * folder name (or its parent) matches the lab convention. */
  const setSourceAndInspect = async (path: string) => {
    setForm((f) => ({ ...f, source: path }));
    setInspect(null);
    if (!path) return;
    try {
      const result = await api.inspectFolder(path);
      setInspect(result);
      const parsed = result.parsed ?? result.parent_parsed ?? null;
      if (parsed) {
        setForm((f) => ({ ...f, ...parsed }));
      }
    } catch (e) {
      setInspect({
        exists: false, is_dir: false, name: "", image_count: 0,
        parsed: null, parent_parsed: null, parent_name: null,
        suggested_path: null, conflict_project_id: null,
        conflict_project_folder: null,
        suggestion_reason: (e as Error).message,
      });
    }
  };

  const handlePick = async () => {
    const pickFolder = window.pywebview?.api?.pick_folder;
    if (!pickFolder) {
      alert("Native folder picker is only available in the desktop app. " +
        "In the browser, paste the folder path manually below.");
      return;
    }
    setPicking(true);
    try {
      const start = form.source || "/Volumes";
      const chosen = await pickFolder(start);
      if (chosen) await setSourceAndInspect(chosen);
    } finally {
      setPicking(false);
    }
  };

  const useParentFolder = async () => {
    if (!inspect?.suggested_path) return;
    await setSourceAndInspect(inspect.suggested_path);
  };

  const previewName = (() => {
    const { date, location, site, treatment, interval } = form;
    if (![date, location, site, treatment, interval].every(Boolean)) return null;
    return `${date}_${location}_${site}_${treatment}_${interval}`;
  })();

  // Pre-flight conflict from the inspect endpoint (before the user even hits
  // Import). The post-ingest 409 is handled separately below.
  const conflict =
    inspect?.conflict_project_id != null
      ? { id: inspect.conflict_project_id, folder: inspect.conflict_project_folder ?? "" }
      : null;

  // Post-ingest 409 — server returns a structured detail with project_id.
  const ingestConflict = (() => {
    const err = ingest.error as ApiError | null;
    if (!err || err.status !== 409) return null;
    const d = err.detail as { code?: string; project_id?: number; project_folder?: string } | null;
    if (d && d.code === "project_exists" && d.project_id) {
      return { id: d.project_id, folder: d.project_folder ?? "" };
    }
    return null;
  })();

  const blocking = conflict || ingestConflict;
  const allFilled = !!form.source && !!previewName && !blocking;

  return (
    <div className="max-w-2xl mx-auto">
      <Link to="/" className="inline-flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-800 mb-4">
        <ArrowLeft className="h-4 w-4" /> Back
      </Link>

      <h1 className="text-2xl font-semibold tracking-tight">New project from SD card</h1>
      <p className="text-sm text-ink-500 mt-1">
        Pick the project folder (e.g.{" "}
        <code className="mx-0.5">09-03_RG_1_C_1</code>). If you pick the inner{" "}
        <code className="mx-0.5">100RECNX/</code> by accident, we'll figure it
        out. Every copy is verified with a SHA-256 hash.
      </p>

      <div className="card p-6 mt-6 space-y-5">
        <div>
          <label className="label">Source folder</label>

          <div className="flex gap-2">
            <button
              type="button"
              className="btn-primary shrink-0"
              onClick={handlePick}
              disabled={picking}
            >
              <FolderOpen className="h-4 w-4" />
              {picking ? "Opening…" : "Pick folder…"}
            </button>
            <input
              className="input font-mono text-xs"
              placeholder="…or paste an absolute path"
              value={form.source}
              onChange={(e) => update("source")(e.target.value)}
              onBlur={(e) => e.target.value && setSourceAndInspect(e.target.value)}
            />
          </div>

          {inspect && (
            <InspectBanner
              inspect={inspect}
              onUseParent={useParentFolder}
            />
          )}
        </div>

        <div className="grid grid-cols-5 gap-3">
          <Field label="Date (MM-DD)" value={form.date} onChange={update("date")} placeholder="09-03" />
          <Field label="Location" value={form.location} onChange={update("location")} placeholder="RG" />
          <Field label="Site" value={form.site} onChange={update("site")} placeholder="1" />
          <Field label="Treatment" value={form.treatment} onChange={update("treatment")} placeholder="C" />
          <Field label="Interval" value={form.interval} onChange={update("interval")} placeholder="1" />
        </div>

        <label className="flex items-center gap-2 text-sm text-ink-700">
          <input
            type="checkbox"
            checked={form.is_sentinel}
            onChange={(e) => update("is_sentinel")(e.target.checked)}
            className="h-4 w-4 rounded border-ink-300"
          />
          This is a Sentinel camera (uses SentinelData/ tree)
        </label>

        {previewName && !blocking && (
          <div className="rounded-md bg-ink-50 border border-ink-200 px-3 py-2.5">
            <div className="text-xs text-ink-500 mb-0.5">Will create folder</div>
            <div className="font-mono text-sm text-ink-900">{previewName}</div>
          </div>
        )}

        {blocking && (
          <ConflictBanner
            existingId={blocking.id}
            folder={blocking.folder || previewName || ""}
            onView={() => nav(`/projects/${blocking.id}`)}
          />
        )}

        {ingest.error && !ingestConflict && (
          <div className="rounded-md bg-red-50 border border-red-200 px-3 py-2 text-sm text-red-800">
            {(ingest.error as Error).message}
          </div>
        )}

        <div className="flex justify-end">
          <button
            className="btn-primary"
            disabled={ingest.isPending || !allFilled}
            onClick={() => ingest.mutate()}
          >
            <FolderInput className="h-4 w-4" />
            {ingest.isPending ? "Copying images…" :
              inspect?.image_count
                ? `Import & verify ${inspect.image_count.toLocaleString()} images`
                : "Import & verify"}
          </button>
        </div>
      </div>
    </div>
  );
}

function InspectBanner({
  inspect,
  onUseParent,
}: {
  inspect: InspectResult;
  onUseParent: () => void;
}) {
  if (!inspect.exists || !inspect.is_dir) {
    return (
      <div className="mt-2 rounded-md bg-red-50 border border-red-200 px-3 py-2 text-xs text-red-800 flex items-start gap-2">
        <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
        <span>{inspect.suggestion_reason ?? "Folder is not accessible."}</span>
      </div>
    );
  }
  if (inspect.image_count === 0 && !inspect.suggestion_reason?.includes("approximate")) {
    return (
      <div className="mt-2 rounded-md bg-amber-50 border border-amber-200 px-3 py-2 text-xs text-amber-900 flex items-start gap-2">
        <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
        <span>
          No JPGs found under <code>{inspect.name}</code>. Did you pick the
          right folder?
        </span>
      </div>
    );
  }
  const usingParent = !inspect.parsed && !!inspect.parent_parsed;
  return (
    <div className="mt-2 rounded-md bg-emerald-50 border border-emerald-200 px-3 py-2 text-xs text-emerald-900 space-y-1.5">
      <div className="flex items-center gap-2">
        <ImageIcon className="h-4 w-4" />
        <span>
          <strong>{inspect.image_count.toLocaleString()}</strong> JPGs found in{" "}
          <code>{inspect.name}</code>
        </span>
      </div>
      {(inspect.parsed || usingParent) && (
        <div className="flex items-start gap-2">
          <Sparkles className="h-3.5 w-3.5 mt-0.5 shrink-0" />
          <span>
            {usingParent
              ? <>Auto-filled from the parent folder <code>{inspect.parent_name}</code>.</>
              : <>Auto-filled from folder name.</>}
          </span>
        </div>
      )}
      {usingParent && inspect.suggested_path && (
        <button
          type="button"
          className="text-xs underline text-emerald-800 hover:text-emerald-900"
          onClick={onUseParent}
        >
          Switch source to parent folder
        </button>
      )}
      {!inspect.parsed && !usingParent && inspect.suggestion_reason && (
        <div className="flex items-start gap-2 text-emerald-900/80">
          <CheckCircle2 className="h-3.5 w-3.5 mt-0.5 shrink-0" />
          <span>{inspect.suggestion_reason}</span>
        </div>
      )}
    </div>
  );
}

function ConflictBanner({
  folder,
  onView,
}: {
  existingId: number;
  folder: string;
  onView: () => void;
}) {
  return (
    <div className="rounded-md bg-amber-50 border-2 border-amber-300 p-3 flex items-start gap-3">
      <AlertTriangle className="h-5 w-5 text-amber-700 mt-0.5 shrink-0" />
      <div className="flex-1 min-w-0">
        <div className="text-sm font-semibold text-amber-900">
          You've already imported this project.
        </div>
        <p className="text-xs text-amber-800 mt-0.5">
          A project named <code className="font-mono">{folder}</code> already
          exists in this app. Open it to keep working, or pick a different
          source folder.
        </p>
      </div>
      <button className="btn-primary shrink-0" onClick={onView}>
        <ExternalLink className="h-4 w-4" />
        Open existing
      </button>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
}) {
  return (
    <div>
      <label className="label">{label}</label>
      <input
        className="input"
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}
