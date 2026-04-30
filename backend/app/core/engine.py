"""
Core Engine: 织影系统 LangGraph 状态机编排。

职责对照: docs/loom_02_architecture.md & docs/implementation-plan-v1.md
图结构: START → supervisor → (conditional) → storyboard/video_gen
         storyboard → (conditional) → hitl_approval/supervisor/video_gen/END
         hitl_approval → supervisor
         video_gen → END
"""

import logging
import os
import asyncio
import time
from typing import Dict, Any, Optional

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

from app.core.state import LoomState, GenerationMode, ApprovalStatus, PipelineStage
from app.core.supervisor import TaskClassifier, RoutingDecision, should_continue
from app.agents.story.storyboard import StoryboardAgent
from app.agents.video.generator import VideoGenerator
from app.agents.visual.image_gen import ImageGenerator
from app.agents.audio.tts_gen import TTSGenerator
from app.agents.ingestion.batch_analyzer import ParallelAnalyzer
from app.db.checkpointer import CheckpointerFactory
from app.config.settings import settings
from app.modules.asset_paths import build_asset_urls, pick_local_path
from app.modules.cost_guard import update_and_check_cost
from app.modules.ffmpeg_tools import FFmpegAssembler, VideoSegment
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

logger = logging.getLogger("loom.engine")


# === Pipeline Status Helpers (流水线状态辅助函数) ===
# 生成标准化阶段状态字典，写入 LoomState.pipeline_status
# 前端通过 /jobs/{thread_id}/pipeline 读取这些状态来渲染进度条

def _ps_running(stage: str) -> Dict[str, Any]:
    """标记某阶段为运行中，记录开始时间戳"""
    return {stage: {"status": "running", "started_at": time.time()}}

def _ps_completed(stage: str) -> Dict[str, Any]:
    """标记某阶段为已完成，记录完成时间戳"""
    return {stage: {"status": "completed", "completed_at": time.time()}}

def _ps_failed(stage: str, error: str) -> Dict[str, Any]:
    """标记某阶段为失败，附带错误信息和时间戳"""
    return {stage: {"status": "failed", "error": error, "failed_at": time.time()}}

def _ps_skipped(stage: str) -> Dict[str, Any]:
    """标记某阶段为已跳过(如所有场景都走图片管线则跳过视频生成)"""
    return {stage: {"status": "skipped"}}


def get_llm(provider: str, model_name: str):
    """根据提供商和模型名称初始化 LLM"""
    if provider == "google":
        api_key = settings.GOOGLE_API_KEY.get_secret_value() if settings.GOOGLE_API_KEY else None
        return ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,  # type: ignore[arg-type]
        )
    elif provider == "openai":
        api_key = settings.OPENAI_API_KEY.get_secret_value() if settings.OPENAI_API_KEY else None
        return ChatOpenAI(
            model=model_name,
            openai_api_key=api_key,  # type: ignore[arg-type]
        )
    elif provider == "dashscope":
        # 阿里 DashScope 使用 OpenAI 兼容接口或特定包装器
        # 这里优先尝试 ChatOpenAI 兼容
        api_key = settings.DASHSCOPE_API_KEY.get_secret_value() if settings.DASHSCOPE_API_KEY else None
        return ChatOpenAI(
            model=model_name,
            openai_api_key=api_key, # type: ignore[arg-type]
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
    elif provider == "deepseek":
        api_key = settings.DEEPSEEK_API_KEY.get_secret_value() if settings.DEEPSEEK_API_KEY else None
        return ChatOpenAI(
            model=model_name,
            openai_api_key=api_key, # type: ignore[arg-type]
            base_url="https://api.deepseek.com",
        )
    elif provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=model_name,
            base_url=settings.OLLAMA_BASE_URL,
            format="json", # 强制 Ollama 输出 JSON 格式
        )
    else:
        logger.warning(
            "Unknown LLM provider '%s', falling back to default (google/%s)",
            provider, settings.DEFAULT_LLM_MODEL,
        )
        api_key = settings.GOOGLE_API_KEY.get_secret_value() if settings.GOOGLE_API_KEY else None
        return ChatGoogleGenerativeAI(
            model=settings.DEFAULT_LLM_MODEL,
            google_api_key=api_key, # type: ignore[arg-type]
        )


