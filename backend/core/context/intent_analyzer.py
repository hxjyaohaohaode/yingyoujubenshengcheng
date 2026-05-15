import json
import re
import logging
from core.gateway.client import ModelGateway
from .intent_models import IntentResult, EntityInfo

logger = logging.getLogger(__name__)

INTENT_ANALYSIS_PROMPT = """你是一个剧本意图分析专家。请分析用户想要创作什么类型的故事。

用户输入：{user_input}

请返回JSON（只返回JSON，不返回其他内容）：
{{
  "genre": "故事题材",
  "style": "风格",
  "entities": [
    {{"name": "实体名称", "type": "character/location/event/concept", "importance": 0.0-1.0, "description": "简要描述"}}
  ],
  "key_events": ["关键事件"],
  "era": "时代背景",
  "world_elements": ["世界观要素"],
  "confidence": 0.0-1.0,
  "guiding_questions": [],
  "need_search": true/false
}}

规则：confidence<0.5表示输入模糊需引导。need_search=true表示需外部知识。真实历史人物/事件必须提取。"""


class IntentAnalyzer:
    def __init__(self, gateway: ModelGateway):
        self.gateway = gateway

    async def analyze(self, user_input: str) -> IntentResult:
        if not user_input or not user_input.strip():
            return IntentResult(
                confidence=0.0,
                guiding_questions=["请描述您想创作什么类型的故事？", "您想基于什么题材或背景？", "有没有参考作品或人物？"]
            )

        prompt = INTENT_ANALYSIS_PROMPT.format(user_input=user_input.strip())

        try:
            response = await self.gateway.invoke(
                intent="analyze.structure",
                messages=[{"role": "user", "content": prompt}],
                cost_profile="economy",
                temperature=0.3,
                use_cache=False,
            )
            parsed = self._parse_response(response.content)
            if parsed:
                return parsed
            return self._fallback_analyze(user_input)
        except Exception as e:
            logger.error("意图分析失败: %s", str(e)[:200])
            return self._fallback_analyze(user_input)

    def _parse_response(self, content: str) -> IntentResult | None:
        text = content.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group())
                except json.JSONDecodeError:
                    return None
            else:
                return None

        if not isinstance(data, dict):
            return None

        entities = []
        for e in data.get("entities", []):
            if isinstance(e, dict):
                entities.append(EntityInfo(
                    name=e.get("name", ""), type=e.get("type", "concept"),
                    importance=float(e.get("importance", 0.5)),
                    description=e.get("description", ""),
                ))

        return IntentResult(
            genre=data.get("genre", ""), style=data.get("style", ""),
            entities=entities, key_events=data.get("key_events", []),
            era=data.get("era", ""), world_elements=data.get("world_elements", []),
            confidence=float(data.get("confidence", 0.5)),
            guiding_questions=data.get("guiding_questions", []),
            need_search=data.get("need_search", True),
        )

    def _fallback_analyze(self, user_input: str) -> IntentResult:
        chinese_names = re.findall(r'[\u4e00-\u9fff]{2,4}(?:王|帝|后|将|相|子|公|侯|伯|夫|女|君)?', user_input)
        entities = []
        seen = set()
        for name in chinese_names:
            if name not in seen and len(name) >= 2:
                seen.add(name)
                entities.append(EntityInfo(name=name, type="character", importance=0.7))

        events = []
        event_keywords = ["卧薪尝胆", "灭吴", "争霸", "变法", "起义", "北伐", "西征", "统一", "建国"]
        for kw in event_keywords:
            if kw in user_input:
                events.append(kw)

        genre_map = {"改版": "历史改编", "穿越": "穿越", "修仙": "修仙玄幻", "科幻": "科幻", "悬疑": "悬疑",
                     "推理": "推理", "武侠": "武侠", "都市": "都市", "奇幻": "奇幻", "末日": "末日生存", "游戏": "游戏竞技"}
        genre = ""
        for k, v in genre_map.items():
            if k in user_input:
                genre = v
                break

        return IntentResult(
            genre=genre, entities=entities, key_events=events, confidence=0.6 if entities else 0.3,
            guiding_questions=[] if genre else ["请更具体地描述故事题材和风格"],
            need_search=bool(entities or events),
        )