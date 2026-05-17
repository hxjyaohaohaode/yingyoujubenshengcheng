"""
叙事连贯性引擎模块

包含:
- 双层级叙事记忆（短期5场景 + 长期持久化状态）
- 5层逻辑锁定协议（角色/时间线/伏笔/世界观/主题）
- 分层迭代精炼协调器（全局审查 + 单场景精炼）
- 字数分配与控制引擎
- 剧本解析与写作风格分析
"""
from core.narrative.models import NarrativeMemory, WordBudget
from core.narrative.memory_store import (
    store_short_term_memory,
    store_long_term_memory,
    get_short_term_memories,
    get_long_term_memories,
    get_all_memories_for_context,
)
from core.narrative.memory_loader import build_narrative_context
from core.narrative.memory_extractor import extract_and_update_memory
from core.narrative.coherence_checker import (
    CheckResult,
    CoherenceReport,
    run_full_coherence_check,
    check_character_consistency,
    check_timeline_consistency,
    check_foreshadow_consistency,
    check_worldbuilding_consistency,
    check_theme_consistency,
)
from core.narrative.revision_orchestrator import (
    GlobalReviewReport,
    RefineResult,
    SceneDefect,
    SceneReviewReport,
    RevisionAction,
    DramaturgeReport,
    DramaturgeRefiner,
    run_global_review,
    refine_scene,
)
from core.narrative.word_budget import (
    BudgetAllocation,
    count_chinese_words,
    allocate_chapter_budget,
    allocate_scene_budget,
    is_within_budget,
    get_compression_instruction,
    save_budget,
    update_actual_words,
    get_project_budgets,
)
from core.narrative.script_parser import (
    ParsedScript,
    parse_script_content,
    build_narrative_memory_from_script,
)
from core.narrative.style_analyzer import (
    StyleProfile,
    analyze_style,
    get_style_guide,
)

__all__ = [
    "NarrativeMemory",
    "WordBudget",
    "store_short_term_memory",
    "store_long_term_memory",
    "get_short_term_memories",
    "get_long_term_memories",
    "get_all_memories_for_context",
    "build_narrative_context",
    "extract_and_update_memory",
    "CheckResult",
    "CoherenceReport",
    "run_full_coherence_check",
    "check_character_consistency",
    "check_timeline_consistency",
    "check_foreshadow_consistency",
    "check_worldbuilding_consistency",
    "check_theme_consistency",
    "GlobalReviewReport",
    "RefineResult",
    "SceneDefect",
    "SceneReviewReport",
    "RevisionAction",
    "DramaturgeReport",
    "DramaturgeRefiner",
    "run_global_review",
    "refine_scene",
    "BudgetAllocation",
    "count_chinese_words",
    "allocate_chapter_budget",
    "allocate_scene_budget",
    "is_within_budget",
    "get_compression_instruction",
    "save_budget",
    "update_actual_words",
    "get_project_budgets",
    "ParsedScript",
    "parse_script_content",
    "build_narrative_memory_from_script",
    "StyleProfile",
    "analyze_style",
    "get_style_guide",
]