import type { ProjectStage } from "../lib/types";
import { cn } from "../lib/cn";

const META: Record<ProjectStage, { label: string; cls: string }> = {
  needs_megadetector: { label: "Needs MegaDetector", cls: "bg-amber-100 text-amber-800" },
  needs_id: { label: "Needs ID", cls: "bg-sky-100 text-sky-800" },
  done_id: { label: "Done (no CSV)", cls: "bg-emerald-100 text-emerald-800" },
  archived: { label: "Done", cls: "bg-emerald-200 text-emerald-900" },
};

export function StageBadge({ stage }: { stage: ProjectStage }) {
  const m = META[stage];
  return <span className={cn("badge", m.cls)}>{m.label}</span>;
}
