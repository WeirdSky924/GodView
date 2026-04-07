# GodView 项目管理与角色创建增强方案

## Context

用户提出两个核心改进需求：

### 需求 1：Bootstrap 角色提取增强
- 设定结束后自动创建世界和主要角色 Agent
- 随剧情推进动态创建新角色

### 需求 2：项目管理架构改进
- 一本小说作为一级目录（项目）
- 在项目下管理世界、人物、伏笔、剧情等

**当前问题**：
- Character、Chapter、Hook 等模型没有 `project_id` 字段
- Project 仅通过 `world_id` 单向关联 World
- 前端侧边栏没有项目选择功能
- 所有页面无法区分项目上下文

---

## Part 1: 项目管理架构改进

### 1.1 数据模型改进

**文件**: `E:\_Workspace\Godview\app\models\character.py`

为 Character 添加 `project_id` 字段：

```python
class Character(BaseModel):
    id: str = Field(..., description="角色唯一 ID")
    name: str = Field(..., description="角色名称")
    
    # 新增：项目归属
    project_id: Optional[str] = Field(None, description="所属项目ID")
    
    # 原有字段...
    description: Optional[str] = Field(None, description="角色描述")
    role: str = Field(default="supporting", description="角色类型")
    # ...
```

**文件**: `E:\_Workspace\Godview\app\models\world.py`

为 World 添加 `project_id` 字段：

```python
class World(BaseModel):
    id: str = Field(..., description="世界唯一 ID")
    name: str = Field(..., description="世界名称")
    
    # 新增：项目归属
    project_id: Optional[str] = Field(None, description="所属项目ID")
    
    # 原有字段...
```

**文件**: 章节模型（需确认位置）

为 Chapter 添加 `project_id` 字段。

**文件**: `E:\_Workspace\Godview\app\models\hook.py`（需创建或确认位置）

为 Hook 添加 `project_id` 字段。

### 1.2 数据库层改进

**文件**: `E:\_Workspace\Godview\app\database\postgres.py`

修改相关方法支持项目过滤：

```python
async def get_characters(self, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """获取角色列表，支持项目过滤"""
    if project_id:
        query = "SELECT * FROM characters WHERE project_id = $1 ORDER BY created_at DESC"
        results = await self.pool.fetch(query, project_id)
    else:
        query = "SELECT * FROM characters ORDER BY created_at DESC"
        results = await self.pool.fetch(query)
    return [dict(r) for r in results]

async def get_worlds(self, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """获取世界列表，支持项目过滤"""
    # 类似实现

async def get_chapters(self, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """获取章节列表，支持项目过滤"""
    # 类似实现

async def get_hooks(self, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """获取伏笔列表，支持项目过滤"""
    # 类似实现
```

### 1.3 API 层改进

**文件**: `E:\_Workspace\Godview\app\api\routes\characters.py`

```python
@router.get("/", response_model=List[Character])
async def get_characters(project_id: Optional[str] = Query(None)):
    """获取角色列表，支持按项目过滤"""
    return await postgres_db.get_characters(project_id)
```

同样修改：
- `app/api/routes/worlds.py`
- `app/api/routes/chapters.py`（或对应的路由文件）
- 伏笔相关路由

### 1.4 前端架构改进

#### 1.4.1 创建项目上下文

**新文件**: `E:\_Workspace\Godview\frontend\src\contexts\ProjectContext.tsx`

```tsx
import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { getProjects, type Project } from '@/api/projects'

interface ProjectContextType {
  currentProject: Project | null
  projects: Project[]
  setCurrentProject: (project: Project | null) => void
  loading: boolean
  refreshProjects: () => Promise<void>
}

const ProjectContext = createContext<ProjectContextType | null>(null)

export function ProjectProvider({ children }: { children: ReactNode }) {
  const [projects, setProjects] = useState<Project[]>([])
  const [currentProject, setCurrentProject] = useState<Project | null>(null)
  const [loading, setLoading] = useState(true)

  const refreshProjects = async () => {
    try {
      const data = await getProjects()
      setProjects(data)
      // 从 localStorage 恢复上次选择的项目
      const savedProjectId = localStorage.getItem('currentProjectId')
      if (savedProjectId) {
        const saved = data.find(p => p.id === savedProjectId)
        if (saved) setCurrentProject(saved)
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    refreshProjects()
  }, [])

  // 保存项目选择到 localStorage
  const handleSetProject = (project: Project | null) => {
    setCurrentProject(project)
    if (project) {
      localStorage.setItem('currentProjectId', project.id)
    } else {
      localStorage.removeItem('currentProjectId')
    }
  }

  return (
    <ProjectContext.Provider value={{
      currentProject,
      projects,
      setCurrentProject: handleSetProject,
      loading,
      refreshProjects,
    }}>
      {children}
    </ProjectContext.Provider>
  )
}

export function useProject() {
  const context = useContext(ProjectContext)
  if (!context) {
    throw new Error('useProject must be used within ProjectProvider')
  }
  return context
}
```

#### 1.4.2 修改 Layout 添加项目选择器

**文件**: `E:\_Workspace\Godview\frontend\src\components\Layout.tsx`

```tsx
import { useProject } from '@/contexts/ProjectContext'
import { ChevronDown, FolderOpen, Plus } from 'lucide-react'

export default function Layout({ children }: { children: React.ReactNode }) {
  const { currentProject, projects, setCurrentProject, loading } = useProject()
  const [showProjectMenu, setShowProjectMenu] = useState(false)

  return (
    <div className="min-h-screen bg-gray-50 flex">
      <aside className="w-64 bg-white border-r border-gray-200 fixed h-full overflow-y-auto">
        {/* 项目选择器 */}
        <div className="p-4 border-b">
          <div className="relative">
            <button
              onClick={() => setShowProjectMenu(!showProjectMenu)}
              className="w-full flex items-center justify-between p-3 bg-gray-50 rounded-lg hover:bg-gray-100"
            >
              <div className="flex items-center gap-2">
                <FolderOpen size={18} className="text-blue-600" />
                <span className="font-medium text-gray-800 truncate">
                  {currentProject?.name || '选择项目'}
                </span>
              </div>
              <ChevronDown size={16} className="text-gray-400" />
            </button>
            
            {showProjectMenu && (
              <div className="absolute top-full left-0 right-0 mt-1 bg-white border rounded-lg shadow-lg z-50 max-h-64 overflow-auto">
                {projects.map(project => (
                  <button
                    key={project.id}
                    onClick={() => {
                      setCurrentProject(project)
                      setShowProjectMenu(false)
                    }}
                    className={`w-full text-left px-4 py-2 hover:bg-gray-50 flex items-center gap-2 ${
                      currentProject?.id === project.id ? 'bg-blue-50 text-blue-600' : ''
                    }`}
                  >
                    <FolderOpen size={16} />
                    <span>{project.name}</span>
                  </button>
                ))}
                <div className="border-t">
                  <button
                    onClick={() => {
                      window.location.href = '/project-setup'
                    }}
                    className="w-full text-left px-4 py-2 hover:bg-gray-50 flex items-center gap-2 text-blue-600"
                  >
                    <Plus size={16} />
                    <span>新建项目</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* 原有导航 */}
        <div className="p-4">
          <h1 className="text-xl font-bold text-gray-800">🎬 GodView</h1>
          <p className="text-xs text-gray-500 mt-1">AI 小说生成系统</p>
        </div>

        <nav className="mt-4">
          {/* 原有导航项 */}
        </nav>
      </aside>

      <main className="ml-64 flex-1 p-8">
        {children}
      </main>
    </div>
  )
}
```

#### 1.4.3 修改各页面支持项目过滤

**文件**: `E:\_Workspace\Godview\frontend\src\pages\Characters.tsx`

```tsx
import { useProject } from '@/contexts/ProjectContext'

export default function Characters() {
  const { currentProject } = useProject()
  const [characters, setCharacters] = useState<Character[]>([])

  const loadCharacters = useCallback(async () => {
    try {
      // 传递 project_id 进行过滤
      const data = await getCharacters(currentProject?.id)
      setCharacters(data)
    } catch (error) {
      console.error('Failed to load characters:', error)
    }
  }, [currentProject?.id])

  useEffect(() => {
    loadCharacters()
  }, [loadCharacters])

  // 如果没有选择项目，显示提示
  if (!currentProject) {
    return (
      <div className="text-center py-20 text-gray-500">
        <FolderOpen size={48} className="mx-auto mb-4 opacity-50" />
        <p>请先选择一个项目</p>
      </div>
    )
  }

  // 原有渲染逻辑...
}
```

同样修改：
- `Worlds.tsx`
- `Plots.tsx`
- `Hooks.tsx`
- `Interventions.tsx`
- `NovelView.tsx`
- `Director.tsx`

#### 1.4.4 修改 API 接口支持项目参数

**文件**: `E:\_Workspace\Godview\frontend\src\api\characters.ts`

```ts
export async function getCharacters(projectId?: string): Promise<Character[]> {
  const params = projectId ? { project_id: projectId } : {}
  const response = await api.get('/characters', { params })
  return response.data
}
```

同样修改其他 API 文件。

---

## Part 2: Bootstrap 角色提取与动态创建增强

### 2.1 后端 API - 新增"设定结束"端点

