"""
记忆提取器 - 从场景内容自动提取关键信息更新全局叙事记忆
仿RecurrentGPT的记忆更新机制：Input(场景内容+当前记忆) → LLM提取 → 更新记忆
"""
import json
from sqlalchemy.ext.asyncio import AsyncSession
from core.narrative.memory_store import (
    store_short_term_memory,
    store_long_term_memory
)
from core.gateway.client import get_gateway


async def extract_and_update_memory(
    db: AsyncSession,
    project_id: str,
    scene_id: str,
    chapter_id: str,
    scene_content: str,
    current_narrative_context: str = ""
) -> dict:
    """
    从场景内容提取关键信息并更新叙事记忆

    提取5类信息：
    1. character_changes: 角色状态变化 (姓名→当前状态)
    2. foreshadow_progress: 伏笔推进情况 (伏笔ID→推进描述)
    3. new_events: 新事件 (事件摘要+因果链接)
    4. relation_changes: 关系变化 (角色对→关系变化描述)
    5. worldbuilding_reveals: 世界观揭示 (新揭示的规则/设定)

    返回: {"updated": {...}, "summary": "..."}
    """
    gateway = get_gateway()
    if not gateway:
        return {"updated": {}, "summary": "记忆提取失败：LLM网关不可用", "error": True}

    system_prompt = """你是叙事记忆提取器。从给定的场景内容中提取以下5类关键信息，以JSON格式返回。

提取规则：
1. character_changes: 角色在本场景中发生了什么状态变化（情绪、位置、目标、身体状态等）
   格式: {"角色名": "状态变化描述"}
2. foreshadow_progress: 场景中推进或揭示了哪些伏笔
   格式: [{"foreshadow_id": "xxx", "progress": "推进描述", "status": "advanced/hinted/resolved"}]
3. new_events: 场景中发生了哪些新事件
   格式: [{"description": "事件摘要", "causes": "前因", "effects": "后果"}]
4. relation_changes: 角色间关系发生了什么变化
   格式: [{"characters": ["A", "B"], "change": "关系变化描述"}]
5. worldbuilding_reveals: 场景中揭示了哪些世界观信息
   格式: [{"aspect": "方面", "detail": "揭示的内容"}]

只提取明确在内容中出现的信息，不要臆测。如果没有某类信息，返回空数组/对象。"""

    user_prompt = f"""当前叙事上下文：
{current_narrative_context if current_narrative_context else "（新项目，无历史记忆）"}

场景内容（scene_id={scene_id}）：
{scene_content[:6000]}

请提取上述5类信息，返回纯JSON：{{"character_changes": {{}}, "foreshadow_progress": [], "new_events": [], "relation_changes": [], "worldbuilding_reveals": []}}"""

    try:
        response = await gateway.invoke(
            intent="analyze.extract_memory",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            cost_profile="economy",
            temperature=0.1,
            max_tokens=2000,
            model_override="ds-v4-pro",
        )

        content = response.content if hasattr(response, 'content') else str(response)
        result = _parse_json(content)

        updated = {}

        char_changes = result.get("character_changes", {})
        for char_name, change_desc in char_changes.items():
            if change_desc:
                await store_long_term_memory(
                    db, project_id, 'character', char_name,
                    f"角色：{char_name}。最新变化：{change_desc}（场景{scene_id}）"
                )
                updated[f"character:{char_name}"] = change_desc

        rel_changes = result.get("relation_changes", [])
        for rel in rel_changes:
            if isinstance(rel, dict) and rel.get("change"):
                chars_key = "-".join(sorted(rel.get("characters", [])))
                await store_long_term_memory(
                    db, project_id, 'relation', chars_key,
                    f"角色关系：{' ↔ '.join(rel.get('characters', []))}。变化：{rel['change']}（场景{scene_id}）"
                )

        new_events = result.get("new_events", [])
        for evt in new_events:
            if isinstance(evt, dict) and evt.get("description"):
                causes = evt.get("causes", "")
                effects = evt.get("effects", "")
                event_text = f"事件：{evt['description']}。前因：{causes}。后果：{effects}（场景{scene_id}）"
                await store_short_term_memory(
                    db, project_id, scene_id, chapter_id, 'timeline', None, event_text
                )

        fw_progress = result.get("foreshadow_progress", [])
        for fw in fw_progress:
            if isinstance(fw, dict) and fw.get("progress"):
                await store_long_term_memory(
                    db, project_id, 'foreshadow', fw.get("foreshadow_id", "unknown"),
                    f"伏笔：{fw.get('foreshadow_id', 'unknown')}。推进：{fw['progress']}。状态：{fw.get('status', 'advanced')}（场景{scene_id}）"
                )

        wb_reveals = result.get("worldbuilding_reveals", [])
        for wb in wb_reveals:
            if isinstance(wb, dict) and wb.get("detail"):
                await store_long_term_memory(
                    db, project_id, 'worldbuilding', wb.get("aspect", "general"),
                    f"世界观：{wb.get('aspect', 'general')}。揭示：{wb['detail']}（场景{scene_id}）"
                )

        return {
            "updated": updated,
            "summary": f"提取了{len(char_changes)}个角色变化、{len(new_events)}个事件、{len(fw_progress)}个伏笔推进",
            "error": False
        }

    except Exception as e:
        return {"updated": {}, "summary": f"记忆提取异常: {str(e)}", "error": True}


def _parse_json(text: str) -> dict:
    """从LLM响应中解析JSON"""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        import re
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return {"character_changes": {}, "foreshadow_progress": [], "new_events": [], "relation_changes": [], "worldbuilding_reveals": []}