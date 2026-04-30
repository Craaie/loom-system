# 织影系统 (Loom System) - 技术架构设计

## 1. 核心架构蓝图 (v2.0 演进)
> [!NOTE]
> 系统已于 2026-03-18 完成从 Streamlit 单体向 **Next.js 15 + FastAPI** 前后端分离架构的重大演进。
> 详情请参考新版文档：[Loom 2.0 架构设计](loom_06_v2_architecture.md) 与 [实施方案](loom_07_v2_implementation.md)。

系统采用基于 LangGraph 的多智能体编排架构，使用 **SSE (Server-Sent Events) 实时流** 处理前端状态同步。

```mermaid
graph TD
    A[Ingestion 节点<br/>小说解析 + 双层 RAG] --> B[Supervisor Agent<br/>Task Classifier + 全局协调]
    B --> C[Storyboard Agent<br/>Pydantic JSON 强约束]
    
    C --> IMG[Image Gen Agent]
    IMG --> TTS[TTS Gen Agent]
    TTS --> HITL[HITL Approval Node]
    
    HITL --> SR[Scene Router ⭐<br/>混合路由决策]
    
    SR --> VID[Video Gen (Kling)]
    SR --> I2V[I2V Agent (SVD)]
    SR -.-> SKIP[Skip → Image+FX]
    
    VID --> ASSET[(Asset Store ⭐<br/>JSON 持久化)]
    I2V --> ASSET
    IMG --> ASSET
    
    ASSET --> TL[Timeline Builder ⭐]
    TL --> DIR[FFmpeg Director ⭐<br/>Zoom/Pan + 归一化]
    
    B -.->|循环自省 / 降级路由| C
    B -.->|成本熔断| CostGuard[成本熔断器<br/>cost_accumulator]
```

## 2. 核心技术栈选型

| 层级 | 技术选型 | 设计意图 |
| :--- | :--- | :--- |
| **工作流引擎** | **LangGraph (Supervisor 模式)** | 有向图编排，支持条件分支、循环自省、`Send()` 并行 Map-Reduce。 |
| **并发控制 (MVP)** | **asyncio + Semaphore** | 单进程内并发调用视频 API，通过信号量限流，避免引入 Celery 的运维复杂度。 |
| **并发控制 (Scale)** | **Celery + Redis (预留)** | 多机器扩容时启用，实现跨进程/跨节点的任务分发与削峰填谷。 |
| **持久化与记忆** | **PostgreSQL (pgvector) + Checkpointer** | 统一存储图状态与长短期记忆；支持断点续跑。 |
| **向量知识库** | **ChromaDB (MVP) → Milvus (生产)** | MVP 使用轻量级 ChromaDB；生产环境迁移至 Milvus 集群支撑百万级向量。 |
| **模型路由** | **Task Classifier + Ollama/Cloud** | 规则引擎分类任务复杂度，自动路由至本地或云端模型。 |
| **监控链路** | **LangSmith + Prometheus** | 全链路 Tracing，实时统计 Token 成本与成功率。 |

## 3. 核心增强设计

### 3.1 Supervisor Agent (大脑决策)

*   **Task Classifier (路由内核)**：基于规则引擎判定任务复杂度：
    *   文本长度 < 500 字 且 无角色描写 → **Ollama 本地处理**
    *   涉及角色外貌生成 / 视觉场景 → **云端大模型 (DeepSeek/Qwen)**
    *   视频片段生成 → **Kling 3.0 / Runway Gen-4**
*   **Map-Reduce 并行**：利用 LangGraph `Send()` API，多章节同时分发至不同 Worker 子图。
*   **自动降级**：云端 API 连续失败 N 次 → 自动切换至 Ollama 兜底。

### 3.2 成本熔断机制 (Cost Circuit Breaker)

*   State 内嵌 `cost_accumulator`，每次 API 调用后实时累加费用。
*   达到用户预设阈值时自动挂起管线（`interrupt_before`），推送通知。
*   与 LangSmith 仪表盘联动，提供事后成本审计。

### 3.3 asyncio vs Celery 分层策略

| 场景 | MVP 方案 | 扩容方案 |
| :--- | :--- | :--- |
| 单 Agent 内并发调用多个视频 API | `asyncio.gather()` + `Semaphore(N)` | 不变 |
| 多章节并行处理 | LangGraph `Send()` | 不变 |
| 跨机器任务分发 | 不需要 | Celery + Redis |
| 长时间轮询视频生成结果 | `asyncio.sleep()` + 超时保护 | Celery Beat + Callback |

### 3.4 多租户隔离方案

*   每个团队/用户独立 Thread ID + Session ID。
*   数据库层面通过 PostgreSQL RLS 实现行级数据隔离。
*   向量库按 namespace/collection 隔离不同用户的角色档案。
