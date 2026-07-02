import { Link } from "react-router-dom";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Plus, Download, Settings as SettingsIcon, AlertCircle, Loader2 } from "lucide-react";
import { api, downloadViaFetch } from "../lib/api";
import type { Project, ProjectStage } from "../lib/types";
import { StageBadge } from "../components/StageBadge";

const COLUMNS: { stage: ProjectStage; title: string; hint: string }[] = [
  { stage: "needs_megadetector", title: "Needs MegaDetector", hint: "Just ingested. Ready to send to detector." },
  { stage: "needs_id", title: "Needs ID", hint: "Detection done. Ready to tag." },
  { stage: "done_id", title: "Done (no CSV)", hint: "All images tagged. CSV not exported yet." },
  { stage: "archived", title: "Done", hint: "Tagged and CSV saved with the data." },
];

export default function Dashboard() {
  const projects = useQuery({
    queryKey: ["projects"],
    queryFn: () => api.listProjects(),
    refetchInterval: 4000,
  });
  const running = useQuery({
    queryKey: ["detect-running"],
    queryFn: api.detectRunningIds,
    refetchInterval: 2000,
  });
  const settings = useQuery({ queryKey: ["settings"], queryFn: api.settings });

  const runningIds = new Set(running.data?.project_ids ?? []);
  const [masterCsvBusy, setMasterCsvBusy] = useState(false);

  const grouped: Record<ProjectStage, Project[]> = {
    needs_megadetector: [],
    needs_id: [],
    done_id: [],
    archived: [],
  };
  for (const p of projects.data ?? []) grouped[p.stage].push(p);

  const needsSetup = settings.data && !settings.data.is_configured;

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Projects</h1>
          <p className="text-sm text-ink-500 mt-1">
            One pipeline. SD card → MegaDetector → tag → CSV.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="btn-secondary"
            disabled={masterCsvBusy}
            onClick={async () => {
              setMasterCsvBusy(true);
              try {
                await downloadViaFetch(api.masterCsvUrl(), "ImageData_DBExport.csv");
              } catch (e) {
                alert(e instanceof Error ? e.message : "Export failed");
              } finally {
                setMasterCsvBusy(false);
              }
            }}
          >
            <Download className="h-4 w-4" />
            {masterCsvBusy ? "Exporting…" : "Master CSV"}
          </button>
          <Link to="/new" className="btn-primary">
            <Plus className="h-4 w-4" />
            New from SD card
          </Link>
        </div>
      </div>

      {needsSetup && (
        <div className="rounded-lg border-2 border-amber-300 bg-amber-50 p-4 flex items-start gap-3">
          <AlertCircle className="h-5 w-5 text-amber-700 mt-0.5 shrink-0" />
          <div className="flex-1">
            <div className="font-semibold text-amber-900">First time? Quick setup.</div>
            <p className="text-sm text-amber-800 mt-1">
              Tell us your GatorLink so we know where to put your photos on
              HiPerGator. Takes 30 seconds.
            </p>
          </div>
          <Link to="/settings" className="btn-primary shrink-0">
            <SettingsIcon className="h-4 w-4" />
            Set up
          </Link>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {COLUMNS.map((col) => (
          <Column key={col.stage} {...col} projects={grouped[col.stage]} runningIds={runningIds} />
        ))}
      </div>
    </div>
  );
}

function Column({
  stage,
  title,
  hint,
  projects,
  runningIds,
}: {
  stage: ProjectStage;
  title: string;
  hint: string;
  projects: Project[];
  runningIds: Set<number>;
}) {
  return (
    <div className="card p-3 flex flex-col gap-3 min-h-[300px]">
      <div>
        <div className="flex items-center justify-between">
          <h2 className="font-semibold text-sm">{title}</h2>
          <span className="text-xs text-ink-400">{projects.length}</span>
        </div>
        <p className="text-xs text-ink-400 mt-0.5">{hint}</p>
      </div>
      <div className="flex flex-col gap-2">
        {projects.length === 0 ? (
          <div className="text-xs text-ink-400 italic px-2 py-3">No projects.</div>
        ) : (
          projects.map((p) => <ProjectCard key={p.id} project={p} detecting={runningIds.has(p.id)} />)
        )}
      </div>
      <div className="text-[10px] uppercase tracking-wider text-ink-300 mt-auto">
        {stage}
      </div>
    </div>
  );
}

function ProjectCard({ project, detecting }: { project: Project; detecting: boolean }) {
  return (
    <Link
      to={`/projects/${project.id}`}
      className="block rounded-md border border-ink-200 hover:border-ink-400 bg-white px-3 py-2.5 transition-colors"
    >
      <div className="flex items-center justify-between gap-2">
        <span className="font-mono text-sm text-ink-900 truncate">{project.folder}</span>
        <StageBadge stage={project.stage} />
      </div>
      <div className="mt-1.5 flex items-center gap-3 text-xs text-ink-500 flex-wrap">
        <span>{project.image_count} imgs</span>
        {detecting && (
          <span className="inline-flex items-center gap-1 text-sky-700 font-medium">
            <Loader2 className="h-3 w-3 animate-spin" />
            Detection running
          </span>
        )}
        {project.flagged_count > 0 && (
          <span className="text-amber-700">
            {project.reviewed_count}/{project.flagged_count} reviewed
          </span>
        )}
        {project.is_sentinel && <span className="text-purple-700">Sentinel</span>}
      </div>
    </Link>
  );
}
