"""
世界观层次展开服务
GodView v9: 世界观层次展开系统

管理地图升级路线、势力更迭、战力天花板等数据
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from app.models.world_expansion import (
    MapLevel,
    ForceStatus,
    WorldMapLevel,
    ForceFaction,
    PowerCeiling,
    InformationLevel,
    CreateWorldMapLevelDTO,
    CreateForceFactionDTO,
    UpdateForceFactionDTO,
    CreatePowerCeilingDTO,
    CreateInformationLevelDTO,
    WorldExpansionSummary,
)


class WorldExpansionService:
    """世界观层次展开服务"""

    def __init__(self, db=None):
        self.db = db
        # 内存缓存
        self._map_levels: Dict[str, WorldMapLevel] = {}
        self._forces: Dict[str, ForceFaction] = {}
        self._power_ceilings: Dict[str, PowerCeiling] = {}
        self._information_levels: Dict[str, InformationLevel] = {}

    # ==================== 地图等级管理 ====================

    async def create_map_level(self, data: CreateWorldMapLevelDTO) -> WorldMapLevel:
        """创建地图等级"""
        map_level = WorldMapLevel(**data.model_dump())
        self._map_levels[map_level.id] = map_level
        return map_level

    async def get_map_levels(self, project_id: str) -> List[WorldMapLevel]:
        """获取项目地图等级列表"""
        return [m for m in self._map_levels.values() if m.project_id == project_id]

    async def get_map_level(self, level_id: str) -> Optional[WorldMapLevel]:
        """获取地图等级详情"""
        return self._map_levels.get(level_id)

    async def update_map_level(self, level_id: str, data: Dict) -> Optional[WorldMapLevel]:
        """更新地图等级"""
        map_level = self._map_levels.get(level_id)
        if not map_level:
            return None

        for key, value in data.items():
            if hasattr(map_level, key) and value is not None:
                setattr(map_level, key, value)

        map_level.updated_at = datetime.now()
        return map_level

    async def delete_map_level(self, level_id: str) -> bool:
        """删除地图等级"""
        if level_id in self._map_levels:
            del self._map_levels[level_id]
            return True
        return False

    # ==================== 势力管理 ====================

    async def create_force(self, data: CreateForceFactionDTO) -> ForceFaction:
        """创建势力"""
        force = ForceFaction(**data.model_dump())
        self._forces[force.id] = force
        return force

    async def get_forces(self, project_id: str, status: Optional[ForceStatus] = None) -> List[ForceFaction]:
        """获取势力列表"""
        forces = [f for f in self._forces.values() if f.project_id == project_id]
        if status:
            forces = [f for f in forces if f.status == status]
        return forces

    async def get_force(self, force_id: str) -> Optional[ForceFaction]:
        """获取势力详情"""
        return self._forces.get(force_id)

    async def update_force(self, force_id: str, data: UpdateForceFactionDTO) -> Optional[ForceFaction]:
        """更新势力"""
        force = self._forces.get(force_id)
        if not force:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if value is not None:
                setattr(force, key, value)

        force.updated_at = datetime.now()
        return force

    async def update_force_status(self, force_id: str, new_status: ForceStatus, chapter: int) -> Optional[ForceFaction]:
        """更新势力状态"""
        force = self._forces.get(force_id)
        if not force:
            return None

        old_status = force.status
        force.status = new_status

        # 记录状态变化
        if new_status == ForceStatus.PEAK:
            force.peak_chapter = chapter
        elif new_status == ForceStatus.DECLINING:
            force.decline_chapter = chapter
        elif new_status == ForceStatus.EXTINCT:
            force.end_chapter = chapter

        force.updated_at = datetime.now()
        return force

    async def add_force_relationship(self, force_id: str, relationship_type: str, target_force_id: str) -> Optional[ForceFaction]:
        """添加势力关系"""
        force = self._forces.get(force_id)
        if not force:
            return None

        if relationship_type == "ally":
            if target_force_id not in force.allies:
                force.allies.append(target_force_id)
        elif relationship_type == "enemy":
            if target_force_id not in force.enemies:
                force.enemies.append(target_force_id)

        force.updated_at = datetime.now()
        return force

    async def delete_force(self, force_id: str) -> bool:
        """删除势力"""
        if force_id in self._forces:
            del self._forces[force_id]
            return True
        return False

    # ==================== 战力天花板管理 ====================

    async def create_power_ceiling(self, data: CreatePowerCeilingDTO) -> PowerCeiling:
        """创建战力天花板"""
        ceiling = PowerCeiling(**data.model_dump())
        self._power_ceilings[ceiling.id] = ceiling
        return ceiling

    async def get_power_ceilings(self, project_id: str) -> List[PowerCeiling]:
        """获取战力天花板列表"""
        ceilings = [c for c in self._power_ceilings.values() if c.project_id == project_id]
        return sorted(ceilings, key=lambda c: c.start_chapter)

    async def get_current_power_ceiling(self, project_id: str, current_chapter: int) -> Optional[PowerCeiling]:
        """获取当前章节的战力天花板"""
        ceilings = await self.get_power_ceilings(project_id)

        for ceiling in reversed(ceilings):
            if ceiling.end_chapter is None and current_chapter >= ceiling.start_chapter:
                return ceiling
            elif ceiling.end_chapter and ceiling.start_chapter <= current_chapter <= ceiling.end_chapter:
                return ceiling

        return None

    async def update_power_ceiling(self, ceiling_id: str, data: Dict) -> Optional[PowerCeiling]:
        """更新战力天花板"""
        ceiling = self._power_ceilings.get(ceiling_id)
        if not ceiling:
            return None

        for key, value in data.items():
            if hasattr(ceiling, key) and value is not None:
                setattr(ceiling, key, value)

        ceiling.updated_at = datetime.now()
        return ceiling

    # ==================== 信息层级管理 ====================

    async def create_information_level(self, data: CreateInformationLevelDTO) -> InformationLevel:
        """创建信息层级"""
        info = InformationLevel(**data.model_dump())
        self._information_levels[info.id] = info
        return info

    async def get_information_levels(self, project_id: str, info_type: Optional[str] = None) -> List[InformationLevel]:
        """获取信息层级列表"""
        infos = [i for i in self._information_levels.values() if i.project_id == project_id]
        if info_type:
            infos = [i for i in infos if i.info_type == info_type]
        return sorted(infos, key=lambda i: (i.importance, i.first_hint_chapter or 999), reverse=True)

    async def get_pending_reveals(self, project_id: str, current_chapter: int) -> List[InformationLevel]:
        """获取当前章节应该揭示的信息"""
        infos = await self.get_information_levels(project_id)

        pending = []
        for info in infos:
            # 检查是否到了部分揭示时机
            if info.partial_reveal_chapter and current_chapter >= info.partial_reveal_chapter:
                if info.full_reveal_chapter is None or current_chapter < info.full_reveal_chapter:
                    pending.append(info)
            # 检查是否到了完全揭示时机
            elif info.full_reveal_chapter and current_chapter >= info.full_reveal_chapter:
                pending.append(info)

        return pending

    async def update_information_level(self, info_id: str, data: Dict) -> Optional[InformationLevel]:
        """更新信息层级"""
        info = self._information_levels.get(info_id)
        if not info:
            return None

        for key, value in data.items():
            if hasattr(info, key) and value is not None:
                setattr(info, key, value)

        info.updated_at = datetime.now()
        return info

    # ==================== 综合功能 ====================

    async def get_expansion_summary(self, project_id: str, current_chapter: int = 1) -> WorldExpansionSummary:
        """获取世界观展开摘要"""
        map_levels = await self.get_map_levels(project_id)
        forces = await self.get_forces(project_id)
        power_ceilings = await self.get_power_ceilings(project_id)

        # 获取下阶段展开提示
        next_expansion = None
        if map_levels:
            next_map = next((m for m in map_levels if m.unlock_chapter and m.unlock_chapter > current_chapter), None)
            if next_map:
                next_expansion = f"下一地图: {next_map.name} (第{next_map.unlock_chapter}章解锁)"

        if power_ceilings:
            next_ceiling = next((c for c in power_ceilings if c.start_chapter > current_chapter), None)
            if next_ceiling:
                hint = f"战力天花板: {next_ceiling.ceiling_level} (第{next_ceiling.start_chapter}章)"
                next_expansion = f"{next_expansion}; {hint}" if next_expansion else hint

        return WorldExpansionSummary(
            project_id=project_id,
            map_levels=sorted(map_levels, key=lambda m: m.level.value),
            forces=forces,
            power_ceilings=power_ceilings,
            information_levels=await self.get_information_levels(project_id),
            next_expansion_hint=next_expansion
        )

    async def analyze_force_changes(self, project_id: str, start_chapter: int, end_chapter: int) -> Dict[str, Any]:
        """分析章节区间的势力变化"""
        forces = await self.get_forces(project_id)

        changes = []
        for force in forces:
            force_changes = []

            if force.founded_chapter and start_chapter <= force.founded_chapter <= end_chapter:
                force_changes.append(f"第{force.founded_chapter}章: {force.name} 创立")

            if force.peak_chapter and start_chapter <= force.peak_chapter <= end_chapter:
                force_changes.append(f"第{force.peak_chapter}章: {force.name} 达到鼎盛")

            if force.decline_chapter and start_chapter <= force.decline_chapter <= end_chapter:
                force_changes.append(f"第{force.decline_chapter}章: {force.name} 开始衰落")

            if force.end_chapter and start_chapter <= force.end_chapter <= end_chapter:
                force_changes.append(f"第{force.end_chapter}章: {force.name} 灭亡")

            if force_changes:
                changes.append({
                    "force_id": force.id,
                    "force_name": force.name,
                    "changes": force_changes
                })

        return {
            "start_chapter": start_chapter,
            "end_chapter": end_chapter,
            "forces_count": len(forces),
            "changes": changes
        }