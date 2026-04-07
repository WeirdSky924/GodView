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

## Part 6: Agent Skill 系统

### 6.1 概述

Agent Skill 系统允许：
1. **Skill 生成** - Agent 或用户可以创建新的 skill
2. **Skill 库** - 所有 skills 存储在全局库中，可跨项目共享
3. **Skill 分配** - 用户可将 skill 分配给特定项目的特定 Agent
4. **Skill 调用** - Agent 在运行时可调用分配给它的 skills

### 6.2 Skill 类型

| 类型 | 描述 | 用途示例 |
|------|------|----------|
| `prompt` | 提示词模板 | 角色扮演、写作风格、对话模式 |
| `function` | Python 函数 | 数据处理、格式转换、复杂计算 |
| `workflow` | 多步骤工作流 | 内容生成流水线、审批流程 |
| `knowledge` | 知识片段 | 世界设定、角色背景、剧情摘要 |

### 6.3 数据模型

**新文件**: `E:\_Workspace\Godview\app\models\skill.py`

```python
"""
Agent Skill 数据模型
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SkillType(str, Enum):
    """Skill 类型"""
    PROMPT = "prompt"        # 提示词模板
    FUNCTION = "function"    # Python 函数
    WORKFLOW = "workflow"    # 多步骤工作流
    KNOWLEDGE = "knowledge"  # 知识片段


class SkillStatus(str, Enum):
    """Skill 状态"""
    DRAFT = "draft"          # 草稿
    ACTIVE = "active"        # 激活
    DEPRECATED = "deprecated" # 已废弃


class SkillParameter(BaseModel):
    """Skill 参数定义"""
    name: str = Field(..., description="参数名")
    type: str = Field(default="string", description="参数类型: string/number/boolean/array/object")
    description: Optional[str] = Field(None, description="参数描述")
    default: Optional[Any] = Field(None, description="默认值")
    required: bool = Field(default=True, description="是否必填")
    enum: Optional[List[str]] = Field(None, description="枚举值列表")


class Skill(BaseModel):
    """Skill 模型"""
    
    id: str = Field(..., description="Skill ID")
    name: str = Field(..., description="Skill 名称")
    description: str = Field(..., description="Skill 描述")
    skill_type: SkillType = Field(..., description="Skill 类型")
    
    # 内容定义（根据类型使用不同字段）
    prompt_template: Optional[str] = Field(None, description="Prompt 模板，支持 {{param}} 变量")
    function_code: Optional[str] = Field(None, description="Python 函数代码")
    workflow_steps: Optional[List[Dict[str, Any]]] = Field(None, description="工作流步骤")
    knowledge_content: Optional[str] = Field(None, description="知识内容")
    
    # 参数定义
    parameters: List[SkillParameter] = Field(default_factory=list, description="参数列表")
    
    # 元数据
    tags: List[str] = Field(default_factory=list, description="标签")
    version: str = Field(default="1.0.0", description="版本号")
    status: SkillStatus = Field(default=SkillStatus.DRAFT, description="状态")
    
    # 创建来源
    creator_project_id: Optional[str] = Field(None, description="创建项目 ID")
    creator_agent_id: Optional[str] = Field(None, description="创建 Agent ID")
    creator_user_id: Optional[str] = Field(None, description="创建用户 ID")
    
    # 使用统计
    usage_count: int = Field(default=0, description="使用次数")
    last_used_at: Optional[datetime] = Field(None, description="最后使用时间")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class SkillAssignment(BaseModel):
    """Skill 分配模型"""
    
    id: str = Field(..., description="分配 ID")
    skill_id: str = Field(..., description="Skill ID")
    project_id: str = Field(..., description="项目 ID")
    agent_id: str = Field(..., description="Agent ID (character_id)")
    
    # 分配配置
    custom_parameters: Optional[Dict[str, Any]] = Field(None, description="覆盖默认参数")
    priority: int = Field(default=0, description="执行优先级，数字越大越优先")
    
    assigned_by: str = Field(default="user", description="分配者")
    assigned_at: datetime = Field(default_factory=datetime.utcnow)


class SkillExecutionLog(BaseModel):
    """Skill 执行日志"""
    
    id: str = Field(..., description="日志 ID")
    skill_id: str = Field(..., description="Skill ID")
    project_id: str = Field(..., description="项目 ID")
    agent_id: str = Field(..., description="Agent ID")
    
    input_params: Dict[str, Any] = Field(default_factory=dict, description="输入参数")
    output_result: Optional[str] = Field(None, description="输出结果")
    success: bool = Field(default=True, description="是否成功")
    error_message: Optional[str] = Field(None, description="错误信息")
    execution_time_ms: Optional[int] = Field(None, description="执行耗时(ms)")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

### 6.4 Skill 服务

**新文件**: `E:\_Workspace\Godview\app\services\skill_service.py`

```python
"""
Skill 管理服务
"""
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.models.skill import Skill, SkillAssignment, SkillType, SkillStatus
from app.database.postgres import PostgresDB

logger = logging.getLogger(__name__)


class SkillService:
    """Skill 管理服务"""
    
    def __init__(self, db: PostgresDB):
        self.db = db
    
    async def generate_skill(
        self,
        name: str,
        description: str,
        skill_type: SkillType,
        content: str,
        parameters: Optional[List[Dict]] = None,
        tags: Optional[List[str]] = None,
        creator_project_id: Optional[str] = None,
        creator_agent_id: Optional[str] = None,
        creator_user_id: Optional[str] = None,
    ) -> Skill:
        """
        生成新的 Skill
        
        Args:
            name: Skill 名称
            description: Skill 描述
            skill_type: Skill 类型
            content: 内容（根据类型含义不同）
            parameters: 参数定义
            tags: 标签
            creator_project_id: 创建项目 ID
            creator_agent_id: 创建 Agent ID
            creator_user_id: 创建用户 ID
        
        Returns:
            Skill: 创建的 Skill
        """
        skill_id = f"skill_{uuid.uuid4().hex[:12]}"
        
        skill_data = {
            "id": skill_id,
            "name": name,
            "description": description,
            "skill_type": skill_type.value,
            "tags": tags or [],
            "parameters": parameters or [],
            "status": SkillStatus.DRAFT.value,
            "creator_project_id": creator_project_id,
            "creator_agent_id": creator_agent_id,
            "creator_user_id": creator_user_id,
        }
        
        # 根据类型设置内容
        if skill_type == SkillType.PROMPT:
            skill_data["prompt_template"] = content
        elif skill_type == SkillType.FUNCTION:
            skill_data["function_code"] = content
        elif skill_type == SkillType.WORKFLOW:
            skill_data["workflow_steps"] = content  # JSON string or list
        elif skill_type == SkillType.KNOWLEDGE:
            skill_data["knowledge_content"] = content
        
        await self.db.save_skill(skill_data)
        
        return Skill(**skill_data)
    
    async def assign_skill_to_agent(
        self,
        skill_id: str,
        project_id: str,
        agent_id: str,
        custom_parameters: Optional[Dict] = None,
        priority: int = 0,
        assigned_by: str = "user",
    ) -> SkillAssignment:
        """
        将 Skill 分配给 Agent
        
        Args:
            skill_id: Skill ID
            project_id: 项目 ID
            agent_id: Agent ID
            custom_parameters: 自定义参数
            priority: 优先级
            assigned_by: 分配者
        
        Returns:
            SkillAssignment: 分配记录
        """
        # 检查 skill 是否存在
        skill = await self.db.get_skill(skill_id)
        if not skill:
            raise ValueError(f"Skill {skill_id} 不存在")
        
        # 检查是否已分配
        existing = await self.db.get_skill_assignment(skill_id, project_id, agent_id)
        if existing:
            raise ValueError(f"Skill {skill_id} 已分配给 Agent {agent_id}")
        
        assignment_id = f"assign_{uuid.uuid4().hex[:12]}"
        
        assignment_data = {
            "id": assignment_id,
            "skill_id": skill_id,
            "project_id": project_id,
            "agent_id": agent_id,
            "custom_parameters": custom_parameters,
            "priority": priority,
            "assigned_by": assigned_by,
        }
        
        await self.db.save_skill_assignment(assignment_data)
        
        return SkillAssignment(**assignment_data)
    
    async def get_agent_skills(self, project_id: str, agent_id: str) -> List[Dict[str, Any]]:
        """
        获取 Agent 已分配的 Skills
        
        Args:
            project_id: 项目 ID
            agent_id: Agent ID
        
        Returns:
            List: Skill 列表（包含分配信息）
        """
        return await self.db.get_agent_skills(project_id, agent_id)
    
    async def list_skills(
        self,
        skill_type: Optional[SkillType] = None,
        status: Optional[SkillStatus] = None,
        tags: Optional[List[str]] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        列出 Skills
        
        Args:
            skill_type: 类型过滤
            status: 状态过滤
            tags: 标签过滤
            search: 搜索关键词
            limit: 数量限制
            offset: 偏移量
        
        Returns:
            List: Skill 列表
        """
        return await self.db.list_skills(
            skill_type=skill_type.value if skill_type else None,
            status=status.value if status else None,
            tags=tags,
            search=search,
            limit=limit,
            offset=offset,
        )
```

### 6.5 Skill 执行器

**新文件**: `E:\_Workspace\Godview\app\services\skill_executor.py`

```python
"""
Skill 执行器
"""
import time
import logging
from typing import Any, Dict, Optional

from app.models.skill import Skill, SkillType
from app.services.model_router import create_llm

logger = logging.getLogger(__name__)


class SkillExecutor:
    """Skill 执行器"""
    
    def __init__(self):
        self.execution_logs = []
    
    async def execute_skill(
        self,
        skill: Skill,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        执行 Skill
        
        Args:
            skill: Skill 对象
            params: 执行参数
            context: 执行上下文（包含 agent、project 等信息）
        
        Returns:
            Dict: 执行结果
        """
        start_time = time.time()
        
        try:
            # 合并默认参数
            merged_params = self._merge_parameters(skill, params)
            
            # 根据类型执行
            if skill.skill_type == SkillType.PROMPT:
                result = await self._execute_prompt_skill(skill, merged_params, context)
            elif skill.skill_type == SkillType.FUNCTION:
                result = await self._execute_function_skill(skill, merged_params, context)
            elif skill.skill_type == SkillType.WORKFLOW:
                result = await self._execute_workflow_skill(skill, merged_params, context)
            elif skill.skill_type == SkillType.KNOWLEDGE:
                result = await self._execute_knowledge_skill(skill, merged_params, context)
            else:
                raise ValueError(f"未知的 Skill 类型: {skill.skill_type}")
            
            execution_time = int((time.time() - start_time) * 1000)
            
            return {
                "success": True,
                "result": result,
                "execution_time_ms": execution_time,
            }
        
        except Exception as e:
            execution_time = int((time.time() - start_time) * 1000)
            logger.error(f"Skill 执行失败: {skill.id} - {e}")
            
            return {
                "success": False,
                "error": str(e),
                "execution_time_ms": execution_time,
            }
    
    def _merge_parameters(self, skill: Skill, params: Dict[str, Any]) -> Dict[str, Any]:
        """合并默认参数和传入参数"""
        merged = {}
        
        # 设置默认值
        for param in skill.parameters:
            if param.default is not None:
                merged[param.name] = param.default
        
        # 覆盖传入参数
        merged.update(params)
        
        # 检查必填参数
        for param in skill.parameters:
            if param.required and param.name not in merged:
                raise ValueError(f"缺少必填参数: {param.name}")
        
        return merged
    
    async def _execute_prompt_skill(
        self,
        skill: Skill,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]],
    ) -> str:
        """执行 Prompt 类型 Skill"""
        # 替换模板变量
        prompt = skill.prompt_template
        for key, value in params.items():
            prompt = prompt.replace(f"{{{{{key}}}}}", str(value))
        
        # 添加上下文
        if context:
            agent_info = context.get("agent", {})
            if agent_info:
                prompt = f"[角色: {agent_info.get('name', '未知')}]\n\n{prompt}"
        
        # 调用 LLM
        from app.config import settings
        llm = create_llm(
            provider=settings.llm_provider,
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )
        
        response = await llm.ainvoke([{"role": "user", "content": prompt}])
        return response.content
    
    async def _execute_function_skill(
        self,
        skill: Skill,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]],
    ) -> Any:
        """执行 Function 类型 Skill"""
        # 创建安全的执行环境
        safe_globals = {
            "__builtins__": {
                "len": len,
                "str": str,
                "int": int,
                "float": float,
                "list": list,
                "dict": dict,
                "range": range,
                "enumerate": enumerate,
                "zip": zip,
            }
        }
        
        # 执行代码
        local_vars = {"params": params, "context": context, "result": None}
        exec(skill.function_code, safe_globals, local_vars)
        
        return local_vars.get("result")
    
    async def _execute_workflow_skill(
        self,
        skill: Skill,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """执行 Workflow 类型 Skill"""
        results = {}
        
        for step in skill.workflow_steps:
            step_type = step.get("type")
            step_params = {**params, **step.get("params", {})}
            
            if step_type == "prompt":
                # 执行 prompt 步骤
                prompt = step.get("template")
                for key, value in {**step_params, **results}.items():
                    prompt = prompt.replace(f"{{{{{key}}}}}", str(value))
                
                # 调用 LLM
                from app.config import settings
                llm = create_llm(
                    provider=settings.llm_provider,
                    model=settings.llm_model,
                    api_key=settings.llm_api_key,
                    base_url=settings.llm_base_url,
                )
                response = await llm.ainvoke([{"role": "user", "content": prompt}])
                results[step.get("output_key", f"step_{len(results)}")] = response.content
            
            elif step_type == "transform":
                # 执行数据转换
                # TODO: 实现转换逻辑
                pass
        
        return results
    
    async def _execute_knowledge_skill(
        self,
        skill: Skill,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]],
    ) -> str:
        """执行 Knowledge 类型 Skill"""
        # 直接返回知识内容
        return skill.knowledge_content
