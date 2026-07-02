import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Cpu,
  Download,
  PlayCircle,
  Eye,
  Archive,
  CheckCircle2,
  AlertCircle,
  Loader2,
  Trash2,
  XCircle,
} from "lucide-react";
import { api, downloadViaFetch } from "../lib/api";
import { useChannel } from "../lib/ws";
import { StageBadge } from "../components/StageBadge";

export default function Project() {
  const { id } = useParams();
  const projectId = Number(id);
  const qc = useQueryClient();

  // Load global settings to use as defaults
  const settings = useQuery({
    queryKey: ["settings"],
    queryFn: () => api.settings(),
  });

  const [selectedDetector, setSelectedDetector] = useState<string>("local");
  const [selectedMem, setSelectedMem] = useState<string>("8gb");

  // Sync state with global settings once loaded
  useEffect(() => {
    if (settings.data) {
      setSelectedDetector(settings.data.detector || "local");
      setSelectedMem(settings.data.hipergator?.mem || "8gb");
    }
  }, [settings.data]);

  const project = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => api.getProject(projectId),
    refetchInterval: 3000,
  });

  const detectStatus = useQuery({
    queryKey: ["detect-status", projectId],
    queryFn: () => api.detectStatus(projectId),
    refetchInterval: 2500,
    enabled: !!project.data && project.data.stage === "needs_megadetector",
  });

  const detectProgressPoll = useQuery({
    queryKey: ["detect-progress", projectId],
    queryFn: () => api.detectProgress(projectId),
    refetchInterval: 2000,
    enabled: !!project.data && project.data.stage === "needs_megadetector",
  });

  const [ingestProgress, setIngestProgress] = useState<{
    i: number; total: number; current: string;
  } | null>(null);
  const [csvExporting, setCsvExporting] = useState(false);

  const ingestStream = useChannel<{ type: string; i?: number; total?: number; current?: string }>(
    project.data ? `project:${projectId}:ingest` : null
  );
  useEffect(() => {
    if (ingestStream.last?.type === "ingest" &&
      typeof ingestStream.last.i === "number" &&
      typeof ingestStream.last.total === "number") {
      setIngestProgress({
        i: ingestStream.last.i,
        total: ingestStream.last.total,
        current: ingestStream.last.current ?? "",
      });
    }
  }, [ingestStream.last]);

  // Always subscribe to the fixed channel name — survives navigation away
  // and back. The server task keeps running; only the WebSocket reconnects.
  const detectStream = useChannel<{
    type: string; stage: string; pct: number | null; msg: string; detector: string;
  }>(project.data ? `project:${projectId}:detect` : null);

  const mergedDetect = useMemo(() => {
    if (project.data?.stage !== "needs_megadetector") {
      return null;
    }
    const pol = detectProgressPoll.data;
    const ws = detectStream.last;
    if (pol?.stage) {
      return {
        type: "detect" as const,
        stage: pol.stage,
        pct: pol.pct,
        msg: pol.msg,
        detector: pol.detector,
      };
    }
    return ws;
  }, [project.data?.stage, detectProgressPoll.data, detectStream.last]);

  useEffect(() => {
    const s = mergedDetect?.stage;
    if (s === "imported" || s === "error") {
      qc.invalidateQueries({ queryKey: ["project", projectId] });
    }
  }, [mergedDetect?.stage, projectId, qc]);

  const startDetect = useMutation({
    mutationFn: () => api.startDetection(projectId, selectedDetector, selectedMem),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["detect-status", projectId] });
      qc.invalidateQueries({ queryKey: ["detect-running"] });
      qc.invalidateQueries({ queryKey: ["detect-progress", projectId] });
    },
  });

  const cancelDetect = useMutation({
    mutationFn: () => api.cancelDetection(projectId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["detect-status", projectId] });
      qc.invalidateQueries({ queryKey: ["detect-running"] });
      qc.invalidateQueries({ queryKey: ["detect-progress", projectId] });
    },
  });

  const archive = useMutation({
    mutationFn: () => api.patchProject(projectId, { stage: "archived" } as any),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["project", projectId] }),
  });

  const deleteProj = useMutation({
    mutationFn: () => api.deleteProject(projectId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["project"] });
      window.location.href = "/";
    },
  });

  if (project.isLoading) return <div className="text-sm text-ink-500">Loading…</div>;
  if (project.isError) return <div className="text-sm text-red-700">Project not found.</div>;
  const p = project.data!;

  const jobRunning = detectStatus.data?.running ?? false;
  const detectDone =
    mergedDetect?.stage === "imported" ||
    mergedDetect?.stage === "done" ||
    p.stage === "needs_id" ||
    p.stage === "done_id" ||
    p.stage === "archived";
  const detectErr = mergedDetect?.stage === "error";
  const detectPct = mergedDetect?.pct ?? null;
  const showProgress =
    jobRunning ||
    startDetect.isPending ||
    (mergedDetect && !detectDone && !detectErr);

  return (
    <div className="space-y-6">
      <Link to="/" className="inline-flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-800">
        <ArrowLeft className="h-4 w-4" /> Back to dashboard
      </Link>

      <div className="flex items-end justify-between gap-4">
        <div>
          <div className="font-mono text-xl font-semibold">{p.folder}</div>
          <div className="mt-2 flex items-center gap-3 text-sm text-ink-500">
            <StageBadge stage={p.stage} />
            <span>{p.image_count} images</span>
            {p.detection_count > 0 && (
              <span title="Boxes = all MegaDetector hits. To review = images with at least one hit above your confidence threshold (Settings).">
                {p.detection_count} detection boxes · {p.flagged_count} images to review
              </span>
            )}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="btn-secondary"
            disabled={csvExporting}
            onClick={async () => {
              setCsvExporting(true);
              try {
                await downloadViaFetch(api.csvUrl(p.id), `${p.folder}_ImageData.csv`);
              } catch (e) {
                alert(e instanceof Error ? e.message : "Export failed");
              } finally {
                setCsvExporting(false);
              }
            }}
          >
            <Download className="h-4 w-4" /> {csvExporting ? "Exporting…" : "Export CSV"}
          </button>
          {p.stage === "done_id" && (
            <button className="btn-secondary" onClick={() => archive.mutate()} disabled={archive.isPending}>
              <Archive className="h-4 w-4" /> Archive
            </button>
          )}
          <button
            className="btn-secondary text-red-600 hover:text-red-700 hover:bg-red-50"
            onClick={() => {
              if (confirm("Are you sure you want to delete this project? This will erase all its images from your hard drive permanently.")) {
                deleteProj.mutate();
              }
            }}
            disabled={deleteProj.isPending}
          >
            <Trash2 className="h-4 w-4" /> {deleteProj.isPending ? "Deleting…" : "Delete"}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Step
          n={1}
          title="Ingest"
          icon={<CheckCircle2 className="h-5 w-5 text-emerald-600" />}
          done
          body={
            ingestProgress && ingestProgress.i < ingestProgress.total ? (
              <Progress value={ingestProgress.i / ingestProgress.total}
                hint={`${ingestProgress.i} / ${ingestProgress.total}`} />
            ) : (
              <div className="text-sm text-ink-600">{p.image_count} images copied with hash verify</div>
            )
          }
        />

        <Step
          n={2}
          title="MegaDetector"
          icon={
            detectErr ? <AlertCircle className="h-5 w-5 text-red-600" /> :
              detectDone ? <CheckCircle2 className="h-5 w-5 text-emerald-600" /> :
                jobRunning ? <Loader2 className="h-5 w-5 text-ink-600 animate-spin" /> :
                  <Cpu className="h-5 w-5 text-ink-400" />
          }
          done={detectDone}
          body={
            <div className="space-y-3">
              {(detectErr || mergedDetect?.stage === "cancelled") && (
                <div className={`p-3 rounded-lg border flex gap-3 ${detectErr ? "bg-red-50 border-red-100 text-red-800" : "bg-amber-50 border-amber-100 text-amber-800"}`}>
                  {detectErr ? <AlertCircle className="h-5 w-5 shrink-0" /> : <XCircle className="h-5 w-5 shrink-0" />}
                  <div className="text-sm">
                    <div className="font-semibold">{detectErr ? "Detection Failed" : "Job Cancelled"}</div>
                    <div className="mt-0.5 opacity-90">{mergedDetect?.msg}</div>
                  </div>
                </div>
              )}

              {showProgress ? (
                <div className="space-y-2">
                  <Progress
                    value={detectPct ?? (jobRunning ? 0.1 : 0)}
                    hint={
                      jobRunning && !mergedDetect
                        ? "Running detection — safe to leave this page."
                        : (mergedDetect?.msg ?? "")
                    }
                  />
                  <div className="flex items-center justify-between mt-2">
                    <div className="text-xs text-ink-400">
                      {mergedDetect?.detector ? (
                        <span>via {mergedDetect.detector}</span>
                      ) : jobRunning ? (
                        <span>Starting…</span>
                      ) : null}
                    </div>
                    <button
                      className="btn-secondary py-1 px-2 text-xs text-red-600 hover:text-red-700 hover:bg-red-50"
                      disabled={cancelDetect.isPending}
                      onClick={() => {
                        if (confirm("Are you sure you want to stop this detection job?")) {
                          cancelDetect.mutate();
                        }
                      }}
                    >
                      <XCircle className="h-3.5 w-3.5" />
                      {cancelDetect.isPending ? "Stopping…" : "Stop job"}
                    </button>
                  </div>
                </div>
              ) : detectDone ? (
                <div className="text-sm text-ink-600">
                  <CheckCircle2 className="h-4 w-4 inline mr-1 text-emerald-600" />
                  {p.detection_count} detections imported
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="space-y-2 pb-2 mb-2 border-b border-ink-200">
                    <div className="flex justify-between items-center text-sm">
                      <label className="text-ink-600 font-medium">Inference Backend</label>
                      <select
                        className="form-input py-1 px-2 text-xs w-auto min-w-[120px]"
                        value={selectedDetector}
                        onChange={(e) => setSelectedDetector(e.target.value)}
                        disabled={startDetect.isPending}
                      >
                        <option value="local">Local Mac (Apple Silicon)</option>
                        <option value="hipergator">HiPerGator (Remote Cluster)</option>
                      </select>
                    </div>

                    {selectedDetector === "hipergator" && (
                      <div className="flex justify-between items-center text-sm transition-opacity duration-200">
                        <div className="flex flex-col">
                          <label className="text-ink-600 font-medium">HiPerGator Memory</label>
                          <span className="text-[10px] text-ink-400 -mt-1">Try 2GB/4GB to avoid long queues</span>
                        </div>
                        <select
                          className="form-input py-1 px-2 text-xs w-auto min-w-[120px]"
                          value={selectedMem}
                          onChange={(e) => setSelectedMem(e.target.value)}
                          disabled={startDetect.isPending}
                        >
                          <option value="2gb">2GB</option>
                          <option value="4gb">4GB</option>
                          <option value="6gb">6GB</option>
                          <option value="8gb">8GB</option>
                          <option value="16gb">16GB</option>
                          <option value="32gb">32GB</option>
                        </select>
                      </div>
                    )}
                  </div>

                  <button
                    className="btn-primary w-full"
                    onClick={() => startDetect.mutate()}
                    disabled={
                      p.image_count === 0 ||
                      jobRunning ||
                      (ingestProgress !== null && ingestProgress.i < ingestProgress.total)
                    }
                  >
                    <PlayCircle className="h-4 w-4" />
                    {detectErr || mergedDetect?.stage === "cancelled" ? "Try again" : "Run detection"}
                  </button>
                </div>
              )}
            </div>
          }
        />

        <Step
          n={3}
          title="Review & tag"
          icon={
            p.flagged_count === 0 ? <Eye className="h-5 w-5 text-ink-400" /> :
              p.reviewed_count >= p.flagged_count ? <CheckCircle2 className="h-5 w-5 text-emerald-600" /> :
                <Eye className="h-5 w-5 text-ink-400" />
          }
          done={p.flagged_count > 0 && p.reviewed_count >= p.flagged_count}
          body={
            p.flagged_count === 0 && !detectDone ? (
              <div className="text-sm text-ink-400">Run detection first.</div>
            ) : p.flagged_count === 0 ? (
              <div className="text-sm text-ink-600">No images above the confidence threshold — nothing to review.</div>
            ) : (
              <Link to={`/projects/${p.id}/review`} className="btn-primary w-full">
                <Eye className="h-4 w-4" />
                Review {p.flagged_count - p.reviewed_count} images
              </Link>
            )
          }
        />
      </div>
    </div>
  );
}

function Step({
  n, title, icon, body, done,
}: {
  n: number; title: string; icon: React.ReactNode; body: React.ReactNode; done?: boolean;
}) {
  return (
    <div className={`card p-4 ${done ? "border-emerald-200 bg-emerald-50/40" : ""}`}>
      <div className="flex items-center gap-2 mb-3">
        {icon}
        <div className="text-xs uppercase tracking-wide text-ink-500">Step {n}</div>
        <div className="font-semibold">{title}</div>
      </div>
      {body}
    </div>
  );
}

function Progress({ value, hint }: { value: number; hint: string }) {
  const pct = Math.max(0, Math.min(1, value));
  return (
    <div>
      <div className="h-1.5 bg-ink-200 rounded-full overflow-hidden">
        <div
          className="h-full bg-ink-900 transition-all"
          style={{ width: `${pct * 100}%` }}
        />
      </div>
      <div className="text-xs text-ink-500 mt-1.5 truncate">{hint}</div>
    </div>
  );
}
