from dataclasses import dataclass, field


@dataclass
class SearchResult:
    entity_name: str
    title: str
    snippet: str
    url: str
    source: str = ""
    relevance_score: float = 1.0
    saved: bool = False
    searched_at: str = ""


@dataclass
class KnowledgeCard:
    entity_name: str
    entity_type: str
    summary: str = ""
    key_facts: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    raw_text: str = ""

    def to_prompt_text(self) -> str:
        parts = [f"## {self.entity_name} ({self.entity_type})"]
        if self.summary:
            parts.append(f"**概述**: {self.summary}")
        if self.key_facts:
            parts.append("**关键信息**:")
            for fact in self.key_facts[:8]:
                parts.append(f"- {fact}")
        if self.sources:
            parts.append(f"**来源**: {', '.join(self.sources[:3])}")
        return "\n".join(parts)