async def supervisor_node(state: LoomState) -> Dict[str, Any]:
    """路由决策节点：运行 TaskClassifier 并将决策写入 State"""
    stage = PipelineStage.SUPERVISOR.value
    decision = TaskClassifier.classify(state)
    logger.info(
        "🧠 [任务-%s] 决策中心：路由至 [%s]，使用模型 %s/%s — 原因: %s",
        state.get("thread_id"),
        decision.next_node,
        decision.model_provider,
        decision.model_name,
        decision.reason,
    )

    mode = GenerationMode.LOCAL if decision.model_provider == "ollama" else GenerationMode.CLOUD
    
    # 终极静态兜底逻辑：如果错误次数太多，直接由 Supervisor 注入预定义模板并推进
    if decision.model_name == "static-fallback":
        from app.agents.story.storyboard import FALLBACK_TEMPLATE
        logger.warning("🏁 [任务-%s] 激活终极静态兜底，将使用预定义分镜模板结束由于 AI 的连续错误。", state.get("thread_id"))
        return {
            "storyboard_json": [s.model_dump() for s in FALLBACK_TEMPLATE.scenes],
            "approval_status": ApprovalStatus.APPROVED.value, # 终极兜底直接通过，防止死循环
            "error_count": 0,
            "execution_logs": [{
                "source": "SUPERVISOR",
                "level": "error",
                "message": "AI 生成连续失败，已激活终极静态兜底方案。",
                "ts": time.time()
            }]
        }

    # 注入实时日志
    log_entry = {
        "source": "SUPERVISOR",
        "level": "info",
        "message": f"路由决策：{decision.next_node} (模型: {decision.model_name}) - 原因: {decision.reason}",
        "ts": time.time()
    }
    
    return {
        "generation_mode": mode.value if hasattr(mode, "value") else mode,
        "_routing_model_provider": decision.model_provider,
        "_routing_model_name": decision.model_name,
        "_routing_next_node": decision.next_node,
        "execution_logs": [log_entry],
        "pipeline_status": _ps_completed(stage),
    }


