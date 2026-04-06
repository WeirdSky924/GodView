# GodView - 新手可直接照着做的启动说明

这份说明按**从零开始**写。你只要按顺序执行，不需要先理解全部代码。

如果你只是想先把项目跑起来，请直接从下面的 **第 1 步** 开始。

---

## 0. 这个项目现在能做什么

当前项目已经具备这些主要页面和能力：

- 前端管理界面
- Director 导演模式页面
- 小说章节编辑 / 保存
- 章节评估
- 读者模拟
- Diff 对比工具
- 可视化工作台
- 干预日志与效果评估

目前最适合的使用方式是：

1. 先启动后端
2. 再启动前端
3. 通过网页逐页验证功能

---

## 1. 你需要先安装的软件

请先安装下面 4 个软件：

### 1.1 Python 3.11

下载地址：

- https://www.python.org/downloads/

安装时请勾选：

- `Add python.exe to PATH`

安装完成后，在终端执行：

```bash
python --version
```

如果能看到类似下面的输出，就表示成功：

```bash
Python 3.11.x
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

### 1.4 Docker Desktop

下载地址：

- https://www.docker.com/products/docker-desktop/

安装完成后，先启动 Docker Desktop，再执行：

```bash
docker --version
docker compose version
```

---

## 2. 获取项目代码

如果你还没有代码，请执行：

```bash
git clone <你的仓库地址>
cd Godview
```

如果你已经有代码，只要进入项目根目录即可。项目根目录应该能看到这些文件：

- `main.py`
- `scripts.py`
- `requirements.txt`
- `docker-compose.yml`
- `frontend/`

---

## 3. 配置 Python 虚拟环境

下面是 **Windows 最推荐方式**。

### 3.1 创建虚拟环境

```bash
python -m venv .venv
```

### 3.2 激活虚拟环境

Windows PowerShell：

```bash
.venv\Scripts\Activate.ps1
```

Windows CMD：

```bash
.venv\Scripts\activate.bat
```

激活成功后，你的命令行前面通常会出现：

```bash
(.venv)
```

### 3.3 安装后端依赖

```bash
pip install -r requirements.txt
```

### 3.4 检查依赖是否正常

```bash
python scripts.py check
```

看到类似下面内容即可：

```bash
[OK] 核心依赖已安装
```

---

## 4. 配置前端依赖

进入前端目录：

```bash
cd frontend
```

安装依赖：

```bash
npm install
```

安装完成后先不要关闭这个项目目录，后面还要继续使用。

然后回到项目根目录：

```bash
cd ..
```

---

## 5. 配置环境变量

### 5.1 复制模板文件

Windows：

```bash
copy .env.example .env
```

如果 `copy` 不可用，也可以手动复制 `.env.example`，并重命名为 `.env`。

### 5.2 修改 `.env`

用记事本或 VS Code 打开 `.env`。

优先确认下面这些配置：

```ini
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/godview
QDRANT_URL=http://localhost:6333
EMBEDDING_PROVIDER=sentence_transformers
EMBEDDING_MODEL=all-MiniLM-L6-v2
LLM_PROVIDER=openai
LLM_API_KEY=your-api-key-here
LLM_MODEL=gpt-4o
```

### 5.3 新手最简单建议

如果你只是先跑通项目，建议先保持：

```ini
EMBEDDING_PROVIDER=sentence_transformers
EMBEDDING_MODEL=all-MiniLM-L6-v2
```

这样 embedding 不需要额外 API Key。

但是：

- `LLM_API_KEY` 你仍然需要自己填写真实值
- 不填真实大模型 Key 时，涉及生成内容的功能可能不可用

---

## 6. 启动数据库

先确保 Docker Desktop 已经打开。

在项目根目录执行：

### 6.1 推荐最小启动方式

```bash
docker compose up -d postgres qdrant
```

这是当前最推荐的启动方式，因为项目的主要链路主要依赖：

- PostgreSQL
- Qdrant

### 6.2 如果你也想把图数据库一起启动

```bash
docker compose up -d
```

### 6.3 检查容器状态

```bash
docker compose ps
```

你至少应该看到：

- `godview-postgres`
- `godview-qdrant`

状态最好是 `Up`。

---

## 7. 初始化数据库表

第一次运行时执行：

```bash
python scripts.py init-db
```

如果成功，会看到类似：

```bash
[OK] 数据库初始化完成
```

---

## 8. 启动后端

在项目根目录执行：

```bash
python scripts.py start --reload
```

如果成功，你会看到类似输出：

```bash
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
```

**这一窗口不要关掉。**

后端默认地址：

- http://localhost:8000

---

## 9. 启动前端

新开一个终端窗口。

进入项目前端目录：

```bash
cd frontend
```

启动前端开发服务器：

```bash
npm run dev
```

如果成功，通常会看到类似：

```bash
Local:   http://localhost:5173/
```

**这一窗口也不要关掉。**

前端默认地址：

- http://localhost:5173

前端已经配置了代理，请求 `/api` 时会自动转发到后端 `http://localhost:8000`。

