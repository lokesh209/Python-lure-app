import { useEffect, useRef, useState } from "react";
import type { Detection } from "../lib/types";
import { ZoomIn } from "lucide-react";

const CATEGORY_COLOR: Record<string, string> = {
  animal: "#10b981",
  person: "#f59e0b",
  vehicle: "#3b82f6",
};

/**
 * Stroke width in SCREEN PIXELS so it renders consistently regardless of
 * image size. Scales with sqrt(conf) so high-conf boxes pop and low-conf
 * ones fade into faint outlines.
 */
function strokePx(conf: number): number {
  return 2 + 4 * Math.sqrt(Math.max(0, Math.min(1, conf)));
}

export function BboxCanvas({
  src,
  detections,
  threshold,
  highlightedIndex,
}: {
  src: string;
  detections: Detection[];
  threshold: number;
  highlightedIndex?: number | null;
}) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const [size, setSize] = useState<{ w: number; h: number } | null>(null);
  
  const [isZoomed, setIsZoomed] = useState(false);
  const [zoomOrigin, setZoomOrigin] = useState("center center");

  // Reset zoom when image changes
  useEffect(() => {
    setIsZoomed(false);
  }, [src]);

  const handleZoomClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (isZoomed) {
      setIsZoomed(false);
    } else {
      const rect = e.currentTarget.getBoundingClientRect();
      const x = ((e.clientX - rect.left) / rect.width) * 100;
      const y = ((e.clientY - rect.top) / rect.height) * 100;
      setZoomOrigin(`${x}% ${y}%`);
      setIsZoomed(true);
    }
  };

  // Keep the SVG overlay exactly aligned with the rendered image.
  useEffect(() => {
    const recompute = () => {
      const im = imgRef.current;
      if (im && im.clientWidth && im.clientHeight) {
        setSize({ w: im.clientWidth, h: im.clientHeight });
      }
    };
    recompute();
    const ro = new ResizeObserver(recompute);
    if (imgRef.current) ro.observe(imgRef.current);
    window.addEventListener("resize", recompute);
    return () => {
      ro.disconnect();
      window.removeEventListener("resize", recompute);
    };
  }, [src]);

  const visible = detections
    .map((d, i) => ({ d, i }))
    .filter(({ d }) => d.conf >= threshold)
    .sort((a, b) => a.d.conf - b.d.conf);

  return (
    <div ref={wrapRef} className="relative inline-block max-w-full max-h-full rounded-md shadow overflow-hidden group">
      <div 
        className="relative inline-block transition-transform duration-200 ease-out select-none"
        style={{
          transform: isZoomed ? 'scale(2.5)' : 'scale(1)',
          transformOrigin: zoomOrigin,
          cursor: isZoomed ? 'zoom-out' : 'zoom-in',
        }}
        onClick={handleZoomClick}
      >
        <img
          ref={imgRef}
          src={src}
          alt=""
          onLoad={() => {
            const im = imgRef.current;
            if (im) setSize({ w: im.clientWidth, h: im.clientHeight });
          }}
          className="block max-w-full max-h-[70vh]"
          draggable={false}
        />
      {size && (
        <svg
          className="absolute inset-0 pointer-events-none"
          width={size.w}
          height={size.h}
          viewBox={`0 0 ${size.w} ${size.h}`}
        >
          {visible.map(({ d, i }) => {
            const [bx, by, bw, bh] = d.bbox;
            const x = bx * size.w;
            const y = by * size.h;
            const w = bw * size.w;
            const h = bh * size.h;
            const color = CATEGORY_COLOR[d.category_name] ?? "#ec4899";
            const isHi = highlightedIndex === i;
            const sw = isHi ? strokePx(d.conf) * 1.6 : strokePx(d.conf);
            const labelH = 18;
            const labelText = `#${i + 1} ${(d.conf * 100).toFixed(0)}%`;
            const labelW = 8 + labelText.length * 7;
            const ly = Math.max(0, y - labelH);
            return (
              <g key={i} opacity={isHi ? 1 : Math.max(0.55, 0.5 + d.conf * 0.6)}>
                <rect
                  x={x}
                  y={y}
                  width={w}
                  height={h}
                  fill="none"
                  stroke={color}
                  strokeWidth={sw}
                />
                <rect
                  x={x}
                  y={ly}
                  width={labelW}
                  height={labelH}
                  fill={color}
                  opacity={0.92}
                />
                <text
                  x={x + 4}
                  y={ly + labelH - 5}
                  fill="white"
                  fontSize={12}
                  fontWeight={600}
                  fontFamily="system-ui, sans-serif"
                >
                  {labelText}
                </text>
              </g>
            );
          })}
        </svg>
      )}
      </div>

      <div 
        className={`absolute top-3 right-3 bg-ink-900/70 text-white text-[11px] px-2 py-1.5 rounded-md pointer-events-none transition-opacity duration-200 flex items-center gap-1.5 ${isZoomed ? 'opacity-0' : 'opacity-0 group-hover:opacity-100'}`}
      >
        <ZoomIn className="h-3.5 w-3.5" />
        Click to zoom
      </div>
    </div>
  );
}
