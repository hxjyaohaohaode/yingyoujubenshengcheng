import json
import logging
from typing import Any, Optional

from core.search.brave_search import get_brave_search
from core.gateway.client import ModelGateway

logger = logging.getLogger(__name__)

WEB_SEARCH_TOOL_DEFINITION = {
    "type": "function",
    "function": {
        "name": "search_web",
        "description": "联网搜索获取实时信息、核实事实、获取专业领域知识。当需要确认历史事件细节、人物信息、地点特征、文化背景、科技知识或其他不确定的事实性信息时调用此工具。返回相关网页的摘要和来源。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词，需精确描述需要查询的信息，例如：'明代土木堡之变 时间地点 关键人物'",
                }
            },
            "required": ["query"],
        },
    },
}

WEB_SEARCH_SYSTEM_PROMPT_ADDON = """
## 联网搜索工具
你可以使用 search_web 工具来查询外部信息。当遇到以下情况时，你应该主动调用此工具：
1. 不确定的历史事件细节、时间、人物
2. 特定地域的文化习俗、建筑风格、自然景观
3. 专业领域知识（医学、法律、军事、科技等）
4. 现实世界的地点、机构、文物等

使用方式：在回复中输出以下格式来调用工具：
<tool_call>{"name": "search_web", "arguments": {"query": "你的搜索关键词"}}</tool_call>

系统会自动执行搜索并将结果返回给你，然后你可以基于搜索结果继续生成内容。
"""


async def execute_search_tool(query: str, gateway: Optional[ModelGateway] = None) -> dict[str, Any]:
    brave = get_brave_search()
    result = await brave.search_and_summarize(query, gateway)
    return result


def parse_tool_calls(text: str) -> list[dict]:
    calls = []
    import re
    pattern = re.compile(r'<tool_call>(.*?)</tool_call>', re.DOTALL)
    for match in pattern.finditer(text):
        try:
            call_data = json.loads(match.group(1).strip())
            if call_data.get("name") == "search_web":
                calls.append(call_data)
        except json.JSONDecodeError:
            logger.warning("无法解析tool_call: %s", match.group(1)[:200])
    return calls


def format_search_results_for_agent(results: dict) -> str:
    lines = ["## 联网搜索结果\n"]
    if results.get("summary"):
        lines.append(f"### 综合摘要\n{results['summary']}\n")
    if results.get("sources"):
        lines.append("### 信息来源")
        for s in results["sources"]:
            lines.append(f"- [{s.get('title', '未知')}]({s.get('url', '')})")
            if s.get("snippet"):
                lines.append(f"  摘要: {s['snippet'][:200]}")
    return "\n".join(lines)


async def auto_research_if_needed(
    prompt: str,
    gateway: Optional[ModelGateway] = None,
    max_searches: int = 3,
) -> str:
    import re

    research_prompt = f"""分析以下剧本创作提示，判断是否需要联网搜索来获取准确信息。
如果需要，列出最多{max_searches}个关键搜索词（每行一个，以"SEARCH:"开头）。
如果不需要搜索，回复"NO_SEARCH"。

提示内容：
{prompt[:2000]}

判断标准：
- 是否包含真实历史事件、人物、地点？
- 是否涉及专业领域知识？
- 是否有需要核实的文化或科技细节？

回复格式（如需要搜索）：
SEARCH: 关键词1
SEARCH: 关键词2
SEARCH: 关键词3

或回复 NO_SEARCH"""

    if not gateway:
        return ""

    try:
        response = await gateway.invoke(
            intent="analyze.research",
            messages=[{"role": "user", "content": research_prompt}],
            cost_profile="economy",
            temperature=0.1,
            max_tokens=256,
            use_cache=True,
        )
        text = response.content.strip()
    except Exception as e:
        logger.warning("auto_research分析失败: %s", str(e)[:100])
        return ""

    if "NO_SEARCH" in text.upper():
        return ""

    queries = re.findall(r'SEARCH:\s*(.+)', text)
    if not queries:
        return ""

    queries = queries[:max_searches]
    logger.info("auto_research: 需要搜索 %d 个关键词", len(queries))

    brave = get_brave_search()
    all_results = []
    for query in queries:
        try:
            result = await brave.search_and_summarize(query.strip(), gateway)
            all_results.append(result)
        except Exception as e:
            logger.warning("auto_research搜索失败 '%s': %s", query, str(e)[:100])

    if not all_results:
        return ""

    context_parts = ["\n\n## 自动联网研究结果（AI在创作前核实的知识）\n"]
    for r in all_results:
        context_parts.append(format_search_results_for_agent(r))
        context_parts.append("")

    return "\n".join(context_parts)