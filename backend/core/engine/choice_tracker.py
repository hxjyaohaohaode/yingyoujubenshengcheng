from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ChoiceRecord:
    choice_id: str
    chapter_number: int
    scene_id: str
    choice_text: str
    moral_alignment: str = "gray"
    is_hidden: bool = False
    consequences: dict = field(default_factory=dict)
    character_state_changes: dict[str, dict] = field(default_factory=dict)
    timestamp: str = ""


@dataclass
class CharacterState:
    character_id: str
    trust: float = 50.0
    affection: float = 50.0
    known_info: list[str] = field(default_factory=list)
    status_modifiers: dict[str, float] = field(default_factory=dict)


class ChoiceTracker:
    def __init__(self, project_id: str):
        self.project_id = project_id
        self._history: list[ChoiceRecord] = []
        self._character_states: dict[str, CharacterState] = {}
        self._active_consequences: dict[str, dict] = {}
        self._choice_index: dict[str, ChoiceRecord] = {}

    def record_choice(
        self,
        choice_id: str,
        chapter_number: int,
        scene_id: str,
        choice_text: str,
        moral_alignment: str = "gray",
        is_hidden: bool = False,
        consequences: Optional[dict] = None,
        character_state_changes: Optional[dict[str, dict]] = None,
        timestamp: str = "",
    ) -> ChoiceRecord:
        record = ChoiceRecord(
            choice_id=choice_id,
            chapter_number=chapter_number,
            scene_id=scene_id,
            choice_text=choice_text,
            moral_alignment=moral_alignment,
            is_hidden=is_hidden,
            consequences=consequences or {},
            character_state_changes=character_state_changes or {},
            timestamp=timestamp,
        )

        self._history.append(record)
        self._choice_index[choice_id] = record

        if consequences:
            self._active_consequences[choice_id] = {
                "direct": consequences.get("consequence_direct", ""),
                "indirect": consequences.get("consequence_indirect", ""),
                "long_term": consequences.get("consequence_long_term", ""),
                "triggered_at_chapter": chapter_number,
                "resolved": False,
            }

        if character_state_changes:
            for char_id, changes in character_state_changes.items():
                self._update_character_state(char_id, changes)

        return record

    def get_choice_history(
        self,
        chapter_number: Optional[int] = None,
        moral_alignment: Optional[str] = None,
        include_hidden: bool = True,
    ) -> list[ChoiceRecord]:
        results = list(self._history)

        if chapter_number is not None:
            results = [r for r in results if r.chapter_number == chapter_number]

        if moral_alignment is not None:
            results = [r for r in results if r.moral_alignment == moral_alignment]

        if not include_hidden:
            results = [r for r in results if not r.is_hidden]

        return results

    def get_active_consequences(
        self,
        current_chapter: Optional[int] = None,
    ) -> dict[str, dict]:
        if current_chapter is None:
            return {k: v for k, v in self._active_consequences.items() if not v.get("resolved", False)}

        active: dict[str, dict] = {}
        for choice_id, consequence in self._active_consequences.items():
            if consequence.get("resolved", False):
                continue

            triggered_at = consequence.get("triggered_at_chapter", 0)
            long_term = consequence.get("long_term", "")

            if long_term and current_chapter - triggered_at < 3:
                active[choice_id] = consequence
            elif not long_term:
                active[choice_id] = consequence

        return active

    def get_character_states(self, character_id: Optional[str] = None) -> dict[str, CharacterState] | CharacterState | None:
        if character_id is not None:
            return self._character_states.get(character_id)
        return dict(self._character_states)

    def resolve_consequence(self, choice_id: str) -> bool:
        if choice_id in self._active_consequences:
            self._active_consequences[choice_id]["resolved"] = True
            return True
        return False

    def get_choices_by_chapter(self, chapter_number: int) -> list[ChoiceRecord]:
        return [r for r in self._history if r.chapter_number == chapter_number]

    def get_moral_balance(self) -> dict[str, int]:
        balance: dict[str, int] = {"good": 0, "neutral": 0, "evil": 0, "gray": 0}
        for record in self._history:
            alignment = record.moral_alignment
            if alignment in balance:
                balance[alignment] += 1
            else:
                balance["gray"] += 1
        return balance

    def get_hidden_choices_discovered(self) -> list[ChoiceRecord]:
        return [r for r in self._history if r.is_hidden]

    def _update_character_state(self, character_id: str, changes: dict) -> None:
        if character_id not in self._character_states:
            self._character_states[character_id] = CharacterState(character_id=character_id)

        state = self._character_states[character_id]

        if "trust" in changes:
            state.trust = max(0.0, min(100.0, state.trust + changes["trust"]))
        if "trust_delta" in changes:
            state.trust = max(0.0, min(100.0, state.trust + changes["trust_delta"]))
        if "affection" in changes:
            state.affection = max(0.0, min(100.0, state.affection + changes["affection"]))
        if "affection_delta" in changes:
            state.affection = max(0.0, min(100.0, state.affection + changes["affection_delta"]))

        known_info = changes.get("known_info", [])
        if isinstance(known_info, list):
            for info in known_info:
                if info not in state.known_info:
                    state.known_info.append(info)

        status_modifiers = changes.get("status_modifiers", {})
        if isinstance(status_modifiers, dict):
            for key, value in status_modifiers.items():
                state.status_modifiers[key] = state.status_modifiers.get(key, 0.0) + value

    def to_dict(self) -> dict:
        return {
            "project_id": self.project_id,
            "history": [
                {
                    "choice_id": r.choice_id,
                    "chapter_number": r.chapter_number,
                    "scene_id": r.scene_id,
                    "choice_text": r.choice_text,
                    "moral_alignment": r.moral_alignment,
                    "is_hidden": r.is_hidden,
                    "consequences": r.consequences,
                    "character_state_changes": r.character_state_changes,
                    "timestamp": r.timestamp,
                }
                for r in self._history
            ],
            "character_states": {
                cid: {
                    "character_id": s.character_id,
                    "trust": s.trust,
                    "affection": s.affection,
                    "known_info": s.known_info,
                    "status_modifiers": s.status_modifiers,
                }
                for cid, s in self._character_states.items()
            },
            "active_consequences": dict(self._active_consequences),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ChoiceTracker":
        tracker = cls(project_id=data.get("project_id", ""))

        for r_data in data.get("history", []):
            record = ChoiceRecord(
                choice_id=r_data.get("choice_id", ""),
                chapter_number=r_data.get("chapter_number", 0),
                scene_id=r_data.get("scene_id", ""),
                choice_text=r_data.get("choice_text", ""),
                moral_alignment=r_data.get("moral_alignment", "gray"),
                is_hidden=r_data.get("is_hidden", False),
                consequences=r_data.get("consequences", {}),
                character_state_changes=r_data.get("character_state_changes", {}),
                timestamp=r_data.get("timestamp", ""),
            )
            tracker._history.append(record)
            tracker._choice_index[record.choice_id] = record

        for cid, s_data in data.get("character_states", {}).items():
            tracker._character_states[cid] = CharacterState(
                character_id=s_data.get("character_id", cid),
                trust=s_data.get("trust", 50.0),
                affection=s_data.get("affection", 50.0),
                known_info=s_data.get("known_info", []),
                status_modifiers=s_data.get("status_modifiers", {}),
            )

        tracker._active_consequences = data.get("active_consequences", {})

        return tracker
