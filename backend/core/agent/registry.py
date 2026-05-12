"""
Agent 注册表: 管理所有 Agent 的注册和获取。
"""

AGENT_REGISTRY: dict[str, type] = {}


def register_agent(cls):
    AGENT_REGISTRY[cls.name] = cls
    return cls


def get_agent(name: str, gateway, rag, storage):
    cls = AGENT_REGISTRY.get(name)
    if not cls:
        raise ValueError(f"Unknown agent: {name}. Available: {list(AGENT_REGISTRY.keys())}")
    return cls(gateway, rag, storage)


def list_agents() -> list[dict]:
    return [
        {"name": cls.name, "description": cls.description}
        for cls in AGENT_REGISTRY.values()
    ]