```

### 6.6 API 路由

**新文件**: `E:\_Workspace\Godview\app\api\routes\skills.py`

```python
"""
Skill 管理 API 路由
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.app import postgres_db
from app.models.skill import SkillType, SkillStatus

logger = logging.getLogger(__name__)

router = APIRouter()


class CreateSkillRequest(BaseModel):
    """创建 Skill 请求"""
    name: str
    description: str
    skill_type: str
    content: str  # 根据 type 不同，含义不同
    parameters: Optional[List[Dict]] = None
    tags: Optional[List[str]] = None
    creator_project_id: Optional[str] = None
    creator_agent_id: Optional[str] = None


class AssignSkillRequest(BaseModel):
    """分配 Skill 请求"""
    project_id: str
    agent_id: str
    custom_parameters: Optional[Dict[str, Any]] = None
    priority: Optional[int] = 0


@router.get("", response_model=List[Dict[str, Any]])
async def list_skills(
    skill_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    tags: Optional[str] = Query(None),  # 逗号分隔
    search: Optional[str] = Query(None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
):
    """获取 Skill 列表"""
    tag_list = tags.split(",") if tags else None
    
    skills = await postgres_db.list_skills(
        skill_type=skill_type,
        status=status,
        tags=tag_list,
        search=search,
        limit=limit,
        offset=offset,
    )
    return skills


@router.post("", response_model=Dict[str, Any])
async def create_skill(request: CreateSkillRequest):
    """创建新 Skill"""
    try:
        skill_type = SkillType(request.skill_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"无效的 skill_type: {request.skill_type}")
    
    skill_data = {
        "name": request.name,
        "description": request.description,
        "skill_type": skill_type.value,
        "parameters": request.parameters or [],
        "tags": request.tags or [],
        "status": SkillStatus.DRAFT.value,
        "creator_project_id": request.creator_project_id,
        "creator_agent_id": request.creator_agent_id,
    }
    
    # 根据类型设置内容
    if skill_type == SkillType.PROMPT:
        skill_data["prompt_template"] = request.content
    elif skill_type == SkillType.FUNCTION:
        skill_data["function_code"] = request.content
    elif skill_type == SkillType.WORKFLOW:
        skill_data["workflow_steps"] = request.content
    elif skill_type == SkillType.KNOWLEDGE:
        skill_data["knowledge_content"] = request.content
    
    skill_id = await postgres_db.save_skill(skill_data)
    
    return {
        "success": True,
        "id": skill_id,
        "message": f"Skill '{request.name}' 创建成功",
    }


@router.get("/{skill_id}", response_model=Dict[str, Any])
async def get_skill(skill_id: str):
    """获取 Skill 详情"""
    skill = await postgres_db.get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill 不存在")
    return skill


@router.put("/{skill_id}", response_model=Dict[str, Any])
async def update_skill(skill_id: str, updates: Dict[str, Any]):
    """更新 Skill"""
    existing = await postgres_db.get_skill(skill_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Skill 不存在")
    
    await postgres_db.update_skill(skill_id, updates)
    
    return {
        "success": True,
        "id": skill_id,
        "message": "Skill 更新成功",
    }


@router.delete("/{skill_id}", response_model=Dict[str, Any])
async def delete_skill(skill_id: str):
    """删除 Skill"""
    await postgres_db.delete_skill(skill_id)
    
    return {
        "success": True,
        "message": f"Skill {skill_id} 已删除",
    }


@router.post("/{skill_id}/assign", response_model=Dict[str, Any])
async def assign_skill(skill_id: str, request: AssignSkillRequest):
    """将 Skill 分配给 Agent"""
    # 检查 skill 是否存在
    skill = await postgres_db.get_skill(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail="Skill 不存在")
    
    # 检查是否已分配
    existing = await postgres_db.get_skill_assignment(
        skill_id, request.project_id, request.agent_id
    )
    if existing:
        raise HTTPException(status_code=400, detail="Skill 已分配给该 Agent")
    
    assignment_data = {
        "skill_id": skill_id,
        "project_id": request.project_id,
        "agent_id": request.agent_id,
        "custom_parameters": request.custom_parameters,
        "priority": request.priority,
    }
    
    await postgres_db.save_skill_assignment(assignment_data)
    
    return {
        "success": True,
        "message": f"Skill 已分配给 Agent",
    }


@router.delete("/{skill_id}/assign", response_model=Dict[str, Any])
async def unassign_skill(skill_id: str, project_id: str, agent_id: str):
    """取消 Skill 分配"""
    await postgres_db.delete_skill_assignment(skill_id, project_id, agent_id)
    
    return {
        "success": True,
        "message": "Skill 分配已取消",
    }


@router.get("/agents/{project_id}/{agent_id}", response_model=List[Dict[str, Any]])
async def get_agent_skills(project_id: str, agent_id: str):
    """获取 Agent 已分配的 Skills"""
    skills = await postgres_db.get_agent_skills(project_id, agent_id)
    return skills


@router.post("/{skill_id}/test", response_model=Dict[str, Any])
async def test_skill(skill_id: str, params: Dict[str, Any]):
    """测试 Skill"""
    from app.services.skill_executor import SkillExecutor
    from app.models.skill import Skill
    
    skill_data = await postgres_db.get_skill(skill_id)
    if not skill_data:
        raise HTTPException(status_code=404, detail="Skill 不存在")
    
    skill = Skill(**skill_data)
    executor = SkillExecutor()
    
    result = await executor.execute_skill(skill, params)
    
    return result
```

### 6.7 前端组件

**新文件**: `E:\_Workspace\Godview\frontend\src\pages\Skills.tsx`

```tsx
import { useState, useEffect } from 'react'
import { Card, Button, Input } from '@/components/ui'
import { getSkills, createSkill, deleteSkill } from '@/api/skills'
import { Plus, Trash2, Play, Tag, Code, FileText, Workflow, BookOpen } from 'lucide-react'

export default function Skills() {
  const [skills, setSkills] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState({
    type: '',
    search: '',
  })
  
  const loadSkills = async () => {
    setLoading(true)
    try {
      const data = await getSkills(filter)
      setSkills(data)
    } finally {
      setLoading(false)
    }
  }
  
  useEffect(() => {
    loadSkills()
  }, [filter])
  
  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'prompt': return <FileText size={18} />
      case 'function': return <Code size={18} />
      case 'workflow': return <Workflow size={18} />
      case 'knowledge': return <BookOpen size={18} />
      default: return <FileText size={18} />
    }
  }
  
  return (
    <div>
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold text-gray-800">🛠️ Skill 库</h1>
        <Button onClick={() => {/* 打开创建对话框 */}}>
          <Plus size={18} className="mr-2" />
          创建 Skill
        </Button>
      </div>
      
      {/* 过滤器 */}
      <div className="flex gap-4 mb-6">
        <Input
          placeholder="搜索 Skill..."
          value={filter.search}
          onChange={(e) => setFilter({ ...filter, search: e.target.value })}
          className="w-64"
        />
        <select
          className="px-3 py-2 border rounded-lg"
          value={filter.type}
          onChange={(e) => setFilter({ ...filter, type: e.target.value })}
        >
          <option value="">所有类型</option>
          <option value="prompt">Prompt</option>
          <option value="function">Function</option>
          <option value="workflow">Workflow</option>
          <option value="knowledge">Knowledge</option>
        </select>
      </div>
      
      {/* Skill 列表 */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {skills.map(skill => (
          <Card key={skill.id} className="p-4">
            <div className="flex items-start justify-between mb-2">
              <div className="flex items-center gap-2">
                {getTypeIcon(skill.skill_type)}
                <h3 className="font-semibold text-gray-800">{skill.name}</h3>
              </div>
              <span className={`text-xs px-2 py-1 rounded ${
                skill.status === 'active' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'
              }`}>
                {skill.status}
              </span>
            </div>
            
            <p className="text-sm text-gray-600 mb-3 line-clamp-2">{skill.description}</p>
            
            {/* 标签 */}
            <div className="flex flex-wrap gap-1 mb-3">
              {skill.tags?.map((tag: string, i: number) => (
                <span key={i} className="text-xs px-2 py-0.5 bg-blue-50 text-blue-600 rounded">
                  {tag}
                </span>
              ))}
            </div>
            
            {/* 操作按钮 */}
            <div className="flex gap-2 pt-2 border-t">
              <Button size="sm" variant="outline">
                <Play size={14} className="mr-1" />
                测试
              </Button>
              <Button size="sm" variant="outline">
                分配
              </Button>
              <Button size="sm" variant="outline" className="text-red-600">
                <Trash2 size={14} />
              </Button>
            </div>
          </Card>
        ))}
      </div>
      
      {skills.length === 0 && !loading && (
        <div className="text-center py-12 text-gray-500">
          <p>暂无 Skill，点击上方按钮创建</p>
        </div>
      )}
    </div>
  )
}
```

### 6.8 数据库服务层扩展

**文件**: `E:\_Workspace\Godview\app\database\postgres.py`

添加以下方法：

```python
# ==================== Skill 相关操作 ====================

async def save_skill(self, skill_data: Dict[str, Any]) -> str:
    """保存 Skill"""
    query = """
    INSERT INTO skills (id, name, description, skill_type, prompt_template, function_code,
                       workflow_steps, knowledge_content, parameters, tags, version, status,
                       creator_project_id, creator_agent_id, creator_user_id, usage_count,
                       last_used_at, created_at, updated_at)
    VALUES (:id, :name, :description, :skill_type, :prompt_template, :function_code,
            :workflow_steps, :knowledge_content, :parameters, :tags, :version, :status,
            :creator_project_id, :creator_agent_id, :creator_user_id, :usage_count,
            :last_used_at, :created_at, :updated_at)
    ON CONFLICT (id) DO UPDATE SET
        name = EXCLUDED.name,
        description = EXCLUDED.description,
        prompt_template = EXCLUDED.prompt_template,
        function_code = EXCLUDED.function_code,
        workflow_steps = EXCLUDED.workflow_steps,
        knowledge_content = EXCLUDED.knowledge_content,
        parameters = EXCLUDED.parameters,
        tags = EXCLUDED.tags,
        version = EXCLUDED.version,
        status = EXCLUDED.status,
        updated_at = EXCLUDED.updated_at
    """
    await self.execute_query(query, skill_data)
    return skill_data.get("id", "")

async def get_skill(self, skill_id: str) -> Optional[Dict[str, Any]]:
    """获取 Skill"""
    query = "SELECT * FROM skills WHERE id = :id"
    results = await self.execute_query(query, {"id": skill_id})
    return results[0] if results else None

async def list_skills(self, skill_type=None, status=None, tags=None, search=None, limit=50, offset=0):
    """列出 Skills"""
    conditions = []
    params = {"limit": limit, "offset": offset}
    
    if skill_type:
        conditions.append("skill_type = :skill_type")
        params["skill_type"] = skill_type
    if status:
        conditions.append("status = :status")
        params["status"] = status
    if search:
        conditions.append("(name ILIKE :search OR description ILIKE :search)")
        params["search"] = f"%{search}%"
    
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    
    query = f"""
    SELECT * FROM skills {where_clause}
    ORDER BY created_at DESC
    LIMIT :limit OFFSET :offset
    """
    return await self.execute_query(query, params)

async def save_skill_assignment(self, assignment_data: Dict[str, Any]) -> str:
    """保存 Skill 分配"""
    query = """
    INSERT INTO skill_assignments (id, skill_id, project_id, agent_id, custom_parameters, priority, assigned_by, assigned_at)
    VALUES (:id, :skill_id, :project_id, :agent_id, :custom_parameters, :priority, :assigned_by, :assigned_at)
    ON CONFLICT (skill_id, project_id, agent_id) DO UPDATE SET
        custom_parameters = EXCLUDED.custom_parameters,
        priority = EXCLUDED.priority
    """
    await self.execute_query(query, assignment_data)
    return assignment_data.get("id", "")

async def get_agent_skills(self, project_id: str, agent_id: str) -> List[Dict[str, Any]]:
    """获取 Agent 的 Skills"""
    query = """
    SELECT s.*, sa.custom_parameters, sa.priority, sa.assigned_at
    FROM skills s
    JOIN skill_assignments sa ON s.id = sa.skill_id
    WHERE sa.project_id = :project_id AND sa.agent_id = :agent_id
    ORDER BY sa.priority DESC, sa.assigned_at DESC
    """
    return await self.execute_query(query, {"project_id": project_id, "agent_id": agent_id})
```

---

## Files to Modify (Part 6)

| 文件 | 修改内容 |
|------|----------|
| `app/models/skill.py` | **新建** - Skill 数据模型 |
| `app/services/skill_service.py` | **新建** - Skill 管理服务 |
| `app/services/skill_executor.py` | **新建** - Skill 执行器 |
| `app/api/routes/skills.py` | **新建** - Skill API 路由 |
| `app/database/postgres.py` | 添加 Skill 相关数据库方法 |
| `app/agents/character_agent.py` | 添加 Skill 调用能力 |
| `frontend/src/pages/Skills.tsx` | **新建** - Skill 管理页面 |
| `frontend/src/components/skills/SkillEditor.tsx` | **新建** - Skill 编辑器 |
| `frontend/src/components/skills/SkillAssignDialog.tsx` | **新建** - 分配对话框 |
| `frontend/src/api/skills.ts` | **新建** - Skill API |
| `frontend/src/components/Layout.tsx` | 添加 Skills 菜单项 |

---

## Part 7: 双 RAG 架构设计（动态剧情 + 静态设定）

### 7.1 架构概述

现有的向量/图数据库记录的是世界的"现在进行时"（动态剧情），需要补充一个充当"世界宪法"和"风物志"的静态设定 RAG，记录世界的"底层运转逻辑"。

```
┌─────────────────────────────────────────────────────────────────┐
│                        GodView 双 RAG 架构                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────┐    ┌─────────────────────────────┐ │
│  │   静态设定 RAG (Lore)   │    │   动态剧情 RAG (Narrative)  │ │
│  │   "世界宪法 + 风物志"    │    │      "现在进行时"           │ │
│  ├─────────────────────────┤    ├─────────────────────────────┤ │
│  │ • 世界观规则            │    │ • 当前事件                  │ │
│  │ • 地理设定              │    │ • 角色状态变化              │ │
│  │ • 历史背景              │    │ • 关系演变                  │ │
│  │ • 势力体系              │    │ • 剧情进展                  │ │
│  │ • 种族/职业设定         │    │ • 角色记忆                  │ │
│  │ • 物品/装备设定         │    │ • 伏笔状态                  │ │
│  │ • 文化习俗              │    │ • 时间线快照                │ │
│  └─────────────────────────┘    └─────────────────────────────┘ │
│           │                                │                    │
│           ▼                                ▼                    │
│  ┌─────────────────────────┐    ┌─────────────────────────────┐ │
│  │  Qdrant: lore_records   │    │  Qdrant: narrative_records  │ │
│  │  Nebula: lore_entities  │    │  Nebula: narrative_entities │ │
│  └─────────────────────────┘    └─────────────────────────────┘ │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 7.2 数据模型

**新文件**: `app/models/lore.py`

```python
"""
静态设定数据模型（Lore）
充当"世界宪法"和"风物志"，记录世界的"底层运转逻辑"
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class LoreCategory(str, Enum):
    """设定类别"""
    
    # 世界层面
    WORLD_RULE = "world_rule"           # 世界规则（物理法则、魔法体系）
    GEOGRAPHY = "geography"             # 地理设定（区域、地形、气候）
    HISTORY = "history"                 # 历史背景（重大事件、时代划分）
    
    # 社会层面
    FACTION = "faction"                 # 势力/组织
    CULTURE = "culture"                 # 文化习俗
    RELIGION = "religion"               # 宗教信仰
    ECONOMY = "economy"                 # 经济体系
    
    # 生物层面
    RACE = "race"                       # 种族设定
    PROFESSION = "profession"           # 职业/阶层
    CREATURE = "creature"               # 生物/怪物
    
    # 物品层面
    ITEM = "item"                       # 物品/装备
    MATERIAL = "material"               # 材料/资源
    ARTIFACT = "artifact"               # 神器/宝物
    
    # 技能层面
    SKILL = "skill"                     # 技能/能力
    SPELL = "spell"                     # 法术/招式
    TECHNIQUE = "technique"             # 功法/秘术


