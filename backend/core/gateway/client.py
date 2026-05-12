"""
统一模型调用入口。
Agent 不直接调 DeepSeek/MiMo API，全部通过 ModelGateway。
全局单例模式，复用httpx连接池。

用法:
    gateway = get_gateway()
    response = await gateway.invoke(
        intent="write.prose",
        messages=[{"role": "user", "content": "写一个场景..."}],
        cost_profile="balanced"
    )
"""

import os
import httpx
import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Optional

from .router import ModelRouter, CostProfile, COST_PROFILES

logger = logging.getLogger(__name__)


@dataclass
class ModelResponse:
    content: str
    model: str
    input_tokens: int
    output_tokens: int
    cost: float
    cached: bool = False


MODEL_CONFIG = {
    "ds-v4-pro": {
        "base_url": "https://api.deepseek.com/v1",
        "api_key_env": "DEEPSEEK_API_KEY",
        "api_name": "deepseek-chat",
        "input_price": 3.0,
        "cached_input_price": 0.025,
        "output_price": 6.0,
    },
    "ds-v4-flash": {
        "base_url": "https://api.deepseek.com/v1",
        "api_key_env": "DEEPSEEK_API_KEY",
        "api_name": "deepseek-chat",
        "input_price": 1.0,
        "cached_input_price": 0.02,
        "output_price": 2.0,
    },
    "ds-reasoner": {
        "base_url": "https://api.deepseek.com/v1",
        "api_key_env": "DEEPSEEK_API_KEY",
        "api_name": "deepseek-reasoner",
        "input_price": 4.0,
        "cached_input_price": 0.5,
        "output_price": 16.0,
    },
    "mimo-v2-pro": {
        "base_url": "https://token-plan-cn.xiaomimimo.com/v1",
        "api_key_env": "MIMO_API_KEY",
        "api_name": "mimo-v2-pro",
        "input_price": 1.0,
        "cached_input_price": 0.5,
        "output_price": 3.0,
    },
    "mimo-v2.5-pro": {
        "base_url": "https://token-plan-cn.xiaomimimo.com/v1",
        "api_key_env": "MIMO_API_KEY",
        "api_name": "mimo-v2.5-pro",
        "input_price": 1.5,
        "cached_input_price": 0.75,
        "output_price": 4.0,
    },
    "mimo-v2.5": {
        "base_url": "https://token-plan-cn.xiaomimimo.com/v1",
        "api_key_env": "MIMO_API_KEY",
        "api_name": "mimo-v2.5",
        "input_price": 0.5,
        "cached_input_price": 0.25,
        "output_price": 1.5,
    },
    "mimo-v2-omni": {
        "base_url": "https://token-plan-cn.xiaomimimo.com/v1",
        "api_key_env": "MIMO_API_KEY",
        "api_name": "mimo-v2-omni",
        "input_price": 1.0,
        "cached_input_price": 0.5,
        "output_price": 3.0,
    },
    "ds-embed": {
        "base_url": "https://api.deepseek.com/v1",
        "api_key_env": "DEEPSEEK_API_KEY",
        "api_name": "deepseek-embed",
        "input_price": 1.0,
        "cached_input_price": 0.1,
        "output_price": 0,
    },
}

_global_gateway: Optional["ModelGateway"] = None


def get_gateway(redis_client=None) -> "ModelGateway":
    global _global_gateway
    if _global_gateway is None:
        _global_gateway = ModelGateway(redis_client=redis_client)
    return _global_gateway


