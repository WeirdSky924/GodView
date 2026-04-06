# Godview - AI 小说世界生成器

一个基于多 Agent 系统的叙事生态系统，将小说创作从"生成文本"转变为"模拟世界"。

## 核心理念

通过 LLM 自动生成带有特定性格和目标的"角色 Agent"，通过它们在特定世界观下的互动，自下而上地涌现出剧情。

## 核心特性

- **记忆与世界锚定**：使用图向量数据库管理角色长期记忆、好感度、物品归属
- **导演系统**：Summarizer → Master Plotter → Hook Manager → Writer Agent 四层架构
- **OOC 审查**：基于 Voice Embedding 和向量相似度的角色一致性检查
- **世界生成机**：程序化生成新区域、NPC、事件
- **创世神干预**：随时暂停、修改、回档，带影响范围提示

## 技术栈

| 模块 | 技术选型 |
|------|----------|
| 控制与编排 | LangChain → LangGraph |
| 大模型引擎 | 多模型路由 (Claude/GPT-4o) |
| 关系/状态存储 | PostgreSQL (Supabase) |
| 逻辑与记忆存储 | NebulaGraph (图 + 向量统一) |
| 后端 | FastAPI + WebSocket |
| 前端 | React + React Flow |
| 可观测性 | LangSmith |

## 项目结构

```
godView/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI 入口
│   ├── config.py            # 配置管理
│   ├── models/              # 数据模型
│   │   ├── __init__.py
│   │   ├── character.py     # 角色模型
│   │   ├── world.py         # 世界观/区域模型
│   │   ├── plot.py          # 剧情/伏笔模型
│   │   └── snapshot.py      # 世界快照模型
│   ├── agents/              # Agent 系统
│   │   ├── __init__.py
│   │   ├── base.py          # Agent 基类
│   │   ├── director/        # 导演系统
│   │   │   ├── __init__.py
│   │   │   ├── summarizer.py
│   │   │   ├── master_plotter.py
│   │   │   ├── hook_manager.py
│   │   │   └── writer.py
│   │   ├── character_agent.py
│   │   ├── procgen.py       # 世界生成 Agent
│   │   └── evaluator.py     # 章节判定/读者模拟
│   ├── database/            # 数据库层
│   │   ├── __init__.py
│   │   ├── postgres.py      # PostgreSQL 操作
│   │   └── nebulagraph.py   # NebulaGraph 操作
│   ├── router/              # Agent 路由
│   │   ├── __init__.py
│   │   └── model_router.py
│   └── api/                 # API 路由
│       ├── __init__.py
│       ├── routes.py
│       └── websocket.py
├── frontend/                # React 前端 (待实现)
├── tests/                   # 测试文件
├── config/
│   ├── settings.yaml        # 配置文件
│   └── prompts/             # Prompt 模板
├── logs/                    # 日志目录
├── requirements.txt
└── .env.example
```

## 快速开始

### 1. 环境准备

```bash
# 创建虚拟环境
python -m venv venv
venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 填入 API 密钥和数据库连接
```

### 3. 运行

```bash
# 启动后端
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 访问 API 文档
http://localhost:8000/docs
```

## 状态

🚧 开发中 - 初步原型阶段

## License

MIT
