"""
测试剩余 API 接口
"""
import asyncio
import aiohttp
import json
import sys
from datetime import datetime

BASE_URL = "http://localhost:8894"

# 存储测试过程中创建的资源ID
test_data = {
    "project_id": None,
    "world_id": None,
    "character_id": None,
    "chapter_id": None,
    "bootstrap_session_id": None,
    "hook_id": None,
    "lore_id": None,
    "skill_id": None,
    "region_id": None,
    "snapshot_id": None,
}

results = []

async def test_endpoint(session, method, path, name, data=None, params=None):
    """测试单个接口"""
    url = f"{BASE_URL}{path}"
    try:
        async with session.request(method, url, json=data, params=params) as resp:
            status = resp.status
            if status < 400:
                result = "[PASS]"
            else:
                result = f"[FAIL {status}]"

            try:
                resp_data = await resp.json()
            except:
                resp_data = await resp.text()

            results.append({
                "name": name,
                "method": method,
                "path": path,
                "status": status,
                "result": result,
            })
            print(f"{result} - {method} {path}")
            return resp_data if status < 400 else None
    except Exception as e:
        results.append({
            "name": name,
            "method": method,
            "path": path,
            "status": 0,
            "result": f"[ERROR] {str(e)[:50]}",
        })
        print(f"[ERROR] - {method} {path}: {str(e)[:50]}")
        return None

async def setup_test_data(session):
    """准备测试数据"""
    print("\n=== 准备测试数据 ===")

    # 获取或创建项目
    resp = await test_endpoint(session, "GET", "/api/projects?limit=1", "Get project")
    if resp and len(resp) > 0:
        test_data["project_id"] = resp[0]["id"]
    else:
        resp = await test_endpoint(session, "POST", "/api/projects", "Create project",
                                   {"name": "Test Project", "description": "Test"})
        if resp:
            test_data["project_id"] = resp.get("id")

    # 获取或创建世界
    resp = await test_endpoint(session, "GET", "/api/worlds?limit=1", "Get world")
    if resp and len(resp) > 0:
        test_data["world_id"] = resp[0]["id"]

    # 获取角色
    resp = await test_endpoint(session, "GET", "/api/characters?limit=1", "Get character")
    if resp and len(resp) > 0:
        test_data["character_id"] = resp[0]["id"]

    # 获取章节
    resp = await test_endpoint(session, "GET", "/api/plots/chapters?limit=1", "Get chapter")
    if resp and len(resp) > 0:
        test_data["chapter_id"] = resp[0]["id"]

    # 获取伏笔
    resp = await test_endpoint(session, "GET", "/api/plots/hooks?limit=1", "Get hook")
    if resp and len(resp) > 0:
        test_data["hook_id"] = resp[0]["id"]

    # 获取设定
    resp = await test_endpoint(session, "GET", "/api/lore?limit=1", "Get lore")
    if resp and len(resp) > 0:
        test_data["lore_id"] = resp[0]["id"]

    # 获取技能
    resp = await test_endpoint(session, "GET", "/api/skills?limit=1", "Get skill")
    if resp and len(resp) > 0:
        test_data["skill_id"] = resp[0]["id"]

    print(f"\n测试数据: {json.dumps(test_data, indent=2)}")

async def test_characters_endpoints(session):
    """测试 Characters 剩余接口"""
    print("\n=== Characters 接口 ===")

    if not test_data["character_id"]:
        print("跳过 - 无角色ID")
        return

    char_id = test_data["character_id"]

    # POST voice-samples
    await test_endpoint(session, "POST", f"/api/characters/{char_id}/voice-samples",
                       "Add voice sample",
                       {"id": "voice-test-001", "character_id": char_id,
                        "text": "Test voice sample", "context": "test"})

    # GET voice-samples
    await test_endpoint(session, "GET", f"/api/characters/{char_id}/voice-samples?limit=5",
                       "Get voice samples")