class LorePriority(str, Enum):
    """设定优先级（用于冲突解决）"""
    CONSTITUTIONAL = "constitutional"   # 宪法级（不可违反）
    CORE = "core"                       # 核心设定
    STANDARD = "standard"               # 标准设定
    FLEXIBLE = "flexible"               # 灵活设定


class LoreEntry(BaseModel):
    """设定条目"""
    
    id: str = Field(..., description="设定 ID")
    project_id: str = Field(..., description="所属项目 ID")
    
    # 基本信息
    name: str = Field(..., description="设定名称")
    category: LoreCategory = Field(..., description="设定类别")
    description: str = Field(..., description="设定描述")
    
    # 详细内容
    content: str = Field(..., description="详细设定内容（Markdown）")
    keywords: List[str] = Field(default_factory=list, description="关键词列表")
    
    # 优先级
    priority: LorePriority = Field(default=LorePriority.STANDARD, description="优先级")
    
    # 关联
    parent_id: Optional[str] = Field(None, description="父设定 ID（用于层级关系）")
    related_entities: List[str] = Field(default_factory=list, description="关联实体 ID")
    related_lore: List[str] = Field(default_factory=list, description="关联设定 ID")
    
    # 约束条件
    constraints: List[str] = Field(default_factory=list, description="约束条件（该设定衍生的规则）")
    forbidden_actions: List[str] = Field(default_factory=list, description="禁止的行为")
    
    # 来源
    source: str = Field(default="user", description="来源：user/bootstrap/derived")
    source_reference: Optional[str] = Field(None, description="来源引用")
    
    # 元数据
    tags: List[str] = Field(default_factory=list, description="标签")
    version: int = Field(default=1, description="版本号")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # 向量嵌入信息
    embedding_hash: Optional[str] = Field(None, description="嵌入内容的哈希（用于检测变化）")


class LoreReference(BaseModel):
    """设定引用（用于追踪哪些内容引用了设定）"""
    
    id: str = Field(..., description="引用 ID")
    lore_id: str = Field(..., description="设定 ID")
    
    # 引用来源
    reference_type: str = Field(..., description="引用类型：chapter/event/dialogue/character")
    reference_id: str = Field(..., description="引用来源 ID")
    
    # 引用上下文
    context: Optional[str] = Field(None, description="引用上下文")
    quoted_content: Optional[str] = Field(None, description="引用的具体内容")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)


class LoreConflict(BaseModel):
    """设定冲突记录"""
    
    id: str = Field(..., description="冲突 ID")
    project_id: str = Field(..., description="项目 ID")
    
    # 冲突信息
    lore_id_1: str = Field(..., description="设定 1 ID")
    lore_id_2: str = Field(..., description="设定 2 ID")
    conflict_type: str = Field(..., description="冲突类型：contradiction/overlap/undefined")
    description: str = Field(..., description="冲突描述")
    
    # 解决状态
    status: str = Field(default="pending", description="状态：pending/resolved/ignored")
    resolution: Optional[str] = Field(None, description="解决方案")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
