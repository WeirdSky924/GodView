"""
文本处理工具函数
"""

import re
from typing import Tuple


def count_chinese_chars(text: str) -> int:
    """
    统计中文字符数

    Args:
        text: 输入文本

    Returns:
        int: 中文字符数
    """
    if not text:
        return 0
    # 匹配中文字符范围
    chinese_pattern = re.compile(r'[\u4e00-\u9fff]')
    return len(chinese_pattern.findall(text))


def count_english_words(text: str) -> int:
    """
    统计英文单词数

    Args:
        text: 输入文本

    Returns:
        int: 英文单词数
    """
    if not text:
        return 0
    # 匹配英文单词
    english_pattern = re.compile(r'\b[a-zA-Z]+\b')
    return len(english_pattern.findall(text))


def count_mixed_text(text: str) -> int:
    """
    统计混合文本的字数（中文按字计，英文按词计）

    这是网文常用的字数统计方式

    Args:
        text: 输入文本

    Returns:
        int: 总字数
    """
    if not text:
        return 0

    chinese_count = count_chinese_chars(text)
    english_count = count_english_words(text)

    # 标点符号和数字按 0.5 个字计算
    punctuation_pattern = re.compile(r'[，。！？、；：""''（）【】《》\.,!?;:\'\"\(\)\[\]{}<>0-9]+')
    punctuation_count = len(punctuation_pattern.findall(text)) * 0.5

    return int(chinese_count + english_count + punctuation_count)


def count_total_chars(text: str) -> int:
    """
    统计总字符数（包含所有字符）

    Args:
        text: 输入文本

    Returns:
        int: 总字符数
    """
    if not text:
        return 0
    # 移除空白字符后统计
    return len(text.replace(' ', '').replace('\n', '').replace('\t', ''))


def validate_word_count(
    text: str,
    target: int,
    tolerance: float = 0.1,
    min_ratio: float = 0.8,
) -> Tuple[bool, int, str]:
    """
    验证字数是否达标

    Args:
        text: 输入文本
        target: 目标字数
        tolerance: 允许的误差范围（默认10%）
        min_ratio: 最低完成比例（默认80%）

    Returns:
        Tuple[bool, int, str]: (是否达标, 实际字数, 状态消息)
    """
    actual_count = count_mixed_text(text)
    min_required = int(target * min_ratio)
    max_allowed = int(target * (1 + tolerance))

    if actual_count < min_required:
        return (
            False,
            actual_count,
            f"字数不足：实际 {actual_count} 字，最低要求 {min_required} 字（目标 {target} 字的 {int(min_ratio*100)}%），差 {min_required - actual_count} 字"
        )
    elif actual_count > max_allowed:
        return (
            True,  # 超字也算达标
            actual_count,
            f"字数超标：实际 {actual_count} 字，目标 {target} 字（允许上限 {max_allowed} 字），超出 {actual_count - target} 字"
        )
    else:
        return (
            True,
            actual_count,
            f"字数达标：实际 {actual_count} 字，目标 {target} 字"
        )


def analyze_text_structure(text: str) -> dict:
    """
    分析文本结构

    Args:
        text: 输入文本

    Returns:
        dict: 结构分析结果
    """
    if not text:
        return {
            "total_chars": 0,
            "chinese_chars": 0,
            "english_words": 0,
            "paragraphs": 0,
            "dialogues": 0,
            "avg_paragraph_length": 0,
        }

    # 统计段落
    paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
    paragraph_count = len(paragraphs)

    # 统计对话（引号内容）
    dialogue_pattern = re.compile(r'[""「」『』](.*?)[""「」『』]')
    dialogues = dialogue_pattern.findall(text)

    return {
        "total_chars": count_total_chars(text),
        "chinese_chars": count_chinese_chars(text),
        "english_words": count_english_words(text),
        "word_count": count_mixed_text(text),
        "paragraphs": paragraph_count,
        "dialogues": len(dialogues),
        "avg_paragraph_length": count_mixed_text(text) / paragraph_count if paragraph_count > 0 else 0,
    }