async def test_worlds_endpoints(session):
    """测试 Worlds 剩余接口"""
    print("\n=== Worlds 接口 ===")

    if not test_data["world_id"]:
        print("跳过 - 无世界ID")
        return

    world_id = test_data["world_id"]

    # POST regions
    resp = await test_endpoint(session, "POST", f"/api/worlds/{world_id}/regions",
                              "Create region",
                              {"name": "Test Region", "region_type": "city",
                               "description": "A test region"})
    if resp and resp.get("id"):
        test_data["region_id"] = resp["id"]

    # GET regions
    await test_endpoint(session, "GET", f"/api/worlds/{world_id}/regions",
                       "Get regions")

    # POST snapshots
    resp = await test_endpoint(session, "POST", f"/api/worlds/{world_id}/snapshots",
                              "Create snapshot",
                              {"name": "Test Snapshot", "description": "Test snapshot"})
    if resp and resp.get("id"):
        test_data["snapshot_id"] = resp["id"]

    # GET snapshots
    await test_endpoint(session, "GET", f"/api/worlds/{world_id}/snapshots",
                       "Get snapshots")

    # POST rollback (if snapshot exists)
    if test_data["snapshot_id"]:
        await test_endpoint(session, "POST",
                           f"/api/worlds/{world_id}/rollback?snapshot_id={test_data['snapshot_id']}",
                           "Rollback to snapshot")

async def test_bootstrap_endpoints(session):
    """测试 Bootstrap 接口"""
    print("\n=== Bootstrap 接口 ===")

    if not test_data["project_id"]:
        print("跳过 - 无项目ID")
        return

    # POST start
    resp = await test_endpoint(session, "POST", "/api/bootstrap/start",
                              "Bootstrap start",
                              {"project_id": test_data["project_id"],
                               "initial_idea": "A fantasy story about magic"})
    if resp and resp.get("session_id"):
        test_data["bootstrap_session_id"] = resp["session_id"]
        session_id = resp["session_id"]

        # GET session
        await test_endpoint(session, "GET", f"/api/bootstrap/{session_id}",
                           "Get bootstrap session")

        # GET status
        await test_endpoint(session, "GET", f"/api/bootstrap/{session_id}/status",
                           "Get bootstrap status")

        # POST message
        await test_endpoint(session, "POST", "/api/bootstrap/message",
                           "Send bootstrap message",
                           {"session_id": session_id, "message": "Tell me more"})

        # GET messages
        await test_endpoint(session, "GET", f"/api/bootstrap/{session_id}/messages",
                           "Get bootstrap messages")

        # POST outline
        await test_endpoint(session, "POST", "/api/bootstrap/outline",
                           "Create bootstrap outline",
                           {"session_id": session_id, "outline": {"chapters": []}})

        # POST finalize-setting
        await test_endpoint(session, "POST", f"/api/bootstrap/{session_id}/finalize-setting",
                           "Finalize bootstrap setting")

async def test_setting_agent_endpoints(session):
    """测试 Setting Agent 接口"""
    print("\n=== Setting Agent 接口 ===")

    if not test_data["project_id"]:
        print("跳过 - 无项目ID")
        return

    project_id = test_data["project_id"]

    # POST chat
    await test_endpoint(session, "POST", "/api/setting-agent/chat",
                       "Setting Agent chat",
                       {"project_id": project_id, "message": "Hello"})

    # POST change
    await test_endpoint(session, "POST", "/api/setting-agent/change",
                       "Setting Agent change request",
                       {"project_id": project_id, "change_request": "Add more magic"})

    # POST negotiate
    await test_endpoint(session, "POST", "/api/setting-agent/negotiate",
                       "Setting Agent negotiate",
                       {"project_id": project_id, "proposal": {"magic_system": "detailed"}})

    # GET summary
    await test_endpoint(session, "GET", f"/api/setting-agent/{project_id}/summary",
                       "Get setting summary")

    # GET history
    await test_endpoint(session, "GET", f"/api/setting-agent/{project_id}/history",
                       "Get setting history")

    # GET conflicts
    await test_endpoint(session, "GET", f"/api/setting-agent/{project_id}/conflicts",
                       "Get setting conflicts")

    # POST session
    await test_endpoint(session, "POST", f"/api/setting-agent/{project_id}/session",
                       "Create setting session")

