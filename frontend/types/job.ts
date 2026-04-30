/**
 * Loom 前端类型定义 — 任务状态与业务模型
 * 
 * 对应后端 LoomState TypedDict (backend/app/core/state.py)
 */

// ============================================================
// 枚举 & 常量
// ============================================================

export type GenerationMode = "cloud" | "local";

export type ApprovalStatus = "pending" | "approved" | "rejected" | "revision_requested";

export type SceneStatus = "pending" | "generating" | "done" | "failed";

export type LogLevel = "info" | "warning" | "error";

// ============================================================
// 分镜 (Storyboard)
// ============================================================

export interface Storyboard {
  /** 对应的小说原文片段 */
  source_text?: string;
  /** 画面描述 / 图像生成提示词 */
  image_prompt: string;
  /** 视觉风格建议 */
  visual_style?: string;
  /** 镜头运动 */
  camera_movement?: string;
  /** 旁白文本 */
  narration: string;
  /** 时长（秒） */
  duration: number;
  /** 角色引用列表 */
  characters?: string[];
  /** 生成的关键帧图像 URL */
  image_path?: string;
  /** 生成的配音音频 URL */
  audio_path?: string;
  /** 场景状态 */
  status?: SceneStatus;
  /** 扩展字段 */
  [key: string]: unknown;
}

// ============================================================
// 执行日志
// ============================================================

export interface ExecutionLog {
  /** 日志来源节点 */
  source: string;
  /** 日志级别 */
  level: LogLevel;
  /** 日志消息 */
  message: string;
  /** Unix 时间戳（秒） */
  ts: number;
}

// ============================================================
// 场景元数据
// ============================================================

export interface SceneMetadata {
  scene_index: number;
  status: SceneStatus;
  video_path?: string;
  error?: string;
}

// ============================================================
// 任务状态（对应后端 LoomState）
// ============================================================

export interface JobValues {
  novel_content?: string;
  storyboard_json?: Storyboard[];
  execution_logs?: ExecutionLog[];
  scene_metadata?: SceneMetadata[];
  generation_mode?: GenerationMode;
  approval_status?: ApprovalStatus;
  cost_total?: number;
  cost_accumulator?: number;
  cost_limit?: number;
  error_count?: number;
  _routing_model_provider?: string;
  _routing_model_name?: string;
  pipeline_status?: Record<string, any>;
  image_tasks?: ImageTask[];
  audio_tasks?: AudioTask[];
  video_tasks?: VideoTask[];
  character_registry?: Record<string, any>;
  analysis_prompt?: string;
}

export interface ImageTask {
  task_id: string;
  status: SceneStatus;
  image_path?: string;
  error?: string;
}

export interface AudioTask {
  task_id: string;
  status: SceneStatus;
  audio_path?: string;
  error?: string;
}

export interface VideoTask {
  task_id: string;
  status: "pending" | "generating" | "done" | "failed";
  video_path?: string;
  error?: string;
}

export interface JobState {
  thread_id: string;
  values: JobValues;
  next: string[];
}

// ============================================================
// 工作流节点定义
// ============================================================

/** 与后端 PIPELINE_STAGE_ORDER 完全一致的 8 阶段定义 */
export const WORKFLOW_NODES = [
  "batch_analysis",
  "supervisor",
  "storyboard",
  "hitl_storyboard",
  "image_gen",
  "tts_gen",
  "hitl_approval",
  "video_gen",
  "assembly",
] as const;

export type WorkflowNode = (typeof WORKFLOW_NODES)[number];

/** 节点显示名称映射 */
export const NODE_LABELS: Record<WorkflowNode, string> = {
  batch_analysis: "内容解析",
  supervisor: "路由决策",
  storyboard: "分镜创作",
  hitl_storyboard: "剧本审核",
  image_gen: "图片生成",
  tts_gen: "语音合成",
  hitl_approval: "成片审核",
  video_gen: "视频生成",
  assembly: "后期合辑",
};
