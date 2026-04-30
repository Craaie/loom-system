项目名称：织影 (Loom System) —— 基于多智能体协作的长文本转视频自动化系统
核心职责：
设计并实现基于 LangGraph 的有向图工作流，支持任务的循环自省（Self-correction）与断点续跑，确保复杂任务的长链路稳定性。
研发双层 RAG (Retrieval-Augmented Generation) 策略，通过章节级与实体级（角色档案）的精准检索，解决长文本视频化过程中的视觉一致性问题。
构建实时成本熔断机制与智能模型路由框架，根据任务复杂度自动切换本地 Ollama 与云端 Kling/DeepSeek 模型，有效平衡生成质量与 API 成本。
利用 asyncio 与 aiolimiter 实现高并发生成管线，集成 FFmpeg 自动化后期处理，实现素材的标准化归一与动态转场合成。

项目亮点：
实现了从“长篇小说”到“成品短视频”的全自动化闭环。
引入 HITL (Human-in-the-Loop) 机制，通过 Streamlit 审批界面实现关键节点的人工干预。
解决了大模型生成视频过程中常见的格式不统一、音频不对位、人物“变脸”等生产级痛点。


# Loom System (织影) AI Agent 开发面试指南

本报告基于 **方案A：侧重 AI 工程化与架构** 编写，涵盖了 10 个以上 AI Agent 开发工程师职位的核心面试题、深度答案、关键技术点以及项目中对应的代码参考。

---