async def test_time_system_endpoints(session):
    """测试 Time System 接口"""
    print("\n=== Time System 接口 ===")

    if not test_data["world_id"]:
        print("跳过 - 无世界ID")
        return

    world_id = test_data["world_id"]

    # GET time system
    await test_endpoint(session, "GET", f"/api/time/systems/{world_id}",
                       "Get time system")

    # POST time control - advance
    await test_endpoint(session, "POST", "/api/time/control",
                       "Time control - advance",
                       {"world_id": world_id, "action": "advance", "amount": 1})

    # POST time jump
    await test_endpoint(session, "POST", "/api/time/jump",
                       "Time jump",
                       {"world_id": world_id, "target_time": "2024-01-15T00:00:00"})

    # GET time branches
    await test_endpoint(session, "GET", f"/api/time/branches/{world_id}",
                       "Get time branches")

    # GET time history
    await test_endpoint(session, "GET", f"/api/time/history/{world_id}",
                       "Get time history")

async def test_simulation_endpoints(session):
    """测试 Simulation 接口"""
    print("\n=== Simulation 接口 ===")

    if not test_data["project_id"] or not test_data["chapter_id"]:
        print("跳过 - 无项目ID或章节ID")
        return

    project_id = test_data["project_id"]
    chapter_id = test_data["chapter_id"]

    # POST simulate reading
    await test_endpoint(session, "POST", "/api/simulation/reading",
                       "Simulate reading",
                       {"project_id": project_id, "chapter_id": chapter_id})

    # POST simulate reaction
    await test_endpoint(session, "POST", "/api/simulation/reaction",
                       "Simulate reaction",
                       {"project_id": project_id, "content": "Test content"})

async def test_visualization_endpoints(session):
    """测试可视化接口"""
    print("\n=== 剧情可视化接口 ===")

    if not test_data["project_id"]:
        print("跳过 - 无项目ID")
        return

    project_id = test_data["project_id"]

    # GET plot timeline
    await test_endpoint(session, "GET", f"/api/visualization/plots/{project_id}/timeline",
                       "Get plot timeline")

    # GET plot graph
    await test_endpoint(session, "GET", f"/api/visualization/plots/{project_id}/graph",
                       "Get plot graph")

    # GET character relationships
    await test_endpoint(session, "GET", f"/api/visualization/characters/{project_id}/relationships",
                       "Get character relationships")

    # GET world map
    if test_data["world_id"]:
        await test_endpoint(session, "GET",
                           f"/api/visualization/worlds/{test_data['world_id']}/map",
                           "Get world map")

async def print_summary():
    """打印测试摘要"""
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)

    passed = sum(1 for r in results if "PASS" in r["result"])
    failed = sum(1 for r in results if "FAIL" in r["result"])
    errors = sum(1 for r in results if "ERROR" in r["result"])

    print(f"Total: {len(results)} endpoints")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Errors: {errors}")

    if failed > 0 or errors > 0:
        print("\nFailed endpoints:")
        for r in results:
            if "FAIL" in r["result"] or "ERROR" in r["result"]:
                print(f"  - {r['method']} {r['path']}: {r['result']}")

async def main():
    async with aiohttp.ClientSession() as session:
        # 检查服务器状态
        try:
            async with session.get(f"{BASE_URL}/api/config/database/status") as resp:
                if resp.status != 200:
                    print("服务器未响应，请确保服务器已启动")
                    return
                print("服务器连接正常")
        except Exception as e:
            print(f"无法连接服务器: {e}")
            return

        # 准备测试数据
        await setup_test_data(session)

        # 测试各组接口
        await test_characters_endpoints(session)
        await test_worlds_endpoints(session)
        await test_bootstrap_endpoints(session)
        await test_setting_agent_endpoints(session)
        await test_time_system_endpoints(session)
        await test_simulation_endpoints(session)
        await test_visualization_endpoints(session)

        # 打印摘要
        await print_summary()

if __name__ == "__main__":
    asyncio.run(main())