```

**新文件**: `app/models/narrative.py`

```python
"""
动态剧情数据模型（Narrative）
记录世界的"现在进行时"
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class NarrativeEntryType(str, Enum):
    """剧情条目类型"""
    EVENT = "event"                     # 事件
    STATE_CHANGE = "state_change"       # 状态变化
    RELATIONSHIP_CHANGE = "relationship_change"  # 关系变化
    LOCATION_CHANGE = "location_change" # 位置变化
    DIALOGUE = "dialogue"               # 对话
    ACTION = "action"                   # 行动
    DISCOVERY = "discovery"             # 发现
    CONFLICT = "conflict"               # 冲突
    RESOLUTION = "resolution"           # 解决


class TemporalScope(str, Enum):
    """时间范围"""
    INSTANT = "instant"                 # 瞬时（几秒）
    SHORT = "short"                     # 短期（几分钟到几小时）
    MEDIUM = "medium"                   # 中期（几天到几周）
    LONG = "long"                       # 长期（几个月到几年）
    PERMANENT = "permanent"             # 永久


class NarrativeEntry(BaseModel):
    """剧情条目"""
    
    id: str = Field(..., description="条目 ID")
    project_id: str = Field(..., description="项目 ID")
    world_id: str = Field(..., description="世界 ID")
    
    # 基本信息
    entry_type: NarrativeEntryType = Field(..., description="条目类型")
    title: str = Field(..., description="标题")
    summary: str = Field(..., description="摘要")
    content: str = Field(..., description="详细内容")
    
    # 时间信息
    narrative_time: Optional[str] = Field(None, description="剧情内时间")
    real_time: datetime = Field(default_factory=datetime.utcnow, description="现实时间")
    temporal_scope: TemporalScope = Field(default=TemporalScope.SHORT, description="时间范围")
    
    # 参与者
    participants: List[str] = Field(default_factory=list, description="参与角色 ID")
    locations: List[str] = Field(default_factory=list, description="涉及地点 ID")
    
    # 因果关系
    causes: List[str] = Field(default_factory=list, description="原因事件 ID")
    effects: List[str] = Field(default_factory=list, description="结果事件 ID")
    
    # 状态变化
    state_changes: Dict[str, Any] = Field(default_factory=dict, description="状态变化记录")
    
    # 关联设定
    lore_references: List[str] = Field(default_factory=list, description="引用的设定 ID")
    
    # 元数据
    importance: float = Field(default=0.5, ge=0, le=1, description="重要性")
    chapter_id: Optional[str] = Field(None, description="所属章节 ID")
    
    # 向量嵌入
    embedding_hash: Optional[str] = Field(None, description="嵌入哈希")


class CharacterState(BaseModel):
    """角色状态（当前进行时）"""
    
    id: str = Field(..., description="状态 ID")
    character_id: str = Field(..., description="角色 ID")
    project_id: str = Field(..., description="项目 ID")
    
    # 当前状态
    current_location: Optional[str] = Field(None, description="当前位置")
    current_status: str = Field(default="active", description="当前状态")
    current_mood: Optional[str] = Field(None, description="当前情绪")
    
    # 属性状态
    attributes: Dict[str, Any] = Field(default_factory=dict, description="当前属性")
    inventory: List[str] = Field(default_factory=list, description="当前物品")
    active_goals: List[str] = Field(default_factory=list, description="当前目标")
    
    # 关系状态
    relationships: Dict[str, float] = Field(default_factory=dict, description="当前关系强度")
    
    # 最近事件
    recent_events: List[str] = Field(default_factory=list, description="最近事件 ID")
    
    # 时间戳
    snapshot_time: datetime = Field(default_factory=datetime.utcnow, description="快照时间")
    version: int = Field(default=1, description="版本号")


class WorldSnapshot(BaseModel):
    """世界快照（记录某一时刻的世界状态）"""
    
    id: str = Field(..., description="快照 ID")
    project_id: str = Field(..., description="项目 ID")
    world_id: str = Field(..., description="世界 ID")
    
    # 快照信息
    name: Optional[str] = Field(None, description="快照名称")
    description: Optional[str] = Field(None, description="快照描述")
    snapshot_type: str = Field(default="auto", description="类型：auto/manual/chapter_end")
    
    # 状态数据
    character_states: Dict[str, Dict] = Field(default_factory=dict, description="角色状态")
    relationship_states: Dict[str, Dict] = Field(default_factory=dict, description="关系状态")
    location_states: Dict[str, Dict] = Field(default_factory=dict, description="地点状态")
    hook_states: Dict[str, Dict] = Field(default_factory=dict, description="伏笔状态")
    
    # 索引信息
    narrative_time: Optional[str] = Field(None, description="剧情时间")
    chapter_id: Optional[str] = Field(None, description="章节 ID")
    
    # 时间戳
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

### 7.3 Qdrant 集合重构

**文件**: `app/database/qdrant.py`

```python
# 新增集合常量
COLLECTION_LORE = "godview_lore"           # 静态设定 RAG
COLLECTION_NARRATIVE = "godview_narrative" # 动态剧情 RAG
COLLECTION_VOICE = "godview_voice"         # 角色声音样本

async def init_collections(self):
    """初始化所有集合"""
    collections = [
        # 静态设定集合
        {
            "name": COLLECTION_LORE,
            "description": "静态设定 RAG - 世界宪法和风物志",
        },
        # 动态剧情集合
        {
            "name": COLLECTION_NARRATIVE,
            "description": "动态剧情 RAG - 现在进行时",
        },
        # 角色声音集合
        {
            "name": COLLECTION_VOICE,
            "description": "角色声音样本",
        },
    ]
    
    for col in collections:
        await self._create_collection_if_not_exists(
            collection_name=col["name"],
            description=col["description"],
        )

# ==================== 静态设定 RAG 操作 ====================

async def add_lore_entry(
    self,
    lore_id: str,
    project_id: str,
    category: str,
    name: str,
    content: str,
    keywords: List[str],
    priority: str,
    embedding: Optional[List[float]] = None,
) -> Optional[str]:
    """
    添加静态设定条目
    
    Args:
        lore_id: 设定 ID
        project_id: 项目 ID
        category: 设定类别
        name: 设定名称
        content: 详细内容
        keywords: 关键词
        priority: 优先级
        embedding: 向量嵌入
    
    Returns:
        str: 条目 ID
    """
    payload = {
        "type": "lore",
        "project_id": project_id,
        "category": category,
        "name": name,
        "keywords": keywords,
        "priority": priority,
        "created_at": datetime.utcnow().isoformat(),
    }
    
    if embedding:
        return await self.insert_vector(embedding, payload, lore_id)
    else:
        return await self.insert_text(content, payload, lore_id)

async def search_lore(
    self,
    project_id: str,
    query: str,
    categories: Optional[List[str]] = None,
    priority_min: Optional[str] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """
    搜索静态设定
    
    Args:
        project_id: 项目 ID
        query: 查询文本
        categories: 类别过滤
        priority_min: 最低优先级
        limit: 返回数量
    
    Returns:
        List: 设定列表
    """
    filter_conditions = {
        "type": "lore",
        "project_id": project_id,
    }
    
    # 类别过滤（Qdrant 不支持多值匹配，需要分开处理）
    
    return await self.search_by_text(
        query_text=query,
        limit=limit,
        filter_conditions=filter_conditions,
    )

async def get_lore_by_keywords(
    self,
    project_id: str,
    keywords: List[str],
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """
    通过关键词获取设定
    
    Args:
        project_id: 项目 ID
        keywords: 关键词列表
        limit: 返回数量
    
    Returns:
        List: 设定列表
    """
    # 使用布尔查询或关键词匹配
    # 注意：Qdrant 的关键词搜索需要通过 payload 过滤
    
    results = []
    for keyword in keywords[:5]:  # 限制关键词数量
        query_result = await self.search_by_text(
            query_text=keyword,
            limit=limit // len(keywords) + 1,
            filter_conditions={
                "type": "lore",
                "project_id": project_id,
            },
        )
        results.extend(query_result)
    
    # 去重
    seen = set()
    unique_results = []
    for r in results:
        if r["id"] not in seen:
            seen.add(r["id"])
            unique_results.append(r)
    
    return unique_results[:limit]

# ==================== 动态剧情 RAG 操作 ====================

async def add_narrative_entry(
    self,
    entry_id: str,
    project_id: str,
    entry_type: str,
    title: str,
    content: str,
    participants: List[str],
    importance: float,
    embedding: Optional[List[float]] = None,
) -> Optional[str]:
    """
    添加动态剧情条目
    
    Args:
        entry_id: 条目 ID
        project_id: 项目 ID
        entry_type: 条目类型
        title: 标题
        content: 内容
        participants: 参与者
        importance: 重要性
        embedding: 向量嵌入
    
    Returns:
        str: 条目 ID
    """
    payload = {
        "type": "narrative",
        "project_id": project_id,
        "entry_type": entry_type,
        "title": title,
        "participants": participants,
        "importance": importance,
        "created_at": datetime.utcnow().isoformat(),
    }
    
    if embedding:
        return await self.insert_vector(embedding, payload, entry_id)
    else:
        return await self.insert_text(content, payload, entry_id)

async def search_narrative(
    self,
    project_id: str,
    query: str,
    entry_types: Optional[List[str]] = None,
    participants: Optional[List[str]] = None,
    min_importance: float = 0.0,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """
    搜索动态剧情
    
    Args:
        project_id: 项目 ID
        query: 查询文本
        entry_types: 条目类型过滤
        participants: 参与者过滤
        min_importance: 最小重要性
        limit: 返回数量
    
    Returns:
        List: 剧情列表
    """
    filter_conditions = {
        "type": "narrative",
        "project_id": project_id,
    }
    
    results = await self.search_by_text(
        query_text=query,
        limit=limit * 2,  # 多取一些用于过滤
        filter_conditions=filter_conditions,
    )
    
    # 过滤重要性
    results = [r for r in results if r.get("payload", {}).get("importance", 0) >= min_importance]
    
    return results[:limit]

async def get_recent_narratives(
    self,
    project_id: str,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """
    获取最近的剧情条目
    
    Args:
        project_id: 项目 ID
        limit: 返回数量
    
    Returns:
        List: 剧情列表
    """
    # 按时间倒序获取
    all_points, _ = self._client.scroll(
        collection_name=COLLECTION_NARRATIVE,
        scroll_filter=Filter(
            must=[
                FieldCondition(key="type", match=MatchValue(value="narrative")),
                FieldCondition(key="project_id", match=MatchValue(value=project_id)),
            ]
        ),
        limit=limit,
        with_payload=True,
        with_vectors=False,
    )
    
    return [
        {
            "id": point.id,
            "score": 1.0,
            "payload": point.payload,
        }
        for point in all_points
    ]
```

### 7.4 NebulaGraph Schema 扩展

**文件**: `app/database/nebulagraph.py`

```python
async def init_lore_schema(self):
    """初始化静态设定图 Schema"""
    
    # 设定实体 Tags
    lore_tags = [
        # 世界规则
        """
        CREATE TAG IF NOT EXISTS lore_world_rule (
            name STRING,
            description STRING,
            priority STRING,
            constraints STRING,
            created_at TIMESTAMP
        )
        """,
        # 地理设定
        """
        CREATE TAG IF NOT EXISTS lore_geography (
            name STRING,
            geography_type STRING,
            description STRING,
            climate STRING,
            created_at TIMESTAMP
        )
        """,
        # 势力
        """
        CREATE TAG IF NOT EXISTS lore_faction (
            name STRING,
            faction_type STRING,
            description STRING,
            power_level INT,
            created_at TIMESTAMP
        )
        """,
        # 种族
        """
        CREATE TAG IF NOT EXISTS lore_race (
            name STRING,
            description STRING,
            traits STRING,
            abilities STRING,
            created_at TIMESTAMP
        )
        """,
        # 物品
        """
        CREATE TAG IF NOT EXISTS lore_item (
            name STRING,
            item_type STRING,
            rarity STRING,
            description STRING,
            created_at TIMESTAMP
        )
        """,
    ]
    
    # 设定关系 Edges
    lore_edges = [
        # 设定层级关系
        """
        CREATE EDGE IF NOT EXISTS lore_parent_of ()
        """,
        # 设定关联
        """
        CREATE EDGE IF NOT EXISTS lore_related_to (
            relation_type STRING
        )
        """,
        # 设定约束
        """
        CREATE EDGE IF NOT EXISTS lore_constrains (
            constraint_type STRING
        )
        """,
    ]
    
    for tag_sql in lore_tags:
        result = self._session_pool.execute(tag_sql)
        if result.is_succeeded():
            logger.info(f"Lore Tag 创建成功")
    
    for edge_sql in lore_edges:
        result = self._session_pool.execute(edge_sql)
        if result.is_succeeded():
            logger.info(f"Lore Edge 创建成功")

async def init_narrative_schema(self):
    """初始化动态剧情图 Schema"""
    
    # 剧情实体 Tags
    narrative_tags = [
        # 事件
        """
        CREATE TAG IF NOT EXISTS narrative_event (
            title STRING,
            summary STRING,
            event_type STRING,
            importance FLOAT,
            narrative_time STRING,
            created_at TIMESTAMP
        )
        """,
        # 状态变化
        """
        CREATE TAG IF NOT EXISTS narrative_state_change (
            entity_type STRING,
            entity_id STRING,
            attribute STRING,
            old_value STRING,
            new_value STRING,
            created_at TIMESTAMP
        )
        """,
        # 关系变化
        """
        CREATE TAG IF NOT EXISTS narrative_relationship_change (
            character_id_1 STRING,
            character_id_2 STRING,
            old_strength FLOAT,
            new_strength FLOAT,
            reason STRING,
            created_at TIMESTAMP
        )
        """,
    ]
    
    # 剧情关系 Edges
    narrative_edges = [
        # 事件因果
        """
        CREATE EDGE IF NOT EXISTS causes ()
        """,
        # 事件参与
        """
        CREATE EDGE IF NOT EXISTS participates_in (
            role STRING
        )
        """,
        # 事件发生地
        """
        CREATE EDGE IF NOT EXISTS occurs_at ()
        """,
        # 引用设定
        """
        CREATE EDGE IF NOT EXISTS references_lore ()
        """,
    ]
    
    for tag_sql in narrative_tags:
        result = self._session_pool.execute(tag_sql)
        if result.is_succeeded():
            logger.info(f"Narrative Tag 创建成功")
    
    for edge_sql in narrative_edges:
        result = self._session_pool.execute(edge_sql)
        if result.is_succeeded():
            logger.info(f"Narrative Edge 创建成功")
```

### 7.5 RAG 服务层

**新文件**: `app/services/lore_rag.py`

```python
"""
静态设定 RAG 服务
充当"世界宪法"和"风物志"
"""

import logging
from typing import Any, Dict, List, Optional

from app.models.lore import LoreCategory, LoreEntry, LorePriority
from app.database.qdrant import QdrantDatabase, COLLECTION_LORE
from app.database.nebulagraph import NebulaGraphDatabase

logger = logging.getLogger(__name__)


class LoreRAGService:
    """静态设定 RAG 服务"""
    
    def __init__(self, qdrant: QdrantDatabase, nebula: NebulaGraphDatabase):
        self.qdrant = qdrant
        self.nebula = nebula
    
    async def add_lore(
        self,
        project_id: str,
        name: str,
        category: LoreCategory,
        content: str,
        description: str = "",
        keywords: List[str] = None,
        priority: LorePriority = LorePriority.STANDARD,
        constraints: List[str] = None,
    ) -> LoreEntry:
        """
        添加静态设定
        
        Args:
            project_id: 项目 ID
            name: 设定名称
            category: 设定类别
            content: 详细内容
            description: 简短描述
            keywords: 关键词
            priority: 优先级
            constraints: 约束条件
        
        Returns:
            LoreEntry: 创建的设定条目
        """
        import uuid
        
        lore_id = f"lore_{uuid.uuid4().hex[:12]}"
        
        # 创建模型
        entry = LoreEntry(
            id=lore_id,
            project_id=project_id,
            name=name,
            category=category,
            description=description or content[:200],
            content=content,
            keywords=keywords or [],
            priority=priority,
            constraints=constraints or [],
        )
        
        # 添加到向量数据库
        await self.qdrant.add_lore_entry(
            lore_id=lore_id,
            project_id=project_id,
            category=category.value,
            name=name,
            content=content,
            keywords=entry.keywords,
            priority=priority.value,
        )
        
        # 添加到图数据库（建立关联）
        await self._add_lore_to_graph(entry)
        
        return entry
    
    async def search_lore(
        self,
        project_id: str,
        query: str,
        categories: Optional[List[LoreCategory]] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        搜索静态设定
        
        Args:
            project_id: 项目 ID
            query: 查询文本
            categories: 类别过滤
            limit: 返回数量
        
        Returns:
            List: 设定列表
        """
        category_values = [c.value for c in categories] if categories else None
        
        return await self.qdrant.search_lore(
            project_id=project_id,
            query=query,
            categories=category_values,
            limit=limit,
        )
    
    async def get_constitutional_rules(
        self,
        project_id: str,
    ) -> List[Dict[str, Any]]:
        """
        获取宪法级规则（不可违反的核心设定）
        
        Args:
            project_id: 项目 ID
        
        Returns:
            List: 宪法级规则列表
        """
        # 搜索宪法级设定
        results = await self.qdrant.search_lore(
            project_id=project_id,
            query="world rule constitutional",
            limit=50,
        )
        
        # 过滤出宪法级
        return [
            r for r in results
            if r.get("payload", {}).get("priority") == LorePriority.CONSTITUTIONAL.value
        ]
    
    async def validate_against_lore(
        self,
        project_id: str,
        content: str,
    ) -> Dict[str, Any]:
        """
        验证内容是否符合静态设定
        
        Args:
            project_id: 项目 ID
            content: 待验证的内容
        
        Returns:
            Dict: 验证结果
        """
        # 搜索相关设定
        relevant_lore = await self.search_lore(
            project_id=project_id,
            query=content,
            limit=10,
        )
        
        # 获取宪法级规则
        constitutional = await self.get_constitutional_rules(project_id)
        
        # 构建验证提示
        validation_prompt = self._build_validation_prompt(
            content=content,
            relevant_lore=relevant_lore,
            constitutional=constitutional,
        )
        
        # TODO: 调用 LLM 进行验证
        
        return {
            "valid": True,
            "conflicts": [],
            "warnings": [],
            "relevant_lore": relevant_lore,
        }
    
    async def get_lore_context_for_generation(
        self,
        project_id: str,
        scene_description: str,
        characters: List[str] = None,
        location: str = None,
    ) -> str:
        """
        获取生成内容所需的设定上下文
        
        Args:
            project_id: 项目 ID
            scene_description: 场景描述
            characters: 涉及角色
            location: 地点
        
        Returns:
            str: 设定上下文
        """
        # 搜索场景相关设定
        scene_lore = await self.search_lore(
            project_id=project_id,
            query=scene_description,
            limit=5,
        )
        
        # 获取地点设定
        location_lore = []
        if location:
            location_lore = await self.search_lore(
                project_id=project_id,
                query=location,
                categories=[LoreCategory.GEOGRAPHY],
                limit=3,
            )
        
        # 获取宪法级规则
        constitutional = await self.get_constitutional_rules(project_id)
        
        # 组装上下文
        context_parts = []
        
        if constitutional:
            context_parts.append("【世界宪法 - 不可违反】")
            for rule in constitutional[:3]:
                payload = rule.get("payload", {})
                context_parts.append(f"- {payload.get('name', '')}: {payload.get('description', '')}")
        
        if location_lore:
            context_parts.append("\n【地点设定】")
            for loc in location_lore:
                payload = loc.get("payload", {})
                context_parts.append(f"- {payload.get('name', '')}: {payload.get('description', '')}")
        
        if scene_lore:
            context_parts.append("\n【相关设定】")
            for lore in scene_lore[:5]:
                payload = lore.get("payload", {})
                context_parts.append(f"- {payload.get('name', '')}: {payload.get('description', '')}")
        
        return "\n".join(context_parts)
    
    async def _add_lore_to_graph(self, entry: LoreEntry):
        """将设定添加到图数据库"""
        # 根据类别选择 Tag
        tag_map = {
            LoreCategory.WORLD_RULE: "lore_world_rule",
            LoreCategory.GEOGRAPHY: "lore_geography",
            LoreCategory.FACTION: "lore_faction",
            LoreCategory.RACE: "lore_race",
            LoreCategory.ITEM: "lore_item",
        }
        
        tag_name = tag_map.get(entry.category, "lore_world_rule")
        
        # 插入节点
        query = f"""
        INSERT VERTEX IF NOT EXISTS {tag_name} (
            name, description, priority, constraints, created_at
        )
        VALUES "{entry.id}": (
            "{entry.name}",
            "{entry.description}",
            "{entry.priority.value}",
            "{entry.constraints}",
            "{entry.created_at.isoformat()}"
        )
        """
        
        await self.nebula.query(query)
