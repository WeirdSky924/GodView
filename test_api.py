#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GodView API 完整测试脚本
覆盖所有主要 API 接口，包含 LLM 调用测试
"""

import httpx
import json
import sys

BASE_URL = "http://127.0.0.1:8000"

# LLM 相关测试的超时时间（秒）
LLM_TIMEOUT = 120.0


def test_api(method: str, path: str, data: dict = None, params: dict = None, description: str = "", timeout: float = 60.0):
    """测试 API 接口"""
    url = f"{BASE_URL}{path}"
    try:
        with httpx.Client(trust_env=False, timeout=timeout) as client:
            if method == "GET":
                response = client.get(url, params=params)
            elif method == "POST":
                response = client.post(url, json=data, params=params)
            elif method == "PUT":
                response = client.put(url, json=data, params=params)
            elif method == "DELETE":
                response = client.delete(url)
            else:
                return None, "Unknown method"

            status = "[OK]" if 200 <= response.status_code < 300 else "[FAIL]"
            result = f"{status} [{response.status_code}] {method} {path}"
            if description:
                result = f"{description}: {result}"
            print(result)

            try:
                return response.status_code, response.json()
            except:
                return response.status_code, response.text[:200]
    except Exception as e:
        print(f"[ERR] {method} {path}: {str(e)[:100]}")
        return None, str(e)


def test_llm_api(method: str, path: str, data: dict = None, params: dict = None, description: str = ""):
    """测试需要 LLM 调用的 API 接口（使用更长超时）"""
    return test_api(method, path, data, params, description, timeout=LLM_TIMEOUT)


def main():
    print("=" * 60)
    print("GodView API 完整测试（含 LLM 调用）")
    print("=" * 60)

    # ==================== 配置管理 ====================
    print("\n【配置管理】")
    test_api("GET", "/api/config/system", description="获取系统配置")
    test_api("GET", "/api/config/database/status", description="获取数据库状态")
    test_api("GET", "/api/config/embedding/providers", description="获取 Embedding 提供商列表")
    test_api("GET", "/api/config/embedding", description="获取当前 Embedding 配置")
    test_api("GET", "/api/config/llm/providers", description="获取 LLM 提供商列表")
    test_api("GET", "/api/config/llm", description="获取当前 LLM 配置")

    # ==================== LLM 配置测试 ====================
    print("\n【LLM 配置测试】")
    test_llm_api("POST", "/api/config/llm/test", description="测试 LLM 连接")

    # ==================== 项目管理 ====================
    print("\n【项目管理】")

    status, result = test_api("POST", "/api/projects",
        {"name": "API测试项目", "description": "自动化测试"},
        "创建项目")
    project_id = result.get("id") if status == 200 else None

    if not project_id:
        print("项目创建失败，终止测试")
        return

    test_api("GET", "/api/projects", description="获取项目列表")
    test_api("GET", f"/api/projects/{project_id}", description="获取项目详情")
    test_api("GET", f"/api/projects/{project_id}/summary", description="获取项目摘要")

    # ==================== 世界管理 ====================
    print("\n【世界管理】")

    status, result = test_api("POST", "/api/worlds",
        {"project_id": project_id, "name": "测试世界", "world_type": "fantasy", "description": "一个奇幻世界"},
        "创建世界")
    world_id = result.get("id") if status == 200 else None

    test_api("GET", f"/api/worlds?project_id={project_id}", description="获取世界列表")

    # ==================== 角色管理 ====================
    print("\n【角色管理】")

    # 注意：personality_traits 需要是 List[PersonalityTrait] 格式
    status, result = test_api("POST", "/api/characters",
        {"project_id": project_id, "name": "艾莉丝", "role": "protagonist",
         "description": "一位勇敢的女战士",
         "personality_traits": [{"name": "勇敢", "value": 0.9}, {"name": "善良", "value": 0.8}]},
        "创建角色")
    character_id = result.get("id") if status == 200 else None

    test_api("GET", f"/api/characters?project_id={project_id}", description="获取角色列表")

    if character_id:
        test_api("GET", f"/api/characters/{character_id}", description="获取角色详情")

    # ==================== 章节管理 ====================
    print("\n【章节管理】")

    status, result = test_api("POST", "/api/plots/chapters",
        {"title": "第一章：启程", "content": "艾莉丝站在城门前，望着远方的山脉。今天，她将开始她的冒险之旅...", "world_id": world_id},
        "创建章节")
    chapter_id = result.get("id") if status == 200 else None

    if chapter_id:
        test_api("GET", f"/api/plots/chapters/{chapter_id}", description="获取章节详情")

        # 章节评估 - 需要 LLM
        print("\n  -- 章节 LLM 功能测试 --")
        test_llm_api("POST", f"/api/plots/chapters/{chapter_id}/evaluate",
            description="评估章节（LLM）")
        test_llm_api("POST", f"/api/plots/chapters/{chapter_id}/reader-simulate",
            description="模拟读者反馈（LLM）")

    # ==================== 设定管理 ====================
    print("\n【设定管理】")

    status, result = test_api("POST", "/api/lore",
        {"project_id": project_id, "title": "魔法体系", "category": "world_rule",
         "content": "本世界存在五种元素魔法：火、水、风、土、光。每种魔法需要对应的元素亲和力才能学习。",
         "priority": "core", "keywords": ["魔法", "元素"]},
        "创建设定")
    lore_id = result.get("id") if status == 200 else None

    test_api("GET", f"/api/lore?project_id={project_id}", description="获取设定列表")

    # 设定验证 - 需要 LLM
    print("\n  -- 设定 LLM 功能测试 --")
    test_llm_api("POST", "/api/lore/validate",
        params={"project_id": project_id, "content": "主角使用第六元素暗影魔法攻击敌人"},
        description="验证设定冲突（LLM）")

    # ==================== 伏笔管理 ====================
    print("\n【伏笔管理】")

    # 注意：priority 范围是 1-5
    status, result = test_api("POST", "/api/plots/hooks",
        {"project_id": project_id, "title": "神秘项链", "hook_type": "mystery",
         "description": "艾莉丝身上佩戴着一条她不记得来历的项链", "priority": 4},
        "创建伏笔")
    hook_id = result.get("id") if status == 200 else None

    test_api("GET", f"/api/plots/hooks?project_id={project_id}", description="获取伏笔列表")

    # ==================== Prompt 模板 ====================
    print("\n【Prompt模板】")

    status, result = test_api("POST", "/api/prompts",
        {"name": "角色扮演", "category": "role",
         "content": "你现在是{{character_name}}，一个{{character_description}}。请用这个角色的语气和风格回答。"},
        "创建Prompt模板")
    prompt_id = result.get("id") if status == 200 else None

    test_api("GET", f"/api/prompts?project_id={project_id}", description="获取Prompt模板列表")

    # Prompt 渲染测试 - 需要 LLM（渲染本身不需要，但可以验证模板）
    if prompt_id:
        test_api("POST", f"/api/prompts/{prompt_id}/render",
            {"character_name": "艾莉丝", "character_description": "勇敢的女战士"},
            description="渲染Prompt模板")

    # ==================== 写作规则 ====================
    print("\n【写作规则】")

    # 注意：severity 枚举值为 required/strong/recommended/optional/info
    test_api("POST", "/api/writing-rules",
        {"name": "禁止现代用语", "category": "style",
         "content": "禁止使用手机、电脑、汽车等现代科技词汇", "severity": "required"},
        "创建写作规则")

    # 写作配置预览 - 需要 LLM
    print("\n  -- 写作规则 LLM 功能测试 --")
    test_llm_api("POST", f"/api/projects/{project_id}/writing-config/preview",
        {"genre": "奇幻", "tone": "史诗"},
        description="预览写作Prompt（LLM）")

    # ==================== Agent 模板 ====================
    print("\n【Agent模板】")

    test_api("GET", "/api/agent-templates", description="获取Agent模板列表")

    # 按类型获取模板 - 仅在存在模板时测试
    status, result = test_api("GET", "/api/agent-templates")
    if status == 200 and result and isinstance(result, list) and len(result) > 0:
        # 获取第一个模板的类型来测试
        first_template = result[0]
        agent_type = first_template.get("agent_type", "character")
        test_api("GET", f"/api/agent-templates/by-type/{agent_type}", description=f"按类型获取{agent_type}模板")

        # Agent 模板预览 - 需要 LLM
        template_id = first_template.get("id")
        if template_id:
            test_llm_api("POST", f"/api/agent-templates/{template_id}/preview",
                {"world_name": "艾尔德兰大陆", "chapter_number": 1},
                description="预览Agent模板渲染（LLM）")
    else:
        print("  -- 无系统模板，跳过by-type和preview测试 --")

    # ==================== Agent 配置 ====================
    print("\n【Agent配置】")

    test_api("GET", f"/api/projects/{project_id}/agents", description="获取项目Agent配置列表")
    test_api("GET", f"/api/projects/{project_id}/agents/director", description="获取Director配置")

    # Agent 配置预览 - 需要 LLM
    test_llm_api("POST", f"/api/projects/{project_id}/agents/director/preview",
        {"scene": "战斗场景", "characters": ["艾莉丝"]},
        description="预览Director Prompt（LLM）")

    # ==================== Setting Agent (LLM) ====================
    print("\n【Setting Agent - LLM 功能】")

    # 与设定代理聊天 - 需要 LLM
    test_llm_api("POST", "/api/setting-agent/chat",
        {"project_id": project_id, "message": "我想添加一个关于龙族的设定，它们是这个世界的古老种族"},
        description="与Setting Agent聊天（LLM）")

    # 获取设定摘要
    test_api("GET", f"/api/setting-agent/{project_id}/summary", description="获取项目设定摘要")
    test_api("GET", f"/api/setting-agent/{project_id}/history", description="获取对话历史")

    # 设定变更请求 - 需要 LLM
    test_llm_api("POST", "/api/setting-agent/change",
        {"project_id": project_id, "change_type": "add",
         "lore_data": {"title": "龙族", "category": "race",
                       "content": "龙族是艾尔德兰大陆最古老的种族，拥有强大的魔法能力"}},
        description="请求设定变更（LLM）")

    # ==================== Bootstrap 流程 (LLM) ====================
    print("\n【Bootstrap 流程 - LLM 功能】")

    # 启动 Bootstrap - 需要 LLM
    status, result = test_llm_api("POST", "/api/bootstrap/start",
        {"project_id": project_id, "initial_message": "我想创作一部奇幻冒险小说"},
        description="启动Bootstrap流程（LLM）")

    session_id = result.get("session", {}).get("id") if status == 200 else None

    if session_id:
        test_api("GET", f"/api/bootstrap/{session_id}", description="获取Bootstrap会话详情")
        test_api("GET", f"/api/bootstrap/{session_id}/status", description="获取Bootstrap状态")

        # 发送消息到 SettingAgent - 需要 LLM
        test_llm_api("POST", "/api/bootstrap/message",
            {"session_id": session_id, "message": "故事发生在一片充满魔法的大陆，主角是一位年轻的女战士"},
            description="发送消息到SettingAgent（LLM）")

        # 结束设定阶段 - 需要 LLM
        test_llm_api("POST", f"/api/bootstrap/{session_id}/finalize-setting",
            description="结束设定阶段提取Seed（LLM）")

    # ==================== 时间系统 ====================
    print("\n【时间系统】")

    if world_id:
        # 注意：time_mode 枚举值为 linear/nonlinear/frozen
        test_api("POST", f"/api/time/systems/{world_id}",
            {"world_id": world_id, "time_mode": "linear", "time_scale": 1.0},
            description="创建时间系统")
        test_api("GET", f"/api/time/systems/{world_id}", description="获取时间系统状态")
        test_api("POST", "/api/time/control",
            {"world_id": world_id, "action": "advance", "advance_minutes": 30},
            description="推进时间30分钟")

    # ==================== Token 使用统计 ====================
    print("\n【Token使用统计】")

    test_api("GET", "/api/token-usage/stats", description="获取所有项目Token统计")
    test_api("GET", f"/api/token-usage/projects/{project_id}/summary", description="获取项目Token摘要")
    test_api("GET", f"/api/token-usage/projects/{project_id}/stats", description="获取项目Token统计")
    test_api("GET", f"/api/token-usage/projects/{project_id}/daily?days=7", description="获取每日Token统计")

    # ==================== 清理测试数据 ====================
    print("\n【清理测试数据】")

    if character_id:
        test_api("DELETE", f"/api/characters/{character_id}", description="删除角色")
    if lore_id:
        test_api("DELETE", f"/api/lore/{lore_id}", description="删除设定")
    if hook_id:
        test_api("DELETE", f"/api/plots/hooks/{hook_id}", description="删除伏笔")
    if chapter_id:
        test_api("DELETE", f"/api/plots/chapters/{chapter_id}", description="删除章节")
    if world_id:
        test_api("DELETE", f"/api/worlds/{world_id}", description="删除世界")

    test_api("DELETE", f"/api/projects/{project_id}", description="删除测试项目")

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