class ModelGateway:
    """统一模型调用网关"""

    def __init__(self, redis_client=None):
        self.router = ModelRouter()
        self.redis = redis_client
        self._clients: dict[str, httpx.AsyncClient] = {}

    async def invoke(
        self,
        intent: str,
        messages: list[dict],
        cost_profile: str = "balanced",
        max_tokens: int | None = None,
        temperature: float = 0.7,
        use_cache: bool = True,
        model_override: str | None = None,
    ) -> ModelResponse:
        if model_override:
            model = model_override
            profile = CostProfile(cost_profile)
        else:
            profile = CostProfile(cost_profile)
            model = self.router.select_model(intent, profile)
        config = MODEL_CONFIG[model]

        if use_cache and self.redis:
            cache_key = self._cache_key(model, messages)
            cached = await self.redis.get(cache_key)
            if cached:
                data = json.loads(cached)
                return ModelResponse(
                    content=data["content"],
                    model=data["model"],
                    input_tokens=data["input_tokens"],
                    output_tokens=data["output_tokens"],
                    cost=data["cost"],
                    cached=True,
                )

        body = self._build_request_body(
            model, messages, max_tokens, temperature, intent, profile
        )

        response = await self._call_with_fallback(model, intent, body, profile)

        if use_cache and self.redis:
            await self.redis.setex(
                self._cache_key(model, messages), 3600,
                json.dumps({
                    "content": response.content,
                    "model": response.model,
                    "input_tokens": response.input_tokens,
                    "output_tokens": response.output_tokens,
                    "cost": response.cost,
                })
            )

        return response

    async def _call_with_fallback(
        self, model: str, intent: str, body: dict, profile: CostProfile
    ) -> ModelResponse:
        models_to_try = [model]
        seen = {model}
        for m in self.router.get_fallbacks(intent):
            if m not in seen:
                models_to_try.append(m)
                seen.add(m)

        last_error = None
        for m in models_to_try:
            try:
                return await self._call_model(m, body)
            except Exception as e:
                last_error = e
                logger.warning("模型 %s 调用失败: %s，尝试下一个", m, str(e)[:200])
                continue

        raise RuntimeError(
            f"All models failed for intent '{intent}': {last_error}"
        )

    async def _call_model(self, model: str, body: dict) -> ModelResponse:
        config = MODEL_CONFIG[model]
        api_key = os.getenv(config["api_key_env"], "")
        api_model_name = config.get("api_name", model)

        if not api_key:
            raise ValueError(
                f"API Key 未设置: 环境变量 {config['api_key_env']} 为空。"
                f"请在前端「设置」页面配置 {config['api_key_env']} 对应的密钥。"
            )

        client = self._get_client(config["base_url"])

        resp = await client.post(
            f"{config['base_url']}/chat/completions",
            json={**body, "model": api_model_name},
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=300,
        )
        resp.raise_for_status()
        data = resp.json()

        usage = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        cost = self._calculate_cost(model, input_tokens, output_tokens)

        return ModelResponse(
            content=data["choices"][0]["message"]["content"],
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
        )

    def _build_request_body(
        self, model, messages, max_tokens, temperature, intent, profile
    ) -> dict:
        body = {
            "messages": messages,
            "temperature": temperature,
        }

        if max_tokens:
            body["max_tokens"] = max_tokens
        else:
            body["max_tokens"] = COST_PROFILES[profile]["max_tokens"]

        thinking = self.router.get_thinking_config(intent, profile)
        if thinking and "v4-pro" in model:
            body["thinking"] = thinking

        return body

    def _calculate_cost(self, model, input_tokens, output_tokens) -> float:
        config = MODEL_CONFIG[model]
        input_cost = input_tokens * config["input_price"] / 1_000_000
        output_cost = output_tokens * config["output_price"] / 1_000_000
        return round(input_cost + output_cost, 6)

    def _cache_key(self, model, messages) -> str:
        content = json.dumps({"model": model, "messages": messages}, sort_keys=True)
        return f"llm_cache:{hashlib.md5(content.encode()).hexdigest()}"

    def _get_client(self, base_url: str) -> httpx.AsyncClient:
        if base_url not in self._clients:
            self._clients[base_url] = httpx.AsyncClient(
                timeout=300,
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            )
        return self._clients[base_url]

    async def close(self):
        for client in self._clients.values():
            await client.aclose()
        self._clients.clear()