**文件**: `E:\_Workspace\Godview\app\api\routes\bootstrap.py`

```python
@router.post("/{session_id}/finalize-setting", response_model=Dict[str, Any])
async def finalize_setting(session_id: str):
    """
    设定结束，自动创建世界和角色
    
    流程:
    1. 最终提取 seed
    2. 创建世界（关联到项目）
    3. 创建角色（关联到项目）
    4. 创建初始快照
    """
    orchestrator = get_bootstrap_orchestrator()
    setting_agent = get_setting_agent()
    
    session = await orchestrator.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    # 1. 最终提取 seed
    seed_data = await setting_agent.finalize_and_extract_seed(session_id)
    if not seed_data:
        raise HTTPException(status_code=400, detail="无法提取种子数据")
    
    # 2. 确认 seed
    session = await orchestrator.confirm_seed(session_id, seed_data)
    
    # 3. 执行 bootstrap（传入 project_id）
    result = await orchestrator.run_bootstrap(session_id)
    
    return {
        "success": True,
        "message": "设定已完成，世界和角色已创建",
        "result": result,
    }
```

### 2.2 Setting Agent - 新增强制提取方法

**文件**: `E:\_Workspace\Godview\app\services\setting_agent.py`

```python
async def finalize_and_extract_seed(self, session_id: str) -> Optional[Dict[str, Any]]:
    """
    强制从当前对话历史提取 seed（设定结束时调用）
    不依赖对话轮数阈值
    """
    session = self._sessions.get(session_id)
    if not session:
        return None
    
    # 强制提取
    extracted = await self._extract_seed_from_history(session)
    if extracted:
        session.extracted_seed = extracted
        session.current_stage = BootstrapStage.SEED_EXTRACTED
        session.progress = 0.4
    
    return extracted
```

### 2.3 Bootstrap Orchestrator - 增强角色创建

**文件**: `E:\_Workspace\Godview\app\services\bootstrap_orchestrator.py`

```python
async def _bootstrap_world(self, session: BootstrapSession):
    """创建世界 - 关联到项目"""
    seed = session.confirmed_seed
    project_id = session.project_id
    
    world = World(
        id=f"world_{uuid.uuid4().hex[:12]}",
        name=seed.get("world_setting", {}).get("name", "新世界"),
        description=seed.get("world_setting", {}).get("description"),
        project_id=project_id,  # 关联项目
        # ...
    )
    
    await postgres_db.save_world(world.model_dump())
    
    # 更新项目的 world_id
    await postgres_db.update_project(project_id, {"world_id": world.id})
    
    seed["world_id"] = world.id

async def _bootstrap_characters(self, session: BootstrapSession):
    """创建角色 - 关联到项目"""
    seed = session.confirmed_seed
    world_id = seed.get("world_id")
    project_id = session.project_id  # 获取项目 ID
    
    for char_data in all_characters:
        character = Character(
            id=f"char_{uuid.uuid4().hex[:12]}",
            name=char_data.get("name", ""),
            project_id=project_id,  # 关联项目
            world_id=world_id,  # 可选：同时关联世界
            # ...
        )
        await postgres_db.save_character(character.model_dump())
```

### 2.4 WebSocket - 动态角色创建

**文件**: `E:\_Workspace\Godview\app\api\routes\websocket.py`

```python
# 在消息处理字典中注册
MESSAGE_HANDLERS = {
    # 原有处理函数...
    "add_character": handle_add_character,
}

async def handle_add_character(websocket: WebSocket, message: dict, client_id: str):
    """动态添加角色"""
    director = get_or_create_director(client_id)
    char_data = message.get("character_data", {})
    project_id = message.get("project_id")  # 从消息获取项目 ID
    
    # 创建角色模型
    character = Character(
        id=f"char_{uuid.uuid4().hex[:12]}",
        name=char_data.get("name"),
        project_id=project_id,
        description=char_data.get("description", ""),
        role=char_data.get("role", "supporting"),
        # ...
    )
    
    # 保存到数据库
    await postgres_db.save_character(character.model_dump())
    
    # 添加到 Director 运行时
    agent = director._create_character_agent(character.model_dump())
    director.character_agents[agent.character.id] = agent
    
    await websocket.send_json({
        "type": "character_added",
        "status": "success",
        "data": {
            "character_id": agent.character.id,
            "character_name": agent.character.name,
        }
    })
```

### 2.5 Director 服务 - 新增方法

**文件**: `E:\_Workspace\Godview\app\services\director.py`

```python
def add_character(self, char_data: Dict[str, Any]) -> str:
    """动态添加角色到运行时"""
    agent = self._create_character_agent(char_data)
    self.character_agents[agent.character.id] = agent
    logger.info(f"动态添加角色: {agent.character.name}")
    return agent.character.id

def remove_character(self, character_id: str) -> bool:
    """从运行时移除角色"""
    if character_id in self.character_agents:
        del self.character_agents[character_id]
        return True
    return False

def get_all_characters(self) -> List[Dict[str, Any]]:
    """获取所有角色信息"""
    return [
        {"id": a.character.id, "name": a.character.name, "role": a.character.role}
        for a in self.character_agents.values()
    ]
```

### 2.6 前端 Bootstrap 页面 - 添加设定结束按钮

**文件**: `E:\_Workspace\Godview\frontend\src\pages\Bootstrap.tsx`

在 `renderSettingAgent` 函数中添加：

```tsx
const handleFinalizeSetting = async () => {
  if (!session) return
  setLoading(true)
  try {
    const result = await finalizeSetting(session.id)
    if (result.success) {
      setStage('completed')
    }
  } catch (error) {
    setError('设定结束失败')
  } finally {
    setLoading(false)
  }
}

// 在 JSX 中添加按钮
<button
  onClick={handleFinalizeSetting}
  disabled={loading || !session?.setting_agent_history?.length}
  className="px-6 py-3 bg-green-600 text-white font-medium rounded-lg hover:bg-green-700 disabled:opacity-50"
>
  <CheckCircle className="w-5 h-5 inline mr-2" />
  设定结束，创建世界和角色
</button>
```

### 2.7 前端 Director 页面 - 动态添加角色

**文件**: `E:\_Workspace\Godview\frontend\src\pages\Director.tsx`

```tsx
const [showAddCharacterModal, setShowAddCharacterModal] = useState(false)
const [newCharacter, setNewCharacter] = useState({
  name: '',
  description: '',
  role: 'supporting',
  background_story: '',
  speech_pattern: '',
})

const handleAddCharacter = () => {
  if (!newCharacter.name.trim() || !currentProject) return
  
  send({
    type: 'add_character',
    project_id: currentProject.id,
    character_data: newCharacter,
  })
  
  setShowAddCharacterModal(false)
  setNewCharacter({ name: '', description: '', role: 'supporting', background_story: '', speech_pattern: '' })
}

// 在快速操作区添加按钮
<Button onClick={() => setShowAddCharacterModal(true)}>
  <UserPlus size={18} className="mr-2" />
  动态添加角色
</Button>

// Modal 组件
<Modal isOpen={showAddCharacterModal} onClose={() => setShowAddCharacterModal(false)} title="添加新角色">
  {/* 表单内容 */}
</Modal>
```

---

## Files to Modify Summary

### 后端

| 文件 | 修改内容 |
|------|----------|
| `app/models/character.py` | 添加 `project_id` 字段 |
| `app/models/world.py` | 添加 `project_id` 字段 |
| `app/models/chapter.py` | 添加 `project_id` 字段 |
| `app/models/hook.py` | 添加 `project_id` 字段（如不存在则创建） |
| `app/database/postgres.py` | 所有列表方法支持 `project_id` 过滤 |
| `app/api/routes/characters.py` | GET 接口支持 `project_id` 参数 |
| `app/api/routes/worlds.py` | GET 接口支持 `project_id` 参数 |
| `app/api/routes/chapters.py` | GET 接口支持 `project_id` 参数 |
| `app/api/routes/bootstrap.py` | 新增 `finalize-setting` 端点 |
| `app/api/routes/websocket.py` | 新增 `add_character` 消息处理 |
| `app/services/setting_agent.py` | 新增 `finalize_and_extract_seed` 方法 |
| `app/services/bootstrap_orchestrator.py` | 增强 `_bootstrap_characters`，角色关联项目 |
| `app/services/director.py` | 新增 `add_character` 等方法 |

### 前端

| 文件 | 修改内容 |
|------|----------|
| `frontend/src/contexts/ProjectContext.tsx` | **新建** - 项目上下文 |
| `frontend/src/components/Layout.tsx` | 添加项目选择器 |
| `frontend/src/main.tsx` | 包裹 ProjectProvider |
| `frontend/src/api/characters.ts` | 支持 `projectId` 参数 |
| `frontend/src/api/worlds.ts` | 支持 `projectId` 参数 |
| `frontend/src/api/chapters.ts` | 支持 `projectId` 参数 |
| `frontend/src/api/bootstrap.ts` | 新增 `finalizeSetting` 函数 |
| `frontend/src/pages/Characters.tsx` | 使用项目过滤 |
| `frontend/src/pages/Worlds.tsx` | 使用项目过滤 |
| `frontend/src/pages/Plots.tsx` | 使用项目过滤 |
| `frontend/src/pages/Hooks.tsx` | 使用项目过滤 |
| `frontend/src/pages/Director.tsx` | 使用项目过滤 + 动态添加角色 |
| `frontend/src/pages/Bootstrap.tsx` | 添加设定结束按钮 |

