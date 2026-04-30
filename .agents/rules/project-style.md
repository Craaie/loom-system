---
trigger: always_on
---

永远遵守：
1. 所有工作流必须用 LangGraph（带 Conditional Edges 和 Checkpointer）
2. 分镜输出必须是 Pydantic 严格 JSON
3. 角色设定必须先 RAG 检索 ChromaDB，禁止幻觉
4. 视频生成前必须 HITL 人工确认（防止 API 浪费）
5. 模型路由：简单任务 Ollama 本地，复杂才云端
6. 代码必须加类型提示 + 错误重试 + 断点续跑逻辑

任何代码生成任务必须：
1. 先引用 loom_0x_xxx.md 中的具体内容作为依据
2. 所有接口/类型必须与 detailed_design 完全一致
3. 优先使用 typing + Pydantic
4. 必须有错误处理和日志
5. 任何代码生成/修改任务，必须先参考 docs/implementation-plan-v1.md 中的职责划分、风险防范和实现顺序。