# Implementation Plan - Loom System (织影系统) v1

Implementation Plan, Task List and Thought in Chinese

本项目旨在构建一个基于 LangGraph 的多智能体长文本转视频自动化管线。

## 1. 项目技术栈确认 (Refined)
- **核心框架**: LangGraph (TypedDict + Channel Reducer 模式)
- **并发与限速**: `asyncio` + `Semaphore` + `aiolimiter` (Leaky Bucket 思路)
- **持久化**: 
    - MVP: `SQLiteCheckpointer` (零配置稳定版)
    - 生产预留: PostgreSQL (pgvector 分层 Schema)
- **向量数据库**: ChromaDB (Namespace 隔离模型)
- **监控**: LangSmith (可选开启，默认开关保护)
- **模型支持**: Ollama (本地), DeepSeek/Qwen (云端), Kling 3.0 (视频)
- **合成引擎**: FFmpeg (平台感知型封装)

## 2. 目录结构建议 (Enterprise Src-Layout)
```text
loom-system/
├── src/
│   └── loom/
│       ├── core/
│       │   ├── engine.py          # LangGraph 定义
│       │   ├── state.py           # 状态与 Reducers
│       │   └── supervisor.py      # 路由逻辑
│       ├── agents/                # 原子 Agent
│       ├── modules/               # 通用组件
│       ├── db/                    # 存储适配
│       ├── ui/                    # 审批界面
│       ├── config/                # 配置管理
│       └── main.py                # 系统入口
├── tests/                         # 独立测试目录
├── docs/                          # 文档目录
├── .env.example
├── pyproject.toml                 # 现代 Python 项目配置
├── requirements.txt
└── README.md
```

## 3. 核心模块实现顺序 (Adjusted)
1.  **Foundation (Sprint 1)**: 
    - `state.py` (Reducers), `settings.py` (LangSmith Toggle)。
    - **`cost_guard.py` 提前实现**，拦截所有 API 调用。
2.  **Ingestion & Memory (Sprint 1)**: `processor.py` (双层 RAG), `memory.py` (版本化缓存)。
3.  **Agents & Logic (Sprint 2)**: 
    - `storyboard.py` (Strict JSON), `supervisor.py` (Mock 优先)。
    - `engine.py` (Initial Graph Structure)。
4.  **Persistence & HITL (Sprint 2/3)**: 
    - `SQLiteCheckpointer` 快速上线。
    - **FastAPI + Streamlit** 审批流构建 (解决同步异步混用坑)。
5.  **Video & Rate Limiting (Sprint 3)**: `generator.py` (Semaphore + aiolimiter)。
6.  **Polishing (Sprint 4)**: `ffmpeg_tools.py` (OS 兼容性处理), e2e 测试。

## 4. 关键设计细节补充
- **State 设计**: 使用 `TypedDict` 结合 `Annotated` 定义 `operator.add` 或自定义 reducer，确保状态合并的稳定性。
- **Supervisor 安全**: 手写多智能体协调逻辑，设置 `recursion_limit` 防止死循环，对 API 异常进行 `tenacity` 重试封装。
- **视频任务跟踪**: `video_tasks` 列表存储 `TaskRecord` (ID, Status, Path, Error)，便于 UI 实时展示进度。
- **FFmpeg 兼容性**: 封装层自动检测 `sys.platform`，动态调整字体路径 (e.g., AppleGothic vs Arial)。

## 5. 风险防范 (Updated)
- **连接池健康**: `checkpointer.py` 使用连接池并封装重连逻辑。
- **Streamlit 刷新问题**: 采用 FastAPI 作为真正的主进程运行 LangGraph，Streamlit 仅作为交互层。
- **速率限制**: 引入 `aiolimiter` 确保在并发数为 N 的同时，每分钟请求数不超限。

## 6. 验证计划
- **E2E 流程**: 使用 `pytest-asyncio` 模拟完整长文本输入，通过 Mock Kling 响应验证分镜到生成的闭环。
- **持久化测试**: 在 HITL 节点手动终止进程，重启后验证 `thread_id` 状态能够从 SQLite 恢复。
- **成本熔断**: 设置极低阈值 ($0.01)，验证系统能在 Ingestion 阶段准时刹车。
