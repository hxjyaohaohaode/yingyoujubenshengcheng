"""
剧本解析器 - 支持 .txt / .md / .docx 格式
- 提取章节/场景划分
- 提取角色名称和基本信息
- 提取关键事件和伏笔线索
- 构建初始叙事记忆
"""
import re
import uuid
from dataclasses import dataclass, field
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class ParsedScript:
    title: str = ""
    chapters: list[dict] = field(default_factory=list)
    characters: list[dict] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    total_words: int = 0


def detect_chapter_boundaries(text: str) -> list[tuple[int, int, str]]:
    patterns = [
        r'(?:第[一二三四五六七八九十百千\d]+章[^\n]*)',
        r'(?:CHAPTER\s+\d+[^\n]*)',
        r'(?:^#{1,3}\s+[^\n]+)',
        r'(?:第[一二三四五六七八九十百千\d]+节[^\n]*)',
    ]
    boundaries = []
    for pattern in patterns:
        for m in re.finditer(pattern, text, re.MULTILINE | re.IGNORECASE):
            boundaries.append((m.start(), m.group().strip()))
    boundaries.sort()
    return boundaries


def extract_characters(text: str) -> list[dict]:
    dialogue_pattern = re.findall(r'([^\s，。；：""''（）()\n]{2,4})(?:说|道|问|答|喊|叫|骂|笑|哭|叹|曰)[：:]', text)
    name_counts = {}
    for name in dialogue_pattern:
        if name not in name_counts:
            name_counts[name] = 0
        name_counts[name] += 1
    characters = []
    for name, count in sorted(name_counts.items(), key=lambda x: -x[1]):
        if count >= 2:
            characters.append({"name": name, "description": "", "mention_count": count})
    return characters[:20]


def parse_script_content(text: str, filename: str = "") -> ParsedScript:
    result = ParsedScript()
    result.total_words = len(re.findall(r'[\u4e00-\u9fff]', text))

    boundaries = detect_chapter_boundaries(text)
    if boundaries:
        for i, (pos, title) in enumerate(boundaries):
            start = pos
            end = boundaries[i+1][0] if i+1 < len(boundaries) else len(text)
            chapter_text = text[start:end]
            result.chapters.append({
                "index": i+1,
                "title": title,
                "content": chapter_text[:500] + "..." if len(chapter_text) > 500 else chapter_text,
                "word_count": len(re.findall(r'[\u4e00-\u9fff]', chapter_text))
            })
    else:
        result.chapters.append({
            "index": 1,
            "title": filename or "正文",
            "content": text[:500] + "..." if len(text) > 500 else text,
            "word_count": result.total_words
        })

    result.characters = extract_characters(text)

    return result


async def build_narrative_memory_from_script(db: AsyncSession, project_id: str, parsed: ParsedScript):
    from core.narrative.memory_store import store_short_term_memory, store_long_term_memory

    for char in parsed.characters:
        content = f"角色：{char['name']}。初始状态：刚出场。说话风格：待分析。提及次数：{char['mention_count']}次。"
        await store_long_term_memory(db, project_id, 'character', char['name'], content)

    for ch in parsed.chapters[-3:]:
        content = f"第{ch['index']}章「{ch['title']}」共{ch['word_count']}字。摘要：{ch['content'][:200]}"
        await store_short_term_memory(db, project_id, None, str(ch['index']), 'timeline', None, content)

    return {"characters": len(parsed.characters), "chapters": len(parsed.chapters), "total_words": parsed.total_words}