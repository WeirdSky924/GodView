# GodView - 新手可直接照着做的启动说明

这份说明按**从零开始**写，支持 4 种常见环境：

- Windows + venv
- Windows + conda
- Linux + venv
- Linux + conda

你不需要全部都做，只需要选择**一种**最适合你的方案。

## 我该选哪一种？

- **你是 Windows 用户，而且不熟悉 conda**：选 `Windows + venv`
- **你是 Windows 用户，平时就用 conda**：选 `Windows + conda`
- **你是 Linux 用户，而且不熟悉 conda**：选 `Linux + venv`
- **你是 Linux 用户，平时就用 conda**：选 `Linux + conda`

如果你完全不确定，默认推荐：

- **Windows 用户**：`Windows + venv`
- **Linux 用户**：`Linux + venv`

---

## 快速导航

- [0. 项目目前能做什么](#0-这个项目目前能做什么)
- [1. 先安装这些软件](#1-先安装这些软件)
- [2. 获取项目代码](#2-获取项目代码)
- [3. 选择你的环境方案](#3-选择你的环境方案)
  - [Windows + venv](#windows--venv)
  - [Windows + conda](#windows--conda)
  - [Linux + venv](#linux--venv)
  - [Linux + conda](#linux--conda)
- [4. 页面验证顺序](#4-页面验证顺序)
- [5. 常见问题](#5-常见问题)
- [6. 停止项目](#6-停止项目)

---

## 0. 这个项目目前能做什么

当前项目已经具备这些主要页面和能力：

- 前端管理界面
- Director 导演模式页面
- 小说章节编辑 / 保存 / 导出
- 章节评估
- 读者模拟
- Diff 对比工具
- 可视化工作台
- 干预日志与效果评估

推荐使用顺序：

1. 启动数据库
2. 启动后端
3. 启动前端
4. 打开页面验证

---

## 1. 先安装这些软件

请先安装下面这些软件。

### 1.1 Python 3.11

下载地址：

- https://www.python.org/downloads/

Windows 安装时请勾选：

- `Add python.exe to PATH`

安装完成后执行：

```bash
python --version
```

Linux 如需可执行：

```bash
python3 --version
```

---

### 1.2 Git

下载地址：

- https://git-scm.com/downloads

安装完成后执行：

```bash
git --version
```

---

### 1.3 Node.js 20+

下载地址：

- https://nodejs.org/

安装完成后执行：

```bash
node --version
npm --version
```

---

### 1.4 Docker Desktop / Docker Engine

- Windows 推荐：Docker Desktop
- Linux 推荐：Docker Engine + Docker Compose

安装完成后执行：

```bash
docker --version
docker compose version
```

---

### 1.5 可选：Conda

如果你想用 conda 管理 Python 环境，请先安装：

- Miniconda: https://docs.conda.io/en/latest/miniconda.html
- 或 Anaconda: https://www.anaconda.com/download

安装完成后执行：

```bash
conda --version
```

---

## 2. 获取项目代码

如果你还没有代码，请执行：

```bash
git clone <你的仓库地址>
cd Godview
```

项目根目录应该能看到这些文件：

- `main.py`
- `scripts.py`
- `requirements.txt`
- `docker-compose.yml`
- `frontend/`

---

## 3. 选择你的环境方案

下面 4 个方案只需要选 **一个**。

---

## Windows + venv

<details>
<summary><strong>点击展开：Windows + venv 完整步骤</strong></summary>

### A-1. 创建虚拟环境

```bash
python -m venv .venv
```

### A-2. 激活虚拟环境

PowerShell：

```bash
.venv\Scripts\Activate.ps1
```

CMD：

```bash
.venv\Scripts\activate.bat
```

### A-3. 安装后端依赖

```bash
pip install -r requirements.txt
```

### A-4. 检查后端依赖

```bash
python scripts.py check
```

### A-5. 安装前端依赖

```bash
cd frontend
npm install
cd ..
```

### A-6. 复制环境变量

```bash
copy .env.example .env
```

然后打开 `.env`，至少确认这些值：

```ini
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/godview
QDRANT_URL=http://localhost:6333
EMBEDDING_PROVIDER=sentence_transformers
EMBEDDING_MODEL=all-MiniLM-L6-v2
LLM_PROVIDER=openai
LLM_API_KEY=your-api-key-here
LLM_MODEL=gpt-4o
```

### A-7. 启动数据库

先打开 Docker Desktop，再执行：

```bash
docker compose up -d postgres qdrant
```

检查状态：

```bash
docker compose ps
```

### A-8. 初始化数据库

```bash
python scripts.py init-db
```

### A-9. 启动后端

```bash
python scripts.py start --reload
```

### A-10. 启动前端

新开一个终端窗口：

```bash
cd frontend
npm run dev
```

### A-11. 打开页面

- 前端：http://localhost:5173
- 后端文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

</details>

---

## Windows + conda

<details>
<summary><strong>点击展开：Windows + conda 完整步骤</strong></summary>

### B-1. 创建 conda 环境

```bash
conda create -n godview python=3.11 -y
```

### B-2. 激活 conda 环境

```bash
conda activate godview
```

### B-3. 安装后端依赖

```bash
pip install -r requirements.txt
```

### B-4. 检查后端依赖

```bash
python scripts.py check
```

### B-5. 安装前端依赖

```bash
cd frontend
npm install
cd ..
```

### B-6. 复制环境变量

```bash
copy .env.example .env
```

然后打开 `.env`，至少确认这些值：

```ini
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/godview
QDRANT_URL=http://localhost:6333
EMBEDDING_PROVIDER=sentence_transformers
EMBEDDING_MODEL=all-MiniLM-L6-v2
LLM_PROVIDER=openai
LLM_API_KEY=your-api-key-here
LLM_MODEL=gpt-4o
```

### B-7. 启动数据库

先打开 Docker Desktop，再执行：

```bash
docker compose up -d postgres qdrant
```

### B-8. 初始化数据库

```bash
python scripts.py init-db
```

### B-9. 启动后端

```bash
python scripts.py start --reload
```

### B-10. 启动前端

新开一个终端窗口：

```bash
cd frontend
npm run dev
```

### B-11. 打开页面

- 前端：http://localhost:5173
- 后端文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

以后再次进入项目时，先执行：

```bash
conda activate godview
```

</details>

---

## Linux + venv

<details>
<summary><strong>点击展开：Linux + venv 完整步骤</strong></summary>

### C-1. 创建虚拟环境

```bash
python3 -m venv .venv
```

### C-2. 激活虚拟环境

```bash
source .venv/bin/activate
```

### C-3. 安装后端依赖

```bash
pip install -r requirements.txt
```

### C-4. 检查后端依赖

```bash
python3 scripts.py check
```

### C-5. 安装前端依赖

```bash
cd frontend
npm install
cd ..
```

### C-6. 复制环境变量

```bash
cp .env.example .env
```

然后打开 `.env`，至少确认这些值：

```ini
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/godview
QDRANT_URL=http://localhost:6333
EMBEDDING_PROVIDER=sentence_transformers
EMBEDDING_MODEL=all-MiniLM-L6-v2
LLM_PROVIDER=openai
LLM_API_KEY=your-api-key-here
LLM_MODEL=gpt-4o
```

### C-7. 启动 Docker

如果 Docker 服务未启动，可执行：

```bash
sudo systemctl start docker
```

### C-8. 启动数据库

```bash
docker compose up -d postgres qdrant
```

### C-9. 初始化数据库

```bash
python3 scripts.py init-db
```

### C-10. 启动后端

```bash
python3 scripts.py start --reload
```

### C-11. 启动前端

新开一个终端窗口：

```bash
cd frontend
npm run dev
```

### C-12. 打开页面

- 前端：http://localhost:5173
- 后端文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

</details>

---

## Linux + conda

<details>
<summary><strong>点击展开：Linux + conda 完整步骤</strong></summary>

### D-1. 创建 conda 环境

```bash
conda create -n godview python=3.11 -y
```

### D-2. 激活 conda 环境

```bash
conda activate godview
```

### D-3. 安装后端依赖

```bash
pip install -r requirements.txt
```

### D-4. 检查后端依赖

```bash
python scripts.py check
```

### D-5. 安装前端依赖

```bash
cd frontend
npm install
cd ..
```

### D-6. 复制环境变量

```bash
cp .env.example .env
```

然后打开 `.env`，至少确认这些值：

```ini
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/godview
QDRANT_URL=http://localhost:6333
EMBEDDING_PROVIDER=sentence_transformers
EMBEDDING_MODEL=all-MiniLM-L6-v2
LLM_PROVIDER=openai
LLM_API_KEY=your-api-key-here
LLM_MODEL=gpt-4o
```

### D-7. 启动 Docker

如果 Docker 服务未启动，可执行：

```bash
sudo systemctl start docker
```

### D-8. 启动数据库

```bash
docker compose up -d postgres qdrant
```

### D-9. 初始化数据库

```bash
python scripts.py init-db
```

### D-10. 启动后端

```bash
python scripts.py start --reload
```

### D-11. 启动前端

新开一个终端窗口：

```bash
cd frontend
npm run dev
```

### D-12. 打开页面

- 前端：http://localhost:5173
- 后端文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health

以后再次进入项目时，先执行：

```bash
conda activate godview
```

</details>

---

## 4. 页面验证顺序

启动完成后，建议按下面顺序检查。

### 4.1 小说编辑页

重点确认：

- 能看到章节列表
- 能新建章节
- 能修改章节标题和正文
- 能保存章节
- 能导出 TXT / Markdown

### 4.2 章节评估页

重点确认：

- 能读取章节
- 能触发评估
- 页面不会因为章节接口报错而空白

### 4.3 读者模拟页

重点确认：

- 能读取章节列表
- 能执行模拟

### 4.4 Director 页面

重点确认：

- 页面能打开
- 能建立会话
- 工作流日志能显示
- 运行时面板能刷新

如果 `.env` 中的 `LLM_API_KEY` 没填真实值，生成类功能可能无法正常使用。

### 4.5 Diff 工具页

重点确认：

- 页面能打开
- 能选择对比模式
- 快照对比接口能正常返回

### 4.6 可视化工作台

重点确认：

- 页面能打开
- 能选择世界
- 能看到工作流 / 剧情树 / 版本树

### 4.7 干预日志页

重点确认：

- 能加载干预记录
- 能选择快照并创建干预
- 能填写效果评分和备注并保存

---

## 5. 常见问题

### 5.1 `python` 命令不可用

可能是：

- Windows 没把 Python 加入 PATH
- Linux 需要使用 `python3`

### 5.2 `conda activate godview` 失败

可先执行：

```bash
conda init
```

然后关闭终端重新打开，再执行：

```bash
conda activate godview
```

### 5.3 `docker compose` 失败

通常是 Docker 没启动。

Windows：

- 先打开 Docker Desktop

Linux：

```bash
sudo systemctl start docker
```

### 5.4 `python scripts.py init-db` 失败

先执行：

```bash
docker compose ps
```

确认 PostgreSQL 已启动，再检查 `.env` 中的：

```ini
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/godview
```

### 5.5 `npm run dev` 失败

先确认你在 `frontend` 目录下，再执行：

```bash
npm install
npm run dev
```

### 5.6 页面能打开，但生成能力不能用

通常是：

- `LLM_API_KEY` 没填真实值
- 模型服务不可用

请检查：

```ini
LLM_PROVIDER=openai
LLM_API_KEY=你的真实Key
LLM_MODEL=gpt-4o
```

---

## 6. 停止项目

### 6.1 停止前端

在前端终端按：

```bash
Ctrl + C
```

### 6.2 停止后端

在后端终端按：

```bash
Ctrl + C
```

### 6.3 退出 conda 环境（如果你在用 conda）

```bash
conda deactivate
```

### 6.4 停止 Docker 容器

```bash
docker compose down
```

---

## 7. 当前项目目录结构（简化版）

```text
Godview/
├── app/                  # 后端代码
├── frontend/             # 前端代码
├── main.py               # FastAPI 入口
├── scripts.py            # 启动/检查/初始化命令
├── docker-compose.yml    # Docker 数据库服务
├── requirements.txt      # 后端依赖
├── .env.example          # 环境变量模板
└── README.md             # 当前说明文档
```

---

## 8. 许可证

MIT License
