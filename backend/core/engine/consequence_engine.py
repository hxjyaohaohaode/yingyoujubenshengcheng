from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ConsequenceLayer:
    layer_type: str
    description: str
    affected_characters: list[str] = field(default_factory=list)
    magnitude: float = 0.0
    metadata: dict = field(default_factory=dict)


@dataclass
class ConsequenceChain:
    choice_id: str
    direct: ConsequenceLayer = field(default_factory=lambda: ConsequenceLayer(layer_type="direct", description=""))
    indirect: ConsequenceLayer = field(default_factory=lambda: ConsequenceLayer(layer_type="indirect", description=""))
    long_term: ConsequenceLayer = field(default_factory=lambda: ConsequenceLayer(layer_type="long_term", description=""))
    relationship_impact: ConsequenceLayer = field(default_factory=lambda: ConsequenceLayer(layer_type="relationship", description=""))
    character_state_changes: dict[str, dict] = field(default_factory=dict)
    foreshadow_triggers: list[str] = field(default_factory=list)
    branch_divergence_point: bool = False


class ConsequenceEngine:
    def __init__(self, story_plan: dict, character_states: dict[str, dict]):
        self.story_plan = story_plan
        self.character_states = character_states
        self._character_arcs = story_plan.get("character_arcs", {})
        self._foreshadow_roadmap = story_plan.get("foreshadow_roadmap", {})
        self._world_constraints = story_plan.get("world_constraints", {})
        self._impossible = story_plan.get("impossible", [])

    def compute_consequences(
        self,
        choice_id: str,
        choice_data: dict,
        story_plan: Optional[dict] = None,
        character_states: Optional[dict[str, dict]] = None,
    ) -> ConsequenceChain:
        if story_plan:
            self.story_plan = story_plan
            self._character_arcs = story_plan.get("character_arcs", {})
            self._foreshadow_roadmap = story_plan.get("foreshadow_roadmap", {})
            self._world_constraints = story_plan.get("world_constraints", {})
            self._impossible = story_plan.get("impossible", [])
        if character_states:
            self.character_states = character_states

        chain = ConsequenceChain(choice_id=choice_id)

        chain.direct = self._compute_direct(choice_data)
        chain.indirect = self._compute_indirect(choice_data, chain.direct)
        chain.long_term = self._compute_long_term(choice_data, chain.indirect)
        chain.relationship_impact = self._compute_relationship_impact(choice_data, chain.direct, chain.indirect)

        chain.character_state_changes = self._compute_character_state_changes(
            choice_data, chain.direct, chain.indirect, chain.long_term
        )
        chain.foreshadow_triggers = self._compute_foreshadow_triggers(choice_data)
        chain.branch_divergence_point = self._is_branch_divergence_point(choice_data)

        return chain

    def _compute_direct(self, choice_data: dict) -> ConsequenceLayer:
        consequence_text = choice_data.get("consequence_direct", "")
        character_impact = choice_data.get("character_impact", [])
        affected = []
        if isinstance(character_impact, list):
            for ci in character_impact:
                if isinstance(ci, dict):
                    char_id = ci.get("character_id", ci.get("name", ""))
                    if char_id:
                        affected.append(char_id)

        magnitude = self._estimate_magnitude(consequence_text, character_impact)

        return ConsequenceLayer(
            layer_type="direct",
            description=consequence_text,
            affected_characters=affected,
            magnitude=magnitude,
            metadata={"moral_alignment": choice_data.get("moral_alignment", "gray")},
        )

    def _compute_indirect(self, choice_data: dict, direct: ConsequenceLayer) -> ConsequenceLayer:
        consequence_text = choice_data.get("consequence_indirect", "")
        affected = list(direct.affected_characters)
        for char_id in direct.affected_characters:
            char_state = self.character_states.get(char_id, {})
            relations = char_state.get("relations", {})
            for rel_name in relations:
                if rel_name not in affected:
                    affected.append(rel_name)

        magnitude = self._estimate_magnitude(consequence_text, [])
        magnitude *= 0.7

        return ConsequenceLayer(
            layer_type="indirect",
            description=consequence_text,
            affected_characters=affected,
            magnitude=magnitude,
            metadata={"triggered_by": direct.layer_type},
        )

    def _compute_long_term(self, choice_data: dict, indirect: ConsequenceLayer) -> ConsequenceLayer:
        consequence_text = choice_data.get("consequence_long_term", "")
        affected = list(indirect.affected_characters)

        for char_id in indirect.affected_characters:
            arc = self._character_arcs.get(char_id, {})
            if arc:
                arc_affected = arc.get("affected_by_choices", [])
                for ac in arc_affected:
                    if isinstance(ac, str) and ac not in affected:
                        affected.append(ac)

        magnitude = self._estimate_magnitude(consequence_text, [])
        magnitude *= 0.4

        foreshadow_refs = []
        for fs_name, fs_data in self._foreshadow_roadmap.items():
            if isinstance(fs_data, dict):
                triggers = fs_data.get("trigger_choices", [])
                if choice_data.get("text", "") in triggers or choice_data.get("id", "") in triggers:
                    foreshadow_refs.append(fs_name)

        return ConsequenceLayer(
            layer_type="long_term",
            description=consequence_text,
            affected_characters=affected,
            magnitude=magnitude,
            metadata={"foreshadow_refs": foreshadow_refs},
        )

    def _compute_relationship_impact(
        self,
        choice_data: dict,
        direct: ConsequenceLayer,
        indirect: ConsequenceLayer,
    ) -> ConsequenceLayer:
        character_impact = choice_data.get("character_impact", [])
        impact_descriptions: list[str] = []
        affected_pairs: list[str] = []

        if isinstance(character_impact, list):
            for ci in character_impact:
                if not isinstance(ci, dict):
                    continue
                char_id = ci.get("character_id", ci.get("name", ""))
                trust_change = ci.get("trust_change", 0)
                affection_change = ci.get("affection_change", 0)
                desc = ci.get("description", "")

                if desc:
                    impact_descriptions.append(f"{char_id}: {desc}")
                if trust_change != 0 or affection_change != 0:
                    char_state = self.character_states.get(char_id, {})
                    relations = char_state.get("relations", {})
                    for rel_name, rel_data in relations.items():
                        if isinstance(rel_data, dict):
                            pair_key = f"{char_id}-{rel_name}"
                            if pair_key not in affected_pairs:
                                affected_pairs.append(pair_key)

        all_affected = []
        for pair in affected_pairs:
            parts = pair.split("-")
            for p in parts:
                if p not in all_affected:
                    all_affected.append(p)
        all_affected.extend(direct.affected_characters)

        description = "; ".join(impact_descriptions) if impact_descriptions else "无直接关系影响"
        magnitude = len(impact_descriptions) * 0.3

        return ConsequenceLayer(
            layer_type="relationship",
            description=description,
            affected_characters=all_affected,
            magnitude=min(1.0, magnitude),
            metadata={"affected_pairs": affected_pairs},
        )

    def _compute_character_state_changes(
        self,
        choice_data: dict,
        direct: ConsequenceLayer,
        indirect: ConsequenceLayer,
        long_term: ConsequenceLayer,
    ) -> dict[str, dict]:
        changes: dict[str, dict] = {}
        character_impact = choice_data.get("character_impact", [])

        if isinstance(character_impact, list):
            for ci in character_impact:
                if not isinstance(ci, dict):
                    continue
                char_id = ci.get("character_id", ci.get("name", ""))
                if not char_id:
                    continue

                trust_change = ci.get("trust_change", 0)
                affection_change = ci.get("affection_change", 0)
                current = self.character_states.get(char_id, {})

                new_trust = current.get("trust", 50) + trust_change
                new_affection = current.get("affection", 50) + affection_change
                new_known_info = list(current.get("known_info", []))

                if direct.description:
                    info_key = f"choice_{choice_data.get('id', '')}_direct"
                    if info_key not in new_known_info:
                        new_known_info.append(info_key)

                changes[char_id] = {
                    "trust": max(0, min(100, new_trust)),
                    "affection": max(0, min(100, new_affection)),
                    "trust_delta": trust_change,
                    "affection_delta": affection_change,
                    "known_info": new_known_info,
                }

        return changes

    def _compute_foreshadow_triggers(self, choice_data: dict) -> list[str]:
        triggers: list[str] = []
        choice_text = choice_data.get("text", "")
        choice_id = choice_data.get("id", "")

        for fs_name, fs_data in self._foreshadow_roadmap.items():
            if not isinstance(fs_data, dict):
                continue
            trigger_choices = fs_data.get("trigger_choices", [])
            trigger_keywords = fs_data.get("trigger_keywords", [])

            if choice_id in trigger_choices:
                triggers.append(fs_name)
                continue

            for keyword in trigger_keywords:
                if keyword and keyword in choice_text:
                    triggers.append(fs_name)
                    break

        return triggers

    def _is_branch_divergence_point(self, choice_data: dict) -> bool:
        moral = choice_data.get("moral_alignment", "gray")
        is_hidden = choice_data.get("is_hidden", False)
        has_long_term = bool(choice_data.get("consequence_long_term", ""))

        if is_hidden:
            return True
        if moral in ("good", "evil") and has_long_term:
            return True
        if choice_data.get("branch_target", ""):
            return True
        return False

    def _estimate_magnitude(self, text: str, character_impact: list) -> float:
        magnitude = 0.1
        if not text:
            return magnitude

        magnitude += min(0.5, len(text) / 500.0)

        high_keywords = ["死亡", "背叛", "揭露", "真相", "牺牲", "毁灭", "崩溃", "反转"]
        for kw in high_keywords:
            if kw in text:
                magnitude += 0.15

        if isinstance(character_impact, list):
            magnitude += min(0.3, len(character_impact) * 0.1)

        return min(1.0, magnitude)
