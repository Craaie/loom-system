# 织影系统 (Loom System) - 项目实施计划

## 1. 迭代周期 (2026 Q2)
采用敏捷开发模式，分为 4 个 Sprint，每双周为一个周期。

### Sprint 1: 基础设施与"文本大脑" (Weeks 1-2)

**目标**：跑通从小说文本到 JSON 分镜的完整链路。

| 任务 | 交付物 | 验收标准 |
| :--- | :--- | :--- |
| 容器化环境 | `docker-compose.yml` (Postgres, Redis, ChromaDB) | `docker-compose up` 一键启动 |
| 双层 RAG 分片 | Ingestion Service：章节粗切 + 角色实体细切 | 百万字小说 < 5 分钟完成索引 |
| 分镜生成脚本 | DeepSeek API + Pydantic 约束输出 | JSON 校验通过率 > 95% |
| State 定义 | 14 字段版 `LoomState` TypedDict | 含 `cost_accumulator` 和 `character_registry` |

### Sprint 2: 工作流编排与人工审批 (Weeks 3-4)

**目标**：让脚本升级为"有状态、可中断、可恢复"的工作流。

| 任务 | 交付物 | 验收标准 |
| :--- | :--- | :--- |
| Supervisor Agent | LangGraph 条件图 + Task Classifier 路由 | 简单任务走 Ollama，复杂任务走云端 |
| 循环自省 | Pydantic 校验失败 → 自动重写（最多 3 轮） | 3 轮后降级至模板兜底 |
| Checkpointer | Postgres Checkpointer 持久化 | 模拟宕机后可恢复至上一状态 |
| HITL 审批台 | Streamlit MVP：通过/修改/拒绝 + 超时策略 | 24h 超时低风险项自动通过 |

### Sprint 3: 异步并发与视频生成 (Weeks 5-6)

**目标**：打通视频 API 并实现稳定的并发生成。

| 任务 | 交付物 | 验收标准 |
| :--- | :--- | :--- |
| 视频 API 对接 | Kling 3.0 / Runway Gen-4 异步调用 | 单镜头 10s 视频生成 < 3 分钟 |
| asyncio 并发 | `Semaphore(5)` 限流 + 超时保护 | 5 路并发稳定运行 30 分钟无崩溃 |
| 成本熔断器 | `cost_accumulator` 累加 + 阈值触发中断 | 达到 ¥100 自动暂停管线 |
| 多 API Key 轮换 | Key 池 + 指数退避重试 | 单 Key 触发限流后自动切换 |

### Sprint 4: 合成、监控与封装 (Weeks 7-8)

**目标**：达到可交付、可展示的完整系统。

| 任务 | 交付物 | 验收标准 |
| :--- | :--- | :--- |
| FFmpegAssembler | 格式归一化 + 字幕压制 + 错误回退 | 10 分镜拼接 < 2 分钟 |
| LangSmith 监控 | 全链路 Trace + Token 成本仪表盘 | 可追溯任意一次分镜的 Prompt |
| 角色记忆缓存 | `character_registry` 缓存 + HITL 刷新 | 同一任务内零重复 RAG 查询 |
| API 文档 | FastAPI OpenAPI 规范文档 | 所有接口可通过 Swagger UI 调用 |

## 2. 风险缓冲

| 风险项 | 影响 | 缓冲策略 |
| :--- | :--- | :--- |
| 视频 API 频繁变更 | Sprint 3 阻塞 | 预留 Runway 作为 Fallback |
| 长小说 Token 溢出 | 分镜质量下降 | Context Compression 摘要前文 |
| Streamlit 并发瓶颈 | 多人审批卡顿 | Sprint 4 预研 FastAPI WebSocket 替代方案 |