---

## Verification

### 测试步骤

1. **项目管理测试**
   - 创建多个项目
   - 在侧边栏切换项目
   - 验证角色、世界、章节等按项目过滤

2. **Bootstrap 设定结束测试**
   - 进入 Bootstrap 页面
   - 选择项目并与设定 Agent 对话
   - 点击「设定结束」按钮
   - 验证世界和角色已创建并关联到项目

3. **动态添加角色测试**
   - 进入 Director 模式
   - 点击「动态添加角色」
   - 填写信息并创建
   - 验证角色已添加到运行时和数据库

---

## Part 3: LLM 模型配置增强

### 3.1 后端 - 扩展 LLM Provider 列表

**文件**: `E:\_Workspace\Godview\app\api\routes\config.py`

扩展 `LLM_PROVIDERS` 列表，添加国内主流模型提供商：

```python
LLM_PROVIDERS = [
    # ========== 国际模型 ==========
    {
        "id": "openai",
        "name": "OpenAI API",
        "description": "OpenAI 官方 API，支持 GPT-4o、GPT-4-turbo 等模型",
        "default_model": "gpt-4o",
        "default_url": "https://api.openai.com/v1",
        "requires_api_key": True,
        "api_key_hint": "在 platform.openai.com 获取 API Key",
        "models": [
            {"id": "gpt-4o", "name": "GPT-4o (推荐)", "context": "128K"},
            {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "context": "128K"},
            {"id": "gpt-4-turbo", "name": "GPT-4 Turbo", "context": "128K"},
            {"id": "gpt-3.5-turbo", "name": "GPT-3.5 Turbo", "context": "16K"},
        ],
    },
    {
        "id": "anthropic",
        "name": "Anthropic Claude",
        "description": "Claude 系列模型，擅长长文本和复杂推理",
        "default_model": "claude-3-5-sonnet-latest",
        "default_url": "https://api.anthropic.com",
        "requires_api_key": True,
        "api_key_hint": "在 console.anthropic.com 获取 API Key",
        "models": [
            {"id": "claude-3-5-sonnet-latest", "name": "Claude 3.5 Sonnet (推荐)", "context": "200K"},
            {"id": "claude-3-opus-latest", "name": "Claude 3 Opus", "context": "200K"},
            {"id": "claude-3-haiku-latest", "name": "Claude 3 Haiku", "context": "200K"},
        ],
    },
    
    # ========== 国内模型 ==========
    {
        "id": "zhipu",
        "name": "智谱AI (GLM)",
        "description": "智谱清言系列，支持长上下文，中文能力强",
        "default_model": "glm-4-flash",
        "default_url": "https://open.bigmodel.cn/api/paas/v4",
        "requires_api_key": True,
        "api_key_hint": "在 open.bigmodel.cn 注册后获取 API Key",
        "doc_url": "https://open.bigmodel.cn/dev/api",
        "models": [
            {"id": "glm-4-plus", "name": "GLM-4-Plus (最强)", "context": "128K"},
            {"id": "glm-4-0520", "name": "GLM-4-0520", "context": "128K"},
            {"id": "glm-4-flash", "name": "GLM-4-Flash (推荐，免费额度)", "context": "128K"},
            {"id": "glm-4-long", "name": "GLM-4-Long", "context": "1M"},
            {"id": "glm-4-air", "name": "GLM-4-Air", "context": "128K"},
        ],
    },
    {
        "id": "qwen",
        "name": "通义千问 (阿里云)",
        "description": "阿里云通义千问，兼容 OpenAI API 格式",
        "default_model": "qwen-plus",
        "default_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "requires_api_key": True,
        "api_key_hint": "在 dashscope.console.aliyun.com 获取 API Key",
        "doc_url": "https://help.aliyun.com/zh/dashscope/",
        "models": [
            {"id": "qwen-max", "name": "Qwen-Max (最强)", "context": "32K"},
            {"id": "qwen-plus", "name": "Qwen-Plus (推荐)", "context": "128K"},
            {"id": "qwen-turbo", "name": "Qwen-Turbo (快速)", "context": "128K"},
            {"id": "qwen-long", "name": "Qwen-Long", "context": "1M"},
        ],
    },
    {
        "id": "deepseek",
        "name": "DeepSeek (深度求索)",
        "description": "DeepSeek 系列，代码能力强，价格实惠",
        "default_model": "deepseek-chat",
        "default_url": "https://api.deepseek.com",
        "requires_api_key": True,
        "api_key_hint": "在 platform.deepseek.com 获取 API Key",
        "doc_url": "https://platform.deepseek.com/api-docs/",
        "models": [
            {"id": "deepseek-chat", "name": "DeepSeek Chat (推荐)", "context": "64K"},
            {"id": "deepseek-coder", "name": "DeepSeek Coder (代码专用)", "context": "64K"},
            {"id": "deepseek-reasoner", "name": "DeepSeek Reasoner (推理)", "context": "64K"},
        ],
    },
    {
        "id": "moonshot",
        "name": "月之暗面 (Kimi)",
        "description": "Moonshot 系列，擅长长文本处理",
        "default_model": "moonshot-v1-8k",
        "default_url": "https://api.moonshot.cn/v1",
        "requires_api_key": True,
        "api_key_hint": "在 platform.moonshot.cn 获取 API Key",
        "doc_url": "https://platform.moonshot.cn/docs/api",
        "models": [
            {"id": "moonshot-v1-8k", "name": "Moonshot V1 8K", "context": "8K"},
            {"id": "moonshot-v1-32k", "name": "Moonshot V1 32K", "context": "32K"},
            {"id": "moonshot-v1-128k", "name": "Moonshot V1 128K (长文本)", "context": "128K"},
        ],
    },
    {
        "id": "baichuan",
        "name": "百川智能",
        "description": "百川大模型，中文理解能力强",
        "default_model": "Baichuan4",
        "default_url": "https://api.baichuan-ai.com/v1",
        "requires_api_key": True,
        "api_key_hint": "在 platform.baichuan-ai.com 获取 API Key",
        "doc_url": "https://platform.baichuan-ai.com/docs/api",
        "models": [
            {"id": "Baichuan4", "name": "Baichuan4 (最新)", "context": "128K"},
            {"id": "Baichuan3-Turbo", "name": "Baichuan3 Turbo", "context": "32K"},
            {"id": "Baichuan2-Turbo", "name": "Baichuan2 Turbo", "context": "32K"},
        ],
    },
    {
        "id": "baidu",
        "name": "百度文心一言",
        "description": "文心大模型系列，企业级稳定性",
        "default_model": "ernie-4.0-8k",
        "default_url": "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat",
        "requires_api_key": True,
        "api_key_hint": "在 console.bce.baidu.com/qianfan 获取 API Key 和 Secret Key",
        "doc_url": "https://cloud.baidu.com/doc/WENXINWORKSHOP/index.html",
        "models": [
            {"id": "ernie-4.0-8k", "name": "ERNIE 4.0 (最强)", "context": "8K"},
            {"id": "ernie-3.5-8k", "name": "ERNIE 3.5", "context": "8K"},
            {"id": "ernie-speed-8k", "name": "ERNIE Speed (快速)", "context": "8K"},
        ],
    },
    {
        "id": "yi",
        "name": "零一万物 (Yi)",
        "description": "Yi 系列模型，双语能力强",
        "default_model": "yi-large",
        "default_url": "https://api.lingyiwanwu.com/v1",
        "requires_api_key": True,
        "api_key_hint": "在 platform.lingyiwanwu.com 获取 API Key",
        "doc_url": "https://platform.lingyiwanwu.com/docs",
        "models": [
            {"id": "yi-large", "name": "Yi Large (推荐)", "context": "32K"},
            {"id": "yi-medium", "name": "Yi Medium", "context": "16K"},
            {"id": "yi-spark", "name": "Yi Spark (快速)", "context": "16K"},
        ],
    },
    {
        "id": "minimax",
        "name": "MiniMax",
        "description": "MiniMax 大模型，支持长上下文",
        "default_model": "abab6.5-chat",
        "default_url": "https://api.minimax.chat/v1",
        "requires_api_key": True,
        "api_key_hint": "在 api.minimax.chat 获取 API Key",
        "doc_url": "https://www.minimaxi.com/document/",
        "models": [
            {"id": "abab6.5-chat", "name": "ABAB 6.5 (推荐)", "context": "245K"},
            {"id": "abab5.5-chat", "name": "ABAB 5.5", "context": "16K"},
        ],
    },
    {
        "id": "openrouter",
        "name": "OpenRouter (聚合网关)",
        "description": "聚合多个模型提供商，一次 API Key 访问多种模型",
        "default_model": "openai/gpt-4o",
        "default_url": "https://openrouter.ai/api/v1",
        "requires_api_key": True,
        "api_key_hint": "在 openrouter.ai 获取 API Key",
        "doc_url": "https://openrouter.ai/docs",
        "models": [
            {"id": "openai/gpt-4o", "name": "GPT-4o (via OpenRouter)", "context": "128K"},
            {"id": "anthropic/claude-3.5-sonnet", "name": "Claude 3.5 Sonnet", "context": "200K"},
            {"id": "google/gemini-pro", "name": "Gemini Pro", "context": "32K"},
            {"id": "meta-llama/llama-3-70b-instruct", "name": "Llama 3 70B", "context": "8K"},
        ],
    },
    {
        "id": "custom",
        "name": "自定义 (OpenAI 兼容)",
        "description": "任何兼容 OpenAI API 格式的服务，如本地部署的 Ollama、vLLM 等",
        "default_model": "",
        "default_url": "http://localhost:11434/v1",
        "requires_api_key": False,
        "api_key_hint": "本地部署通常不需要 API Key，留空即可",
        "doc_url": "",
        "models": [],
    },
]
```

