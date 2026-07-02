import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  ChevronLeft,
  ChevronRight,
  CheckCircle2,
  ArrowDownNarrowWide,
  ArrowUpNarrowWide,
} from "lucide-react";
import { api } from "../lib/api";
import type { ImageItem } from "../lib/types";
import { BboxCanvas } from "../components/BboxCanvas";
import { DetectionList } from "../components/DetectionList";

export default function Review() {
  const { id } = useParams();
  const projectId = Number(id);
  const qc = useQueryClient();

  const [sortBy, setSortBy] = useState<"max_conf_desc" | "id">("max_conf_desc");
  const [filter, setFilter] = useState<"all" | "animal" | "person" | "vehicle">("all");
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);

  const project = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => api.getProject(projectId),
  });
  const settings = useQuery({ queryKey: ["settings"], queryFn: api.settings });
  const images = useQuery({
    queryKey: ["images", projectId, sortBy],
    queryFn: () => api.listImages(projectId, { flaggedOnly: true, sortBy }),
  });

  const list = useMemo(() => {
    const rawList = images.data ?? [];
    if (filter === "all") return rawList;
    const threshold = settings.data?.conf_threshold ?? 0.05;
    return rawList.filter((img) =>
      img.detections.some((d) => d.category_name === filter && d.conf >= threshold)
    );
  }, [images.data, filter, settings.data?.conf_threshold]);

  const [idx, setIdx] = useState(0);
  const current = list[idx];

  // When the queue is re-sorted or filtered, reset to the start.
  useEffect(() => {
    setIdx(0);
  }, [sortBy, filter]);

  // Pre-fetch the next image for instant loading
  useEffect(() => {
    const nextIdx = idx + 1;
    if (nextIdx < list.length) {
      const nextImg = list[nextIdx];
      const preload = new Image();
      preload.src = api.imageUrl(projectId, nextImg.id);
    }
  }, [idx, list, projectId]);

  const patch = useMutation({
    mutationFn: (body: Partial<ImageItem>) =>
      api.patchImage(projectId, current!.id, body),
    onSuccess: (updated) => {
      qc.setQueryData<ImageItem[]>(["images", projectId, sortBy], (old) =>
        old?.map((i) => (i.id === updated.id ? updated : i)) ?? old
      );
      qc.invalidateQueries({ queryKey: ["project", projectId] });
    },
  });

  const next = useCallback(() => setIdx((i) => Math.min(i + 1, list.length - 1)), [list.length]);
  const prev = useCallback(() => setIdx((i) => Math.max(i - 1, 0)), []);

  const setSpecies = (species: string) => {
    const existing = current?.tags.find(t => t.species === species);
    if (existing) {
      updateTagCount(species, existing.count + 1);
    } else {
      patch.mutate({ tags: [...(current?.tags ?? []), { species, count: 1 }], reviewed: true });
      // Don't auto-next here since they might want to add another species
    }
  };

  const updateTagCount = (species: string, newCount: number) => {
    if (!current) return;
    if (newCount <= 0) {
      patch.mutate({ tags: current.tags.filter(t => t.species !== species), reviewed: true });
    } else {
      patch.mutate({
        tags: current.tags.map(t => t.species === species ? { ...t, count: newCount } : t),
        reviewed: true
      });
    }
  };

  const markEmpty = () => {
    patch.mutate({ tags: [], reviewed: true });
    setTimeout(next, 80);
  };

  const speciesList = useMemo(
    () => settings.data?.species_list ?? [],
    [settings.data]
  );

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (!current || (e.target as HTMLElement)?.tagName === "INPUT") return;
      if (e.key === "ArrowRight") { e.preventDefault(); next(); }
      else if (e.key === "ArrowLeft") { e.preventDefault(); prev(); }
      else if (e.key === " ") { e.preventDefault(); markEmpty(); }
      else if (e.key >= "1" && e.key <= "9") {
        const i = parseInt(e.key, 10) - 1;
        const sp = speciesList[i];
        if (sp) {
          setSpecies(sp);
        }
      }
      // Arrow Up/Down doesn't map well to multiple tags anymore. We can leave it for the first tag or remove.
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [current, next, prev, speciesList]);

  if (images.isLoading) return <div className="text-sm text-ink-500">Loading…</div>;

  if (list.length === 0) {
    return (
      <div className="text-center space-y-3 py-12">
        <CheckCircle2 className="h-12 w-12 text-emerald-500 mx-auto" />
        <div className="text-lg font-semibold">No images to review.</div>
        <p className="text-sm text-ink-500">Either detection hasn't run yet, all images were below the threshold, or no images match the selected filter.</p>
        <Link to={`/projects/${projectId}`} className="btn-secondary inline-flex">Back</Link>
        {filter !== "all" && (
          <button onClick={() => setFilter("all")} className="btn-secondary inline-flex ml-2">Clear Filter</button>
        )}
      </div>
    );
  }

  const reviewed = list.filter((i) => i.reviewed).length;
  const threshold = settings.data?.conf_threshold ?? 0.05;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <Link to={`/projects/${projectId}`} className="inline-flex items-center gap-1.5 text-sm text-ink-500 hover:text-ink-800">
          <ArrowLeft className="h-4 w-4" /> Back
        </Link>
        <div className="text-sm text-ink-600 flex items-center gap-3">
          <span className="font-mono text-xs">{project.data?.folder}</span>
          <span>·</span>
          <span className="font-medium">{idx + 1} / {list.length}</span>
          <span>·</span>
          <span>{reviewed} reviewed</span>
        </div>
        
        <div className="flex items-center gap-4">
          <div className="inline-flex rounded-md border border-ink-200 overflow-hidden text-xs">
            {(["all", "animal", "person", "vehicle"] as const).map((f) => (
              <button
                key={f}
                className={`px-3 py-1.5 ${filter === f ? "bg-emerald-600 text-white" : "bg-white text-ink-700 hover:bg-ink-50"}`}
                onClick={() => setFilter(f)}
              >
                {f.charAt(0).toUpperCase() + f.slice(1)}
              </button>
            ))}
          </div>

          <div className="inline-flex rounded-md border border-ink-200 overflow-hidden text-xs">
            <button
              className={`px-3 py-1.5 inline-flex items-center gap-1.5 ${sortBy === "max_conf_desc" ? "bg-ink-900 text-white" : "bg-white text-ink-700 hover:bg-ink-50"}`}
              onClick={() => setSortBy("max_conf_desc")}
              title="Highest-confidence images first (real animals up top, false positives at the end)"
            >
              <ArrowDownNarrowWide className="h-3.5 w-3.5" />
              By confidence
            </button>
            <button
              className={`px-3 py-1.5 inline-flex items-center gap-1.5 ${sortBy === "id" ? "bg-ink-900 text-white" : "bg-white text-ink-700 hover:bg-ink-50"}`}
              onClick={() => setSortBy("id")}
              title="Original image order (chronological)"
            >
              <ArrowUpNarrowWide className="h-3.5 w-3.5" />
              By time
            </button>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-4">
        <div className="card p-4 flex items-center justify-center bg-ink-900/5 min-h-[60vh]">
          {current && (
            <BboxCanvas
              src={api.imageUrl(projectId, current.id)}
              detections={current.detections}
              threshold={threshold}
              highlightedIndex={hoverIdx}
            />
          )}
        </div>

        <div className="space-y-4">
          <div className="card p-4">
            <div className="text-xs uppercase tracking-wide text-ink-500 mb-1">File</div>
            <div className="font-mono text-sm break-all">
              {current?.relative_path ? `${current.relative_path}/` : ""}{current?.file}
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-ink-500">
              <div><span className="font-medium text-ink-700">Max conf:</span> {(current?.max_conf ?? 0).toFixed(3)}</div>
              <div><span className="font-medium text-ink-700">Detections:</span> {current?.detections.length}</div>
            </div>
          </div>

          <div className="card p-3">
            <div className="label px-1">Detections</div>
            <DetectionList
              detections={current?.detections ?? []}
              threshold={threshold}
              highlightedIndex={hoverIdx}
              onHover={setHoverIdx}
            />
          </div>

          <div className="card p-4 space-y-4">
            <div>
              <div className="label">Active Tags</div>
              {current?.tags && current.tags.length > 0 ? (
                <div className="space-y-2 mt-2">
                  {current.tags.map((t) => (
                    <div key={t.species} className="flex items-center justify-between bg-ink-50 p-2 rounded-md border border-ink-100">
                      <span className="font-medium text-sm text-ink-800">{t.species}</span>
                      <div className="flex items-center gap-1.5">
                        <button className="btn-secondary py-1 px-2 text-xs" onClick={() => updateTagCount(t.species, t.count - 1)}>−</button>
                        <span className="font-mono text-sm w-6 text-center">{t.count}</span>
                        <button className="btn-secondary py-1 px-2 text-xs" onClick={() => updateTagCount(t.species, t.count + 1)}>+</button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-sm text-ink-400 italic mt-2">No tags. Image is marked empty.</div>
              )}
            </div>

            <div className="border-t border-ink-100 pt-3">
              <div className="label mb-2">Add Species</div>
              <div className="grid grid-cols-2 gap-2">
                {speciesList.map((s, i) => (
                  <button
                    key={s}
                    className={`btn-secondary justify-between ${current?.tags.some(t => t.species === s) ? "!border-emerald-200 !bg-emerald-50 text-emerald-800" : ""}`}
                    onClick={() => setSpecies(s)}
                  >
                    <span>{s}</span>
                    <span className="text-[10px] opacity-60">{i + 1}</span>
                  </button>
                ))}
                <button
                  className={`btn-secondary col-span-2 ${current?.tags.length === 0 && current?.reviewed ? "!bg-ink-900 !text-white !border-ink-900" : ""}`}
                  onClick={markEmpty}
                >
                  Empty (Space)
                </button>
              </div>
            </div>

            <div className="flex items-center justify-between pt-2">
              <button className="btn-ghost" onClick={prev} disabled={idx === 0}>
                <ChevronLeft className="h-4 w-4" /> Prev
              </button>
              <button className="btn-primary" onClick={next} disabled={idx >= list.length - 1}>
                Next <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>

          <div className="card p-3 text-xs text-ink-500 leading-relaxed">
            <div className="font-medium text-ink-700 mb-1">Shortcuts</div>
            <kbd>1–{Math.min(9, speciesList.length)}</kbd> toggle/add species ·{" "}
            <kbd>Space</kbd> clear all ·{" "}
            <kbd>←/→</kbd> prev/next
          </div>
        </div>
      </div>
    </div>
  );
}
