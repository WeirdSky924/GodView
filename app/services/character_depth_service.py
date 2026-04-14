"""
角色深度服务
GodView v9: 角色深度系统

管理角色性格特质、成长弧线、关系网络等
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
import json

from app.models.character_depth import (
    PersonalityTrait,
    SpeakingStyle,
    GrowthArcPhase,
    GrowthArc,
    RelationshipType,
    CharacterRelationship,
    AppearanceRule,
    CharacterDepthProfile,
    CreateCharacterDepthDTO,
    UpdateCharacterDepthDTO,
    CreateGrowthArcDTO,
    UpdateGrowthArcDTO,
    CreateRelationshipDTO,
    UpdateRelationshipDTO,
)


class CharacterDepthService:
    """角色深度服务"""

    def __init__(self, db=None):
        self.db = db
        # 内存缓存
        self._profiles: Dict[str, CharacterDepthProfile] = {}
        self._growth_arcs: Dict[str, GrowthArc] = {}
        self._relationships: Dict[str, CharacterRelationship] = {}

    # ==================== 角色深度档案 ====================

    async def create_profile(self, data: CreateCharacterDepthDTO) -> CharacterDepthProfile:
        """创建角色深度档案"""
        profile = CharacterDepthProfile(
            character_id=data.character_id,
            project_id=data.project_id,
            personality_traits=data.personality_traits,
        )
        self._profiles[profile.id] = profile

        # 数据库持久化
        if self.db:
            await self._save_profile_to_db(profile)

        return profile

    async def get_profile(self, character_id: str) -> Optional[CharacterDepthProfile]:
        """获取角色深度档案"""
        # 先查缓存
        for profile in self._profiles.values():
            if profile.character_id == character_id:
                return profile

        # 查数据库
        if self.db:
            profile = await self._load_profile_from_db(character_id)
            if profile:
                self._profiles[profile.id] = profile
                return profile

        return None

    async def update_profile(
        self,
        character_id: str,
        data: UpdateCharacterDepthDTO
    ) -> Optional[CharacterDepthProfile]:
        """更新角色深度档案"""
        profile = await self.get_profile(character_id)
        if not profile:
            return None

        # 更新字段
        if data.personality_traits is not None:
            profile.personality_traits = data.personality_traits
        if data.speaking_style is not None:
            profile.speaking_style = data.speaking_style
        if data.backstory is not None:
            profile.backstory = data.backstory
        if data.inner_world is not None:
            profile.inner_world = data.inner_world
        if data.secrets is not None:
            profile.secrets = data.secrets

        profile.updated_at = datetime.now()

        # 持久化
        if self.db:
            await self._save_profile_to_db(profile)

        return profile

    async def add_personality_trait(
        self,
        character_id: str,
        trait: PersonalityTrait
    ) -> Optional[CharacterDepthProfile]:
        """添加性格特质"""
        profile = await self.get_profile(character_id)
        if not profile:
            return None

        profile.personality_traits.append(trait)
        profile.updated_at = datetime.now()

        if self.db:
            await self._save_profile_to_db(profile)

        return profile

    async def set_speaking_style(
        self,
        character_id: str,
        style: SpeakingStyle
    ) -> Optional[CharacterDepthProfile]:
        """设置说话风格"""
        profile = await self.get_profile(character_id)
        if not profile:
            return None

        profile.speaking_style = style
        profile.updated_at = datetime.now()

        if self.db:
            await self._save_profile_to_db(profile)

        return profile

    async def add_secret(
        self,
        character_id: str,
        secret: str
    ) -> Optional[CharacterDepthProfile]:
        """添加隐藏秘密"""
        profile = await self.get_profile(character_id)
        if not profile:
            return None

        profile.secrets.append(secret)
        profile.updated_at = datetime.now()

        if self.db:
            await self._save_profile_to_db(profile)

        return profile

    # ==================== 成长弧线 ====================

    async def create_growth_arc(self, data: CreateGrowthArcDTO) -> GrowthArc:
        """创建成长弧线"""
        arc = GrowthArc(
            character_id=data.character_id,
            project_id=data.project_id,
            arc_name=data.arc_name,
            arc_description=data.arc_description,
            start_chapter=data.start_chapter,
        )
        self._growth_arcs[arc.id] = arc

        # 关联到角色档案
        profile = await self.get_profile(data.character_id)
        if profile:
            profile.growth_arcs.append(arc)
            if self.db:
                await self._save_profile_to_db(profile)

        if self.db:
            await self._save_growth_arc_to_db(arc)

        return arc

    async def get_growth_arc(self, arc_id: str) -> Optional[GrowthArc]:
        """获取成长弧线"""
        return self._growth_arcs.get(arc_id)

    async def get_character_growth_arcs(self, character_id: str) -> List[GrowthArc]:
        """获取角色的所有成长弧线"""
        return [
            arc for arc in self._growth_arcs.values()
            if arc.character_id == character_id
        ]

    async def update_growth_arc(
        self,
        arc_id: str,
        data: UpdateGrowthArcDTO
    ) -> Optional[GrowthArc]:
        """更新成长弧线"""
        arc = self._growth_arcs.get(arc_id)
        if not arc:
            return None

        if data.current_phase is not None:
            arc.current_phase = data.current_phase
        if data.milestones is not None:
            arc.milestones = data.milestones
        if data.turning_points is not None:
            arc.turning_points = data.turning_points

        arc.updated_at = datetime.now()

        if self.db:
            await self._save_growth_arc_to_db(arc)

        return arc

    async def add_milestone(
        self,
        arc_id: str,
        chapter: int,
        event: str,
        change: str
    ) -> Optional[GrowthArc]:
        """添加成长里程碑"""
        arc = self._growth_arcs.get(arc_id)
        if not arc:
            return None

        arc.milestones.append({
            "chapter": chapter,
            "event": event,
            "change": change,
            "timestamp": datetime.now().isoformat()
        })
        arc.updated_at = datetime.now()

        if self.db:
            await self._save_growth_arc_to_db(arc)

        return arc

    async def add_turning_point(
        self,
        arc_id: str,
        chapter: int,
        description: str,
        impact: str
    ) -> Optional[GrowthArc]:
        """添加转折点"""
        arc = self._growth_arcs.get(arc_id)
        if not arc:
            return None

        arc.turning_points.append({
            "chapter": chapter,
            "description": description,
            "impact": impact,
            "timestamp": datetime.now().isoformat()
        })
        arc.updated_at = datetime.now()

        if self.db:
            await self._save_growth_arc_to_db(arc)

        return arc

    async def advance_phase(
        self,
        arc_id: str,
        new_phase: GrowthArcPhase
    ) -> Optional[GrowthArc]:
        """推进成长阶段"""
        arc = self._growth_arcs.get(arc_id)
        if not arc:
            return None

        old_phase = arc.current_phase
        arc.current_phase = new_phase

        # 记录阶段变化
        arc.changes.append({
            "type": "phase_change",
            "from": old_phase.value,
            "to": new_phase.value,
            "timestamp": datetime.now().isoformat()
        })
        arc.updated_at = datetime.now()

        if self.db:
            await self._save_growth_arc_to_db(arc)

        return arc

    # ==================== 角色关系 ====================

    async def create_relationship(self, data: CreateRelationshipDTO) -> CharacterRelationship:
        """创建角色关系"""
        relationship = CharacterRelationship(
            project_id=data.project_id,
            character_a_id=data.character_a_id,
            character_b_id=data.character_b_id,
            relationship_type=data.relationship_type,
            relationship_description=data.relationship_description or "",
            strength=data.strength,
        )
        self._relationships[relationship.id] = relationship

        # 关联到角色档案
        profile_a = await self.get_profile(data.character_a_id)
        profile_b = await self.get_profile(data.character_b_id)
        if profile_a:
            profile_a.relationships.append(relationship)
        if profile_b:
            profile_b.relationships.append(relationship)

        if self.db:
            await self._save_relationship_to_db(relationship)

        return relationship

    async def get_relationship(self, relationship_id: str) -> Optional[CharacterRelationship]:
        """获取角色关系"""
        return self._relationships.get(relationship_id)

    async def get_character_relationships(
        self,
        character_id: str,
        project_id: Optional[str] = None
    ) -> List[CharacterRelationship]:
        """获取角色的所有关系"""
        relationships = [
            rel for rel in self._relationships.values()
            if rel.character_a_id == character_id or rel.character_b_id == character_id
        ]
        if project_id:
            relationships = [r for r in relationships if r.project_id == project_id]
        return relationships

    async def update_relationship(
        self,
        relationship_id: str,
        data: UpdateRelationshipDTO
    ) -> Optional[CharacterRelationship]:
        """更新角色关系"""
        relationship = self._relationships.get(relationship_id)
        if not relationship:
            return None

        old_strength = relationship.strength
        old_type = relationship.relationship_type

        if data.relationship_type is not None:
            relationship.relationship_type = data.relationship_type
        if data.relationship_description is not None:
            relationship.relationship_description = data.relationship_description
        if data.strength is not None:
            relationship.strength = data.strength

        # 记录变化历史
        if data.strength is not None and data.strength != old_strength:
            relationship.history.append({
                "type": "strength_change",
                "from": old_strength,
                "to": data.strength,
                "timestamp": datetime.now().isoformat()
            })

        relationship.updated_at = datetime.now()

        if self.db:
            await self._save_relationship_to_db(relationship)

        return relationship

    async def update_relationship_strength(
        self,
        relationship_id: str,
        delta: float,
        reason: str
    ) -> Optional[CharacterRelationship]:
        """更新关系强度（增量）"""
        relationship = self._relationships.get(relationship_id)
        if not relationship:
            return None

        old_strength = relationship.strength
        new_strength = max(-1, min(1, old_strength + delta))
        relationship.strength = new_strength

        relationship.history.append({
            "type": "strength_update",
            "from": old_strength,
            "to": new_strength,
            "delta": delta,
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        })
        relationship.updated_at = datetime.now()

        if self.db:
            await self._save_relationship_to_db(relationship)

        return relationship

    # ==================== 出场规则 ====================

    async def set_appearance_rules(
        self,
        character_id: str,
        project_id: str,
        min_interval: int = 1,
        max_absence: int = 5,
        priority: int = 5,
        required_scenes: Optional[List[str]] = None,
        optional_scenes: Optional[List[str]] = None
    ) -> Optional[CharacterDepthProfile]:
        """设置出场规则"""
        profile = await self.get_profile(character_id)
        if not profile:
            # 创建新档案
            profile = CharacterDepthProfile(
                character_id=character_id,
                project_id=project_id,
            )
            self._profiles[profile.id] = profile

        profile.appearance_rules = AppearanceRule(
            character_id=character_id,
            project_id=project_id,
            min_appearance_interval=min_interval,
            max_absence_chapters=max_absence,
            priority=priority,
            required_scenes=required_scenes or [],
            optional_scenes=optional_scenes or [],
        )
        profile.updated_at = datetime.now()

        if self.db:
            await self._save_profile_to_db(profile)

        return profile

    async def record_appearance(
        self,
        character_id: str,
        chapter: int
    ) -> Optional[CharacterDepthProfile]:
        """记录角色出场"""
        profile = await self.get_profile(character_id)
        if not profile or not profile.appearance_rules:
            return None

        rules = profile.appearance_rules
        rules.appearance_history.append(chapter)
        rules.last_appearance = chapter
        rules.warnings = []  # 清除警告

        profile.updated_at = datetime.now()

        if self.db:
            await self._save_profile_to_db(profile)

        return profile

    async def check_appearance_rules(
        self,
        character_id: str,
        current_chapter: int
    ) -> Dict[str, Any]:
        """检查出场规则"""
        profile = await self.get_profile(character_id)
        if not profile or not profile.appearance_rules:
            return {"status": "no_rules", "warnings": []}

        rules = profile.appearance_rules
        warnings = []

        # 检查最大缺席
        if rules.last_appearance:
            absence = current_chapter - rules.last_appearance
            if absence > rules.max_absence_chapters:
                warnings.append(f"角色已缺席 {absence} 章，超过最大 {rules.max_absence_chapters} 章")

        # 检查出场间隔（如果最近出场过于频繁）
        recent_appearances = [ch for ch in rules.appearance_history if ch >= current_chapter - 10]
        if len(recent_appearances) > 5:
            warnings.append(f"最近10章出场 {len(recent_appearances)} 次，可能过于频繁")

        # 更新警告
        rules.warnings = warnings
        if self.db:
            await self._save_profile_to_db(profile)

        return {
            "status": "warning" if warnings else "ok",
            "warnings": warnings,
            "last_appearance": rules.last_appearance,
            "total_appearances": len(rules.appearance_history),
            "priority": rules.priority
        }

    # ==================== 分析功能 ====================

    async def analyze_character_depth(
        self,
        character_id: str
    ) -> Dict[str, Any]:
        """分析角色深度"""
        profile = await self.get_profile(character_id)
        if not profile:
            return {"error": "角色档案不存在"}

        # 计算深度分数
        depth_score = 0.0
        components = {}

        # 性格特质 (25%)
        trait_score = min(len(profile.personality_traits) / 5, 1.0) * 25
        components["personality_traits"] = {
            "score": trait_score,
            "count": len(profile.personality_traits),
            "details": [t.trait_name for t in profile.personality_traits]
        }
        depth_score += trait_score

        # 说话风格 (15%)
        style_score = 15 if profile.speaking_style else 0
        components["speaking_style"] = {
            "score": style_score,
            "exists": profile.speaking_style is not None
        }
        depth_score += style_score

        # 成长弧线 (25%)
        arc_score = min(len(profile.growth_arcs) / 2, 1.0) * 25
        components["growth_arcs"] = {
            "score": arc_score,
            "count": len(profile.growth_arcs),
            "active_arcs": [a.arc_name for a in profile.growth_arcs if a.current_phase != GrowthArcPhase.RESOLUTION]
        }
        depth_score += arc_score

        # 关系网络 (20%)
        rel_score = min(len(profile.relationships) / 5, 1.0) * 20
        components["relationships"] = {
            "score": rel_score,
            "count": len(profile.relationships),
            "types": list(set(r.relationship_type.value for r in profile.relationships))
        }
        depth_score += rel_score

        # 背景故事 (15%)
        bg_score = 15 if profile.backstory else 0
        components["backstory"] = {
            "score": bg_score,
            "exists": profile.backstory is not None
        }
        depth_score += bg_score

        return {
            "character_id": character_id,
            "total_depth_score": round(depth_score, 1),
            "max_score": 100,
            "depth_level": self._get_depth_level(depth_score),
            "components": components,
            "suggestions": self._generate_depth_suggestions(profile, components)
        }

    def _get_depth_level(self, score: float) -> str:
        """获取深度等级"""
        if score >= 80:
            return "极深"
        elif score >= 60:
            return "较深"
        elif score >= 40:
            return "中等"
        elif score >= 20:
            return "较浅"
        else:
            return "扁平"

    def _generate_depth_suggestions(
        self,
        profile: CharacterDepthProfile,
        components: Dict
    ) -> List[str]:
        """生成深度提升建议"""
        suggestions = []

        if components["personality_traits"]["count"] < 3:
            suggestions.append("建议添加更多性格特质，使角色更加立体")

        if not components["speaking_style"]["exists"]:
            suggestions.append("建议设置独特的说话风格，增强角色辨识度")

        if components["growth_arcs"]["count"] == 0:
            suggestions.append("建议设计成长弧线，展现角色变化")

        if components["relationships"]["count"] < 2:
            suggestions.append("建议建立更多角色关系，丰富角色网络")

        if not components["backstory"]["exists"]:
            suggestions.append("建议编写背景故事，增加角色厚度")

        if not profile.inner_world:
            suggestions.append("建议描绘内心世界，展现角色心理")

        return suggestions

    # ==================== 数据库操作 ====================

    async def _save_profile_to_db(self, profile: CharacterDepthProfile):
        """保存档案到数据库"""
        if not self.db:
            return

        query = """
        INSERT INTO character_depth_profiles
        (id, character_id, project_id, personality_traits, speaking_style,
         growth_arcs, relationships, appearance_rules, backstory, inner_world, secrets,
         created_at, updated_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
        ON CONFLICT (id) DO UPDATE SET
            personality_traits = $4,
            speaking_style = $5,
            growth_arcs = $6,
            relationships = $7,
            appearance_rules = $8,
            backstory = $9,
            inner_world = $10,
            secrets = $11,
            updated_at = $13
        """
        await self.db.execute(
            query,
            profile.id,
            profile.character_id,
            profile.project_id,
            json.dumps([t.model_dump() for t in profile.personality_traits]),
            json.dumps(profile.speaking_style.model_dump()) if profile.speaking_style else None,
            json.dumps([a.model_dump() for a in profile.growth_arcs]),
            json.dumps([r.model_dump() for r in profile.relationships]),
            json.dumps(profile.appearance_rules.model_dump()) if profile.appearance_rules else None,
            profile.backstory,
            json.dumps(profile.inner_world),
            json.dumps(profile.secrets),
            profile.created_at,
            profile.updated_at,
        )

    async def _load_profile_from_db(self, character_id: str) -> Optional[CharacterDepthProfile]:
        """从数据库加载档案"""
        if not self.db:
            return None

        query = """
        SELECT * FROM character_depth_profiles WHERE character_id = $1
        """
        row = await self.db.fetch_one(query, character_id)
        if not row:
            return None

        # 解析数据
        profile = CharacterDepthProfile(
            id=row["id"],
            character_id=row["character_id"],
            project_id=row["project_id"],
            personality_traits=[PersonalityTrait(**t) for t in json.loads(row["personality_traits"] or "[]")],
            speaking_style=SpeakingStyle(**json.loads(row["speaking_style"])) if row["speaking_style"] else None,
            growth_arcs=[GrowthArc(**a) for a in json.loads(row["growth_arcs"] or "[]")],
            relationships=[CharacterRelationship(**r) for r in json.loads(row["relationships"] or "[]")],
            appearance_rules=AppearanceRule(**json.loads(row["appearance_rules"])) if row["appearance_rules"] else None,
            backstory=row["backstory"],
            inner_world=json.loads(row["inner_world"] or "{}"),
            secrets=json.loads(row["secrets"] or "[]"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        return profile

    async def _save_growth_arc_to_db(self, arc: GrowthArc):
        """保存成长弧线到数据库"""
        if not self.db:
            return
        # 实现数据库保存逻辑
        pass

    async def _save_relationship_to_db(self, relationship: CharacterRelationship):
        """保存关系到数据库"""
        if not self.db:
            return
        # 实现数据库保存逻辑
        pass
