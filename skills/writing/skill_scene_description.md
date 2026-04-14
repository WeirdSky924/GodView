---
id: skill_scene_description
name: 场景描写
description: 生成生动、有画面感的场景描写
category: writing
skill_type: prompt
tags:
  - 场景
  - 描写
  - 画面感
use_cases:
  - 场景环境描写
  - 氛围渲染
  - 背景构建
applicable_agent_types:
  - writer
  - scene_coordinator
load_mode: on_demand
priority: 60
is_system: true
is_enabled: true
parameters:
  - name: scene_type
    type: string
    description: 场景类型
  - name: location
    type: string
    description: 场景地点
  - name: time_of_day
    type: string
    description: 时间
  - name: atmosphere
    type: string
    description: 氛围基调
  - name: scene_purpose
    type: string
    description: 场景作用
---

# 场景描写技能

## 任务：场景描写

请根据以下信息生成场景描写：

### 场景信息

- 场景类型：{{scene_type}}
- 场景地点：{{location}}
- 时间：{{time_of_day}}
- 氛围基调：{{atmosphere}}

### 场景作用

{{scene_purpose}}

### 描写要求

#### 1. 感官描写

- **视觉**：光线、色彩、形态
- **听觉**：声音、动静、节奏
- **嗅觉**：气味、气息
- **触觉**：温度、质感
- **味觉**（如适用）

#### 2. 氛围营造

- 环境要与情绪呼应
- 用细节传递氛围
- 适度留白，不要过度描写

#### 3. 功能导向

- 描写要服务于情节
- 突出与剧情相关的细节
- 为后续发展做铺垫

#### 4. 篇幅控制

- 主要场景：200-400字
- 过渡场景：50-100字
- 战斗场景：精简有力

### 输出

直接输出场景描写内容，不要包含额外说明。
