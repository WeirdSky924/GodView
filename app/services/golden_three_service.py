"""
黄金三章规则服务
GodView v9: 开局质量保障系统

管理黄金三章规则的配置和检测
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
import json

from app.models.golden_three import (
    GoldenThreeRuleType,
    RuleSeverity,
    GoldenThreeRule,
    GoldenThreeCheckResult,
    CreateGoldenThreeRuleDTO,
    UpdateGoldenThreeRuleDTO,
    DEFAULT_GOLDEN_THREE_RULES,
)


class GoldenThreeService:
    """黄金三章规则服务"""

    def __init__(self, db=None):
        self.db = db
        # 内存缓存
        self._rules: Dict[str, GoldenThreeRule] = {}
        self._initialized = False

    async def initialize(self):
        """初始化默认规则"""
        if self._initialized:
            return

        # 加载默认规则
        for rule_data in DEFAULT_GOLDEN_THREE_RULES:
            rule = GoldenThreeRule(**rule_data)
            self._rules[rule.id] = rule

        # 从数据库加载自定义规则
        if self.db:
            await self._load_rules_from_db()

        self._initialized = True

    # ==================== 规则管理 ====================

    async def get_rules(
        self,
        rule_type: Optional[GoldenThreeRuleType] = None,
        chapter: Optional[int] = None,
        genre: Optional[str] = None,
        active_only: bool = True
    ) -> List[GoldenThreeRule]:
        """获取规则列表"""
        await self.initialize()

        rules = list(self._rules.values())

        # 过滤
        if active_only:
            rules = [r for r in rules if r.is_active]

        if rule_type:
            rules = [r for r in rules if r.rule_type == rule_type]

        if chapter:
            rules = [r for r in rules if r.applicable_chapter == chapter]

        if genre:
            rules = [r for r in rules if not r.applicable_genres or genre in r.applicable_genres]

        # 按权重排序
        rules.sort(key=lambda r: r.weight, reverse=True)

        return rules

    async def get_rule(self, rule_id: str) -> Optional[GoldenThreeRule]:
        """获取单个规则"""
        await self.initialize()
        return self._rules.get(rule_id)

    async def create_rule(self, data: CreateGoldenThreeRuleDTO) -> GoldenThreeRule:
        """创建规则"""
        await self.initialize()

        rule = GoldenThreeRule(**data.model_dump())
        self._rules[rule.id] = rule

        if self.db:
            await self._save_rule_to_db(rule)

        return rule

    async def update_rule(
        self,
        rule_id: str,
        data: UpdateGoldenThreeRuleDTO
    ) -> Optional[GoldenThreeRule]:
        """更新规则"""
        await self.initialize()

        rule = self._rules.get(rule_id)
        if not rule:
            return None

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if value is not None:
                setattr(rule, key, value)

        rule.updated_at = datetime.now()

        if self.db:
            await self._save_rule_to_db(rule)

        return rule

    async def delete_rule(self, rule_id: str) -> bool:
        """删除规则"""
        await self.initialize()

        if rule_id not in self._rules:
            return False

        del self._rules[rule_id]

        if self.db:
            await self._delete_rule_from_db(rule_id)

        return True

    # ==================== 检测功能 ====================

    async def check_chapter(
        self,
        project_id: str,
        chapter_number: int,
        content: str,
        genre: Optional[str] = None
    ) -> Dict[str, Any]:
        """检测单章"""
        await self.initialize()

        # 获取适用规则
        rules = await self.get_rules(chapter=chapter_number, genre=genre)

        results = []
        total_weight = 0
        passed_weight = 0
        issues = []
        suggestions = []

        for rule in rules:
            check_result = self._check_single_rule(rule, content)
            total_weight += rule.weight

            if check_result["passed"]:
                passed_weight += rule.weight
            else:
                issues.append({
                    "rule": rule.rule_name,
                    "severity": rule.severity.value,
                    "description": rule.description,
                    "details": check_result.get("details", [])
                })
                suggestions.extend(rule.fix_suggestions)

            results.append({
                "rule_id": rule.id,
                "rule_name": rule.rule_name,
                "rule_type": rule.rule_type.value,
                "severity": rule.severity.value,
                "passed": check_result["passed"],
                "score": check_result.get("score", 0),
                "details": check_result.get("details", [])
            })

        # 计算分数
        score = (passed_weight / total_weight * 100) if total_weight > 0 else 0

        return {
            "chapter_number": chapter_number,
            "score": round(score, 1),
            "rules_checked": len(rules),
            "rules_passed": sum(1 for r in results if r["passed"]),
            "results": results,
            "issues": issues,
            "suggestions": list(set(suggestions))[:5]  # 去重并限制数量
        }

    def _check_single_rule(self, rule: GoldenThreeRule, content: str) -> Dict[str, Any]:
        """检测单个规则"""
        content_lower = content.lower()
        details = []
        passed_count = 0

        # 基于规则类型的检测逻辑
        if rule.rule_type == GoldenThreeRuleType.HOOK:
            result = self._check_hook_rule(rule, content, content_lower)
        elif rule.rule_type == GoldenThreeRuleType.CONFLICT:
            result = self._check_conflict_rule(rule, content, content_lower)
        elif rule.rule_type == GoldenThreeRuleType.PROTAGONIST:
            result = self._check_protagonist_rule(rule, content, content_lower)
        else:
            result = {"passed": True, "score": 100, "details": ["规则类型未知，默认通过"]}

        return result

    def _check_hook_rule(self, rule: GoldenThreeRule, content: str, content_lower: str) -> Dict[str, Any]:
        """检测钩子规则"""
        details = []
        score = 0

        # 获取前500字
        first_500 = content[:500] if len(content) > 500 else content
        first_50 = content[:50] if len(content) > 50 else content

        # 检查是否以动作/对话/悬念开篇
        if any(word in first_50 for word in ["说", "道", "问", "喊", "叫", "笑"]):
            details.append("以对话开篇")
            score += 30
        if any(word in first_50 for word in ["闪", "飞", "落", "起", "冲", "杀", "打"]):
            details.append("以动作开篇")
            score += 30

        # 检查是否有冲突词
        conflict_words = ["追杀", "陷害", "羞辱", "退婚", "背叛", "死亡", "危机", "危险"]
        if any(word in first_500 for word in conflict_words):
            details.append("前500字出现冲突")
            score += 40

        # 检查是否有悬念词
        suspense_words = ["原来", "竟然", "居然", "不知", "神秘", "诡异", "奇怪"]
        if any(word in first_500 for word in suspense_words):
            details.append("前500字设置悬念")
            score += 20

        passed = score >= 50

        return {
            "passed": passed,
            "score": min(score, 100),
            "details": details if details else ["未检测到明显的钩子元素"]
        }

    def _check_conflict_rule(self, rule: GoldenThreeRule, content: str, content_lower: str) -> Dict[str, Any]:
        """检测冲突规则"""
        details = []
        score = 0

        # 检查冲突关键词
        conflict_keywords = [
            "追杀", "陷害", "羞辱", "退婚", "背叛", "死亡", "危机", "危险",
            "敌人", "对手", "挑战", "威胁", "逼迫", "压迫", "冲突", "矛盾",
            "争斗", "战斗", "战争", "仇恨", "怨气", "不甘"
        ]

        found_conflicts = [kw for kw in conflict_keywords if kw in content]
        if found_conflicts:
            details.append(f"发现冲突元素: {', '.join(found_conflicts[:5])}")
            score += min(len(found_conflicts) * 10, 50)

        # 检查是否有解决的暗示
        solution_keywords = ["希望", "机会", "转机", "突破", "发现", "找到", "获得"]
        found_solutions = [kw for kw in solution_keywords if kw in content]
        if found_solutions:
            details.append(f"发现解决方向: {', '.join(found_solutions[:3])}")
            score += 30

        passed = score >= 40

        return {
            "passed": passed,
            "score": min(score, 100),
            "details": details if details else ["未检测到明显的冲突元素"]
        }

    def _check_protagonist_rule(self, rule: GoldenThreeRule, content: str, content_lower: str) -> Dict[str, Any]:
        """检测主角规则"""
        details = []
        score = 0

        # 主角常见称呼
        protagonist_names = ["林风", "叶凡", "萧炎", "唐三", "罗峰", "主角", "少年", "青年", "男子"]

        # 检查主角出场
        for name in protagonist_names:
            if name in content[:len(content)//3]:
                details.append(f"主角 '{name}' 在前1/3出场")
                score += 30
                break

        # 检查目标关键词
        goal_keywords = ["目标", "梦想", "追求", "想要", "希望", "决心", "誓言"]
        found_goals = [kw for kw in goal_keywords if kw in content]
        if found_goals:
            details.append(f"发现目标元素: {', '.join(found_goals[:3])}")
            score += 25

        # 检查金手指
        golden_finger_keywords = ["系统", "金手指", "宝物", "传承", "觉醒", "激活", "天赋", "异能"]
        found_gf = [kw for kw in golden_finger_keywords if kw in content]
        if found_gf:
            details.append(f"发现金手指元素: {', '.join(found_gf[:3])}")
            score += 25

        # 检查性格亮点
        personality_keywords = ["坚毅", "果断", "善良", "聪明", "勇敢", "冷静", "腹黑", "傲娇"]
        found_personality = [kw for kw in personality_keywords if kw in content]
        if found_personality:
            details.append(f"发现性格特点: {', '.join(found_personality[:3])}")
            score += 20

        passed = score >= 50

        return {
            "passed": passed,
            "score": min(score, 100),
            "details": details if details else ["未检测到明显的主角塑造元素"]
        }

    async def check_golden_three(
        self,
        project_id: str,
        chapters: Dict[int, str],
        genre: Optional[str] = None
    ) -> GoldenThreeCheckResult:
        """检测黄金三章"""
        await self.initialize()

        chapter_results = {}
        total_score = 0
        hook_scores = []
        conflict_scores = []
        protagonist_scores = []
        all_issues = []
        all_suggestions = []

        for chapter_num, content in chapters.items():
            result = await self.check_chapter(project_id, chapter_num, content, genre)
            chapter_results[chapter_num] = result
            total_score += result["score"]

            # 分类评分
            for rule_result in result["results"]:
                if rule_result["rule_type"] == "hook":
                    hook_scores.append(rule_result["score"])
                elif rule_result["rule_type"] == "conflict":
                    conflict_scores.append(rule_result["score"])
                elif rule_result["rule_type"] == "protagonist":
                    protagonist_scores.append(rule_result["score"])

            # 收集问题
            for issue in result["issues"]:
                if issue["severity"] == "critical":
                    all_issues.append(f"第{chapter_num}章: {issue['rule']}")

            all_suggestions.extend(result["suggestions"])

        # 计算各维度评分
        hook_score = sum(hook_scores) / len(hook_scores) if hook_scores else 0
        conflict_score = sum(conflict_scores) / len(conflict_scores) if conflict_scores else 0
        protagonist_score = sum(protagonist_scores) / len(protagonist_scores) if protagonist_scores else 0

        return GoldenThreeCheckResult(
            project_id=project_id,
            chapter_results=chapter_results,
            total_score=round(total_score / len(chapters), 1) if chapters else 0,
            hook_score=round(hook_score, 1),
            conflict_score=round(conflict_score, 1),
            protagonist_score=round(protagonist_score, 1),
            critical_issues=[i for i in all_issues if "必须" in i or "critical" in i.lower()],
            warnings=[i for i in all_issues if i not in all_issues[:3]],
            suggestions=list(dict.fromkeys(all_suggestions))[:10]
        )

    # ==================== 数据库操作 ====================

    async def _load_rules_from_db(self):
        """从数据库加载规则"""
        if not self.db:
            return

        query = "SELECT * FROM golden_three_rules WHERE is_active = true"
        rows = await self.db.fetch_all(query)

        for row in rows:
            rule = GoldenThreeRule(
                id=row["id"],
                rule_type=GoldenThreeRuleType(row["rule_type"]),
                rule_name=row["rule_name"],
                description=row["description"],
                check_points=json.loads(row["check_points"] or "[]"),
                examples=json.loads(row["examples"] or "[]"),
                weight=row["weight"],
                severity=RuleSeverity(row["severity"]),
                applicable_genres=json.loads(row["applicable_genres"] or "[]"),
                applicable_chapter=row["applicable_chapter"],
                fix_suggestions=json.loads(row["fix_suggestions"] or "[]"),
                is_active=row["is_active"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            self._rules[rule.id] = rule

    async def _save_rule_to_db(self, rule: GoldenThreeRule):
        """保存规则到数据库"""
        if not self.db:
            return

        query = """
        INSERT INTO golden_three_rules
        (id, rule_type, rule_name, description, check_points, examples,
         weight, severity, applicable_genres, applicable_chapter, fix_suggestions,
         is_active, created_at, updated_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
        ON CONFLICT (id) DO UPDATE SET
            rule_name = $3,
            description = $4,
            check_points = $5,
            examples = $6,
            weight = $7,
            severity = $8,
            applicable_genres = $9,
            applicable_chapter = $10,
            fix_suggestions = $11,
            is_active = $12,
            updated_at = $14
        """
        await self.db.execute(
            query,
            rule.id,
            rule.rule_type.value,
            rule.rule_name,
            rule.description,
            json.dumps(rule.check_points),
            json.dumps(rule.examples),
            rule.weight,
            rule.severity.value,
            json.dumps(rule.applicable_genres),
            rule.applicable_chapter,
            json.dumps(rule.fix_suggestions),
            rule.is_active,
            rule.created_at,
            rule.updated_at,
        )

    async def _delete_rule_from_db(self, rule_id: str):
        """从数据库删除规则"""
        if not self.db:
            return

        await self.db.execute(
            "DELETE FROM golden_three_rules WHERE id = $1",
            rule_id
        )