```

**新文件**: `app/services/narrative_rag.py`

```python
"""
动态剧情 RAG 服务
记录世界的"现在进行时"
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.models.narrative import NarrativeEntry, NarrativeEntryType, CharacterState
from app.database.qdrant import QdrantDatabase, COLLECTION_NARRATIVE
from app.database.nebulagraph import NebulaGraphDatabase

logger = logging.getLogger(__name__)


class NarrativeRAGService:
    """动态剧情 RAG 服务"""
    
    def __init__(self, qdrant: QdrantDatabase, nebula: NebulaGraphDatabase):
        self.qdrant = qdrant
        self.nebula = nebula
    
    async def record_event(
        self,
        project_id: str,
        world_id: str,
        title: str,
        summary: str,
        content: str,
        participants: List[str],
        event_type: NarrativeEntryType = NarrativeEntryType.EVENT,
        importance: float = 0.5,
        causes: List[str] = None,
    ) -> NarrativeEntry:
        """
        记录剧情事件
        
        Args:
            project_id: 项目 ID
            world_id: 世界 ID
            title: 事件标题
            summary: 事件摘要
            content: 详细内容
            participants: 参与者
            event_type: 事件类型
            importance: 重要性
            causes: 原因事件
        
        Returns:
            NarrativeEntry: 创建的条目
        """
        import uuid
        
        entry_id = f"narr_{uuid.uuid4().hex[:12]}"
        
        entry = NarrativeEntry(
            id=entry_id,
            project_id=project_id,
            world_id=world_id,
            entry_type=event_type,
            title=title,
            summary=summary,
            content=content,
            participants=participants,
            importance=importance,
            causes=causes or [],
        )
        
        # 添加到向量数据库
        await self.qdrant.add_narrative_entry(
            entry_id=entry_id,
            project_id=project_id,
            entry_type=event_type.value,
            title=title,
            content=content,
            participants=participants,
            importance=importance,
        )
        
        # 添加到图数据库
        await self._add_event_to_graph(entry)
        
        # 更新角色状态
        for char_id in participants:
            await self._update_character_state(project_id, char_id, entry)
        
        return entry
    
    async def search_narrative(
        self,
        project_id: str,
        query: str,
        participants: List[str] = None,
        min_importance: float = 0.0,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        搜索剧情
        
        Args:
            project_id: 项目 ID
            query: 查询文本
            participants: 参与者过滤
            min_importance: 最小重要性
            limit: 返回数量
        
        Returns:
            List: 剧情列表
        """
        return await self.qdrant.search_narrative(
            project_id=project_id,
            query=query,
            participants=participants,
            min_importance=min_importance,
            limit=limit,
        )
    
    async def get_character_state(
        self,
        project_id: str,
        character_id: str,
    ) -> Optional[CharacterState]:
        """
        获取角色当前状态
        
        Args:
            project_id: 项目 ID
            character_id: 角色 ID
        
        Returns:
            CharacterState: 角色状态
        """
        # 从 PostgreSQL 获取最新状态
        # 或从内存缓存获取
        pass
    
    async def get_narrative_context(
        self,
        project_id: str,
        character_id: str,
        query: str,
        limit: int = 5,
    ) -> str:
        """
        获取角色的剧情上下文
        
        Args:
            project_id: 项目 ID
            character_id: 角色 ID
            query: 查询
            limit: 返回数量
        
        Returns:
            str: 剧情上下文
        """
        # 搜索角色相关的剧情
        results = await self.search_narrative(
            project_id=project_id,
            query=query,
            participants=[character_id],
            limit=limit,
        )
        
        # 组装上下文
        context_parts = ["【角色相关剧情】"]
        for r in results:
            payload = r.get("payload", {})
            context_parts.append(f"- {payload.get('title', '')}: {payload.get('summary', '')}")
        
        return "\n".join(context_parts)
    
    async def get_recent_events(
        self,
        project_id: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        获取最近的事件
        
        Args:
            project_id: 项目 ID
            limit: 返回数量
        
        Returns:
            List: 事件列表
        """
        return await self.qdrant.get_recent_narratives(
            project_id=project_id,
            limit=limit,
        )
    
    async def _add_event_to_graph(self, entry: NarrativeEntry):
        """将事件添加到图数据库"""
        # 插入事件节点
        query = f"""
        INSERT VERTEX IF NOT EXISTS narrative_event (
            title, summary, event_type, importance, narrative_time, created_at
        )
        VALUES "{entry.id}": (
            "{entry.title}",
            "{entry.summary}",
            "{entry.entry_type.value}",
            {entry.importance},
            "{entry.narrative_time or ''}",
            "{entry.created_at.isoformat()}"
        )
        """
        
        await self.nebula.query(query)
        
        # 创建因果关系边
        for cause_id in entry.causes:
            await self.nebula.query(f"""
            INSERT EDGE IF NOT EXISTS causes ()
            VALUES "{cause_id}" -> "{entry.id}": ()
            """)
        
        # 创建参与者边
        for char_id in entry.participants:
            await self.nebula.query(f"""
            INSERT EDGE IF NOT EXISTS participates_in (role)
            VALUES "{char_id}" -> "{entry.id}": ("participant")
            """)
    
    async def _update_character_state(
        self,
        project_id: str,
        character_id: str,
        event: NarrativeEntry,
    ):
        """更新角色状态"""
        # 记录状态变化
        # 更新最近事件列表
        pass
```

### 7.6 双 RAG 编排服务

**新文件**: `app/services/rag_orchestrator.py`

```python
"""
双 RAG 编排服务
协调静态设定 RAG 和动态剧情 RAG
"""

import logging
from typing import Any, Dict, List, Optional

from app.services.lore_rag import LoreRAGService
from app.services.narrative_rag import NarrativeRAGService

logger = logging.getLogger(__name__)


class RAGOrchestrator:
    """双 RAG 编排器"""
    
    def __init__(
        self,
        lore_rag: LoreRAGService,
        narrative_rag: NarrativeRAGService,
    ):
        self.lore_rag = lore_rag
        self.narrative_rag = narrative_rag
    
    async def get_full_context(
        self,
        project_id: str,
        query: str,
        character_id: Optional[str] = None,
        location: Optional[str] = None,
        include_constitutional: bool = True,
        lore_limit: int = 5,
        narrative_limit: int = 5,
    ) -> Dict[str, Any]:
        """
        获取完整的 RAG 上下文（静态 + 动态）
        
        Args:
            project_id: 项目 ID
            query: 查询
            character_id: 角色 ID
            location: 地点
            include_constitutional: 是否包含宪法级规则
            lore_limit: 设定数量限制
            narrative_limit: 剧情数量限制
        
        Returns:
            Dict: 完整上下文
        """
        # 并行获取静态设定和动态剧情
        import asyncio
        
        lore_task = self.lore_rag.get_lore_context_for_generation(
            project_id=project_id,
            scene_description=query,
            location=location,
        )
        
        narrative_task = self.narrative_rag.get_recent_events(
            project_id=project_id,
            limit=narrative_limit,
        )
        
        character_task = None
        if character_id:
            character_task = self.narrative_rag.get_narrative_context(
                project_id=project_id,
                character_id=character_id,
                query=query,
            )
        
        # 等待所有任务完成
        results = await asyncio.gather(
            lore_task,
            narrative_task,
            character_task or asyncio.sleep(0),
        )
        
        lore_context = results[0]
        recent_events = results[1]
        character_context = results[2] if character_id else ""
        
        # 组装完整上下文
        return {
            "lore_context": lore_context,
            "recent_events": recent_events,
            "character_context": character_context,
            "full_prompt": self._assemble_prompt(
                lore_context=lore_context,
                recent_events=recent_events,
                character_context=character_context,
            ),
        }
    
    def _assemble_prompt(
        self,
        lore_context: str,
        recent_events: List[Dict],
        character_context: str,
    ) -> str:
        """组装完整的生成提示"""
        parts = []
        
        if lore_context:
            parts.append("【世界设定】\n" + lore_context)
        
        if recent_events:
            parts.append("\n【最近发生的事件】")
            for event in recent_events[:5]:
                payload = event.get("payload", {})
                parts.append(f"- {payload.get('title', '')}: {payload.get('summary', '')}")
        
        if character_context:
            parts.append("\n" + character_context)
        
        return "\n".join(parts)
    
    async def validate_generation(
        self,
        project_id: str,
        generated_content: str,
    ) -> Dict[str, Any]:
        """
        验证生成内容是否符合设定
        
        Args:
            project_id: 项目 ID
            generated_content: 生成的内容
        
        Returns:
            Dict: 验证结果
        """
        # 验证是否符合静态设定
        lore_validation = await self.lore_rag.validate_against_lore(
            project_id=project_id,
            content=generated_content,
        )
        
        # 检查剧情连贯性
        # TODO: 实现剧情连贯性检查
        
        return {
            "valid": lore_validation.get("valid", True),
            "conflicts": lore_validation.get("conflicts", []),
            "warnings": lore_validation.get("warnings", []),
        }
```

---

## Files to Modify (Part 7)

| 文件 | 修改内容 |
|------|----------|
| `app/models/lore.py` | **新建** - 静态设定数据模型 |
| `app/models/narrative.py` | **新建** - 动态剧情数据模型 |
| `app/database/qdrant.py` | 重构为多集合架构，添加 Lore/Narrative 操作 |
| `app/database/nebulagraph.py` | 添加 Lore/Narrative Schema |
| `app/services/lore_rag.py` | **新建** - 静态设定 RAG 服务 |
| `app/services/narrative_rag.py` | **新建** - 动态剧情 RAG 服务 |
| `app/services/rag_orchestrator.py` | **新建** - 双 RAG 编排服务 |
| `app/api/routes/lore.py` | **新建** - 设定管理 API |
| `frontend/src/pages/Lore.tsx` | **新建** - 设定管理页面 |

---

## Implementation Notes

- **所有设计基于数据库持久化**
- 当前测试状态可暂用内存存储，正式使用时切换到数据库
- Token 价格参考各模型官方定价，可能需要定期更新
- 费用为估算值，实际费用以 API 提供商账单为准
- LLM Provider 配置为运行时配置，不修改 .env 文件
- **Skill 系统**：支持跨项目共享，安全执行，版本管理
- **双 RAG 架构**：
  - 静态设定 RAG (Lore) 充当"世界宪法"和"风物志"
  - 动态剧情 RAG (Narrative) 记录"现在进行时"
  - 宪法级设定不可违反，用于约束生成内容
  - 设定有优先级，用于解决冲突

---

## Part 8: Setting Agent 持续设定管理

### 8.1 概述

Setting Agent 不是一次性的初始化工具，而是项目的**持续设定管理者**：

```
┌─────────────────────────────────────────────────────────────────┐
│                   Setting Agent 职责演进                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  【Bootstrap 阶段】          【运行时阶段】                       │
│  ─────────────────          ─────────────────                    │
│  • 收集初始设定              • 管理设定 RAG (Lore)               │
│  • 提炼结构化 seed           • 处理设定修改请求                   │
│  • 创建初始世界              • 检测设定冲突                       │
│                              • 与用户协商解决冲突                 │
│                              • 验证新内容是否符合宪法             │
│                              • 维护设定一致性                     │
│                                                                  │
│                   ┌──────────────────────┐                       │
│                   │   Setting Agent      │                       │
│                   │   (常驻服务)          │                       │
│                   │                      │                       │
│                   │  ┌────────────────┐  │                       │
│                   │  │  Lore RAG      │  │                       │
│                   │  │  (静态设定库)   │  │                       │
│                   │  └────────────────┘  │                       │
│                   │                      │                       │
│                   │  ┌────────────────┐  │                       │
│                   │  │ 冲突检测引擎    │  │                       │
│                   │  └────────────────┘  │                       │
│                   │                      │                       │
│                   │  ┌────────────────┐  │                       │
│                   │  │ 协商对话系统    │  │                       │
│                   │  └────────────────┘  │                       │
│                   └──────────────────────┘                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 8.2 数据模型

**扩展文件**: `app/models/setting_agent.py`

```python
"""
Setting Agent 数据模型
持续设定管理者的状态和会话管理
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SettingAgentMode(str, Enum):
    """Setting Agent 运行模式"""
    BOOTSTRAP = "bootstrap"         # 初始化模式（收集初始设定）
    MANAGEMENT = "management"        # 管理模式（持续管理设定）
    CONFLICT_RESOLUTION = "conflict_resolution"  # 冲突解决模式


class SettingChangeType(str, Enum):
    """设定变更类型"""
    ADD = "add"                     # 新增设定
    MODIFY = "modify"               # 修改设定
    DELETE = "delete"               # 删除设定
    MERGE = "merge"                 # 合并设定


class SettingConflict(BaseModel):
    """设定冲突"""
    
    id: str = Field(..., description="冲突 ID")
    project_id: str = Field(..., description="项目 ID")
    
    # 冲突信息
    conflict_type: str = Field(..., description="冲突类型")
    description: str = Field(..., description="冲突描述")
    
    # 涉及的设定
    existing_lore_id: str = Field(..., description="现有设定 ID")
    existing_lore_name: str = Field(..., description="现有设定名称")
    existing_lore_content: str = Field(..., description="现有设定内容")
    
    new_lore_content: str = Field(..., description="新设定内容")
    
    # 冲突级别
    severity: str = Field(default="warning", description="严重程度：critical/warning/info")
    
    # 解决状态
    status: str = Field(default="pending", description="状态：pending/resolved/ignored")
    resolution: Optional[str] = Field(None, description="解决方案")
    resolved_content: Optional[str] = Field(None, description="解决后的内容")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None


class SettingChangeRequest(BaseModel):
    """设定变更请求"""
    
    id: str = Field(..., description="请求 ID")
    project_id: str = Field(..., description="项目 ID")
    
    # 变更信息
    change_type: SettingChangeType = Field(..., description="变更类型")
    category: str = Field(..., description="设定类别")
    name: str = Field(..., description="设定名称")
    description: str = Field(..., description="设定描述")
    content: str = Field(..., description="详细内容")
    
    # 关联信息
    target_lore_id: Optional[str] = Field(None, description="目标设定 ID（修改/删除时）")
    parent_lore_id: Optional[str] = Field(None, description="父设定 ID")
    
    # 用户意图
    user_reason: Optional[str] = Field(None, description="用户变更原因")
    
    # 冲突检测结果
    detected_conflicts: List[SettingConflict] = Field(default_factory=list, description="检测到的冲突")
    
    # 状态
    status: str = Field(default="pending", description="状态：pending/approved/rejected/negotiating")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)