---

## 10. 先做最基础的启动验证

请按顺序打开下面这些地址：

### 10.1 后端检查

浏览器打开：

- http://localhost:8000/health
- http://localhost:8000/docs

如果能打开，说明后端基本正常。

### 10.2 前端检查

浏览器打开：

- http://localhost:5173

如果能看到前端界面，说明前端基本正常。

---

## 11. 按页面顺序验证项目

下面是推荐的验证顺序。你不需要一次全测完，但建议按这个顺序看。

### 11.1 小说编辑页

重点确认：

- 能看到章节列表
- 能新建章节
- 能修改章节标题和正文
- 能保存章节

这是最基础的一条链路。

### 11.2 章节评估页

重点确认：

- 能读取章节
- 能触发评估
- 页面不会因为章节接口报错而空白

### 11.3 读者模拟页

重点确认：

- 能读取章节列表
- 能执行模拟

### 11.4 Director 页面

重点确认：

- 页面能打开
- 能建立会话
- 工作流日志能显示
- 运行时面板能刷新

如果你的 `LLM_API_KEY` 没填真实值，这一页的生成类能力可能无法正常使用。

### 11.5 Diff 工具页

重点确认：

- 页面能打开
- 能选择对比模式
- 快照对比接口能正常返回

### 11.6 可视化工作台

重点确认：

- 页面能打开
- 能选择世界
- 能看到工作流 / 剧情树 / 版本树

### 11.7 干预日志页

重点确认：

- 能加载干预记录
- 能选择快照并创建干预
- 能填写效果评分和备注并保存

---

## 12. 你可以直接用的常用命令

### 12.1 后端相关

```bash
python scripts.py check
python scripts.py init-db
python scripts.py start --reload
```

### 12.2 前端相关

```bash
cd frontend
npm install
npm run dev
npm run build
```

### 12.3 Docker 相关

```bash
docker compose up -d postgres qdrant
docker compose up -d
docker compose ps
docker compose down
```

---

## 13. 如果你只是想最快跑起来

你可以只执行下面这组命令：

### 终端 1：项目根目录

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
python scripts.py init-db
docker compose up -d postgres qdrant
python scripts.py start --reload
```

### 终端 2：项目根目录

```bash
cd frontend
npm install
npm run dev
```

然后打开：

- http://localhost:8000/docs
- http://localhost:5173

---

## 14. 常见问题

### 14.1 `python` 命令不可用

说明 Python 没有加入 PATH。

处理方式：

- 重新安装 Python，并勾选 `Add python.exe to PATH`
- 或者重开终端后再试

### 14.2 `docker compose` 失败

通常是 Docker Desktop 没启动。

先打开 Docker Desktop，等它完全启动后再执行：

```bash
docker compose ps
```

### 14.3 `python scripts.py init-db` 失败

先检查：

```bash
docker compose ps
```

确认 PostgreSQL 已启动。

再检查 `.env` 里的：

```ini
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/godview
```

### 14.4 `npm run dev` 失败

先确认你在 `frontend` 目录下。

然后重新执行：

```bash
npm install
npm run dev
```

### 14.5 页面能打开，但生成功能不能用

这通常表示：

- `LLM_API_KEY` 没填真实值
- 或者模型服务不可用

请检查 `.env` 中的：

```ini
LLM_PROVIDER=openai
LLM_API_KEY=你的真实Key
LLM_MODEL=gpt-4o
```

---

## 15. 当前项目目录结构（简化版）

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

## 16. 推荐你每次启动项目的顺序

以后你再次启动项目，建议固定按下面顺序：

### 第一步：打开 Docker

```bash
docker compose up -d postgres qdrant
```

### 第二步：启动后端

```bash
python scripts.py start --reload
```

### 第三步：启动前端

```bash
cd frontend
npm run dev
```

### 第四步：打开页面

- 前端：http://localhost:5173
- 后端文档：http://localhost:8000/docs

---

## 17. 停止项目

### 停止前端

在前端终端按：

```bash
Ctrl + C
```

### 停止后端

在后端终端按：

```bash
Ctrl + C
```

### 停止 Docker 容器

在项目根目录执行：

```bash
docker compose down
```

---

## 18. 许可证

MIT License
