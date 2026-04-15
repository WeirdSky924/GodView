# GodView - AI 驱动的小说生成系统

GodView 是一个基于多 Agent 协作的智能小说生成平台，支持从大纲创建、章节生成到效果评估的完整创作流程。

## 核心功能

### 创作辅助
- **小说编辑器** - 章节创建、编辑、保存与导出（TXT/Markdown）
- **大纲管理** - 支持章节大纲、情绪曲线设计
- **读者模拟** - 模拟真实读者反馈

### AI 能力
- **Director 上帝模式** - 全局创作指导和干预
- **工作流引擎** - 可视化工作流编排与执行
- **多 Agent 协作** - 设定 Agent、世界管理等智能体

### 分析工具
- **章节评估** - 内容质量与连贯性评估
- **Diff 对比** - 章节版本差异可视化
- **干预日志** - 记录并评估人工干预效果

## 技术架构

### 数据库（31 个模型，200+ 数据表）
- **PostgreSQL** - 关系数据库，存储项目、章节、角色、设定等结构化数据
- **Qdrant** - 向量数据库，用于语义搜索和相似度匹配
- **NebulaGraph** - 图数据库，存储角色关系、记忆关联、伏笔追踪

### LLM 支持
支持多种大语言模型提供商：
- OpenAI（GPT-4o）
- Anthropic（Claude）
- 智谱 AI（GLM-4）
- 通义千问（Qwen）
- DeepSeek
- Moonshot（Kimi）
- 百川（Baichuan）
- 零一万物（Yi）
- MiniMax
- OpenRouter

---

## 一键部署

### 环境要求

| 软件 | 版本 | 说明 |
|------|------|------|
| Python | 3.11+ | 后端运行环境 |
| Node.js | 20+ | 前端运行环境 |
| Docker | 最新版 | 数据库容器 |
| Git | 任意 | 代码管理 |

### 快速安装

```bash
# 1. 克隆项目
git clone <仓库地址>
cd Godview

# 2. 运行安装脚本
python install.py
```

安装脚本会引导你完成：
1. 选择环境类型（Conda / venv）
2. 自动安装 Docker（如未安装）
3. 创建 Python 虚拟环境
4. 安装前后端依赖
5. 初始化数据库
6. 生成启动脚本

### 启动项目

**Linux/macOS:**
```bash
./start.sh
```

**Windows:**
```bash
start.bat
```

启动脚本会自动：
- 启动 Docker 容器（PostgreSQL、Qdrant、NebulaGraph）
- 激活 Conda 环境（如使用 Conda）
- 启动后端服务（端口 8000）
- 启动前端服务（端口 5173）

### 访问地址

| 服务 | 地址 |
|------|------|
| 前端界面 | http://localhost:5173 |
| 后端 API | http://localhost:8000 |
| API 文档 | http://localhost:8000/docs |
| 健康检查 | http://localhost:8000/health |

---

## 配置说明

### 环境变量

复制并编辑配置文件：
```bash
cp .env.example .env
```

### 必要配置

```ini
# 数据库
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/godview
QDRANT_URL=http://localhost:6333
NEBULA_HOST=127.0.0.1
NEBULA_PORT=9669

# LLM（至少配置一个）
LLM_PROVIDER=openai
LLM_OPENAI_API_KEY=your-api-key-here
LLM_OPENAI_MODEL=gpt-4o

# Embedding
EMBEDDING_PROVIDER=sentence_transformers
EMBEDDING_ST_MODEL=all-MiniLM-L6-v2
```

### 多 LLM 配置示例

```ini
# 智谱 AI
LLM_ZHIPU_API_KEY=your-zhipu-key
LLM_ZHIPU_MODEL=glm-4-plus

# 通义千问
LLM_QWEN_API_KEY=your-qwen-key
LLM_QWEN_MODEL=qwen-max

# DeepSeek
LLM_DEEPSEEK_API_KEY=your-deepseek-key
```

---

## 数据备份与恢复

### 备份数据库

```bash
python backup_database.py
```

备份内容：
- PostgreSQL 所有表数据
- Qdrant 向量集合
- NebulaGraph 图数据
- 配置文件（敏感信息脱敏）

备份文件保存在 `./backups/backup_<时间戳>/` 目录。

### 恢复数据

```bash
python restore_database.py ./backups/backup_<时间戳>
```

---

## 项目结构

```
Godview/
├── app/                    # 后端代码
│   ├── api/               # API 路由
│   ├── models/            # 数据模型（31个）
│   ├── services/          # 业务逻辑
│   └── database/          # 数据库连接
├── frontend/              # 前端代码（React + Vite）
├── data/                  # 数据持久化目录
│   ├── postgres/
│   ├── qdrant/
│   └── nebula/
├── init/sql/              # 数据库初始化脚本
├── backups/               # 备份文件目录
├── main.py                # FastAPI 入口
├── install.py             # 一键安装脚本
├── start.sh               # Linux/Mac 启动脚本
├── start.bat              # Windows 启动脚本
├── backup_database.py     # 备份脚本
├── docker-compose.yml     # Docker 配置
├── requirements.txt       # Python 依赖
└── .env.example           # 环境变量模板
```

---

## 页面功能验证

启动后建议按以下顺序检查：

1. **前端管理界面** - http://localhost:5173
2. **Director 上帝模式** - 创建会话、查看工作流日志
3. **小说编辑页** - 创建/编辑/导出章节
4. **章节评估页** - 触发 AI 评估
5. **读者模拟页** - 执行模拟测试
6. **Diff 工具页** - 版本对比
7. **可视化工作台** - 查看工作流/剧情树
8. **干预日志页** - 记录和评估干预效果

---

## 常见问题

### Docker 启动失败

**Windows:** 确保已启动 Docker Desktop

**Linux:**
```bash
sudo systemctl start docker
```

### 数据库初始化失败

检查 PostgreSQL 是否正常运行：
```bash
docker compose ps
```

### 前端启动失败

确保在 `frontend` 目录下执行：
```bash
cd frontend
npm install
npm run dev
```

### AI 功能不可用

检查 `.env` 中的 LLM API Key 是否正确配置。

---

## 许可证

MIT License