class SettingAgentSession(BaseModel):
    """Setting Agent 会话（持久化到项目）"""
    
    id: str = Field(..., description="会话 ID")
    project_id: str = Field(..., description="项目 ID")
    
    # 会话模式
    mode: SettingAgentMode = Field(default=SettingAgentMode.MANAGEMENT, description="运行模式")
    
    # 对话历史
    messages: List[Dict[str, Any]] = Field(default_factory=list, description="对话历史")
    
    # 当前状态
    current_request: Optional[SettingChangeRequest] = Field(None, description="当前处理的请求")
    pending_conflicts: List[SettingConflict] = Field(default_factory=list, description="待解决的冲突")
    
    # 元数据
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class LoreKnowledgeIndex(BaseModel):
    """设定知识索引（用于快速检索和冲突检测）"""
    
    project_id: str = Field(..., description="项目 ID")
    
    # 关键词索引
    keyword_index: Dict[str, List[str]] = Field(default_factory=dict, description="关键词 -> 设定 ID 列表")
    
    # 实体索引
    entity_index: Dict[str, List[str]] = Field(default_factory=dict, description="实体名 -> 设定 ID 列表")
    
    # 规则索引
    rule_index: Dict[str, List[str]] = Field(default_factory=dict, description="规则类型 -> 设定 ID 列表")
    
    # 宪法级规则缓存
    constitutional_rules: List[str] = Field(default_factory=list, description="宪法级设定 ID 列表")
    
    last_updated: datetime = Field(default_factory=datetime.utcnow)