def supervisor_router(state: LoomState) -> str:
    """
    Supervisor 后的条件路由：直接读取 supervisor_node 已缓存的决策结果。
    """
    cached_next = state.get("_routing_next_node")
    if cached_next:
        return cached_next
    # 兆底：如果缓存不存在则重新计算
    decision = TaskClassifier.classify(state)
    return decision.next_node


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((ConnectionError, TimeoutError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
async def storyboard_node(state: LoomState) -> Dict[str, Any]:
    """
    分镜生成节点 (含 tenacity 重试)。
    从 State 中读取 Supervisor 决策的模型，而非硬编码默认值。
    """
    stage = PipelineStage.STORYBOARD.value
    provider = state.get("_routing_model_provider", settings.DEFAULT_LLM_PROVIDER)
    model_name = state.get("_routing_model_name", settings.DEFAULT_LLM_MODEL)

    try:
        llm = get_llm(provider, model_name)
        agent = StoryboardAgent(llm)
        result = await agent.generate_storyboard(state)
        result["pipeline_status"] = _ps_completed(stage)
        return result
    except Exception as e:
        logger.error(f"[storyboard] failed: {e}")
        return {
            "error_count": 1,
            "pipeline_status": _ps_failed(stage, str(e)),
            "execution_logs": [{"source": "STORYBOARD", "level": "error", "message": str(e), "ts": time.time()}],
        }


async def hitl_approval_node(state: LoomState) -> Dict[str, Any]:
    """
    人工审核(HITL)拦截节点。
    LangGraph 通过 interrupt_before=["hitl_approval"] 在此节点前暂停，
    等待前端调用 /threads/{id}/approve 后由 approve_and_continue() 恢复。
    """
    stage = PipelineStage.HITL_APPROVAL.value
    logger.info("Entering HITL approval for thread %s", state.get("thread_id"))
    log_entry = {
        "source": "HITL",
        "level": "warning",
        "message": "All assets ready, awaiting final human review...",
        "ts": time.time()
    }
    return {"execution_logs": [log_entry], "pipeline_status": _ps_completed(stage)}


async def hitl_storyboard_node(state: LoomState) -> Dict[str, Any]:
    """
    阶段级微操阻断：剧本粗拆结束拦截。
    系统刚给出分镜脚本但尚未花费高成本执行图像和视频生成。
    """
    stage = PipelineStage.STORYBOARD.value  # 复用阶段UI或可新建
    log_entry = {
        "source": "HITL",
        "level": "warning",
        "message": "Storyboard script drafted, awaiting human validation before asset generation...",
        "ts": time.time()
    }
    return {"execution_logs": [log_entry]}


async def video_gen_node(state: LoomState) -> Dict[str, Any]:
    """
    视频生成节点：结合 SceneRouter 做场景级智能路由。
    核心逻辑: 遍历分镜场景，通过 SceneRouter 判断走视频还是图片管线，
    VIDEO_HIGH/SIMPLE 交给 VideoGenerator，IMAGE_CINEMATIC 标记为 skipped。
    这是降本增效的关键节点。
    """
    from app.core.supervisor import SceneRouter, SceneProductionStrategy
    stage = PipelineStage.VIDEO_GEN.value

    scenes = state.get("storyboard_json", [])
    v_tasks_to_run = []
    skipped_tasks = []

    for s in scenes:
        strategy = SceneRouter.route_scene(s)
        if strategy in [SceneProductionStrategy.VIDEO_HIGH, SceneProductionStrategy.VIDEO_SIMPLE]:
            v_tasks_to_run.append(s)
        else:
            skipped_tasks.append({
                "task_id": f"video_{s.get('scene_index', 0)}",
                "status": "skipped",
                "reason": "IMAGE_CINEMATIC",
                "provider": "none"
            })

    if not v_tasks_to_run:
        logger.info("All scenes use IMAGE_CINEMATIC, skipping video gen.")
        return {"video_tasks": skipped_tasks, "pipeline_status": _ps_skipped(stage)}

    try:
        provider_name = state.get("video_provider")
        generator = VideoGenerator(provider_name=provider_name)
        temp_state = state.copy()
        temp_state["storyboard_json"] = v_tasks_to_run
        result = await generator.generate_batch(temp_state)
        result["video_tasks"] = result.get("video_tasks", []) + skipped_tasks
        result["pipeline_status"] = _ps_completed(stage)
        return result
    except Exception as e:
        logger.error(f"Video gen failed: {e}")
        return {
            "video_tasks": skipped_tasks,
            "pipeline_status": _ps_failed(stage, str(e)),
            "execution_logs": [{"source": "VIDEO_GEN", "level": "error", "message": str(e), "ts": time.time()}],
        }

from app.agents.ingestion.batch_analyzer import ParallelAnalyzer

async def batch_analysis_node(state: LoomState) -> Dict[str, Any]:
    """
    批量内容分析节点：整条流水线的起点。
    状态机轮询模式: initial->submitted->completed/failed
    LangGraph 图中通过 batch_router 条件边自循环，直到完成才进入 supervisor。
    """
    session_id = state.get("session_id", "default_session")
    batch_id = state.get("batch_id")
    status = state.get("batch_status", "initial")
    provider = state.get("batch_provider") or "deepseek"
    model = state.get("batch_model") or "deepseek-chat"
    analysis_prompt = state.get("analysis_prompt", "")
    stage = PipelineStage.BATCH_ANALYSIS.value
    
    analyzer = ParallelAnalyzer(session_id, provider=provider, model=model, analysis_prompt=analysis_prompt)
    
    if status == "initial":
        logger.info(f"🆕 [任务-{session_id}] 启动并行分析任务 ({provider}/{model})...")
        try:
            new_batch_id = await analyzer.run_parallel_analysis()
            return {
                "batch_id": new_batch_id,
                "batch_status": "submitted",
                "pipeline_status": _ps_running(stage),
                "execution_logs": [{"source": "BATCH", "level": "info", "message": f"Batch started ({provider}): {new_batch_id}", "ts": time.time()}]
            }
        except Exception as e:
            logger.error(f"❌ 分析启动失败: {e}")
            return {"batch_status": "failed", "error_count": 1, "pipeline_status": _ps_failed(stage, str(e))}

    if status == "submitted" and batch_id:
        logger.info(f"⏳ [任务-{session_id}] 检查并行分析任务状态: {batch_id}")
        try:
            batch_info = await analyzer.get_batch_status(batch_id)
            curr_status = batch_info.get("status")
            
            if curr_status == "completed":
                full_registry = analyzer.get_full_registry()
                chapter_summaries = analyzer.get_story_context()
                latest_chapter_index = max((item.get("index", 0) for item in chapter_summaries), default=0)
                return {
                    "batch_status": "completed",
                    "character_registry": full_registry,
                    "global_context": {
                        "chapter_summaries": chapter_summaries,
                        "chapter_count": len(chapter_summaries),
                    },
                    "chapter_index": latest_chapter_index,
                    "pipeline_status": _ps_completed(stage),
                    "execution_logs": [{"source": "BATCH", "level": "info", "message": f"Analysis done, {len(full_registry)} characters, {len(chapter_summaries)} chapter summaries.", "ts": time.time()}]
                }
            elif curr_status == "failed":
                return {"batch_status": "failed", "error_count": 1, "pipeline_status": _ps_failed(stage, "Batch failed")}
            else:
                # 仍处于 processing
                await asyncio.sleep(5)  # 避免由于 graph 循环导致的 CPU 密集型极速轮询
                return {} # 不改变状态，继续循环
        except Exception as e:
            logger.warning(f"⚠️ 检查进度失败: {e}")
            await asyncio.sleep(2)  # 出错时也稍作停顿
            return {}

    return {}


async def image_gen_node(state: LoomState) -> Dict[str, Any]:
    """图像关键帧生成节点：为每个分镜场景生成视觉关键帧，支持多提供商，含成本熔断检查。"""
    stage = PipelineStage.IMAGE_GEN.value
    # 优先使用 Supervisor 的路由决策，兜底使用全局配置
    provider_name = state.get("_routing_model_provider") or state.get("image_provider") or settings.IMAGE_PROVIDER
    try:
        generator = ImageGenerator(provider_name=provider_name)
        result = await generator.generate_batch(state)
        cost = result.pop("_node_cost", 0.0)
        cost_update = update_and_check_cost(state, cost)
        return {**result, "cost_accumulator": cost_update, "pipeline_status": _ps_completed(stage)}
    except Exception as e:
        logger.error(f"Image gen failed with provider {provider_name}: {e}")
        return {"error_count": 1, "pipeline_status": _ps_failed(stage, str(e))}


async def tts_gen_node(state: LoomState) -> Dict[str, Any]:
    """TTS 语音旁白生成节点：为每个分镜生成配音音频，支持多提供商，含成本熔断检查。"""
    stage = PipelineStage.TTS_GEN.value
    # 优先使用 Supervisor 的路由决策，兜底使用全局配置
    provider_name = state.get("_routing_model_provider") or state.get("tts_provider") or settings.TTS_PROVIDER
    try:
        generator = TTSGenerator(provider_name=provider_name)
        result = await generator.generate_batch(state)
        cost = result.pop("_node_cost", 0.0)
        cost_update = update_and_check_cost(state, cost)
        return {**result, "cost_accumulator": cost_update, "pipeline_status": _ps_completed(stage)}
    except Exception as e:
        logger.error(f"TTS gen failed with provider {provider_name}: {e}")
        return {"error_count": 1, "pipeline_status": _ps_failed(stage, str(e))}


async def assembly_node(state: LoomState) -> Dict[str, Any]:
    """最终视频组装节点：通过 TimelineBuilder 对齐时间线，调用 FFmpeg 拼接输出 MP4。"""
    from app.modules.timeline_builder import TimelineBuilder
    stage = PipelineStage.ASSEMBLY.value

    v_tasks = state.get("video_tasks", [])
    a_tasks = state.get("audio_tasks", [])
    i_tasks = state.get("image_tasks", [])
    storyboard = state.get("storyboard_json", [])

    if not v_tasks and not i_tasks:
        logger.warning(f"No assets to assemble for thread {state.get('thread_id')}")
        return {"pipeline_status": _ps_skipped(stage)}

    timeline = TimelineBuilder.build(storyboard, i_tasks, a_tasks, v_tasks)
    if not timeline:
        logger.error(f"Empty timeline for thread {state.get('thread_id')}")
        return {"pipeline_status": _ps_failed(stage, "Empty timeline")}

    segments = []
    audio_paths = []
    for entry in timeline:
        # Resolve Web URLs to Local OS paths for FFmpeg
        local_asset_path = entry.asset_path.replace("/api/v2/output/", "./output/") if entry.asset_path else ""
        local_audio_path = entry.audio_path.replace("/api/v2/output/", "./output/") if entry.audio_path else ""
        
        # Self-healing: If a video path was provided but doesn't exist (e.g. mock generation bug previously),
        # fall back to the image path for this scene!
        if local_asset_path and not os.path.exists(local_asset_path):
            logger.warning(f"Video asset {local_asset_path} missing during assembly. Falling back to image asset.")
            i_asset = next((t for t in i_tasks if t.get('task_id') == f"img_{entry.scene_index}"), None)
            if i_asset and i_asset.get('image_path'):
                local_asset_path = i_asset.get('image_path').replace("/api/v2/output/", "./output/")

        segments.append(VideoSegment(
            segment_id=f"scene_{entry.scene_index}",
            file_path=local_asset_path,
            duration=entry.duration,
            audio_narration=local_audio_path,
            subtitle_text=entry.subtitle_text,
        ))
        if local_audio_path:
            audio_paths.append(local_audio_path)

    try:
        assembler = FFmpegAssembler()
        output_file = f"./output/final_video_{state['thread_id']}.mp4"
        os.makedirs("./output", exist_ok=True)
        final_path = await assembler.assemble(
            segments, output_file,
            audio_paths=audio_paths if audio_paths else None,
            thread_id=state.get("thread_id", "unknown")
        )
        logger.info(f"Assembly done: {final_path}")
        final_urls = build_asset_urls(final_path)
        return {
            "video_tasks": [{
                "task_id": "final_assembly",
                "status": "done",
                "video_path": final_urls["public_url"],
                "local_path": final_urls["local_path"],
            }],
            "pipeline_status": _ps_completed(stage),
        }
    except Exception as e:
        logger.error(f"Assembly failed: {e}")
        return {
            "video_tasks": [{"task_id": "final_assembly", "status": "failed", "error": str(e)}],
            "pipeline_status": _ps_failed(stage, str(e)),
        }


# === 延迟初始化的图单例 ===
_app = None


async def create_loom_graph(use_checkpointer: bool = True):
    """
    创建并编译织影系统有向图。
    """
    workflow = StateGraph(LoomState)

    # ... (nodes/edges same as before) ...
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("storyboard", storyboard_node)
    workflow.add_node("image_gen", image_gen_node)
    workflow.add_node("tts_gen", tts_gen_node)
    workflow.add_node("hitl_approval", hitl_approval_node)
    workflow.add_node("hitl_storyboard", hitl_storyboard_node)
    workflow.add_node("video_gen", video_gen_node)
    workflow.add_node("assembly", assembly_node)

    workflow.add_node("batch_analysis", batch_analysis_node)

    # ====== 边定义：构建有向图的流转路径 ======
    workflow.add_edge(START, "batch_analysis")  # 入口：从批量分析开始
    
    # 批量分析自循环路由：未完成继续轮询，完成后进入 supervisor
    def batch_router(state: LoomState) -> str:
        if state.get("batch_status") == "completed":
            return "supervisor"
        if state.get("batch_status") == "failed":
            return END
        return "batch_analysis"  # 继续轮询等待

    workflow.add_conditional_edges("batch_analysis", batch_router)

    # Supervisor 条件路由：根据 TaskClassifier 决策分发到各节点
    workflow.add_conditional_edges(
        "supervisor",
        supervisor_router,
        {
            "storyboard": "storyboard",        # 生成分镜
            "image_gen": "image_gen",          # 生成关键帧
            "tts_gen": "tts_gen",              # 生成语音
            "video_gen": "video_gen",          # 生成视频
            "hitl_approval": "hitl_approval",  # 人工审核
            "hitl_storyboard": "hitl_storyboard", # 剧本微操
            "END": END,                        # 结束(含终极兜底)
        }
    )

    # Storyboard 条件路由：分镜完成后决定下一步
    workflow.add_conditional_edges(
        "storyboard",
        should_continue,
        {
            "supervisor": "supervisor",
            "image_gen": "image_gen",
            "tts_gen": "tts_gen",
            "hitl_approval": "hitl_approval",
            "hitl_storyboard": "hitl_storyboard",
            "video_gen": "video_gen",
            "__end__": END,
        },
    )

    # 固定边：子节点完成后的固定流转
    workflow.add_edge("image_gen", "supervisor")      # 图片完成 -> 回 supervisor
    workflow.add_edge("tts_gen", "supervisor")        # 语音完成 -> 回 supervisor
    workflow.add_edge("hitl_approval", "supervisor")  # 审核完成 -> 回 supervisor
    workflow.add_edge("hitl_storyboard", "supervisor") # 剧本微操完毕 -> 回 supervisor
    workflow.add_edge("video_gen", "assembly")        # 视频完成 -> 最终组装
    workflow.add_edge("assembly", END)                # 组装完成 -> 流程结束

    # 7. 持久化与编译 (Await async checkpointer if requested)
    if use_checkpointer:
        checkpointer = await CheckpointerFactory.get_sqlite_saver()
    else:
        checkpointer = MemorySaver()
    
    return workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=["hitl_storyboard", "hitl_approval"],
    )


async def get_app(use_checkpointer: bool = True):
    """获取延迟初始化的图单例"""
    global _app
    if _app is None:
        _app = await create_loom_graph(use_checkpointer=use_checkpointer)
    return _app