## 1. 复杂工作流编排：为什么选择 LangGraph 而非简单的线性 Chain？
- **技术点**：有向图逻辑、循环自省（Self-correction）、状态持久化。
- **面试答案**：视频生成管线具有长链路和高度不确定性。线性 Chain 无法处理“生成失败-修正-重试”的循环逻辑。LangGraph 通过 `StateGraph` 定义节点和条件边，允许在分镜生成失败时自动返回 `storyboard` 节点进行修正，且其内置的 `Checkpointer` 确保了长任务的断点续跑。
- **项目代码参考**：
    - [engine.py:L399-465](file:///Users/Colin/web3/loom-system/backend/app/core/engine.py#L399-465) : 定义了复杂的 `StateGraph` 和条件边逻辑。
    - [engine.py:L153-158](file:///Users/Colin/web3/loom-system/backend/app/core/engine.py#L153-158) : 使用 `tenacity` 配合 LangGraph 实现节点级重试。

## 2. 状态管理：如何处理 Agent 运行过程中的状态冲突和数据覆盖？
- **技术点**：`TypedDict` 状态定义、`Annotated` 与 `Reducer` 函数。
- **面试答案**：在多 Agent 协作中，多个节点可能同时更新 State。我们使用了 LangGraph 的 Reducer 机制。通过 `Annotated` 标记字段，并自定义 `reduce_list` 和 `reduce_dict` 函数。例如，`reduce_list` 实现了基于 `task_id` 的自动去重，确保最新的任务状态覆盖旧状态而非盲目追加。
- **项目代码参考**：
    - [state.py:L54-67](file:///Users/Colin/web3/loom-system/backend/app/core/state.py#L54-67) : `reduce_list` 函数实现了基于 ID 的去重逻辑。
    - [state.py:L91-103](file:///Users/Colin/web3/loom-system/backend/app/core/state.py#L91-103) : 使用 `Annotated` 将 Reducer 应用于 `LoomState`。

## 3. 成本控制：如何在 Agent 运行过程中防止 API 费用超支？
- **技术点**：实时成本累加器、熔断器（Circuit Breaker）模式。
- **面试答案**：我们在全局 State 中维护了一个 `cost_accumulator` 字段。每个生成节点完成后，都会调用 `update_and_check_cost` 模块。如果检测到当前累加费用超过预设阈值，会立即抛出 `CostLimitExceededError` 异常，利用 LangGraph 的异常机制挂起管线，而非事后统计，实现了真正的实时熔断。
- **项目代码参考**：
    - [cost_guard.py:L12-34](file:///Users/Colin/web3/loom-system/backend/app/modules/cost_guard.py#L12-34) : 核心熔断器逻辑。
    - [engine.py:L303](file:///Users/Colin/web3/loom-system/backend/app/core/engine.py#L303) : 在节点执行中实时调用成本检查。

## 4. 模型路由：如何根据任务复杂度动态分配 LLM 资源？
- **技术点**：智能调度（Supervisor）、条件分支、本地与云端模型混合方案。
- **面试答案**：我们实现了 `TaskClassifier` 分类器。它根据输入文本长度、是否包含复杂角色描写、以及累计错误率进行多维评估。简单的摘要任务路由至本地 `Ollama`；复杂创意任务路由至 `DeepSeek/Gemini`。在云端 API 连续失败时，Supervisor 会自动路由至本地模型作为兜底，保证系统可用性。
- **项目代码参考**：
    - [supervisor.py:L78-194](file:///Users/Colin/web3/loom-system/backend/app/core/supervisor.py#L78-194) : `TaskClassifier` 包含详细的多级路由决策树。
    - [engine.py:L92-138](file:///Users/Colin/web3/loom-system/backend/app/core/engine.py#L92-138) : `supervisor_node` 处理路由决策的下发。

## 5. 视觉一致性：如何解决 AI 视频生成中的人物“变脸”问题？
- **技术点**：双层 RAG、实体提取记忆、Prompt 注入。
- **面试答案**：我们采用双层索引策略。首先通过 NER 提取角色实体，并为其建立独立的向量集合（Collection）。在生成分镜视频前，Agent 会执行 RAG 检索该角色的“视觉档案”（外貌、衣着特征），并将其作为强制上下文注入生成 Prompt，从而在不同镜头间维持视觉特征的高度一致。
- **项目代码参考**：
    - [detailed_design.md:L7-14](file:///Users/Colin/web3/loom-system/docs/loom_03_detailed_design.md#L7-14) : 详细记录了双层 RAG 分片策略的设计。
    - [state.py:L88](file:///Users/Colin/web3/loom-system/backend/app/core/state.py#L88) : `character_registry` 字段用于存储检索出的角色特征。

## 6. 系统韧性：Agent 运行中途宕机，如何保证不丢失昂贵的视频素材？
- **技术点**：`Checkpointer` 持久化、幂等生成。
- **面试答案**：我们利用 LangGraph 的 `MemorySaver`（MVP阶段）或 `SqliteSaver`（生产阶段）对每个节点的输出进行快照持久化。由于视频生成（如 Kling）费用昂贵且耗时，系统会在生成每个片段后更新状态。宕机恢复后，系统通过 `thread_id` 加载 Checkpoint，跳过已生成的片段，直接从断点处继续执行。
- **项目代码参考**：
    - [engine.py:L458-465](file:///Users/Colin/web3/loom-system/backend/app/core/engine.py#L458-465) : 编译图时配置 Checkpointer。
    - [state.py:L82](file:///Users/Colin/web3/loom-system/backend/app/core/state.py#L82) : `chapter_index` 作为断点续跑的核心锚点。

## 7. 结构化输出保证：模型偶尔不按要求输出 JSON 怎么办？
- **技术点**：Pydantic 协议、自省修正（Self-reflection）循环。
- **面试答案**：我们强约束 Agent 使用 `Pydantic` 模型进行 `BaseModel.model_dump_json()` 输出，并开启 LLM 的 JSON Mode。当解析失败时，Supervisor 捕获 `ValidationError`，并将错误堆栈反馈给 Agent 要求其重新生成。这种“产生-校验-反馈-修正”的闭环大大提高了系统在非确定性输入下的稳定性。
- **项目代码参考**：
    - [engine.py:L107-121](file:///Users/Colin/web3/loom-system/backend/app/core/engine.py#L107-121) : 包含最终静态兜底逻辑，防止死循环。
    - [detailed_design.md:L150-154](file:///Users/Colin/web3/loom-system/docs/loom_03_detailed_design.md#L150-154) : 阐述了 Pydantic + Function Calling 的三层保障机制。

## 8. 并发与限流：如何优雅地处理多 API 供应商的不同频率限制（Rate Limit）？
- **技术点**：`asyncio` 异步管线、`aiolimiter`、令牌桶算法。
- **面试答案**：在批量生成视频和音频时，我们使用 `asyncio.gather` 配合 `Semaphore` 控制总并发数。针对特定供应商（如 Kling 限制 QPS），我们引入了 `aiolimiter` 实现令牌桶限流。这确保了在大规模任务下，系统不会因触发布控方的 429 错误而被封禁，同时也最大化利用了网络带宽。
- **项目代码参考**：
    - [README.md:L16](file:///Users/Colin/web3/loom-system/README.md#L16) : 技术栈中明确列出 `aiolimiter`。
    - [engine.py:L226](file:///Users/Colin/web3/loom-system/backend/app/core/engine.py#L226) : `generator.generate_batch` 封装了内部的并发控制逻辑。

## 9. 智能兜底：如果最先进的视频模型（如 Kling）API 整体挂了，系统如何自愈？
- **技术点**：多级 Fallback 策略、场景路由降级。
- **面试答案**：系统分三层兜底：1. 网络抖动触发 `tenacity` 的指数退避重试；2. 模型侧持续失败则路由至 `SceneRouter` 决定是否降级为“图片+镜头转动”模式；3. 极端情况下，Supervisor 注入预定义的分镜模板（Static Fallback），确保管线能够产出最小可用成品而非卡死。
- **项目代码参考**：
    - [supervisor.py:L50-68](file:///Users/Colin/web3/loom-system/backend/app/core/supervisor.py#L50-68) : `SceneRouter` 实现了根据重要度决策降级策略。
    - [engine.py:L108-111](file:///Users/Colin/web3/loom-system/backend/app/core/engine.py#L108-111) : `static-fallback` 终极降级逻辑。

## 10. 长文本处理：小说字数太多超过 Context Window 怎么办？
- **技术点**：流式摄入、总结式压缩（Summarization）、递归合并。
- **面试答案**：我们不直接将整本小说喂入模型，而是通过 `BatchAnalyzer` 进行流式切片处理。利用 DeepSeek 的 `Batch API` 进行并行角色分析，并将结果递归合并入 `character_registry`。这种“局部处理+全局聚合”的方式，使得系统能处理上百万字的小说而不受单次 Context Window 的限制。
- **项目代码参考**：
    - [engine.py:L240-292](file:///Users/Colin/web3/loom-system/backend/app/core/engine.py#L240-292) : `batch_analysis_node` 处理长文本的并行分析。
    - [detailed_design.md:L8-10](file:///Users/Colin/web3/loom-system/docs/loom_03_detailed_design.md#L8-10) : 描述了粗切与细切的双层分片策略。

---
*文档生成于：2026-03-26*
