-- V12: 分段生成 Skill
-- 为长文本生成提供智能分段能力，供 Writer 和 SceneCoordinator 使用

-- ==================== 分段生成 Skill ====================
INSERT INTO skills (
    id, name, description, skill_type, category, tags,
    applicable_agent_types, function_code,
    parameters, output_spec,
    temperature, max_tokens, priority, status, is_system, is_enabled, is_composable,
    version, author, examples
) VALUES (
    'skill_segmented_writing',
    '分段生成',
    '智能分段生成长文本内容，自动规划段落结构，确保内容丰富完整',
    'function',
    'writing',
    '["writing", "content-generation", "segmented", "long-form"]',
    '["writer", "scene_coordinator", "summarizer"]',
    '
import re
import json

def execute(target_word_count, content_type="narrative", context="", existing_content="", segment_count=None):
    """
    分段生成长文本内容

    Args:
        target_word_count: 目标字数
        content_type: 内容类型 (narrative/dialogue/scene/description)
        context: 上下文信息（大纲、角色、场景等）
        existing_content: 已有内容（续写时）
        segment_count: 指定分段数（可选，默认自动计算）

    Returns:
        dict: 分段规划结果
    """
    # 参数校验
    target_word_count = int(target_word_count) if target_word_count else 1500
    if target_word_count < 500:
        return {"error": "目标字数太少，不适合分段生成", "segment_count": 1}

    # 自动计算分段数
    if not segment_count:
        if target_word_count <= 800:
            segment_count = 1
        elif target_word_count <= 1500:
            segment_count = 2
        elif target_word_count <= 3000:
            segment_count = 3
        elif target_word_count <= 5000:
            segment_count = 4
        else:
            segment_count = min(6, target_word_count // 1200)

    segment_count = int(segment_count)
    words_per_segment = target_word_count // segment_count

    # 分段规划模板
    segment_templates = {
        "narrative": [
            {"phase": "开端", "focus": "引入场景，建立氛围，铺垫情节", "weight": 1.0},
            {"phase": "发展", "focus": "推进情节，展开冲突，深化角色", "weight": 1.2},
            {"phase": "高潮", "focus": "情节高点，情感爆发，关键转折", "weight": 1.3},
            {"phase": "收尾", "focus": "情节收束，伏笔埋设，过渡下章", "weight": 0.8},
        ],
        "dialogue": [
            {"phase": "开场对话", "focus": "建立话题，展现人物性格", "weight": 1.0},
            {"phase": "深入交流", "focus": "揭示信息，推进关系", "weight": 1.2},
            {"phase": "冲突/转折", "focus": "对话高潮，观点碰撞", "weight": 1.3},
            {"phase": "对话收束", "focus": "达成共识或留下悬念", "weight": 0.9},
        ],
        "scene": [
            {"phase": "场景建立", "focus": "环境描写，氛围营造", "weight": 1.0},
            {"phase": "行动展开", "focus": "角色行动，事件推进", "weight": 1.2},
            {"phase": "场景高潮", "focus": "关键事件，情感高点", "weight": 1.3},
            {"phase": "场景收尾", "focus": "事件收束，过渡衔接", "weight": 0.8},
        ],
        "description": [
            {"phase": "整体印象", "focus": "宏观描述，第一印象", "weight": 1.0},
            {"phase": "细节刻画", "focus": "具体细节，感官体验", "weight": 1.2},
            {"phase": "动态呈现", "focus": "变化过程，互动效果", "weight": 1.0},
            {"phase": "意境升华", "focus": "情感共鸣，象征意义", "weight": 0.9},
        ],
    }

    # 获取适合的模板
    template = segment_templates.get(content_type, segment_templates["narrative"])

    # 调整模板以匹配分段数
    if segment_count <= len(template):
        selected_segments = template[:segment_count]
    else:
        # 需要扩展模板
        selected_segments = template.copy()
        extra_count = segment_count - len(template)
        for i in range(extra_count):
            idx = len(selected_segments)
            selected_segments.append({
                "phase": f"延续{idx}",
                "focus": "继续展开内容，保持节奏",
                "weight": 1.0,
            })

    # 构建分段规划
    segments = []
    total_weight = sum(s["weight"] for s in selected_segments)

    for i, seg in enumerate(selected_segments):
        # 按权重分配字数
        seg_words = int(words_per_segment * seg["weight"] * segment_count / total_weight)
        if i == segment_count - 1:
            # 最后一段补足剩余字数
            seg_words = target_word_count - sum(s["word_count"] for s in segments)

        segments.append({
            "segment_id": i + 1,
            "phase": seg["phase"],
            "focus": seg["focus"],
            "target_word_count": max(200, seg_words),
            "weight": seg["weight"],
        })

    # 生成规划摘要
    plan_summary = f"分段规划：{segment_count}段，目标{target_word_count}字"
    if context:
        plan_summary += f"，基于上下文生成"

    return {
        "success": True,
        "segment_count": segment_count,
        "target_word_count": target_word_count,
        "words_per_segment": words_per_segment,
        "content_type": content_type,
        "segments": segments,
        "plan_summary": plan_summary,
        "execution_hint": "请按 segments 顺序逐段生成，每段达到 target_word_count 后进入下一段",
    }
',
    '[{"name": "target_word_count", "type": "integer", "required": true, "description": "目标字数"}, {"name": "content_type", "type": "string", "required": false, "default": "narrative", "description": "内容类型: narrative/dialogue/scene/description"}, {"name": "context", "type": "string", "required": false, "description": "上下文信息"}, {"name": "existing_content", "type": "string", "required": false, "description": "已有内容（续写时）"}, {"name": "segment_count", "type": "integer", "required": false, "description": "指定分段数"}]',
    '[{"name": "success", "type": "boolean", "description": "是否成功"}, {"name": "segment_count", "type": "integer", "description": "分段数量"}, {"name": "segments", "type": "array", "description": "分段规划列表"}, {"name": "plan_summary", "type": "string", "description": "规划摘要"}, {"name": "execution_hint", "type": "string", "description": "执行提示"}]',
    0.3,
    500,
    80,
    'active',
    true,
    true,
    true,
    '1.0.0',
    'system',
    '[{"input": {"target_word_count": 3000, "content_type": "narrative"}, "output": {"segment_count": 4, "plan_summary": "分段规划：4段，目标3000字"}}]'
);

-- ==================== 字数统计 Skill ====================
INSERT INTO skills (
    id, name, description, skill_type, category, tags,
    applicable_agent_types, function_code,
    parameters, output_spec,
    temperature, max_tokens, priority, status, is_system, is_enabled, is_composable,
    version, author
) VALUES (
    'skill_word_count',
    '字数统计',
    '精确统计文本字数，支持中英文混合，返回详细统计信息',
    'function',
    'analysis',
    '["word-count", "analysis", "text"]',
    '["writer", "scene_coordinator", "evaluator", "summarizer"]',
    '
import re

def execute(text, count_type="all"):
    """
    统计文本字数

    Args:
        text: 要统计的文本
        count_type: 统计类型 (all/chinese/english/chars)

    Returns:
        dict: 统计结果
    """
    if not text:
        return {"total_count": 0, "chinese_count": 0, "english_count": 0, "char_count": 0}

    # 中文统计（包括标点）
    chinese_chars = re.findall(r"[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]", text)
    chinese_count = len(chinese_chars)

    # 英文单词统计
    english_words = re.findall(r"\b[a-zA-Z]+\b", text)
    english_count = len(english_words)

    # 字符统计（不含空白）
    char_count = len(re.sub(r"\s", "", text))

    # 总字数（中文+英文单词数）
    total_count = chinese_count + english_count

    return {
        "success": True,
        "total_count": total_count,
        "chinese_count": chinese_count,
        "english_count": english_count,
        "char_count": char_count,
        "detail": {
            "chinese_chars": chinese_count,
            "english_words": english_count,
            "total_chars": len(text),
            "non_whitespace_chars": char_count,
        }
    }
',
    '[{"name": "text", "type": "string", "required": true, "description": "要统计的文本"}, {"name": "count_type", "type": "string", "required": false, "default": "all", "description": "统计类型: all/chinese/english/chars"}]',
    '[{"name": "success", "type": "boolean"}, {"name": "total_count", "type": "integer", "description": "总字数"}, {"name": "chinese_count", "type": "integer", "description": "中文字数"}, {"name": "english_count", "type": "integer", "description": "英文单词数"}, {"name": "char_count", "type": "integer", "description": "字符数"}]',
    0.1,
    100,
    90,
    'active',
    true,
    true,
    true,
    '1.0.0',
    'system'
);

-- ==================== 内容合并 Skill ====================
INSERT INTO skills (
    id, name, description, skill_type, category, tags,
    applicable_agent_types, function_code,
    parameters, output_spec,
    temperature, max_tokens, priority, status, is_system, is_enabled, is_composable,
    version, author
) VALUES (
    'skill_content_merge',
    '内容合并',
    '将多个分段内容智能合并为完整文本，处理衔接和重复',
    'function',
    'writing',
    '["merge", "content", "segments"]',
    '["writer", "scene_coordinator"]',
    '
import re

def execute(segments, merge_style="smooth", add_transitions=True):
    """
    合并分段内容

    Args:
        segments: 分段内容列表
        merge_style: 合并风格 (smooth/direct/chapter)
        add_transitions: 是否添加过渡

    Returns:
        dict: 合并结果
    """
    if not segments:
        return {"success": False, "error": "没有内容可合并"}

    if isinstance(segments, str):
        # 如果传入的是字符串，尝试解析
        import json
        try:
            segments = json.loads(segments)
        except:
            return {"success": False, "error": "segments 格式错误"}

    if len(segments) == 1:
        return {
            "success": True,
            "merged_content": segments[0] if isinstance(segments[0], str) else segments[0].get("content", ""),
            "segment_count": 1,
        }

    # 提取内容
    contents = []
    for seg in segments:
        if isinstance(seg, str):
            contents.append(seg)
        elif isinstance(seg, dict):
            contents.append(seg.get("content", ""))
        else:
            contents.append(str(seg))

    # 过滤空内容
    contents = [c for c in contents if c and c.strip()]

    if not contents:
        return {"success": False, "error": "所有分段内容为空"}

    # 合并策略
    if merge_style == "smooth" and add_transitions:
        # 平滑合并，添加过渡
        merged = contents[0]
        for i, content in enumerate(contents[1:], 1):
            # 检查是否需要过渡
            if not merged.endswith(("。", "！", "？", """, "」", "\n")):
                merged += "。"
            if not content.startswith(("「", """, "\n", "（")):
                merged += "\n\n"
            merged += content
    elif merge_style == "chapter":
        # 章节合并，添加分隔
        merged = ""
        for i, content in enumerate(contents):
            if i > 0:
                merged += "\n\n***\n\n"
            merged += content
    else:
        # 直接合并
        merged = "\n\n".join(contents)

    # 清理多余空白
    merged = re.sub(r"\n{3,}", "\n\n", merged)
    merged = re.sub(r" {2,}", " ", merged)

    return {
        "success": True,
        "merged_content": merged,
        "segment_count": len(contents),
        "total_length": len(merged),
        "merge_style": merge_style,
    }
',
    '[{"name": "segments", "type": "array", "required": true, "description": "分段内容列表"}, {"name": "merge_style", "type": "string", "required": false, "default": "smooth", "description": "合并风格: smooth/direct/chapter"}, {"name": "add_transitions", "type": "boolean", "required": false, "default": true, "description": "是否添加过渡"}]',
    '[{"name": "success", "type": "boolean"}, {"name": "merged_content", "type": "string", "description": "合并后的内容"}, {"name": "segment_count", "type": "integer", "description": "分段数"}, {"name": "total_length", "type": "integer", "description": "总长度"}]',
    0.1,
    100,
    75,
    'active',
    true,
    true,
    true,
    '1.0.0',
    'system'
);

-- ==================== 分配 Skills 到 Agent ====================
-- Writer Agent
INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled) VALUES
('sa_writer_seg', 'skill_segmented_writing', 'writer', 'planning', 80, true),
('sa_writer_count', 'skill_word_count', 'writer', 'analysis', 90, true),
('sa_writer_merge', 'skill_content_merge', 'writer', 'postprocessing', 75, true);

-- SceneCoordinator Agent
INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled) VALUES
('sa_scene_seg', 'skill_segmented_writing', 'scene_coordinator', 'planning', 80, true),
('sa_scene_count', 'skill_word_count', 'scene_coordinator', 'analysis', 90, true),
('sa_scene_merge', 'skill_content_merge', 'scene_coordinator', 'postprocessing', 75, true);

-- Evaluator Agent
INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled) VALUES
('sa_eval_count', 'skill_word_count', 'evaluator', 'analysis', 85, true);

-- Summarizer Agent
INSERT INTO skill_assignments (id, skill_id, agent_type, slot_name, priority, is_enabled) VALUES
('sa_sum_count', 'skill_word_count', 'summarizer', 'analysis', 80, true);

-- 注释
COMMENT ON SKILL skill_segmented_writing IS '分段生成 Skill - 智能规划长文本分段结构';
COMMENT ON SKILL skill_word_count IS '字数统计 Skill - 精确统计中英文字数';
COMMENT ON SKILL skill_content_merge IS '内容合并 Skill - 智能合并分段内容';