```

### 8.3 Setting Agent 服务增强

**扩展文件**: `app/services/setting_agent.py`

```python
"""
Setting Agent 服务（增强版）
持续设定管理者 - 负责项目的设定 RAG 管理和冲突解决
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.config import settings
from app.models.setting_agent import (
    SettingAgentMode,
    SettingAgentSession,
    SettingChangeRequest,
    SettingChangeType,
    SettingConflict,
    LoreKnowledgeIndex,
)
from app.services.lore_rag import LoreRAGService
from app.models.lore import LoreCategory, LorePriority

logger = logging.getLogger(__name__)


class SettingAgentService:
    """
    Setting Agent 服务
    
    职责：
    1. Bootstrap 阶段：收集初始设定，创建世界
    2. 运行时阶段：管理设定 RAG，处理修改请求，检测冲突
    """
    
    def __init__(self, lore_rag: LoreRAGService):
        self.lore_rag = lore_rag
        self.llm_provider = settings.llm_provider
        self.llm_api_key = settings.llm_api_key
        self.llm_base_url = settings.llm_base_url
        self.llm_model = settings.llm_model
        
        # 会话存储
        self._sessions: Dict[str, SettingAgentSession] = {}
        
        # 知识索引缓存
        self._knowledge_indexes: Dict[str, LoreKnowledgeIndex] = {}
    
    # ==================== 会话管理 ====================
    
    async def get_or_create_session(
        self,
        project_id: str,
        mode: SettingAgentMode = SettingAgentMode.MANAGEMENT,
    ) -> SettingAgentSession:
        """
        获取或创建项目的 Setting Agent 会话
        
        Args:
            project_id: 项目 ID
            mode: 运行模式
        
        Returns:
            SettingAgentSession: 会话
        """
        # 查找现有会话
        for session in self._sessions.values():
            if session.project_id == project_id:
                session.mode = mode
                session.updated_at = datetime.utcnow()
                return session
        
        # 创建新会话
        import uuid
        session_id = f"setting_agent_{uuid.uuid4().hex[:12]}"
        
        session = SettingAgentSession(
            id=session_id,
            project_id=project_id,
            mode=mode,
        )
        
        self._sessions[session_id] = session
        
        # 加载知识索引
        await self._load_knowledge_index(project_id)
        
        return session
    
    async def _load_knowledge_index(self, project_id: str):
        """加载项目的设定知识索引"""
        # 获取所有设定
        all_lore = await self.lore_rag.search_lore(
            project_id=project_id,
            query="",  # 空查询获取所有
            limit=1000,
        )
        
        # 构建索引
        index = LoreKnowledgeIndex(project_id=project_id)
        
        for lore in all_lore:
            payload = lore.get("payload", {})
            lore_id = lore.get("id")
            
            # 关键词索引
            for keyword in payload.get("keywords", []):
                if keyword not in index.keyword_index:
                    index.keyword_index[keyword] = []
                index.keyword_index[keyword].append(lore_id)
            
            # 实体索引
            name = payload.get("name", "")
            if name:
                if name not in index.entity_index:
                    index.entity_index[name] = []
                index.entity_index[name].append(lore_id)
            
            # 宪法级规则
            if payload.get("priority") == LorePriority.CONSTITUTIONAL.value:
                index.constitutional_rules.append(lore_id)
        
        self._knowledge_indexes[project_id] = index
    
    # ==================== 设定变更处理 ====================
    
    async def process_setting_change(
        self,
        project_id: str,
        change_type: SettingChangeType,
        category: str,
        name: str,
        description: str,
        content: str,
        target_lore_id: Optional[str] = None,
        user_reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        处理设定变更请求
        
        Args:
            project_id: 项目 ID
            change_type: 变更类型
            category: 设定类别
            name: 设定名称
            description: 描述
            content: 详细内容
            target_lore_id: 目标设定 ID
            user_reason: 用户变更原因
        
        Returns:
            Dict: 处理结果
        """
        # 获取会话
        session = await self.get_or_create_session(project_id)
        
        # 创建变更请求
        import uuid
        request = SettingChangeRequest(
            id=f"change_{uuid.uuid4().hex[:12]}",
            project_id=project_id,
            change_type=change_type,
            category=category,
            name=name,
            description=description,
            content=content,
            target_lore_id=target_lore_id,
            user_reason=user_reason,
        )
        
        # 检测冲突
        conflicts = await self._detect_conflicts(project_id, request)
        request.detected_conflicts = conflicts
        
        # 根据冲突情况决定处理方式
        if not conflicts:
            # 无冲突，直接执行
            result = await self._execute_change(request)
            return {
                "status": "approved",
                "message": "设定变更已执行",
                "result": result,
            }
        
        # 有冲突，进入协商模式
        session.mode = SettingAgentMode.CONFLICT_RESOLUTION
        session.current_request = request
        session.pending_conflicts = conflicts
        
        # 生成冲突说明
        conflict_description = await self._generate_conflict_description(conflicts)
        
        return {
            "status": "conflict_detected",
            "message": "检测到设定冲突，需要协商解决",
            "conflicts": [c.model_dump() for c in conflicts],
            "conflict_description": conflict_description,
            "suggestions": await self._generate_resolution_suggestions(conflicts, request),
        }
    
    async def _detect_conflicts(
        self,
        project_id: str,
        request: SettingChangeRequest,
    ) -> List[SettingConflict]:
        """
        检测设定冲突
        
        Args:
            project_id: 项目 ID
            request: 变更请求
        
        Returns:
            List: 冲突列表
        """
        conflicts = []
        index = self._knowledge_indexes.get(project_id)
        
        if not index:
            return conflicts
        
        # 1. 检查名称冲突
        if request.name in index.entity_index:
            for existing_id in index.entity_index[request.name]:
                # 获取现有设定
                existing = await self._get_lore_by_id(existing_id)
                if existing and existing_id != request.target_lore_id:
                    conflicts.append(SettingConflict(
                        id=f"conflict_{request.id}_name",
                        project_id=project_id,
                        conflict_type="name_collision",
                        description=f"已存在名为「{request.name}」的设定",
                        existing_lore_id=existing_id,
                        existing_lore_name=request.name,
                        existing_lore_content=existing.get("description", ""),
                        new_lore_content=request.content,
                        severity="warning",
                    ))
        
        # 2. 检查关键词冲突
        for keyword in request.content.split()[:20]:  # 提取关键词
            if keyword in index.keyword_index:
                for existing_id in index.keyword_index[keyword]:
                    existing = await self._get_lore_by_id(existing_id)
                    if existing:
                        # 使用 LLM 判断是否真的冲突
                        is_conflict = await self._check_semantic_conflict(
                            existing_content=existing.get("content", ""),
                            new_content=request.content,
                        )
                        if is_conflict:
                            conflicts.append(SettingConflict(
                                id=f"conflict_{request.id}_{keyword}",
                                project_id=project_id,
                                conflict_type="semantic_conflict",
                                description=f"新设定与现有设定「{existing.get('name')}」在语义上存在冲突",
                                existing_lore_id=existing_id,
                                existing_lore_name=existing.get("name", ""),
                                existing_lore_content=existing.get("content", ""),
                                new_lore_content=request.content,
                                severity="warning",
                            ))
        
        # 3. 检查宪法级规则冲突
        for const_id in index.constitutional_rules:
            const_lore = await self._get_lore_by_id(const_id)
            if const_lore:
                violation = await self._check_constitutional_violation(
                    constitutional=const_lore,
                    new_content=request.content,
                )
                if violation:
                    conflicts.append(SettingConflict(
                        id=f"conflict_{request.id}_constitutional",
                        project_id=project_id,
                        conflict_type="constitutional_violation",
                        description=f"新设定违反宪法级规则「{const_lore.get('name')}」",
                        existing_lore_id=const_id,
                        existing_lore_name=const_lore.get("name", ""),
                        existing_lore_content=const_lore.get("content", ""),
                        new_lore_content=request.content,
                        severity="critical",
                    ))
        
        return conflicts
    
    async def _check_semantic_conflict(
        self,
        existing_content: str,
        new_content: str,
    ) -> bool:
        """使用 LLM 检查语义冲突"""
        prompt = f"""请判断以下两段设定是否存在冲突：

【现有设定】
{existing_content}

【新设定】
{new_content}

请回答：是/否。如果存在矛盾、对立或不兼容的内容，请回答"是"；否则回答"否"。
"""
        
        response = await self._call_llm_simple(prompt)
        return "是" in response
    
    async def _check_constitutional_violation(
        self,
        constitutional: Dict[str, Any],
        new_content: str,
    ) -> bool:
        """检查是否违反宪法级规则"""
        const_content = constitutional.get("content", "")
        const_constraints = constitutional.get("constraints", [])
        
        prompt = f"""请判断新设定是否违反以下宪法级规则：

【宪法级规则】
{const_content}

【约束条件】
{chr(10).join(const_constraints) if const_constraints else '无'}

【新设定】
{new_content}

请回答：违反/不违反。如果新设定与宪法级规则存在矛盾或违反约束条件，请回答"违反"。
"""
        
        response = await self._call_llm_simple(prompt)
        return "违反" in response
    
    async def _generate_conflict_description(
        self,
        conflicts: List[SettingConflict],
    ) -> str:
        """生成冲突说明文本"""
        descriptions = []
        for c in conflicts:
            severity_icon = "🚨" if c.severity == "critical" else "⚠️"
            descriptions.append(
                f"{severity_icon} **{c.conflict_type}**: {c.description}\n"
                f"   - 现有设定: {c.existing_lore_name}\n"
                f"   - 冲突级别: {c.severity}"
            )
        return "\n\n".join(descriptions)
    
    async def _generate_resolution_suggestions(
        self,
        conflicts: List[SettingConflict],
        request: SettingChangeRequest,
    ) -> List[Dict[str, Any]]:
        """生成解决建议"""
        suggestions = []
        
        for conflict in conflicts:
            if conflict.severity == "critical":
                # 宪法级冲突，建议修改新设定
                suggestions.append({
                    "type": "modify_new",
                    "description": f"建议修改您的设定以符合「{conflict.existing_lore_name}」规则",
                    "action": "edit",
                })
            else:
                # 普通冲突，提供多个选项
                suggestions.append({
                    "type": "override",
                    "description": f"覆盖现有设定「{conflict.existing_lore_name}」",
                    "action": "override",
                    "target_id": conflict.existing_lore_id,
                })
                suggestions.append({
                    "type": "modify_new",
                    "description": "修改您的新设定以避免冲突",
                    "action": "edit",
                })
                suggestions.append({
                    "type": "keep_both",
                    "description": "保留两者（可能需要后续说明）",
                    "action": "keep_both",
                })
        
        return suggestions
    
    # ==================== 协商对话 ====================
    
    async def negotiate(
        self,
        project_id: str,
        user_message: str,
    ) -> Dict[str, Any]:
        """
        与用户协商解决冲突
        
        Args:
            project_id: 项目 ID
            user_message: 用户消息
        
        Returns:
            Dict: 协商结果
        """
        session = await self.get_or_create_session(project_id)
        
        if not session.current_request:
            return {
                "status": "error",
                "message": "没有待处理的变更请求",
            }
        
        # 添加用户消息到历史
        session.messages.append({
            "role": "user",
            "content": user_message,
            "timestamp": datetime.utcnow().isoformat(),
        })
        
        # 分析用户意图
        intent = await self._analyze_user_intent(user_message)
        
        if intent == "cancel":
            # 用户取消
            session.current_request = None
            session.pending_conflicts = []
            session.mode = SettingAgentMode.MANAGEMENT
            
            return {
                "status": "cancelled",
                "message": "设定变更已取消",
            }
        
        elif intent == "override":
            # 用户选择覆盖
            # 执行变更，标记被覆盖的设定
            result = await self._execute_with_override(session)
            
            session.current_request = None
            session.pending_conflicts = []
            session.mode = SettingAgentMode.MANAGEMENT
            
            return {
                "status": "resolved",
                "message": "设定已更新（覆盖了冲突设定）",
                "result": result,
            }
        
        elif intent == "edit":
            # 用户想要修改
            return {
                "status": "awaiting_edit",
                "message": "请提供修改后的设定内容",
            }
        
        else:
            # 继续协商
            response = await self._generate_negotiation_response(session, user_message)
            
            session.messages.append({
                "role": "assistant",
                "content": response,
                "timestamp": datetime.utcnow().isoformat(),
            })
            
            return {
                "status": "negotiating",
                "message": response,
            }
    
    async def _analyze_user_intent(self, message: str) -> str:
        """分析用户意图"""
        message_lower = message.lower()
        
        if any(w in message_lower for w in ["取消", "不要", "算了", "cancel"]):
            return "cancel"
        elif any(w in message_lower for w in ["覆盖", "替换", "override"]):
            return "override"
        elif any(w in message_lower for w in ["修改", "改", "edit"]):
            return "edit"
        else:
            return "continue"
    
    async def _generate_negotiation_response(
        self,
        session: SettingAgentSession,
        user_message: str,
    ) -> str:
        """生成协商回复"""
        context = f"""当前处理设定变更请求：
- 类型: {session.current_request.change_type.value}
- 名称: {session.current_request.name}
- 内容: {session.current_request.content[:500]}

检测到的冲突：
{await self._generate_conflict_description(session.pending_conflicts)}

用户消息: {user_message}

请作为设定专家，帮助用户解决这些冲突。提供清晰的建议和选项。
"""
        
        return await self._call_llm_simple(context)
    
    # ==================== 设定执行 ====================
    
    async def _execute_change(
        self,
        request: SettingChangeRequest,
    ) -> Dict[str, Any]:
        """执行设定变更"""
        if request.change_type == SettingChangeType.ADD:
            # 添加新设定
            lore = await self.lore_rag.add_lore(
                project_id=request.project_id,
                name=request.name,
                category=LoreCategory(request.category),
                content=request.content,
                description=request.description,
            )
            return {"action": "added", "lore_id": lore.id}
        
        elif request.change_type == SettingChangeType.MODIFY:
            # 修改现有设定
            # TODO: 实现修改逻辑
            return {"action": "modified", "lore_id": request.target_lore_id}
        
        elif request.change_type == SettingChangeType.DELETE:
            # 删除设定
            # TODO: 实现删除逻辑
            return {"action": "deleted", "lore_id": request.target_lore_id}
        
        return {"action": "unknown"}
    
    async def _execute_with_override(
        self,
        session: SettingAgentSession,
    ) -> Dict[str, Any]:
        """执行变更（覆盖冲突设定）"""
        request = session.current_request
        
        # 标记被覆盖的设定
        for conflict in session.pending_conflicts:
            # 更新被覆盖设定的状态
            # TODO: 实现
            pass
        
        # 执行变更
        return await self._execute_change(request)
    
    # ==================== 辅助方法 ====================
    
    async def _get_lore_by_id(self, lore_id: str) -> Optional[Dict[str, Any]]:
        """获取设定详情"""
        # 从 PostgreSQL 或缓存获取
        # TODO: 实现
        return None
    
    async def _call_llm_simple(self, prompt: str) -> str:
        """简单 LLM 调用"""
        # TODO: 实现
        return ""
    
    # ==================== 查询接口 ====================
    
    async def get_project_lore_summary(
        self,
        project_id: str,
    ) -> Dict[str, Any]:
        """
        获取项目设定摘要
        
        Args:
            project_id: 项目 ID
        
        Returns:
            Dict: 设定摘要
        """
        index = self._knowledge_indexes.get(project_id)
        
        if not index:
            await self._load_knowledge_index(project_id)
            index = self._knowledge_indexes.get(project_id)
        
        return {
            "total_lore_count": sum(len(v) for v in index.entity_index.values()) if index else 0,
            "keyword_count": len(index.keyword_index) if index else 0,
            "constitutional_rules_count": len(index.constitutional_rules) if index else 0,
            "categories": list(set(k for k in index.entity_index.keys())) if index else [],
        }
    
    async def chat(
        self,
        project_id: str,
        message: str,
    ) -> Dict[str, Any]:
        """
        与 Setting Agent 聊天
        
        可以用于：
        - 查询现有设定
        - 讨论设定想法
        - 发起变更请求
        
        Args:
            project_id: 项目 ID
            message: 用户消息
        
        Returns:
            Dict: 响应
        """
        session = await self.get_or_create_session(project_id)
        
        # 添加用户消息
        session.messages.append({
            "role": "user",
            "content": message,
            "timestamp": datetime.utcnow().isoformat(),
        })
        
        # 构建上下文
        lore_context = await self.lore_rag.get_lore_context_for_generation(
            project_id=project_id,
            scene_description=message,
        )
        
        # 生成响应
        system_prompt = self._build_management_prompt()
        response = await self._call_llm_with_context(
            system_prompt=system_prompt,
            user_message=message,
            context=f"当前项目设定：\n{lore_context}",
        )
        
        # 添加助手回复
        session.messages.append({
            "role": "assistant",
            "content": response,
            "timestamp": datetime.utcnow().isoformat(),
        })
        
        return {
            "status": "success",
            "message": response,
            "mode": session.mode.value,
        }
    
    def _build_management_prompt(self) -> str:
        """构建管理模式提示词"""
        return """你是项目的设定管理者（Setting Agent）。你的职责是：

1. 管理项目的静态设定 RAG（Lore）
2. 帮助用户查询和理解现有设定
3. 处理用户的设定修改请求
4. 检测设定冲突并提醒用户
5. 与用户协商解决冲突

请遵循以下原则：
- 深入了解项目的所有设定，特别是宪法级规则
- 当用户想要修改设定时，检查是否与现有设定冲突
- 如果检测到冲突，明确告知用户并提供解决方案
- 宪法级规则不可违反，必须提醒用户
- 保持专业、友好的态度

你可以执行的操作：
- 查询设定：搜索并展示相关设定
- 新增设定：创建新的设定条目（需检查冲突）
- 修改设定：更新现有设定（需确认影响）
- 删除设定：移除不再需要的设定（需确认）
"""
```

### 8.4 API 端点

**新文件**: `app/api/routes/setting_agent.py`

```python
"""
Setting Agent API 路由
持续设定管理接口
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter()


class ChatRequest(BaseModel):
    """聊天请求"""
    project_id: str
    message: str


class SettingChangeRequest(BaseModel):
    """设定变更请求"""
    project_id: str
    change_type: str  # add/modify/delete
    category: str
    name: str
    description: str = ""
    content: str
    target_lore_id: Optional[str] = None
    reason: Optional[str] = None


class NegotiateRequest(BaseModel):
    """协商请求"""
    project_id: str
    message: str


@router.post("/chat", response_model=Dict[str, Any])
async def chat_with_setting_agent(request: ChatRequest):
    """
    与 Setting Agent 聊天
    
    可以用于查询设定、讨论想法、发起变更等
    """
    from app.services.setting_agent import get_setting_agent_service
    
    agent = get_setting_agent_service()
    
    result = await agent.chat(
        project_id=request.project_id,
        message=request.message,
    )
    
    return result


@router.post("/change", response_model=Dict[str, Any])
async def request_setting_change(request: SettingChangeRequest):
    """
    请求设定变更
    
    Setting Agent 会检测冲突并返回结果
    """
    from app.services.setting_agent import get_setting_agent_service
    from app.models.setting_agent import SettingChangeType
    
    agent = get_setting_agent_service()
    
    result = await agent.process_setting_change(
        project_id=request.project_id,
        change_type=SettingChangeType(request.change_type),
        category=request.category,
        name=request.name,
        description=request.description,
        content=request.content,
        target_lore_id=request.target_lore_id,
        user_reason=request.reason,
    )
    
    return result


@router.post("/negotiate", response_model=Dict[str, Any])
async def negotiate_conflict(request: NegotiateRequest):
    """
    协商解决设定冲突
    
    当检测到冲突时，通过此接口与 Agent 协商
    """
    from app.services.setting_agent import get_setting_agent_service
    
    agent = get_setting_agent_service()
    
    result = await agent.negotiate(
        project_id=request.project_id,
        user_message=request.message,
    )
    
    return result


@router.get("/{project_id}/summary", response_model=Dict[str, Any])
async def get_lore_summary(project_id: str):
    """
    获取项目设定摘要
    """
    from app.services.setting_agent import get_setting_agent_service
    
    agent = get_setting_agent_service()
    
    result = await agent.get_project_lore_summary(project_id)
    
    return result


@router.get("/{project_id}/history", response_model=List[Dict[str, Any]])
async def get_chat_history(
    project_id: str,
    limit: int = Query(default=50, le=200),
):
    """
    获取与 Setting Agent 的对话历史
    """
    from app.services.setting_agent import get_setting_agent_service
    
    agent = get_setting_agent_service()
    session = await agent.get_or_create_session(project_id)
    
    return session.messages[-limit:]
```

### 8.5 前端集成

**新组件**: `frontend/src/components/setting/SettingAgentChat.tsx`

```tsx
import { useState, useRef, useEffect } from 'react'
import { Card, Button, Input } from '@/components/ui'
import { chatWithSettingAgent, requestSettingChange } from '@/api/settingAgent'
import { Send, Plus, AlertTriangle, CheckCircle } from 'lucide-react'

export function SettingAgentChat({ projectId }: { projectId: string }) {
  const [messages, setMessages] = useState<Array<{role: string; content: string}>>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [pendingConflict, setPendingConflict] = useState<any>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  
  const handleSend = async () => {
    if (!input.trim() || loading) return
    
    const userMessage = input.trim()
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: userMessage }])
    setLoading(true)
    
    try {
      const result = await chatWithSettingAgent(projectId, userMessage)
      
      setMessages(prev => [...prev, { role: 'assistant', content: result.message }])
      
      if (result.status === 'conflict_detected') {
        setPendingConflict(result)
      }
    } catch (error) {
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: '抱歉，处理您的请求时出现错误。' 
      }])
    } finally {
      setLoading(false)
    }
  }
  
  const handleResolveConflict = async (action: 'override' | 'edit' | 'cancel') => {
    if (!pendingConflict) return
    
    // 处理冲突解决
    // ...
  }
  
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])
  
  return (
    <Card className="flex flex-col h-[600px]">
      {/* 标题 */}
      <div className="p-4 border-b">
        <h3 className="font-semibold text-gray-800">🎭 设定管理者</h3>
        <p className="text-xs text-gray-500">管理项目的世界设定，检测冲突</p>
      </div>
      
      {/* 消息列表 */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[80%] p-3 rounded-lg ${
              msg.role === 'user' 
                ? 'bg-blue-500 text-white' 
                : 'bg-gray-100 text-gray-800'
            }`}>
              {msg.content}
            </div>
          </div>
        ))}
        
        {/* 冲突提示 */}
        {pendingConflict && (
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
            <div className="flex items-center gap-2 text-yellow-700 font-medium mb-2">
              <AlertTriangle size={18} />
              检测到设定冲突
            </div>
            <p className="text-sm text-yellow-600 mb-3">
              {pendingConflict.conflict_description}
            </p>
            <div className="flex gap-2">
              <Button 
                size="sm" 
                variant="outline"
                onClick={() => handleResolveConflict('override')}
              >
                覆盖现有设定
              </Button>
              <Button 
                size="sm" 
                variant="outline"
                onClick={() => handleResolveConflict('edit')}
              >
                修改我的设定
              </Button>
              <Button 
                size="sm" 
                variant="outline"
                onClick={() => handleResolveConflict('cancel')}
              >
                取消
              </Button>
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>
      
      {/* 输入区 */}
      <div className="p-4 border-t">
        <div className="flex gap-2">
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="询问设定、添加新设定、修改现有设定..."
            onKeyPress={(e) => e.key === 'Enter' && handleSend()}
            className="flex-1"
          />
          <Button onClick={handleSend} disabled={loading}>
            <Send size={18} />
          </Button>
        </div>
      </div>
    </Card>
  )
}
```

---

## Files to Modify (Part 8)

| 文件 | 修改内容 |
|------|----------|
| `app/models/setting_agent.py` | **新建** - Setting Agent 数据模型 |
| `app/services/setting_agent.py` | **重构** - 持续设定管理服务 |
| `app/api/routes/setting_agent.py` | **新建** - Setting Agent API |
| `frontend/src/components/setting/SettingAgentChat.tsx` | **新建** - 聊天组件 |
| `frontend/src/api/settingAgent.ts` | **新建** - API 函数 |
| `frontend/src/pages/Lore.tsx` | 集成 Setting Agent 聊天 |

---

## 架构对比：改进前 vs 改进后

### 改进前

```
┌─────────────────────────────────┐
│         单一 RAG 架构           │
├─────────────────────────────────┤
│                                 │
│  Qdrant: godview_memory         │
│  ├─ voice_sample (角色声音)     │
│  ├─ memory (角色记忆)           │
│  └─ (剧情事件混杂)              │
│                                 │
│  NebulaGraph: godview_space     │
│  ├─ character, world, region    │
│  ├─ hook, event, memory         │
│  └─ (静态设定和动态剧情混杂)    │
│                                 │
│  问题：                         │
│  ✗ 设定和剧情混在一起           │
│  ✗ 无法区分优先级               │
│  ✗ 难以约束生成内容             │
│  ✗ 设定冲突无法检测             │
│                                 │
└─────────────────────────────────┘
```

### 改进后

```
┌─────────────────────────────────────────────────────────────────┐
│                        双 RAG 架构                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────┐    ┌─────────────────────────────┐ │
│  │   静态设定 RAG (Lore)   │    │   动态剧情 RAG (Narrative)  │ │
│  │   "世界宪法 + 风物志"    │    │      "现在进行时"           │ │
│  ├─────────────────────────┤    ├─────────────────────────────┤ │
│  │ Qdrant: godview_lore    │    │ Qdrant: godview_narrative   │ │
│  │ ├─ world_rule (宪法级)  │    │ ├─ event (事件)             │ │
│  │ ├─ geography (地理)     │    │ ├─ state_change (状态变化)  │ │
│  │ ├─ faction (势力)       │    │ ├─ dialogue (对话)          │ │
│  │ ├─ race (种族)          │    │ └─ discovery (发现)         │ │
│  │ └─ ...                  │    │                              │ │
│  │                          │    │ NebulaGraph: narrative_*    │ │
│  │ NebulaGraph: lore_*      │    │ ├─ causes (因果关系)        │ │
│  │ ├─ parent_of (层级)      │    │ ├─ participates_in (参与)   │ │
│  │ ├─ constrains (约束)     │    │ └─ references_lore (引用)   │ │
│  └─────────────────────────┘    └─────────────────────────────┘ │
│                                                                  │
│  优势：                                                          │
│  ✓ 静态设定和动态剧情分离                                        │
│  ✓ 宪法级设定约束生成                                            │
│  ✓ 优先级解决冲突                                                │
│  ✓ 设定引用追踪                                                  │
│  ✓ 剧情连贯性保障                                                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```
