# GodView - AI 驱动的小说生成系统 (导演模式)

## 项目简介

GodView 是一个基于多 Agent 协同的小说自动/半自动生成系统，采用"导演模式"工作流，实现长篇小说的连贯性生成。

## 核心特性

- **多 Agent 协同**: 角色 Agent、世界生成 Agent、剧情评估 Agent 等各司其职
- **伏笔管理系统**: 自动埋设与回收伏笔，确保剧情完整性
- **图数据库支持**: NebulaGraph 存储人物关系和记忆关联
- **向量检索**: Qdrant 实现语义搜索和角色声音一致性检查
- **实时交互**: WebSocket 支持前端实时协作
- **版本回档**: 世界快照机制支持任意节点回退

## 技术栈

- **后端框架**: FastAPI
- **语言模型**: LangChain + OpenAI/Anthropic
- **关系数据库**: PostgreSQL
- **图数据库**: NebulaGraph
- **向量数据库**: Qdrant
- **异步处理**: asyncio, Celery

## 快速开始

### 环境要求

- Python 3.10+
- PostgreSQL 15+
- NebulaGraph 3.6+
- Qdrant 1.7+

### 安装步骤

```bash
# 1. 克隆项目
git clone <repo-url>
cd godview

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，配置数据库连接和 API Key

# 5. 启动服务
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 数据库初始化

```bash
# PostgreSQL
createdb godview
psql godview -f schema/postgres_init.sql

# NebulaGraph
nebula-console -addr 127.0.0.1 -port 9669 -user root -password nebula \
  -space godview_space < schema/nebula_schema.ngql
```

## 项目结构

```
godview/
├── app/
│   ├── api/              # FastAPI 路由
│   │   ├── routes/       # 具体路由模块
│   │   └── app.py        # 应用创建
│   ├── agents/           # Agent 系统
│   │   ├── director/     # 导演系统 Agents
│   │   ├── base.py       # Agent 基类
│   │   └── character.py  # 角色 Agent
│   ├── database/         # 数据库层
│   │   ├── postgres.py   # PostgreSQL 操作
│   │   ├── nebulagraph.py # NebulaGraph 操作
│   │   └── qdrant.py     # Qdrant 操作
│   ├── models/           # 数据模型
│   └── services/         # 业务服务
├── tests/                # 测试代码
├── schema/               # 数据库 Schema
├── main.py               # 应用入口
├── requirements.txt      # 依赖列表
└── .env.example          # 环境变量模板
```

## API 文档

启动服务后访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## WebSocket 接口

连接地址：`ws://localhost:8000/api/ws/connect/{client_id}`

消息类型:
- `start_session`: 开始会话
- `generate_dialogue`: 生成对话
- `generate_narrative`: 生成叙事
- `chapter_end_check`: 章节结束检查
- `intervention`: 用户干预

## 开发计划

- [ ] 完善 Agent 实现
- [ ] 添加更多剧情模式
- [ ] 前端界面开发
- [ ] 性能优化
- [ ] Docker 容器化

## License

MIT License