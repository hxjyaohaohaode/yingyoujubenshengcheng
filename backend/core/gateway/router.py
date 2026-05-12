"""
模型路由器: 根据任务意图 + 成本策略自动选择模型。

用法:
    router = ModelRouter()
    model = router.select_model("write.prose", cost_profile="balanced")
    # => "mimo-v2-pro"
"""

from enum import Enum


class CostProfile(Enum):
    ECONOMY = "economy"
    BALANCED = "balanced"
    QUALITY = "quality"


ROUTING_TABLE = {
    "write.prose": {
        "models": ["ds-v4-pro"],
        "fallback": ["mimo-v2-pro"],
        "reason": "DeepSeek V4 Pro 中文创作深度最强",
    },
    "write.dialogue": {
        "models": ["ds-v4-pro"],
        "fallback": ["mimo-v2-pro"],
        "reason": "DeepSeek V4 Pro 对白风格化能力强",
    },
    "write.creative": {
        "models": ["ds-v4-pro"],
        "fallback": ["mimo-v2-pro"],
        "reason": "需要深度推理的创意任务",
    },
    "write.outline": {
        "models": ["ds-v4-pro"],
        "fallback": ["mimo-v2-pro"],
        "reason": "大纲需要结构化推理",
    },

    "reason.logic": {
        "models": ["ds-v4-flash"],
        "fallback": ["mimo-v2.5-pro"],
        "reason": "逻辑校验，Flash 性价比最优",
    },
    "reason.causal": {
        "models": ["ds-v4-pro"],
        "fallback": ["ds-v4-flash"],
        "reason": "因果链分析需要深度",
    },
    "reason.complex": {
        "models": ["ds-reasoner"],
        "fallback": ["ds-v4-pro"],
        "reason": "复杂推理（伏笔依赖链等）",
    },

    "analyze.consistency": {
        "models": ["mimo-v2-omni"],
        "fallback": ["mimo-v2.5"],
        "reason": "全模态审计，视觉+文本一致性",
    },
    "analyze.creative": {
        "models": ["ds-v4-pro"],
        "fallback": ["ds-v4-flash"],
        "reason": "创意评分需要审美能力",
    },
    "analyze.structure": {
        "models": ["mimo-v2.5-pro", "ds-v4-pro"],
        "fallback": ["ds-v4-pro", "mimo-v2-pro", "mimo-v2.5"],
        "reason": "结构分析，MiMo首选，DeepSeek强回退",
    },

    "manage.state": {
        "models": ["mimo-v2.5"],
        "fallback": ["ds-v4-flash"],
        "reason": "状态更新，最便宜的模型",
    },
    "manage.context": {
        "models": ["mimo-v2.5"],
        "fallback": ["ds-v4-flash"],
        "reason": "上下文组装，轻量任务",
    },
    "manage.orchestrate": {
        "models": ["mimo-v2-pro"],
        "fallback": ["mimo-v2.5-pro"],
        "reason": "编排调度，需要指令遵循能力",
    },

    "embed.text": {
        "models": ["ds-embed"],
        "fallback": [],
        "reason": "DeepSeek Embedding，中文效果好",
    },

    "planning": {
        "models": ["mimo-v2-pro"],
        "fallback": ["mimo-v2.5-pro"],
        "reason": "编排调度、状态管理、上下文组装等规划任务",
    },
    "search": {
        "models": ["mimo-v2.5"],
        "fallback": ["ds-v4-flash"],
        "reason": "RAG检索、索引查询等搜索任务",
    },
    "analyze.audit": {
        "models": ["ds-v4-pro"],
        "fallback": ["ds-v4-flash"],
        "reason": "全剧终审，需要深度分析能力",
    },
}

COST_PROFILES = {
    CostProfile.ECONOMY: {
        "prefer_fallback": True,
        "enable_thinking": False,
        "max_tokens": 16384,
    },
    CostProfile.BALANCED: {
        "prefer_fallback": False,
        "enable_thinking": False,
        "max_tokens": 32768,
    },
    CostProfile.QUALITY: {
        "prefer_fallback": False,
        "enable_thinking": True,
        "max_tokens": 64000,
    },
}

COST_PROFILE_STR_MAP = {
    "economy": CostProfile.ECONOMY,
    "balanced": CostProfile.BALANCED,
    "quality": CostProfile.QUALITY,
}


def resolve_cost_profile(profile_str: str) -> CostProfile:
    return COST_PROFILE_STR_MAP.get(profile_str, CostProfile.BALANCED)


class ModelRouter:
    """根据意图和成本策略选择模型"""

    def select_model(self, intent: str,
                     cost_profile: CostProfile = CostProfile.BALANCED) -> str:
        route = ROUTING_TABLE.get(intent)
        if not route:
            raise ValueError(f"Unknown intent: {intent}")

        profile = COST_PROFILES[cost_profile]

        if profile["prefer_fallback"] and route["fallback"]:
            return route["fallback"][0]
        return route["models"][0]

    def get_fallbacks(self, intent: str) -> list[str]:
        route = ROUTING_TABLE.get(intent, {})
        return route.get("fallback", [])

    def get_thinking_config(self, intent: str,
                           cost_profile: CostProfile) -> dict | None:
        profile = COST_PROFILES[cost_profile]
        if not profile["enable_thinking"]:
            return None

        route = ROUTING_TABLE.get(intent, {})
        primary = route["models"][0]

        if primary == "ds-v4-pro":
            return {"type": "enabled", "budget": 32768}
        return None
