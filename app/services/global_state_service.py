"""
全局状态服务 - 管理跨 Agent 的共享状态

职责：
1. 存储工作流级别的共享状态
2. 提供 Agent 间的数据传递机制
3. 支持状态的版本控制和回滚
4. 与 Skill 系统集成
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class GlobalStateService:
    """全局状态服务"""

    def __init__(self, db=None):
        self._db = db
        # 内存缓存：project_id -> state_dict
        self._state_cache: Dict[str, Dict[str, Any]] = {}
        # 状态历史：用于回滚
        self._state_history: Dict[str, List[Dict[str, Any]]] = {}
        # 最大历史记录数
        self._max_history = 10

    async def get_state(
        self,
        project_id: str,
        keys: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        获取项目的全局状态

        Args:
            project_id: 项目 ID
            keys: 要获取的键列表，None 表示获取全部

        Returns:
            Dict[str, Any]: 状态字典
        """
        cache_key = f"global:{project_id}"

        # 检查缓存
        if cache_key not in self._state_cache:
            # 从数据库加载
            state = await self._load_from_db(project_id)
            self._state_cache[cache_key] = state

        state = self._state_cache[cache_key]

        # 过滤键
        if keys:
            return {k: state.get(k) for k in keys if k in state}
        return state.copy()

    async def set_state(
        self,
        project_id: str,
        updates: Dict[str, Any],
        agent_type: Optional[str] = None,
        workflow_execution_id: Optional[str] = None,
    ) -> bool:
        """
        更新全局状态

        Args:
            project_id: 项目 ID
            updates: 要更新的键值对
            agent_type: 执行更新的 Agent 类型
            workflow_execution_id: 工作流执行 ID

        Returns:
            bool: 是否更新成功
        """
        cache_key = f"global:{project_id}"

        # 获取当前状态
        current_state = await self.get_state(project_id)

        # 保存历史（用于回滚）
        if cache_key not in self._state_history:
            self._state_history[cache_key] = []
        self._state_history[cache_key].append(current_state.copy())

        # 限制历史记录数
        if len(self._state_history[cache_key]) > self._max_history:
            self._state_history[cache_key].pop(0)

        # 应用更新
        current_state.update(updates)
        current_state["_last_updated"] = datetime.now().isoformat()
        current_state["_last_updated_by"] = agent_type

        # 更新缓存
        self._state_cache[cache_key] = current_state

        # 持久化到数据库
        return await self._save_to_db(
            project_id,
            current_state,
            updates,
            agent_type,
            workflow_execution_id,
        )

    async def get_state_keys(
        self,
        project_id: str,
        pattern: Optional[str] = None,
    ) -> List[str]:
        """
        获取状态键列表

        Args:
            project_id: 项目 ID
            pattern: 键模式（支持通配符 *）

        Returns:
            List[str]: 键列表
        """
        state = await self.get_state(project_id)
        keys = list(state.keys())

        if pattern:
            # 简单通配符匹配
            import fnmatch
            keys = [k for k in keys if fnmatch.fnmatch(k, pattern)]

        return keys

    async def delete_state_key(
        self,
        project_id: str,
        key: str,
    ) -> bool:
        """
        删除状态键

        Args:
            project_id: 项目 ID
            key: 要删除的键

        Returns:
            bool: 是否删除成功
        """
        cache_key = f"global:{project_id}"

        if cache_key in self._state_cache:
            if key in self._state_cache[cache_key]:
                del self._state_cache[cache_key][key]
                await self._save_to_db(
                    project_id,
                    self._state_cache[cache_key],
                    {},
                    None,
                    None,
                )
                return True
        return False

    async def rollback(
        self,
        project_id: str,
        steps: int = 1,
    ) -> Optional[Dict[str, Any]]:
        """
        回滚状态

        Args:
            project_id: 项目 ID
            steps: 回滚步数

        Returns:
            Optional[Dict[str, Any]]: 回滚后的状态，失败返回 None
        """
        cache_key = f"global:{project_id}"

        if cache_key not in self._state_history:
            logger.warning(f"没有状态历史可回滚: {project_id}")
            return None

        history = self._state_history[cache_key]
        if len(history) < steps:
            logger.warning(f"历史记录不足，无法回滚 {steps} 步")
            return None

        # 回滚
        for _ in range(steps):
            history.pop()

        if history:
            rollback_state = history[-1].copy()
        else:
            rollback_state = {}

        # 更新缓存和数据库
        self._state_cache[cache_key] = rollback_state
        await self._save_to_db(project_id, rollback_state, {}, None, None)

        logger.info(f"状态已回滚 {steps} 步: {project_id}")
        return rollback_state

    async def _load_from_db(self, project_id: str) -> Dict[str, Any]:
        """从数据库加载状态"""
        if not self._db:
            return {}

        try:
            query = """
                SELECT state_data FROM global_state
                WHERE project_id = CAST(:project_id AS UUID)
            """
            results = await self._db.execute_query(
                query, {"project_id": project_id}
            )

            if results and len(results) > 0:
                state_data = results[0].get("state_data", {})
                if isinstance(state_data, str):
                    state_data = json.loads(state_data)
                return state_data

        except Exception as e:
            logger.error(f"加载全局状态失败: {e}")

        return {}

    async def _save_to_db(
        self,
        project_id: str,
        state: Dict[str, Any],
        updates: Dict[str, Any],
        agent_type: Optional[str],
        workflow_execution_id: Optional[str],
    ) -> bool:
        """保存状态到数据库"""
        if not self._db:
            return False

        try:
            # 更新主状态表
            query = """
                INSERT INTO global_state (project_id, state_data, updated_at)
                VALUES (CAST(:project_id AS UUID), CAST(:state_data AS jsonb), NOW())
                ON CONFLICT (project_id) DO UPDATE SET
                    state_data = EXCLUDED.state_data,
                    updated_at = NOW()
            """
            await self._db.execute_write(
                query,
                {
                    "project_id": project_id,
                    "state_data": json.dumps(state, default=str),
                },
            )

            # 记录变更历史
            if updates:
                history_query = """
                    INSERT INTO global_state_history (
                        id, project_id, agent_type, workflow_execution_id,
                        changes, created_at
                    ) VALUES (
                        gen_random_uuid(), CAST(:project_id AS UUID),
                        :agent_type, :workflow_execution_id,
                        CAST(:changes AS jsonb), NOW()
                    )
                """
                await self._db.execute_write(
                    history_query,
                    {
                        "project_id": project_id,
                        "agent_type": agent_type,
                        "workflow_execution_id": workflow_execution_id,
                        "changes": json.dumps(updates, default=str),
                    },
                )

            return True

        except Exception as e:
            logger.error(f"保存全局状态失败: {e}")
            return False

    def clear_cache(self, project_id: Optional[str] = None):
        """清除缓存"""
        if project_id:
            cache_key = f"global:{project_id}"
            if cache_key in self._state_cache:
                del self._state_cache[cache_key]
            if cache_key in self._state_history:
                del self._state_history[cache_key]
        else:
            self._state_cache.clear()
            self._state_history.clear()

        logger.info(f"清除全局状态缓存: {project_id or '全部'}")


# 单例实例
_state_service: Optional[GlobalStateService] = None


def get_global_state_service(db=None) -> GlobalStateService:
    """获取全局状态服务单例"""
    global _state_service
    if _state_service is None:
        _state_service = GlobalStateService(db)
    elif db is not None:
        _state_service._db = db
    return _state_service
