import logging
import re
from collections import defaultdict

logger = logging.getLogger(__name__)


def check_voice_consistency(
    scenes: list[dict],
    characters: list[dict],
) -> dict:
    char_dialogue_samples = defaultdict(list)
    char_style_map = {}

    for char in characters:
        cid = str(char.get("id", ""))
        char_style_map[cid] = {
            "name": char.get("name", "?"),
            "language_style": char.get("language_style", ""),
            "catchphrase": char.get("catchphrase", ""),
            "role_type": char.get("role_type", ""),
        }

    for scene in scenes:
        dialogue = scene.get("dialogue", []) or []
        if isinstance(dialogue, str):
            try:
                import json
                dialogue = json.loads(dialogue)
            except (json.JSONDecodeError, TypeError):
                continue

        if not isinstance(dialogue, list):
            continue

        scene_code = scene.get("scene_code", "?")
        for d in dialogue:
            if not isinstance(d, dict):
                continue
            char_name = d.get("character_name", d.get("speaker", d.get("char", "")))
            text = d.get("text", "")
            if char_name and text:
                char_dialogue_samples[char_name].append({
                    "scene": scene_code,
                    "text": text,
                    "length": len(text),
                })

    voice_drift_warnings = []
    char_voice_profiles = {}

    for char_name, samples in char_dialogue_samples.items():
        if len(samples) < 3:
            continue

        lengths = [s["length"] for s in samples]
        avg_length = sum(lengths) / len(lengths)
        length_variance = sum((l - avg_length) ** 2 for l in lengths) / len(lengths)

        sentences_per_line = []
        for s in samples:
            sentences = len(re.split(r"[。！？!?]", s["text"]))
            sentences_per_line.append(max(sentences, 1))

        avg_sentences = sum(sentences_per_line) / len(sentences_per_line)

        char_voice_profiles[char_name] = {
            "sample_count": len(samples),
            "avg_line_length": round(avg_length, 1),
            "length_variance": round(length_variance, 1),
            "avg_sentences_per_line": round(avg_sentences, 1),
        }

        if avg_length > 0:
            cv = length_variance / avg_length
            if cv > 1.5:
                voice_drift_warnings.append(
                    f"[{char_name}] 对白长度波动较大(CV={cv:.1f})，可能存在声音不稳定"
                )

            for i, sample in enumerate(samples):
                if abs(sample["length"] - avg_length) > avg_length * 2:
                    voice_drift_warnings.append(
                        f"[{char_name}] {sample['scene']}: 对白长度{sample['length']}字，"
                        f"偏离平均值{avg_length:.0f}字超过2倍"
                    )

    narrative_voice_issues = []
    narration_styles = []

    for scene in scenes:
        narration = scene.get("narration", "") or ""
        if not narration:
            continue

        scene_code = scene.get("scene_code", "?")
        sentence_count = len(re.split(r"[。！？!?\n]", narration))

        metaphor_count = len(re.findall(r"仿佛|似乎|好像|如同|犹如|宛如|宛若", narration))
        adjective_count = len(re.findall(r"的(?![^)]*\))", narration))
        idiom_count = len(re.findall(
            r"[一-龥]{4}(?:[，。！？]|$)",
            narration,
        ))

        narration_styles.append({
            "scene": scene_code,
            "sentence_count": sentence_count,
            "metaphor_density": round(metaphor_count / max(len(narration), 1) * 100, 2),
            "adjective_density": round(adjective_count / max(len(narration), 1) * 100, 2),
        })

    if narration_styles:
        avg_metaphor = sum(ns["metaphor_density"] for ns in narration_styles) / len(narration_styles)
        avg_adjective = sum(ns["adjective_density"] for ns in narration_styles) / len(narration_styles)

        for ns in narration_styles:
            if ns["metaphor_density"] > avg_metaphor * 3:
                narrative_voice_issues.append(
                    f"[{ns['scene']}] 比喻密度{ns['metaphor_density']}远高于均值{avg_metaphor:.2f}，风格突变"
                )
            if ns["adjective_density"] > avg_adjective * 3:
                narrative_voice_issues.append(
                    f"[{ns['scene']}] 形容词密度{ns['adjective_density']}远高于均值{avg_adjective:.2f}，文风突变"
                )

    total_issues = len(voice_drift_warnings) + len(narrative_voice_issues)
    pass_check = total_issues <= max(len(char_dialogue_samples) * 0.2, 2)

    return {
        "pass": pass_check,
        "char_voice_drifts": voice_drift_warnings,
        "narrative_voice_issues": narrative_voice_issues,
        "char_voice_profiles": char_voice_profiles,
        "total_issues": total_issues,
        "suggestion": (
            "叙事声音一致" if pass_check
            else f"发现{total_issues}处声音/文风漂移，建议复查角色对白风格和叙述风格的一致性"
        ),
    }
