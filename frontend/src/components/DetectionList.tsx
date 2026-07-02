import type { Detection } from "../lib/types";
import { cn } from "../lib/cn";

const CATEGORY_COLOR: Record<string, string> = {
  animal: "bg-emerald-500",
  person: "bg-amber-500",
  vehicle: "bg-blue-500",
};

export function DetectionList({
  detections,
  threshold,
  highlightedIndex,
  onHover,
}: {
  detections: Detection[];
  threshold: number;
  highlightedIndex?: number | null;
  onHover?: (idx: number | null) => void;
}) {
  if (detections.length === 0) {
    return (
      <div className="text-xs text-ink-400 italic px-1 py-2">
        No detections on this image.
      </div>
    );
  }

  return (
    <ul className="space-y-1">
      {detections.map((d, i) => {
        const above = d.conf >= threshold;
        const dot = CATEGORY_COLOR[d.category_name] ?? "bg-pink-500";
        const isHi = highlightedIndex === i;
        return (
          <li
            key={i}
            onMouseEnter={() => onHover?.(i)}
            onMouseLeave={() => onHover?.(null)}
            className={cn(
              "flex items-center gap-2 rounded px-2 py-1 text-xs transition-colors",
              isHi ? "bg-ink-100" : "hover:bg-ink-50",
              !above && "opacity-50"
            )}
          >
            <span className="w-5 text-center text-ink-400 tabular-nums">#{i + 1}</span>
            <span className={cn("h-2 w-2 rounded-full", dot)} />
            <span className="flex-1 capitalize">{d.category_name}</span>
            <span className="tabular-nums font-medium">
              {(d.conf * 100).toFixed(1)}%
            </span>
            {!above && <span className="text-ink-400">filtered</span>}
          </li>
        );
      })}
    </ul>
  );
}
