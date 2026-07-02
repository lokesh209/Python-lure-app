import type { ImageItem, Project, ProjectStage, Settings, SettingsPatch } from "./types";

/** Error thrown on non-2xx. ``detail`` is preserved as either string or object. */
export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, message: string, detail: unknown) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

async function jfetch<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) {
    let detail: unknown = null;
    let detailText = "";
    try {
      detailText = await res.text();
      const body = JSON.parse(detailText);
      detail = body?.detail ?? body;
      detailText = typeof detail === "string" ? detail : JSON.stringify(detail);
    } catch {
      detail = detailText;
    }
    throw new ApiError(res.status, `${res.status} ${res.statusText}: ${detailText}`, detail);
  }
  return res.json() as Promise<T>;
}

/** Download a URL via fetch + Blob (works in WKWebView; raw `<a download href="/api/...">` often does not). */
export async function downloadViaFetch(url: string, fallbackFilename: string): Promise<void> {
  const res = await fetch(url);
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`;
    try {
      const t = await res.text();
      if (t) msg = t.length > 300 ? `${t.slice(0, 300)}…` : t;
    } catch {
      /* ignore */
    }
    throw new Error(msg);
  }
  const cd = res.headers.get("Content-Disposition");
  let filename = fallbackFilename;
  const quoted = cd?.match(/filename="([^"]+)"/i);
  const loose = cd?.match(/filename=([^;\s]+)/i);
  if (quoted) {
    filename = quoted[1];
  } else if (loose) {
    filename = loose[1].replace(/^["']|["']$/g, "");
  }

  const text = await res.text();

  // PyWebView on macOS (WKWebView) intercepts Blob URL navigation and replaces 
  // the entire window contents with the file instead of downloading it.
  // Use the native Python-side file saver if available.
  const api = (window as any).pywebview?.api;
  if (api?.save_file) {
    await api.save_file(text, filename);
    return;
  }

  const blob = new Blob([text], { type: res.headers.get("Content-Type") || "text/plain" });
  const objectUrl = URL.createObjectURL(blob);
  try {
    const a = document.createElement("a");
    a.href = objectUrl;
    a.download = filename;
    a.rel = "noopener";
    document.body.appendChild(a);
    a.click();
    a.remove();
  } finally {
    URL.revokeObjectURL(objectUrl);
  }
}

export const api = {
  health: () => jfetch<{ ok: boolean; data_root: string; detector: string }>("/api/health"),
  settings: () => jfetch<Settings>("/api/settings"),
  patchSettings: (body: SettingsPatch) =>
    jfetch<Settings>("/api/settings", { method: "PATCH", body: JSON.stringify(body) }),

  listProjects: (stage?: ProjectStage) =>
    jfetch<Project[]>(`/api/projects${stage ? `?stage=${stage}` : ""}`),
  getProject: (id: number) => jfetch<Project>(`/api/projects/${id}`),
  ingestProject: (body: {
    source: string;
    date: string;
    location: string;
    site: string;
    treatment: string;
    interval: string;
    is_sentinel: boolean;
  }) =>
    jfetch<Project>("/api/projects/ingest", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  startDetection(projectId: number, detector?: string, hipergator_mem?: string) {
    return jfetch<{ status: string; channel: string; detector: string }>(`/api/projects/${projectId}/detect`, { 
      method: "POST",
      body: JSON.stringify({ detector, hipergator_mem })
    });
  },
  detectStatus: (id: number) => jfetch<{ running: boolean }>(`/api/projects/${id}/detect-status`),
  cancelDetection: (id: number) => jfetch<{ ok: boolean }>(`/api/projects/${id}/detect-cancel`, { method: "POST" }),
  detectProgress: (id: number) =>
    jfetch<{
      running: boolean;
      stage: string | null;
      pct: number | null;
      msg: string;
      detector: string;
      ts?: number | null;
    }>(`/api/projects/${id}/detect-progress`),
  detectRunningIds: () => jfetch<{ project_ids: number[] }>("/api/projects/detect-running"),
  importDetections: (id: number, jsonPath?: string) =>
    jfetch<Project>(
      `/api/projects/${id}/import-detections${jsonPath ? `?json_path=${encodeURIComponent(jsonPath)}` : ""}`,
      { method: "POST" }
    ),
  patchProject: (id: number, body: Partial<Project>) =>
    jfetch<Project>(`/api/projects/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteProject: (id: number) =>
    jfetch<{ ok: boolean }>(`/api/projects/${id}`, {
      method: "DELETE",
    }),

  listImages: (projectId: number, opts?: { flaggedOnly?: boolean; onlyUnreviewed?: boolean; sortBy?: "id" | "max_conf_desc" }) => {
    const p = new URLSearchParams();
    p.set("flagged_only", String(opts?.flaggedOnly ?? true));
    if (opts?.onlyUnreviewed) p.set("only_unreviewed", "true");
    if (opts?.sortBy) p.set("sort_by", opts.sortBy);
    return jfetch<ImageItem[]>(`/api/projects/${projectId}/images?${p}`);
  },
  patchImage: (projectId: number, imageId: number, body: Partial<ImageItem>) =>
    jfetch<ImageItem>(`/api/projects/${projectId}/images/${imageId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  imageUrl: (projectId: number, imageId: number) =>
    `/api/projects/${projectId}/images/${imageId}/file`,
  csvUrl: (projectId: number) => `/api/projects/${projectId}/csv`,
  masterCsvUrl: () => `/api/projects/export/master`,

  hpgStatus: () => jfetch<{ status: "ok" | "expired" | "no_config"; message: string; has_saved_password: boolean }>(
    "/api/hipergator/status"
  ),
  hpgForget: () => jfetch<{ ok: boolean }>("/api/hipergator/forget", { method: "POST" }),
  hpgDisconnect: () => jfetch<{ ok: boolean }>("/api/hipergator/disconnect", { method: "POST" }),

  openConfig: () => jfetch<{ path: string; created: boolean }>(
    "/api/settings/open-config",
    { method: "POST" }
  ),

  inspectFolder: (path: string) => jfetch<{
    exists: boolean;
    is_dir: boolean;
    name: string;
    image_count: number;
    parsed: { date: string; location: string; site: string; treatment: string; interval: string } | null;
    parent_parsed: { date: string; location: string; site: string; treatment: string; interval: string } | null;
    parent_name: string | null;
    suggested_path: string | null;
    conflict_project_id: number | null;
    conflict_project_folder: string | null;
    suggestion_reason: string | null;
  }>("/api/projects/inspect-folder", {
    method: "POST",
    body: JSON.stringify({ path }),
  }),
};
