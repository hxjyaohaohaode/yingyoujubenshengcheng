from dataclasses import dataclass, field


@dataclass
class EntityInfo:
    name: str
    type: str
    importance: float = 0.5
    description: str = ""


@dataclass
class IntentResult:
    genre: str = ""
    style: str = ""
    entities: list[EntityInfo] = field(default_factory=list)
    key_events: list[str] = field(default_factory=list)
    era: str = ""
    world_elements: list[str] = field(default_factory=list)
    confidence: float = 0.0
    guiding_questions: list[str] = field(default_factory=list)
    need_search: bool = True

    def to_dict(self) -> dict:
        return {
            "genre": self.genre,
            "style": self.style,
            "entities": [
                {"name": e.name, "type": e.type, "importance": e.importance, "description": e.description}
                for e in self.entities
            ],
            "key_events": self.key_events,
            "era": self.era,
            "world_elements": self.world_elements,
            "confidence": self.confidence,
            "guiding_questions": self.guiding_questions,
            "need_search": self.need_search,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "IntentResult":
        return cls(
            genre=data.get("genre", ""),
            style=data.get("style", ""),
            entities=[EntityInfo(**e) for e in data.get("entities", [])],
            key_events=data.get("key_events", []),
            era=data.get("era", ""),
            world_elements=data.get("world_elements", []),
            confidence=data.get("confidence", 0.0),
            guiding_questions=data.get("guiding_questions", []),
            need_search=data.get("need_search", True),
        )