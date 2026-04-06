# GodView - AI 驱动的小说生成系统 (导演模式)

## 项目简介

GodView 是一个基于多 Agent 协同的小说自动/半自动生成系统。采用"导演模式"工作流，多个 AI Agent 各司其职（角色演绎、伏笔管理、剧情推进、文本生成），实现长篇小说的连贯性生成。

## 系统组件一览

本项目由 **4 个组件** 构成，你可以根据需要选择全部或仅启动核心服务：

| 组件 | 作用 | 是否必须 |
|------|------|---------|
| **FastAPI 后端** | 核心服务，提供 API 和 WebSocket | ✅ 必须 |
| **PostgreSQL** | 存储角色、剧情、章节等结构化数据 | 推荐 |
| **Qdrant** | 向量数据库，用于语义搜索和角色声音一致性 | 推荐 |
| **NebulaGraph** | 图数据库，存储人物关系和记忆关联 | 可选 |

> **小白提示**：即使不安装任何数据库，后端也能正常启动（会显示部分功能不可用）。建议至少安装 Docker 并用 `docker compose` 一键启动 PostgreSQL + Qdrant。

---

## 快速开始（从零开始）

### 前置准备

安装以下软件（全部免费）：

| 软件 | 下载链接 | 用途 |
|------|---------|------|
| **Python 3.10+** | https://www.python.org/downloads/ | 运行后端 |
| **Git** | https://git-scm.com/ | 下载代码 |
| **Docker Desktop** | https://www.docker.com/products/docker-desktop/ | 一键启动数据库 |

---

### 第 1 步：下载项目

```bash
git clone <repo-url>
cd Godview
```

---

### 第 2 步：配置 Python 环境（三选一）

#### 方式 A：Conda（推荐）

```bash
# 创建环境（Python 3.11）
conda create -n godview python=3.11 -y

# 激活环境
conda activate godview

# 安装依赖
pip install -r requirements.txt
```

#### 方式 B：venv 虚拟环境

```bash
# 创建虚拟环境
python -m venv venv

# 激活（Windows）
venv\Scripts\activate

# 激活（Linux/Mac）
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

#### 方式 C：全局安装（不推荐，但最简单）

```bash
pip install -r requirements.txt
```

---

### 第 3 步：配置环境变量

```bash
# 复制模板
copy .env.example .env        # Windows
cp .env.example .env          # Linux/Mac
```

用文本编辑器打开 `.env`，至少修改以下内容：

| 配置项 | 说明 | 示例值 |
|--------|------|--------|
| `LLM_API_KEY` | 大模型 API Key | `sk-xxxxxxxx` |
| `EMBEDDING_PROVIDER` | Embedding 模式 | `sentence_transformers` |

#### Embedding 模式说明（三选一）

| 模式 | 配置值 | 需要 API Key？ | 需要联网？ | 适合谁？ |
|------|--------|:---:|:---:|---------|
| **OpenAI API** | `openai` | ✅ 是 | ✅ 是 | 有 OpenAI/兼容 API Key 的用户 |
| **Sentence-Transformers** | `sentence_transformers` | ❌ 否 | 首次需要 | 最省事，首次运行自动下载模型（约 80MB） |
| **Ollama** | `ollama` | ❌ 否 | 不需要 | 已安装 Ollama 的用户 |

**最简单的配置**（适合新手）：
```ini
EMBEDDING_PROVIDER=sentence_transformers
EMBEDDING_MODEL=all-MiniLM-L6-v2
```
无需任何 API Key，首次运行时自动下载模型到本地。

---

### 第 4 步：启动数据库（Docker 方式）

确保已安装并启动 Docker Desktop，然后在项目根目录执行：

```bash
# 启动 PostgreSQL + Qdrant（推荐）
docker compose up -d postgres qdrant

# 或启动全部组件（含 NebulaGraph）
docker compose up -d
```

等待 1-2 分钟，验证服务状态：
```bash
docker compose ps
```

看到所有服务状态为 `Up` 即可。

#### 不使用 Docker 的手动安装

如果你不想用 Docker，也可以手动安装：

**PostgreSQL**
```bash
# Windows: 从 https://www.postgresql.org/download/windows/ 下载安装包
# 安装后执行：
createdb -U postgres godview
```

**Qdrant**
```bash
# 下载：https://qdrant.tech/documentation/quickstart/
# 或直接用 Docker：
docker run -d -p 6333:6333 qdrant/qdrant
```

**NebulaGraph**（可选）
```bash
# 参考：https://docs.nebula-graph.io/3.6.0/
# 或使用 Docker Compose：
docker compose up -d storaged metastore graphd
```

---

### 第 5 步：启动后端服务

```bash
# 初始化数据库表（首次运行）
python scripts.py init-db