### 3.2 后端 - 新增模型列表 API

**文件**: `E:\_Workspace\Godview\app\api\routes\config.py`

新增端点获取指定 Provider 的模型列表：

```python
@router.get("/llm/providers/{provider_id}/models")
async def get_provider_models(provider_id: str) -> List[Dict[str, Any]]:
    """获取指定 Provider 的模型列表"""
    provider = next((p for p in LLM_PROVIDERS if p["id"] == provider_id), None)
    if not provider:
        raise HTTPException(status_code=404, detail=f"Provider {provider_id} 不存在")
    return provider.get("models", [])
```

### 3.3 前端 - 增强设置页面

**文件**: `E:\_Workspace\Godview\frontend\src\pages\Settings.tsx`

重构 LLM 配置区域，支持：
- Provider 选择卡片
- 模型下拉选择
- 配置提示信息
- API Key 获取链接

```tsx
import { useState, useEffect } from 'react'
import { Card, Button, Input } from '@/components/ui'
import {
  getLLMProviders, getLLMConfig, updateLLMConfig, testLLMConfig,
  getProviderModels
} from '@/api/config'
import { Check, RefreshCw, ExternalLink, ChevronDown, Info } from 'lucide-react'

interface LLMProvider {
  id: string
  name: string
  description: string
  default_model: string
  default_url: string
  requires_api_key: boolean
  api_key_hint?: string
  doc_url?: string
  models: Array<{ id: string; name: string; context: string }>
}

export default function Settings() {
  const [providers, setProviders] = useState<LLMProvider[]>([])
  const [selectedProvider, setSelectedProvider] = useState<LLMProvider | null>(null)
  const [config, setConfig] = useState({
    provider: 'openai',
    model: '',
    api_key: '',
    base_url: '',
    temperature: 0.7,
    max_tokens: 4096,
  })
  const [loading, setLoading] = useState(true)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<{ success?: boolean; message?: string } | null>(null)

  useEffect(() => {
    loadSettings()
  }, [])

  const loadSettings = async () => {
    try {
      const [providersData, configData] = await Promise.all([
        getLLMProviders(),
        getLLMConfig(),
      ])
      setProviders(providersData)
      setConfig({
        provider: configData.provider,
        model: configData.model,
        api_key: configData.api_key,
        base_url: configData.base_url,
        temperature: configData.temperature,
        max_tokens: configData.max_tokens,
      })
      // 设置当前选中的 provider
      const current = providersData.find((p: LLMProvider) => p.id === configData.provider)
      setSelectedProvider(current || providersData[0])
    } catch (error) {
      console.error('Failed to load settings:', error)
    } finally {
      setLoading(false)
    }
  }

  const selectProvider = (provider: LLMProvider) => {
    setSelectedProvider(provider)
    setConfig(prev => ({
      ...prev,
      provider: provider.id,
      model: prev.model || provider.default_model,
      base_url: prev.base_url || provider.default_url,
    }))
  }

  const handleTest = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const result = await testLLMConfig(config)
      setTestResult(result)
    } catch (error) {
      setTestResult({ success: false, message: String(error) })
    } finally {
      setTesting(false)
    }
  }

  const handleSave = async () => {
    await updateLLMConfig(config)
    await handleTest()
  }

  return (
    <div>
      <h1 className="text-3xl font-bold text-gray-800 mb-8">⚙️ 系统设置</h1>

      {loading ? (
        <p className="text-center text-gray-500 py-12">加载中...</p>
      ) : (
        <div className="space-y-6">
          {/* LLM 配置 */}
          <Card title="LLM 模型配置" description="选择 AI 模型服务提供商">
            <div className="space-y-6">
              {/* Provider 选择网格 */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-3">
                  选择模型服务商
                </label>
                <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                  {providers.map(provider => (
                    <button
                      key={provider.id}
                      onClick={() => selectProvider(provider)}
                      className={`p-4 border-2 rounded-lg text-left transition-all ${
                        config.provider === provider.id
                          ? 'border-blue-500 bg-blue-50'
                          : 'border-gray-200 hover:border-gray-300'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-sm">{provider.name}</span>
                        {config.provider === provider.id && (
                          <Check size={16} className="text-blue-500" />
                        )}
                      </div>
                      <p className="text-xs text-gray-500 mt-1 line-clamp-2">
                        {provider.description}
                      </p>
                    </button>
                  ))}
                </div>
              </div>

              {/* 当前 Provider 详情 */}
              {selectedProvider && (
                <div className="p-4 bg-gray-50 rounded-lg border">
                  <div className="flex items-start gap-3">
                    <Info size={18} className="text-blue-500 mt-0.5" />
                    <div className="flex-1">
                      <p className="text-sm text-gray-700">{selectedProvider.description}</p>
                      {selectedProvider.api_key_hint && (
                        <p className="text-sm text-gray-600 mt-2">
                          <span className="font-medium">API Key 获取：</span>
                          {selectedProvider.api_key_hint}
                        </p>
                      )}
                      {selectedProvider.doc_url && (
                        <a
                          href={selectedProvider.doc_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1 text-sm text-blue-600 hover:text-blue-700 mt-2"
                        >
                          查看官方文档 <ExternalLink size={14} />
                        </a>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* 模型选择 */}
              {selectedProvider?.models && selectedProvider.models.length > 0 && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    选择模型
                  </label>
                  <select
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                    value={config.model}
                    onChange={e => setConfig(prev => ({ ...prev, model: e.target.value }))}
                  >
                    <option value="">选择模型...</option>
                    {selectedProvider.models.map(model => (
                      <option key={model.id} value={model.id}>
                        {model.name} ({model.context} 上下文)
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {/* API Key */}
              {selectedProvider?.requires_api_key && (
                <Input
                  label="API Key"
                  type="password"
                  value={config.api_key}
                  onChange={e => setConfig(prev => ({ ...prev, api_key: e.target.value }))}
                  placeholder={selectedProvider.api_key_hint || '输入 API Key'}
                />
              )}

              {/* Base URL */}
              <Input
                label="API 地址 (Base URL)"
                value={config.base_url}
                onChange={e => setConfig(prev => ({ ...prev, base_url: e.target.value }))}
                placeholder="通常无需修改"
              />

              {/* 高级参数 */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Temperature (创造性)
                  </label>
                  <input
                    type="range"
                    min="0"
                    max="2"
                    step="0.1"
                    value={config.temperature}
                    onChange={e => setConfig(prev => ({ ...prev, temperature: parseFloat(e.target.value) }))}
                    className="w-full"
                  />
                  <div className="flex justify-between text-xs text-gray-500">
                    <span>精确 (0)</span>
                    <span>{config.temperature}</span>
                    <span>创意 (2)</span>
                  </div>
                </div>
                <Input
                  label="Max Tokens (最大输出长度)"
                  type="number"
                  value={String(config.max_tokens)}
                  onChange={e => setConfig(prev => ({ ...prev, max_tokens: parseInt(e.target.value) || 4096 }))}
                />
              </div>

              {/* 测试结果 */}
              {testResult && (
                <div className={`p-4 rounded-lg ${
                  testResult.success ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'
                }`}>
                  {testResult.message}
                </div>
              )}

              {/* 操作按钮 */}
              <div className="flex gap-3 pt-4">
                <Button onClick={handleTest} loading={testing}>
                  <RefreshCw size={18} className={`mr-2 ${testing ? 'animate-spin' : ''}`} />
                  测试连接
                </Button>
                <Button onClick={handleSave}>保存配置</Button>
              </div>
            </div>
          </Card>

          {/* Embedding 配置 - 保持原有结构 */}
          {/* ... */}
        </div>
      )}
    </div>
  )
}
```

### 3.4 前端 API 更新

**文件**: `E:\_Workspace\Godview\frontend\src\api\config.ts`

新增获取 Provider 模型列表的函数：

```ts
export async function getProviderModels(providerId: string): Promise<Array<{id: string; name: string; context: string}>> {
  const response = await api.get(`/config/llm/providers/${providerId}/models`)
  return response.data
}
```

---

## Files to Modify (Part 3)

| 文件 | 修改内容 |
|------|----------|
| `app/api/routes/config.py` | 扩展 `LLM_PROVIDERS` 列表，新增模型列表 API |
| `frontend/src/pages/Settings.tsx` | 重构 LLM 配置 UI，支持模型选择和配置提示 |
| `frontend/src/api/config.ts` | 新增 `getProviderModels` 函数 |

---

## Provider 配置速查表

| Provider | 默认模型 | API 地址 | 特点 |
|----------|----------|----------|------|
| **OpenAI** | gpt-4o | https://api.openai.com/v1 | 最强综合能力 |
| **Anthropic** | claude-3-5-sonnet | https://api.anthropic.com | 长文本、推理能力强 |
| **智谱GLM** | glm-4-flash | https://open.bigmodel.cn/api/paas/v4 | 中文强，有免费额度 |
| **通义千问** | qwen-plus | https://dashscope.aliyuncs.com/compatible-mode/v1 | 阿里云，稳定性高 |
| **DeepSeek** | deepseek-chat | https://api.deepseek.com | 价格低，代码能力强 |
| **月之暗面** | moonshot-v1-8k | https://api.moonshot.cn/v1 | 长文本处理 |
| **百川** | Baichuan4 | https://api.baichuan-ai.com/v1 | 中文理解 |
| **百度文心** | ernie-4.0-8k | https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat | 企业级稳定 |
| **零一万物** | yi-large | https://api.lingyiwanwu.com/v1 | 双语能力强 |
| **MiniMax** | abab6.5-chat | https://api.minimax.chat/v1 | 超长上下文 |
| **OpenRouter** | openai/gpt-4o | https://openrouter.ai/api/v1 | 聚合网关，多模型 |
| **自定义** | - | 用户填写 | 本地部署、私有服务 |

---

## Part 4: 项目 Token 消耗统计

### 4.1 数据模型 - Token 使用记录

**新文件**: `E:\_Workspace\Godview\app\models\token_usage.py`

```python
"""
Token 使用记录模型
用于追踪每个项目的 LLM 调用消耗
"""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class TokenType(str, Enum):
    """Token 类型"""
    INPUT = "input"      # 输入 token
    OUTPUT = "output"    # 输出 token


class UsageCategory(str, Enum):
    """使用场景分类"""
    BOOTSTRAP = "bootstrap"           # 项目初始化
    DIALOGUE = "dialogue"             # 对话生成
    NARRATIVE = "narrative"           # 叙事生成
    EVALUATION = "evaluation"         # 内容评估
    SUMMARY = "summary"               # 剧情总结
    HOOK_MANAGEMENT = "hook"          # 伏笔管理
    CHARACTER_VOICE = "character"     # 角色声音
    SETTING_AGENT = "setting"         # 设定对话
    OTHER = "other"                   # 其他


class TokenUsageRecord(BaseModel):
    """Token 使用记录"""
    
    id: str = Field(..., description="记录 ID")
    project_id: str = Field(..., description="所属项目 ID")
    
    # Token 数量
    input_tokens: int = Field(default=0, description="输入 token 数")
    output_tokens: int = Field(default=0, description="输出 token 数")
    total_tokens: int = Field(default=0, description="总 token 数")
    
    # 模型信息
    provider: str = Field(..., description="模型提供商")
    model: str = Field(..., description="使用的模型")
    
    # 使用场景
    category: UsageCategory = Field(..., description="使用场景")
    agent_name: Optional[str] = Field(None, description="调用的 Agent 名称")
    
    # 详细信息
    request_id: Optional[str] = Field(None, description="请求 ID")
    session_id: Optional[str] = Field(None, description="会话 ID")
    chapter_id: Optional[str] = Field(None, description="关联章节 ID")
    character_id: Optional[str] = Field(None, description="关联角色 ID")
    
    # 费用估算（美元）
    estimated_cost: Optional[float] = Field(None, description="估算费用")
    
    # 时间戳
    created_at: datetime = Field(default_factory=datetime.utcnow, description="创建时间")
    
    # 元数据
    metadata: Dict[str, Any] = Field(default_factory=dict, description="额外元数据")


class TokenUsageSummary(BaseModel):
    """Token 使用统计摘要"""
    
    project_id: str = Field(..., description="项目 ID")
    
    # 总量统计
    total_input_tokens: int = Field(default=0, description="总输入 token")
    total_output_tokens: int = Field(default=0, description="总输出 token")
    total_tokens: int = Field(default=0, description="总 token")
    
    # 费用统计
    total_estimated_cost: float = Field(default=0.0, description="总估算费用")
    
    # 分类统计
    by_category: Dict[str, int] = Field(default_factory=dict, description="按场景分类统计")
    by_model: Dict[str, int] = Field(default_factory=dict, description="按模型分类统计")
    by_agent: Dict[str, int] = Field(default_factory=dict, description="按 Agent 分类统计")
    
    # 时间范围
    first_usage: Optional[datetime] = Field(None, description="首次使用时间")
    last_usage: Optional[datetime] = Field(None, description="最近使用时间")
    
    # 记录数
    record_count: int = Field(default=0, description="记录总数")


class ProjectTokenStats(BaseModel):
    """项目 Token 统计（用于前端展示）"""
    
    project_id: str
    project_name: str
    
    # 核心指标
    total_tokens: int
    total_cost: float
    
    # 今日统计
    today_tokens: int
    today_cost: float
    
    # 本周统计
    week_tokens: int
    week_cost: float
    
    # 本月统计
    month_tokens: int
    month_cost: float
    
    # 趋势数据（最近 7 天）
    daily_tokens: list  # [{date: str, tokens: int, cost: float}]
    
    # 分类占比
    category_breakdown: list  # [{category: str, tokens: int, percent: float}]


# 各模型的价格参考（美元/1K tokens）
MODEL_PRICING = {
    # OpenAI
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    
    # Anthropic
    "claude-3-5-sonnet-latest": {"input": 0.003, "output": 0.015},
    "claude-3-opus-latest": {"input": 0.015, "output": 0.075},
    "claude-3-haiku-latest": {"input": 0.00025, "output": 0.00125},
    
    # 智谱
    "glm-4-plus": {"input": 0.0007, "output": 0.0007},
    "glm-4-flash": {"input": 0.0001, "output": 0.0001},
    "glm-4-long": {"input": 0.001, "output": 0.001},
    
    # 通义千问
    "qwen-max": {"input": 0.0024, "output": 0.0096},
    "qwen-plus": {"input": 0.0004, "output": 0.0012},
    "qwen-turbo": {"input": 0.0002, "output": 0.0006},
    
    # DeepSeek
    "deepseek-chat": {"input": 0.00014, "output": 0.00028},
    "deepseek-coder": {"input": 0.00014, "output": 0.00028},
    
    # 月之暗面
    "moonshot-v1-8k": {"input": 0.012, "output": 0.012},
    "moonshot-v1-32k": {"input": 0.024, "output": 0.024},
    "moonshot-v1-128k": {"input": 0.06, "output": 0.06},
    
    # 百川
    "Baichuan4": {"input": 0.012, "output": 0.012},
    
    # 文心
    "ernie-4.0-8k": {"input": 0.12, "output": 0.12},
    "ernie-3.5-8k": {"input": 0.012, "output": 0.012},
    
    # 零一万物
    "yi-large": {"input": 0.0025, "output": 0.0025},
    
    # MiniMax
    "abab6.5-chat": {"input": 0.03, "output": 0.03},
    
    # 默认价格（未知模型）
    "default": {"input": 0.001, "output": 0.002},
}


def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """计算 token 费用"""
    pricing = MODEL_PRICING.get(model, MODEL_PRICING["default"])
    input_cost = (input_tokens / 1000) * pricing["input"]
    output_cost = (output_tokens / 1000) * pricing["output"]
    return round(input_cost + output_cost, 6)
```

### 4.2 更新 Project 模型

**文件**: `E:\_Workspace\Godview\app\models\project.py`

添加 token 统计字段：

```python
class Project(BaseModel):
    """项目模型"""
    
    id: str = Field(..., description="项目ID")
    name: str = Field(..., description="项目名称")
    description: Optional[str] = Field(None, description="项目描述")
    
    # 关联实体
    world_id: Optional[str] = Field(None, description="关联的世界ID")
    
    # Token 统计（冗余字段，用于快速查询）
    total_tokens: int = Field(default=0, description="总 Token 消耗")
    total_cost: float = Field(default=0.0, description="总费用（美元）")
    
    # 时间戳
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    # 状态
    status: ProjectStatus = Field(default=ProjectStatus.DRAFT)
    
    # 元数据
    metadata: Dict[str, Any] = Field(default_factory=dict)
```

### 4.3 Token 使用追踪服务

**新文件**: `E:\_Workspace\Godview\app\services\token_tracker.py`

```python
"""
Token 使用追踪服务
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.models.token_usage import (
    TokenUsageRecord,
    TokenUsageSummary,
    ProjectTokenStats,
    UsageCategory,
    calculate_cost,
)

logger = logging.getLogger(__name__)


class TokenTracker:
    """Token 使用追踪器"""
    
    def __init__(self):
        # 内存存储（生产环境应使用数据库）
        self._records: Dict[str, TokenUsageRecord] = {}
    
    async def record_usage(
        self,
        project_id: str,
        input_tokens: int,
        output_tokens: int,
        provider: str,
        model: str,
        category: UsageCategory,
        agent_name: Optional[str] = None,
        session_id: Optional[str] = None,
        chapter_id: Optional[str] = None,
        character_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> TokenUsageRecord:
        """
        记录一次 token 使用
        
        Args:
            project_id: 项目 ID
            input_tokens: 输入 token 数
            output_tokens: 输出 token 数
            provider: 模型提供商
            model: 模型名称
            category: 使用场景
            agent_name: Agent 名称
            session_id: 会话 ID
            chapter_id: 章节 ID
            character_id: 角色 ID
            metadata: 额外元数据
        
        Returns:
            TokenUsageRecord: 使用记录
        """
        total_tokens = input_tokens + output_tokens
        estimated_cost = calculate_cost(model, input_tokens, output_tokens)
        
        record = TokenUsageRecord(
            id=f"usage_{uuid.uuid4().hex[:12]}",
            project_id=project_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            provider=provider,
            model=model,
            category=category,
            agent_name=agent_name,
            session_id=session_id,
            chapter_id=chapter_id,
            character_id=character_id,
            estimated_cost=estimated_cost,
            metadata=metadata or {},
        )
        
        self._records[record.id] = record
        
        logger.info(
            f"Token 使用记录: project={project_id}, model={model}, "
            f"tokens={total_tokens}, cost=${estimated_cost:.4f}"
        )
        
        return record
    
    async def get_project_summary(self, project_id: str) -> TokenUsageSummary:
        """获取项目的 token 使用统计"""
        project_records = [
            r for r in self._records.values() if r.project_id == project_id
        ]
        
        if not project_records:
            return TokenUsageSummary(project_id=project_id)
        
        total_input = sum(r.input_tokens for r in project_records)
        total_output = sum(r.output_tokens for r in project_records)
        total_cost = sum(r.estimated_cost or 0 for r in project_records)
        
        # 按分类统计
        by_category: Dict[str, int] = {}
        for r in project_records:
            cat = r.category.value
            by_category[cat] = by_category.get(cat, 0) + r.total_tokens
        
        # 按模型统计
        by_model: Dict[str, int] = {}
        for r in project_records:
            by_model[r.model] = by_model.get(r.model, 0) + r.total_tokens
        
        # 按 Agent 统计
        by_agent: Dict[str, int] = {}
        for r in project_records:
            if r.agent_name:
                by_agent[r.agent_name] = by_agent.get(r.agent_name, 0) + r.total_tokens
        
        timestamps = [r.created_at for r in project_records]
        
        return TokenUsageSummary(
            project_id=project_id,
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            total_tokens=total_input + total_output,
            total_estimated_cost=total_cost,
            by_category=by_category,
            by_model=by_model,
            by_agent=by_agent,
            first_usage=min(timestamps),
            last_usage=max(timestamps),
            record_count=len(project_records),
        )
    
    async def get_project_stats(self, project_id: str, project_name: str) -> ProjectTokenStats:
        """获取项目的 token 统计（用于前端展示）"""
        project_records = [
            r for r in self._records.values() if r.project_id == project_id
        ]
        
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=today_start.weekday())
        month_start = today_start.replace(day=1)
        
        # 计算各时间段的统计
        today_tokens = 0
        today_cost = 0.0
        week_tokens = 0
        week_cost = 0.0
        month_tokens = 0
        month_cost = 0.0
        
        for r in project_records:
            if r.created_at >= today_start:
                today_tokens += r.total_tokens
                today_cost += r.estimated_cost or 0
            if r.created_at >= week_start:
                week_tokens += r.total_tokens
                week_cost += r.estimated_cost or 0
            if r.created_at >= month_start:
                month_tokens += r.total_tokens
                month_cost += r.estimated_cost or 0
        
        # 最近 7 天趋势
        daily_tokens = []
        for i in range(7):
            day = today_start - timedelta(days=6 - i)
            day_end = day + timedelta(days=1)
            day_records = [
                r for r in project_records
                if day <= r.created_at < day_end
            ]
            daily_tokens.append({
                "date": day.strftime("%m-%d"),
                "tokens": sum(r.total_tokens for r in day_records),
                "cost": sum(r.estimated_cost or 0 for r in day_records),
            })
        
        # 分类占比
        summary = await self.get_project_summary(project_id)
        category_breakdown = []
        for cat, tokens in summary.by_category.items():
            percent = (tokens / summary.total_tokens * 100) if summary.total_tokens > 0 else 0
            category_breakdown.append({
                "category": cat,
                "tokens": tokens,
                "percent": round(percent, 1),
            })
        
        return ProjectTokenStats(
            project_id=project_id,
            project_name=project_name,
            total_tokens=summary.total_tokens,
            total_cost=summary.total_estimated_cost,
            today_tokens=today_tokens,
            today_cost=today_cost,
            week_tokens=week_tokens,
            week_cost=week_cost,
            month_tokens=month_tokens,
            month_cost=month_cost,
            daily_tokens=daily_tokens,
            category_breakdown=sorted(category_breakdown, key=lambda x: x["tokens"], reverse=True),
        )
    
    async def get_all_project_stats(self) -> List[ProjectTokenStats]:
        """获取所有项目的 token 统计"""
        # 按项目分组
        project_ids = set(r.project_id for r in self._records.values())
        
        stats = []
        for pid in project_ids:
            stats.append(await self.get_project_stats(pid, pid))  # TODO: 获取真实项目名
        
        return sorted(stats, key=lambda x: x.total_tokens, reverse=True)


# 全局单例
_token_tracker: Optional[TokenTracker] = None


def get_token_tracker() -> TokenTracker:
    """获取 Token 追踪器单例"""
    global _token_tracker
    if _token_tracker is None:
        _token_tracker = TokenTracker()
    return _token_tracker
```

### 4.4 集成到 LLM 调用

**文件**: `E:\_Workspace\Godview\app\services\model_router.py`

在 LLM 调用后记录 token 使用：

```python
from app.services.token_tracker import get_token_tracker
from app.models.token_usage import UsageCategory

async def call_llm_with_tracking(
    project_id: str,
    messages: List[Dict],
    category: UsageCategory,
    agent_name: Optional[str] = None,
    **kwargs
) -> Tuple[str, Dict[str, int]]:
    """
    调用 LLM 并记录 token 使用
    
    Returns:
        Tuple[str, Dict]: (响应文本, token 使用信息)
    """
    # 调用 LLM
    response = await llm.ainvoke(messages, **kwargs)
    
    # 获取 token 使用信息
    usage = response.response_metadata.get("token_usage", {})
    input_tokens = usage.get("prompt_tokens", 0)
    output_tokens = usage.get("completion_tokens", 0)
    
    # 记录使用
    tracker = get_token_tracker()
    await tracker.record_usage(
        project_id=project_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        provider=settings.llm_provider,
        model=settings.llm_model,
        category=category,
        agent_name=agent_name,
    )
    
    return response.content, usage
```

### 4.5 API 端点

**文件**: `E:\_Workspace\Godview\app\api\routes\token_usage.py`

```python
"""
Token 使用统计 API
"""

from fastapi import APIRouter, Query
from typing import List, Optional

from app.services.token_tracker import get_token_tracker
from app.models.token_usage import TokenUsageSummary, ProjectTokenStats

router = APIRouter()


@router.get("/projects/{project_id}/summary", response_model=TokenUsageSummary)
async def get_project_token_summary(project_id: str):
    """获取项目的 Token 使用统计摘要"""
    tracker = get_token_tracker()
    return await tracker.get_project_summary(project_id)


@router.get("/projects/{project_id}/stats", response_model=ProjectTokenStats)
async def get_project_token_stats(project_id: str, name: Optional[str] = Query(None)):
    """获取项目的 Token 详细统计"""
    tracker = get_token_tracker()
    return await tracker.get_project_stats(project_id, name or project_id)


@router.get("/stats", response_model=List[ProjectTokenStats])
async def get_all_token_stats():
    """获取所有项目的 Token 统计"""
    tracker = get_token_tracker()
    return await tracker.get_all_project_stats()
```

### 4.6 前端 - 项目 Token 统计组件

**新文件**: `E:\_Workspace\Godview\frontend\src\components\TokenStats.tsx`

```tsx
import { useState, useEffect } from 'react'
import { Card } from '@/components/ui'
import { getProjectTokenStats } from '@/api/tokenUsage'
import { Coins, TrendingUp, Calendar, BarChart3 } from 'lucide-react'

interface TokenStatsProps {
  projectId: string
  projectName: string
}

interface TokenStats {
  total_tokens: number
  total_cost: number
  today_tokens: number
  today_cost: number
  week_tokens: number
  week_cost: number
  month_tokens: number
  month_cost: number
  daily_tokens: Array<{ date: string; tokens: number; cost: number }>
  category_breakdown: Array<{ category: string; tokens: number; percent: number }>
}

export function TokenStats({ projectId, projectName }: TokenStatsProps) {
  const [stats, setStats] = useState<TokenStats | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadStats()
  }, [projectId])

  const loadStats = async () => {
    try {
      const data = await getProjectTokenStats(projectId, projectName)
      setStats(data)
    } catch (error) {
      console.error('Failed to load token stats:', error)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return <Card className="p-6">加载中...</Card>
  }

  if (!stats) {
    return null
  }

  const formatTokens = (n: number) => {
    if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`
    if (n >= 1000) return `${(n / 1000).toFixed(1)}K`
    return n.toString()
  }

  const formatCost = (n: number) => {
    if (n >= 1) return `$${n.toFixed(2)}`
    if (n >= 0.01) return `$${n.toFixed(3)}`
    return `$${n.toFixed(4)}`
  }

  const getCategoryLabel = (cat: string) => {
    const labels: Record<string, string> = {
      bootstrap: '项目初始化',
      dialogue: '对话生成',
      narrative: '叙事生成',
      evaluation: '内容评估',
      summary: '剧情总结',
      hook: '伏笔管理',
      character: '角色声音',
      setting: '设定对话',
      other: '其他',
    }
    return labels[cat] || cat
  }

  return (
    <div className="space-y-6">
      {/* 核心指标 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="p-4">
          <div className="flex items-center gap-2 text-gray-500 mb-1">
            <Coins size={16} />
            <span className="text-sm">总消耗</span>
          </div>
          <div className="text-2xl font-bold text-gray-800">
            {formatTokens(stats.total_tokens)}
          </div>
          <div className="text-sm text-gray-500">{formatCost(stats.total_cost)}</div>
        </Card>
        
        <Card className="p-4">
          <div className="flex items-center gap-2 text-gray-500 mb-1">
            <Calendar size={16} />
            <span className="text-sm">今日</span>
          </div>
          <div className="text-xl font-bold text-gray-800">
            {formatTokens(stats.today_tokens)}
          </div>
          <div className="text-sm text-gray-500">{formatCost(stats.today_cost)}</div>
        </Card>
        
        <Card className="p-4">
          <div className="flex items-center gap-2 text-gray-500 mb-1">
            <TrendingUp size={16} />
            <span className="text-sm">本周</span>
          </div>
          <div className="text-xl font-bold text-gray-800">
            {formatTokens(stats.week_tokens)}
          </div>
          <div className="text-sm text-gray-500">{formatCost(stats.week_cost)}</div>
        </Card>
        
        <Card className="p-4">
          <div className="flex items-center gap-2 text-gray-500 mb-1">
            <BarChart3 size={16} />
            <span className="text-sm">本月</span>
          </div>
          <div className="text-xl font-bold text-gray-800">
            {formatTokens(stats.month_tokens)}
          </div>
          <div className="text-sm text-gray-500">{formatCost(stats.month_cost)}</div>
        </Card>
      </div>

      {/* 趋势图 */}
      <Card title="最近 7 天趋势">
        <div className="h-40 flex items-end gap-2">
          {stats.daily_tokens.map((day, i) => {
            const maxTokens = Math.max(...stats.daily_tokens.map(d => d.tokens), 1)
            const height = (day.tokens / maxTokens) * 100
            return (
              <div key={i} className="flex-1 flex flex-col items-center">
                <div 
                  className="w-full bg-blue-500 rounded-t transition-all"
                  style={{ height: `${Math.max(height, 2)}%` }}
                  title={`${formatTokens(day.tokens)} / ${formatCost(day.cost)}`}
                />
                <span className="text-xs text-gray-400 mt-1">{day.date}</span>
              </div>
            )
          })}
        </div>
      </Card>

      {/* 分类占比 */}
      <Card title="使用场景分布">
        <div className="space-y-3">
          {stats.category_breakdown.map((item, i) => (
            <div key={i}>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-600">{getCategoryLabel(item.category)}</span>
                <span className="text-gray-800">
                  {formatTokens(item.tokens)} ({item.percent}%)
                </span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div 
                  className="bg-blue-500 h-2 rounded-full"
                  style={{ width: `${item.percent}%` }}
                />
              </div>
            </div>
          ))}
          {stats.category_breakdown.length === 0 && (
            <p className="text-gray-500 text-center py-4">暂无使用记录</p>
          )}
        </div>
      </Card>
    </div>
  )
}
```

### 4.7 前端 - 在 Dashboard 显示

**文件**: `E:\_Workspace\Godview\frontend\src\pages\Dashboard.tsx`

添加 Token 统计卡片：

```tsx
import { TokenStats } from '@/components/TokenStats'
import { useProject } from '@/contexts/ProjectContext'

export default function Dashboard() {
  const { currentProject } = useProject()
  
  return (
    <div>
      <h1 className="text-3xl font-bold text-gray-800 mb-8">仪表盘</h1>
      
      {/* Token 消耗统计 */}
      {currentProject && (
        <div className="mb-8">
          <h2 className="text-xl font-semibold text-gray-800 mb-4">💰 Token 消耗统计</h2>
          <TokenStats 
            projectId={currentProject.id} 
            projectName={currentProject.name} 
          />
        </div>
      )}
      
      {/* 原有内容... */}
    </div>
  )
}
```

### 4.8 前端 API

**新文件**: `E:\_Workspace\Godview\frontend\src\api\tokenUsage.ts`

```ts
import { api } from './client'

export interface TokenStats {
  project_id: string
  project_name: string
  total_tokens: number
  total_cost: number
  today_tokens: number
  today_cost: number
  week_tokens: number
  week_cost: number
  month_tokens: number
  month_cost: number
  daily_tokens: Array<{ date: string; tokens: number; cost: number }>
  category_breakdown: Array<{ category: string; tokens: number; percent: number }>
}

export async function getProjectTokenStats(
  projectId: string, 
  name?: string
): Promise<TokenStats> {
  const params = name ? { name } : {}
  const response = await api.get(`/token-usage/projects/${projectId}/stats`, { params })
  return response.data
}

export async function getAllTokenStats(): Promise<TokenStats[]> {
  const response = await api.get('/token-usage/stats')
  return response.data
}
```

---

## Files to Modify (Part 4)

| 文件 | 修改内容 |
|------|----------|
| `app/models/token_usage.py` | **新建** - Token 使用记录模型 |
| `app/models/project.py` | 添加 `total_tokens`、`total_cost` 字段 |
| `app/services/token_tracker.py` | **新建** - Token 追踪服务 |
| `app/services/model_router.py` | 集成 token 使用记录 |
| `app/api/routes/token_usage.py` | **新建** - Token 统计 API |
| `frontend/src/components/TokenStats.tsx` | **新建** - Token 统计组件 |
| `frontend/src/api/tokenUsage.ts` | **新建** - Token API |
| `frontend/src/pages/Dashboard.tsx` | 显示 Token 统计 |

---

---

## Part 5: 数据库表结构设计

> 所有设计基于数据库持久化，当前测试状态可暂用内存存储，正式使用时切换到数据库。

### 5.1 PostgreSQL 表结构

#### 5.1.1 项目表 (projects)

```sql
CREATE TABLE projects (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    user_id VARCHAR(64),
    
    -- 关联
    world_id VARCHAR(64),
    
    -- Token 统计
    total_tokens BIGINT DEFAULT 0,
    total_cost DECIMAL(10, 6) DEFAULT 0,
    
    -- 状态
    status VARCHAR(32) DEFAULT 'draft',
    
    -- 时间戳
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- 元数据
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_projects_user_id ON projects(user_id);
CREATE INDEX idx_projects_status ON projects(status);
```

#### 5.1.2 世界表 (worlds)

```sql
CREATE TABLE worlds (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    
    -- 项目关联
    project_id VARCHAR(64) REFERENCES projects(id),
    
    -- 世界属性
    world_type VARCHAR(32) DEFAULT 'fantasy',
    tone VARCHAR(32) DEFAULT 'serious',
    
    -- 时间戳
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_worlds_project_id ON worlds(project_id);
```

#### 5.1.3 角色表 (characters)

```sql
CREATE TABLE characters (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    
    -- 项目关联
    project_id VARCHAR(64) REFERENCES projects(id),
    world_id VARCHAR(64) REFERENCES worlds(id),
    
    -- 基础信息
    description TEXT,
    role VARCHAR(32) DEFAULT 'supporting',
    status VARCHAR(32) DEFAULT 'active',
    
    -- 外观
    appearance TEXT,
    age INTEGER,
    gender VARCHAR(32),
    
    -- 性格
    personality_traits JSONB DEFAULT '[]',
    background_story TEXT,
    
    -- 语言风格
    speech_pattern TEXT,
    lexicon JSONB DEFAULT '[]',
    forbidden_words JSONB DEFAULT '[]',
    voice_samples JSONB DEFAULT '[]',
    
    -- 状态属性
    attributes JSONB DEFAULT '{}',
    goals JSONB DEFAULT '[]',
    inventory JSONB DEFAULT '[]',
    current_location VARCHAR(64),
    
    -- 时间戳
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(64) DEFAULT 'system'
);

CREATE INDEX idx_characters_project_id ON characters(project_id);
CREATE INDEX idx_characters_world_id ON characters(world_id);
CREATE INDEX idx_characters_status ON characters(status);
```

#### 5.1.4 章节表 (chapters)

```sql
CREATE TABLE chapters (
    id VARCHAR(64) PRIMARY KEY,
    
    -- 项目关联
    project_id VARCHAR(64) REFERENCES projects(id),
    world_id VARCHAR(64) REFERENCES worlds(id),
    
    -- 章节信息
    title VARCHAR(255) NOT NULL,
    content TEXT,
    status VARCHAR(32) DEFAULT 'draft',
    word_count INTEGER DEFAULT 0,
    "order" INTEGER DEFAULT 0,
    
    -- 时间戳
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_chapters_project_id ON chapters(project_id);
CREATE INDEX idx_chapters_world_id ON chapters(world_id);
```

#### 5.1.5 伏笔表 (hooks)

```sql
CREATE TABLE hooks (
    id VARCHAR(64) PRIMARY KEY,
    
    -- 项目关联
    project_id VARCHAR(64) REFERENCES projects(id),
    world_id VARCHAR(64) REFERENCES worlds(id),
    
    -- 伏笔信息
    title VARCHAR(255) NOT NULL,
    description TEXT,
    hook_type VARCHAR(32) DEFAULT 'foreshadowing',
    status VARCHAR(32) DEFAULT 'planted',
    priority INTEGER DEFAULT 1,
    
    -- 关联信息
    related_characters JSONB DEFAULT '[]',
    related_locations JSONB DEFAULT '[]',
    related_objects JSONB DEFAULT '[]',
    
    -- 埋设与回收
    plant_context TEXT,
    plant_chapter VARCHAR(64),
    resolution_hint TEXT,
    resolution_chapter VARCHAR(64),
    
    -- 时间戳
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP
);

CREATE INDEX idx_hooks_project_id ON hooks(project_id);
CREATE INDEX idx_hooks_status ON hooks(status);
```

#### 5.1.6 Token 使用记录表 (token_usage)

```sql
CREATE TABLE token_usage (
    id VARCHAR(64) PRIMARY KEY,
    project_id VARCHAR(64) NOT NULL REFERENCES projects(id),
    
    -- Token 数量
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    
    -- 模型信息
    provider VARCHAR(64) NOT NULL,
    model VARCHAR(128) NOT NULL,
    
    -- 使用场景
    category VARCHAR(32) NOT NULL,
    agent_name VARCHAR(64),
    
    -- 关联信息
    request_id VARCHAR(64),
    session_id VARCHAR(64),
    chapter_id VARCHAR(64),
    character_id VARCHAR(64),
    
    -- 费用
    estimated_cost DECIMAL(10, 6),
    
    -- 时间戳
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- 元数据
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_token_usage_project_id ON token_usage(project_id);
CREATE INDEX idx_token_usage_category ON token_usage(category);
CREATE INDEX idx_token_usage_created_at ON token_usage(created_at);
CREATE INDEX idx_token_usage_model ON token_usage(model);
```

#### 5.1.7 干预记录表 (interventions)

```sql
CREATE TABLE interventions (
    id VARCHAR(64) PRIMARY KEY,
    
    -- 项目关联
    project_id VARCHAR(64) REFERENCES projects(id),
    snapshot_id VARCHAR(64),
    
    -- 干预信息
    intervention_type VARCHAR(32) NOT NULL,
    description TEXT NOT NULL,
    details JSONB DEFAULT '{}',
    
    -- 影响范围
    affected_characters JSONB DEFAULT '[]',
    affected_hooks JSONB DEFAULT '[]',
    affected_relationships JSONB DEFAULT '[]',
    
    -- 效果评估
    outcome_rating INTEGER,
    outcome_notes TEXT,
    
    -- 时间戳
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_interventions_project_id ON interventions(project_id);
```

#### 5.1.8 快照表 (snapshots)

```sql
CREATE TABLE snapshots (
    id VARCHAR(64) PRIMARY KEY,
    
    -- 项目关联
    project_id VARCHAR(64) REFERENCES projects(id),
    world_id VARCHAR(64) REFERENCES worlds(id),
    
    -- 快照信息
    name VARCHAR(255),
    description TEXT,
    snapshot_type VARCHAR(32) DEFAULT 'auto',
    
    -- 分支信息
    parent_snapshot_id VARCHAR(64) REFERENCES snapshots(id),
    is_branch BOOLEAN DEFAULT FALSE,
    branch_reason TEXT,
    
    -- 世界状态
    world_state JSONB DEFAULT '{}',
    
    -- 时间戳
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_snapshots_project_id ON snapshots(project_id);
CREATE INDEX idx_snapshots_world_id ON snapshots(world_id);
CREATE INDEX idx_snapshots_parent_id ON snapshots(parent_snapshot_id);
```

### 5.2 数据库服务层更新

**文件**: `E:\_Workspace\Godview\app\database\postgres.py`

新增 Token 使用相关方法：

```python
class PostgresDB:
    # ... 原有方法 ...
    
    async def save_token_usage(self, record: Dict[str, Any]) -> str:
        """保存 Token 使用记录"""
        query = """
            INSERT INTO token_usage 
            (id, project_id, input_tokens, output_tokens, total_tokens, 
             provider, model, category, agent_name, session_id, 
             chapter_id, character_id, estimated_cost, metadata)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
        """
        await self.pool.execute(
            query,
            record["id"], record["project_id"], record["input_tokens"],
            record["output_tokens"], record["total_tokens"], record["provider"],
            record["model"], record["category"], record.get("agent_name"),
            record.get("session_id"), record.get("chapter_id"),
            record.get("character_id"), record.get("estimated_cost"),
            json.dumps(record.get("metadata", {}))
        )
        
        # 更新项目统计
        await self._update_project_token_stats(
            record["project_id"],
            record["total_tokens"],
            record.get("estimated_cost", 0)
        )
        
        return record["id"]
    
    async def _update_project_token_stats(
        self, project_id: str, tokens: int, cost: float
    ):
        """更新项目的 Token 统计"""
        query = """
            UPDATE projects 
            SET total_tokens = total_tokens + $2,
                total_cost = total_cost + $3,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = $1
        """
        await self.pool.execute(query, project_id, tokens, cost)
    
    async def get_token_usage_by_project(
        self, 
        project_id: str, 
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """获取项目的 Token 使用记录"""
        conditions = ["project_id = $1"]
        params = [project_id]
        
        if start_date:
            params.append(start_date)
            conditions.append(f"created_at >= ${len(params)}")
        if end_date:
            params.append(end_date)
            conditions.append(f"created_at <= ${len(params)}")
        
        query = f"""
            SELECT * FROM token_usage 
            WHERE {' AND '.join(conditions)}
            ORDER BY created_at DESC
        """
        results = await self.pool.fetch(query, *params)
        return [dict(r) for r in results]
    
    async def get_token_stats_by_project(self, project_id: str) -> Dict[str, Any]:
        """获取项目的 Token 统计摘要"""
        query = """
            SELECT 
                COUNT(*) as record_count,
                SUM(input_tokens) as total_input_tokens,
                SUM(output_tokens) as total_output_tokens,
                SUM(total_tokens) as total_tokens,
                SUM(estimated_cost) as total_cost
            FROM token_usage
            WHERE project_id = $1
        """
        result = await self.pool.fetchrow(query, project_id)
        return dict(result)
    
    async def get_token_stats_by_category(self, project_id: str) -> List[Dict[str, Any]]:
        """按场景分类统计"""
        query = """
            SELECT category, SUM(total_tokens) as tokens
            FROM token_usage
            WHERE project_id = $1
            GROUP BY category
            ORDER BY tokens DESC
        """
        results = await self.pool.fetch(query, project_id)
        return [dict(r) for r in results]
    
    async def get_token_stats_by_model(self, project_id: str) -> List[Dict[str, Any]]:
        """按模型分类统计"""
        query = """
            SELECT model, SUM(total_tokens) as tokens
            FROM token_usage
            WHERE project_id = $1
            GROUP BY model
            ORDER BY tokens DESC
        """
        results = await self.pool.fetch(query, project_id)
        return [dict(r) for r in results]
    
    async def get_daily_token_stats(
        self, project_id: str, days: int = 7
    ) -> List[Dict[str, Any]]:
        """获取每日 Token 统计"""
        query = """
            SELECT 
                DATE(created_at) as date,
                SUM(total_tokens) as tokens,
                SUM(estimated_cost) as cost
            FROM token_usage
            WHERE project_id = $1 
              AND created_at >= CURRENT_DATE - INTERVAL '%s days'
            GROUP BY DATE(created_at)
            ORDER BY date
        """ % days
        results = await self.pool.fetch(query, project_id)
        return [dict(r) for r in results]
    
    async def get_all_project_token_stats(self) -> List[Dict[str, Any]]:
        """获取所有项目的 Token 统计"""
        query = """
            SELECT 
                p.id as project_id,
                p.name as project_name,
                p.total_tokens,
                p.total_cost
            FROM projects p
            WHERE p.total_tokens > 0
            ORDER BY p.total_tokens DESC
        """
        results = await self.pool.fetch(query)
        return [dict(r) for r in results]
```

### 5.3 数据库初始化脚本

**文件**: `E:\_Workspace\Godview\scripts.py`

添加表创建命令：

```python
async def init_tables():
    """初始化数据库表"""
    from app.database.postgres import PostgresDB
    
    db = PostgresDB()
    await db.connect()
    
    # 读取并执行建表 SQL
    tables_sql = """
    -- 上述所有 CREATE TABLE 语句
    """
    
    await db.pool.execute(tables_sql)
    print("数据库表初始化完成")
```

---

## Implementation Notes

- **所有设计基于数据库持久化**
- 当前测试状态可暂用内存存储，正式使用时切换到数据库
- Token 价格参考各模型官方定价，可能需要定期更新
- 费用为估算值，实际费用以 API 提供商账单为准
- LLM Provider 配置为运行时配置，不修改 .env 文件
