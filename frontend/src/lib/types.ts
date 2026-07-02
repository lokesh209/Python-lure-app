export type ProjectStage =
  | "needs_megadetector"
  | "needs_id"
  | "done_id"
  | "archived";

export interface Project {
  id: number;
  folder: string;
  date: string;
  location: string;
  site: string;
  treatment: string;
  interval: string;
  stage: ProjectStage;
  is_sentinel: boolean;
  image_count: number;
  detection_count: number;
  flagged_count: number;
  reviewed_count: number;
  created_at: string;
  detected_at: string | null;
  completed_at: string | null;
}

export interface Detection {
  category: string;
  category_name: string;
  conf: number;
  bbox: [number, number, number, number];
}

export interface ImageTag {
  id?: number;
  species: string;
  count: number;
}

export interface ImageItem {
  id: number;
  file: string;
  relative_path: string;
  flagged: boolean;
  reviewed: boolean;
  species: string;
  count: number;
  delete_flag: boolean;
  max_conf: number;
  width: number;
  height: number;
  detections: Detection[];
  tags: ImageTag[];
}

export interface HiPerGatorBlock {
  ssh_alias: string;
  remote_base: string;
  conda_env: string;
  account: string;
  qos: string;
  partition: string;
  gres: string;
  mem: string;
  email: string;
  poll_sec: number;
}

export interface Settings {
  data_root: string;
  detector: string;
  conf_threshold: number;
  species_list: string[];
  config_path: string;
  config_exists: boolean;
  gatorlink: string | null;
  is_configured: boolean;
  hipergator: HiPerGatorBlock;
}

export interface SettingsPatch {
  gatorlink?: string;
  data_root?: string;
  detector?: string;
  conf_threshold?: number;
  hipergator_ssh_alias?: string;
  hipergator_remote_base?: string;
  hipergator_conda_env?: string;
  hipergator_account?: string;
  hipergator_qos?: string;
  hipergator_partition?: string;
  hipergator_gres?: string;
  hipergator_mem?: string;
  hipergator_email?: string;
  hipergator_poll_sec?: number;
}