# 启动服务（开发模式，自动热重载）
python scripts.py start --reload
```

或者直接：
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

看到类似输出说明启动成功：
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
```

---

### 第 6 步：验证

浏览器打开以下地址：

| 地址 | 说明 |
|------|------|
| http://localhost:8000/ | 根页面 |
| http://localhost:8000/health | 健康检查 |
| http://localhost:8000/docs | API 文档（Swagger UI） |
| http://localhost:8000/redoc | API 文档（ReDoc） |

测试 Embedding 配置接口：
```bash
# 查看支持的 Embedding Provider
curl http://localhost:8000/api/config/embedding/providers

# 查看当前配置
curl http://localhost:8000/api/config/embedding

# 测试连接
curl -X POST http://localhost:8000/api/config/embedding/test
```

---

## 配置管理 API

运行时可通过 API 动态切换 Embedding 模式，无需重启服务：

### 获取支持的 Provider 列表
```bash
GET /api/config/embedding/providers
```

### 切换 Embedding 模式
```bash
PUT /api/config/embedding
Content-Type: application/json

{
  "provider": "ollama",
  "model": "nomic-embed-text",
  "base_url": "http://localhost:11434"
}
```

### 测试连接
```bash
POST /api/config/embedding/test
```

---

## 项目结构

```
Godview/
├── app/
│   ├── api/              # FastAPI 路由
│   │   ├── routes/       # 具体路由模块
│   │   │   ├── characters.py   # 角色管理
│   │   │   ├── worlds.py       # 世界管理
│   │   │   ├── plots.py        # 剧情管理
│   │   │   ├── websocket.py    # WebSocket 实时交互
│   │   │   └── config.py       # 配置管理
│   │   └── app.py        # 应用创建
│   ├── agents/           # Agent 系统
│   │   ├── director/     # 导演系统 Agents
│   │   │   ├── summarizer.py     # 剧情总结员
│   │   │   ├── master_plotter.py # 总编剧
│   │   │   ├── hook_manager.py   # 伏笔管理员
│   │   │   └── writer.py         # 内容执行官
│   │   ├── base.py       # Agent 基类
│   │   └── character.py  # 角色 Agent
│   ├── database/         # 数据库层
│   │   ├── postgres.py   # PostgreSQL 操作
│   │   ├── nebulagraph.py # NebulaGraph 操作
│   │   └── qdrant.py     # Qdrant 操作
│   ├── models/           # 数据模型
│   ├── services/         # 业务服务
│   │   ├── director.py           # 导演系统核心
│   │   ├── embedding_service.py  # Embedding 服务抽象层
│   │   └── novel_file_manager.py # 小说文件管理
│   └── config.py         # 应用配置
├── tests/                # 测试代码
├── schema/               # 数据库 Schema
├── main.py               # 应用入口
├── scripts.py            # 命令行工具
├── docker-compose.yml    # Docker 编排
├── requirements.txt      # 依赖列表
└── .env.example          # 环境变量模板
```

---

## 常用命令

```bash
# 启动服务
python scripts.py start --reload

# 初始化数据库
python scripts.py init-db

# 检查依赖
python scripts.py check

# Docker 启动全部数据库
docker compose up -d

# Docker 停止数据库
docker compose down

# Docker 查看日志
docker compose logs -f postgres
```

---

## 常见问题

### Q: `sentence_transformers` 下载模型很慢？
模型约 80MB，首次运行自动从 HuggingFace 下载。如果网络不佳，可临时改用 `openai` 模式或手动下载模型到本地。

### Q: Ollama 连接失败？
确保 Ollama 已启动且运行了 embedding 模型：
```bash
ollama pull nomic-embed-text
ollama serve
```

### Q: PostgreSQL 连接失败？
确认数据库已启动且端口 5432 未被占用：
```bash
docker compose ps postgres
```

---

## 开发计划

- [ ] 完善 Agent 实现
- [ ] 添加更多剧情模式
- [ ] 前端界面开发
- [ ] 性能优化

## License

MIT License