export interface Project {
  id: string;
  name: string;
  description?: string;
  novels?: Novel[];
  created_at?: string;
}

export interface Novel {
  id: string;
  project_id?: string;
  title: string;
  author?: string;
  volumes?: Volume[];
  latest_thread_id?: string;
}

export interface Volume {
  id: string;
  novel_id: string;
  title: string;
  index: number;
  file_path?: string;
  latest_thread_id?: string;
}
