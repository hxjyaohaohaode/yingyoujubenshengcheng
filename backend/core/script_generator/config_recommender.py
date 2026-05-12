"""
智能参数推荐引擎
根据目标字数、体裁、复杂度等，自动推荐合理的剧本结构参数。
确保大项目（如150万字）的参数配置能够支撑高质量AI生成。
"""

from dataclasses import dataclass
from typing import Dict, Optional, Tuple


@dataclass
class RecommendedConfig:
    """推荐配置结果"""
    chapter_count: int
    min_words_per_chapter: int
    max_words_per_chapter: int
    scenes_per_chapter_min: int
    scenes_per_chapter_max: int
    target_ending_count: int
    max_branch_depth: int
    min_branches_per_choice: int
    max_branches_per_choice: int
    wow_moment_density: float
    world_building_depth: int
    character_depth_target: int
    plot_complexity: int
    min_dialogue_ratio: float
    max_narration_ratio: float
    estimated_total_scenes: int
    estimated_wow_moments: int
    estimated_branch_nodes: int
    genre_notes: str
    reasoning: str


class ConfigRecommender:
    """
    剧本参数智能推荐器

    推荐逻辑基于以下原则：
    1. 字数规模决定结构复杂度
    2. 互动性（分支/结局）与字数正相关
    3. 爽点密度与叙事节奏匹配
    4. 每章字数有合理区间（3000-20000字）
    5. 分支深度与结局数存在数学关系
    """

    # 字数规模分级（万字）
    SCALE_TIERS = [
        (0, 3, "微型", "micro"),
        (3, 10, "短篇", "short"),
        (10, 30, "中篇", "medium"),
        (30, 80, "长篇", "long"),
        (80, 150, "超长篇", "epic"),
        (150, 999, "史诗", "saga"),
    ]

    # 体裁对参数的影响系数
    GENRE_MULTIPLIERS = {
        "悬疑": {"chapter_density": 1.2, "branch_depth": 1.3, "ending_count": 1.2, "wow_density": 1.1},
        "推理": {"chapter_density": 1.2, "branch_depth": 1.3, "ending_count": 1.2, "wow_density": 1.1},
        "爱情": {"chapter_density": 1.0, "branch_depth": 1.0, "ending_count": 1.5, "wow_density": 0.9},
        "武侠": {"chapter_density": 0.9, "branch_depth": 1.1, "ending_count": 1.0, "wow_density": 1.2},
        "科幻": {"chapter_density": 1.0, "branch_depth": 1.2, "ending_count": 1.1, "wow_density": 1.0},
        "奇幻": {"chapter_density": 0.9, "branch_depth": 1.2, "ending_count": 1.1, "wow_density": 1.1},
        "恐怖": {"chapter_density": 1.1, "branch_depth": 1.1, "ending_count": 1.3, "wow_density": 1.0},
        "历史": {"chapter_density": 0.9, "branch_depth": 1.0, "ending_count": 1.0, "wow_density": 0.8},
        "玄幻": {"chapter_density": 0.8, "branch_depth": 1.1, "ending_count": 1.0, "wow_density": 1.2},
        "仙侠": {"chapter_density": 0.8, "branch_depth": 1.1, "ending_count": 1.0, "wow_density": 1.1},
        "都市": {"chapter_density": 1.1, "branch_depth": 1.0, "ending_count": 1.1, "wow_density": 1.0},
        "军事": {"chapter_density": 1.0, "branch_depth": 1.0, "ending_count": 1.0, "wow_density": 1.1},
        "竞技": {"chapter_density": 1.1, "branch_depth": 1.0, "ending_count": 1.2, "wow_density": 1.2},
        "轻小说": {"chapter_density": 1.2, "branch_depth": 1.0, "ending_count": 1.2, "wow_density": 1.0},
        "二次元": {"chapter_density": 1.2, "branch_depth": 1.0, "ending_count": 1.2, "wow_density": 1.0},
        "其他": {"chapter_density": 1.0, "branch_depth": 1.0, "ending_count": 1.0, "wow_density": 1.0},
    }

    @classmethod
    def get_scale_tier(cls, word_count_wan: float) -> Tuple[str, str]:
        """获取字数规模分级"""
        for min_w, max_w, cn_name, en_name in cls.SCALE_TIERS:
            if min_w <= word_count_wan < max_w:
                return cn_name, en_name
        return "史诗", "saga"

    @classmethod
    def recommend(cls,
                  target_word_count: int,
                  genre: str = "",
                  work_mode: str = "standard",
                  player_count: str = "single") -> RecommendedConfig:
        """
        根据目标字数和体裁推荐完整的配置参数

        Args:
            target_word_count: 目标总字数
            genre: 体裁
            work_mode: 工作模式 (light/standard/heavy)
            player_count: 玩家模式 (single/dual/multi)

        Returns:
            RecommendedConfig: 推荐配置
        """
        word_count_wan = target_word_count / 10000
        scale_cn, scale_en = cls.get_scale_tier(word_count_wan)

        # 获取体裁系数
        gm = cls.GENRE_MULTIPLIERS.get(genre, cls.GENRE_MULTIPLIERS["其他"])

        # 工作模式系数
        mode_multipliers = {
            "light": 0.7,
            "standard": 1.0,
            "heavy": 1.3,
        }
        mm = mode_multipliers.get(work_mode, 1.0)

        # 多人模式系数
        player_multipliers = {
            "single": 1.0,
            "dual": 1.2,
            "multi": 1.4,
        }
        pm = player_multipliers.get(player_count, 1.0)

        # ========== 章节数计算 ==========
        # 基础逻辑：每章 5000-15000 字为最佳阅读体验
        # 短篇可以更短，长篇需要更长章节
        if word_count_wan <= 3:
            base_chapter_count = max(5, int(word_count_wan * 3))
            target_words_per_chapter = 3000
        elif word_count_wan <= 10:
            base_chapter_count = max(10, int(word_count_wan * 2.5))
            target_words_per_chapter = 5000
        elif word_count_wan <= 30:
            base_chapter_count = max(20, int(word_count_wan * 2))
            target_words_per_chapter = 6000
        elif word_count_wan <= 80:
            base_chapter_count = max(40, int(word_count_wan * 1.5))
            target_words_per_chapter = 8000
        elif word_count_wan <= 150:
            base_chapter_count = max(80, int(word_count_wan * 1.2))
            target_words_per_chapter = 10000
        else:
            base_chapter_count = max(150, int(word_count_wan))
            target_words_per_chapter = 12000

        # 应用体裁系数调整章节密度
        chapter_count = max(5, int(base_chapter_count * gm["chapter_density"]))
        chapter_count = min(chapter_count, 500)  # 上限

        # ========== 每章字数范围 ==========
        # 确保总字数能被章节结构容纳
        min_wpc = max(1000, int(target_words_per_chapter * 0.4))
        max_wpc = min(50000, int(target_words_per_chapter * 1.8))

        # 校验：chapter_count * max_wpc 必须 >= target_word_count
        required_max_wpc = int(target_word_count / chapter_count * 1.5)
        if max_wpc < required_max_wpc:
            max_wpc = required_max_wpc
            # 同时调整min_wpc保持合理比例
            min_wpc = max(1000, int(max_wpc * 0.3))

        # ========== 场景数 ==========
        # 每章场景数与字数正相关
        scenes_per_1000 = 0.8  # 每1000字约0.8个场景
        base_scenes = max(2, int(target_words_per_chapter / 1000 * scenes_per_1000))
        scenes_min = max(1, int(base_scenes * 0.6))
        scenes_max = min(50, int(base_scenes * 1.5))

        # ========== 结局数 ==========
        # 基础：短篇1-3个，长篇3-8个，超长篇5-15个
        if word_count_wan <= 5:
            base_endings = 2
        elif word_count_wan <= 15:
            base_endings = 3
        elif word_count_wan <= 50:
            base_endings = 5
        elif word_count_wan <= 100:
            base_endings = 8
        else:
            base_endings = 12

        target_ending_count = max(1, int(base_endings * gm["ending_count"] * pm))
        target_ending_count = min(target_ending_count, 20)

        # ========== 分支深度 ==========
        # 分支深度与结局数、字数都相关
        # 数学关系： endings ≈ branches^(depth-1) （简化模型）
        if word_count_wan <= 5:
            base_depth = 1
        elif word_count_wan <= 15:
            base_depth = 2
        elif word_count_wan <= 50:
            base_depth = 3
        elif word_count_wan <= 100:
            base_depth = 4
        else:
            base_depth = 5

        max_branch_depth = max(1, int(base_depth * gm["branch_depth"] * mm))
        max_branch_depth = min(max_branch_depth, 10)

        # 确保分支深度与结局数匹配
        # 如果 depth > 1，至少需要 2 个结局
        if max_branch_depth > 1 and target_ending_count < 2:
            target_ending_count = 2

        # ========== 分支选项数 ==========
        # 最少分支选项：2-3个
        # 最多分支选项：与深度相关，深度越大选项应越多
        min_branches = 2
        max_branches = min(20, max(3, int(2 + max_branch_depth * 0.5)))

        # ========== 爽点密度 ==========
        # 每章爽点数：短篇可密集，长篇需节奏控制
        if word_count_wan <= 5:
            base_wow = 2.0
        elif word_count_wan <= 20:
            base_wow = 2.5
        elif word_count_wan <= 50:
            base_wow = 3.0
        elif word_count_wan <= 100:
            base_wow = 3.5
        else:
            base_wow = 4.0

        wow_moment_density = round(base_wow * gm["wow_density"], 1)
        wow_moment_density = min(10.0, max(0.5, wow_moment_density))

        # ========== 世界观/角色/情节深度 ==========
        # 与字数规模正相关
        if word_count_wan <= 5:
            depth_base = 3
        elif word_count_wan <= 20:
            depth_base = 4
        elif word_count_wan <= 50:
            depth_base = 5
        elif word_count_wan <= 100:
            depth_base = 6
        else:
            depth_base = 7

        world_building_depth = min(10, max(1, depth_base + 1))
        character_depth_target = min(10, max(1, depth_base + 1))
        plot_complexity = min(10, max(1, int(depth_base * mm)))

        # ========== 对白/叙述比例 ==========
        # 互动影游对白比例较高
        min_dialogue_ratio = 0.25
        max_narration_ratio = 0.50

        # ========== 估算统计 ==========
        estimated_total_scenes = int(chapter_count * (scenes_min + scenes_max) / 2)
        estimated_wow_moments = int(chapter_count * wow_moment_density)
        # 分支节点估算：每章可能有 1-2 个分支点
        estimated_branch_nodes = int(chapter_count * min(2, max_branch_depth * 0.3))

        # ========== 生成说明 ==========
        reasoning = (
            f"【{scale_cn}规模推荐】目标{word_count_wan:.0f}万字，"
            f"推荐{chapter_count}章（每章{min_wpc}-{max_wpc}字），"
            f"共约{estimated_total_scenes}个场景。"
            f"基于{genre or '通用'}体裁，"
            f"建议{target_ending_count}个结局、{max_branch_depth}层分支深度，"
            f"预计全篇约{estimated_wow_moments}个爽点/反转时刻。"
        )

        genre_notes = cls._get_genre_notes(genre, word_count_wan)

        return RecommendedConfig(
            chapter_count=chapter_count,
            min_words_per_chapter=min_wpc,
            max_words_per_chapter=max_wpc,
            scenes_per_chapter_min=scenes_min,
            scenes_per_chapter_max=scenes_max,
            target_ending_count=target_ending_count,
            max_branch_depth=max_branch_depth,
            min_branches_per_choice=min_branches,
            max_branches_per_choice=max_branches,
            wow_moment_density=wow_moment_density,
            world_building_depth=world_building_depth,
            character_depth_target=character_depth_target,
            plot_complexity=plot_complexity,
            min_dialogue_ratio=min_dialogue_ratio,
            max_narration_ratio=max_narration_ratio,
            estimated_total_scenes=estimated_total_scenes,
            estimated_wow_moments=estimated_wow_moments,
            estimated_branch_nodes=estimated_branch_nodes,
            genre_notes=genre_notes,
            reasoning=reasoning,
        )

    @classmethod
    def _get_genre_notes(cls, genre: str, word_count_wan: float) -> str:
        """获取体裁特定的建议说明"""
        notes = {
            "悬疑": "悬疑类建议保持较高章节密度，每章结尾设置悬念钩子。分支深度可较深以支撑多线推理。",
            "推理": "推理类需要严密逻辑链，分支应围绕'线索选择'设计。结局数可较多以容纳不同推理路径。",
            "爱情": "爱情类可适度降低爽点密度，增加情感细腻度。结局数建议较多以覆盖不同CP组合。",
            "武侠": "武侠类爽点密度可较高，世界观深度建议≥6以支撑门派/功法体系。",
            "科幻": "科幻类需要充分的世界观铺陈，前20%章节可用于设定展开。分支可围绕'科技伦理抉择'设计。",
            "奇幻": "奇幻类世界观深度建议≥7，魔法体系需要详细规则。爽点可与'能力觉醒/魔法对决'绑定。",
            "恐怖": "恐怖类建议控制单章字数（不宜过长），保持节奏紧凑。结局数可较多以覆盖不同幸存组合。",
            "历史": "历史类爽点密度可适度降低，注重史实感和厚重感。世界观深度建议≥6。",
            "玄幻": "玄幻类爽点密度可高，'升级突破'是核心爽点来源。章节可较长以容纳战斗描写。",
            "仙侠": "仙侠类世界观需要完整的修炼体系，建议世界观深度≥7。情感线与修仙线可并行。",
            "都市": "都市类节奏可快，章节密度高。爽点围绕'事业/情感逆袭'设计。",
            "竞技": "竞技类爽点密度建议最高，比赛场景是核心。结局数可覆盖不同赛事结果。",
        }
        base = notes.get(genre, "通用配置，适用于大多数互动影游项目。")

        if word_count_wan >= 80:
            base += " 超长篇项目建议采用'卷-章'二级结构，每卷有独立的小高潮和悬念。"
        elif word_count_wan >= 30:
            base += " 长篇项目建议在中点设置重大转折，将故事分为上下两部。"

        return base

    @classmethod
    def validate_and_adjust(cls,
                           target_word_count: int,
                           chapter_count: int,
                           min_words_per_chapter: int,
                           max_words_per_chapter: int,
                           target_ending_count: int,
                           max_branch_depth: int,
                           **kwargs) -> Tuple[bool, str, Optional[Dict]]:
        """
        验证用户自定义参数是否合理，并给出调整建议

        Returns:
            (is_valid, message, suggested_values)
        """
        issues = []
        suggestions = {}

        # 1. 章节容量检查
        min_capacity = chapter_count * min_words_per_chapter
        max_capacity = chapter_count * max_words_per_chapter

        if target_word_count > max_capacity:
            issues.append(
                f"目标字数({target_word_count:,}字)超出章节最大容量({max_capacity:,}字 = "
                f"{chapter_count}章 × {max_words_per_chapter}字/章)"
            )
            # 建议调整
            suggested_max_wpc = int(target_word_count / chapter_count * 1.2)
            suggestions["max_words_per_chapter"] = min(50000, suggested_max_wpc)
            suggestions["chapter_count"] = int(target_word_count / max_words_per_chapter * 1.1) + 1

        if target_word_count < min_capacity * 0.5:
            issues.append(
                f"目标字数({target_word_count:,}字)远低于章节最小容量({min_capacity:,}字)，"
                f"建议减少章节数或降低每章最少字数"
            )
            suggestions["chapter_count"] = max(5, int(target_word_count / max_words_per_chapter * 0.8))

        # 2. 分支深度与结局数匹配
        if max_branch_depth > 1 and target_ending_count < 2:
            issues.append(f"分支深度为{max_branch_depth}时，至少需要2个结局")
            suggestions["target_ending_count"] = max(2, int(max_branch_depth * 1.5))

        # 3. 分支深度与字数匹配
        word_count_wan = target_word_count / 10000
        if word_count_wan >= 50 and max_branch_depth < 3:
            issues.append(f"{word_count_wan:.0f}万字的长篇项目建议分支深度≥3，以支撑足够的互动性")
            suggestions["max_branch_depth"] = 3

        if word_count_wan <= 5 and max_branch_depth > 3:
            issues.append(f"{word_count_wan:.0f}万字的短篇项目不建议分支深度>{max_branch_depth}，可能导致内容碎片化")
            suggestions["max_branch_depth"] = 2

        # 4. 结局数与字数匹配
        if word_count_wan >= 100 and target_ending_count < 5:
            issues.append(f"{word_count_wan:.0f}万字的史诗级项目建议结局数≥5，以充分发挥重玩价值")
            suggestions["target_ending_count"] = max(5, int(word_count_wan / 15))

        # 5. 每章字数合理性
        if max_words_per_chapter < 2000 and word_count_wan >= 20:
            issues.append(f"每章最多{max_words_per_chapter}字对于{word_count_wan:.0f}万字项目过少，建议≥3000字")
            suggestions["max_words_per_chapter"] = max(3000, int(target_word_count / chapter_count * 1.2))

        if min_words_per_chapter > max_words_per_chapter:
            issues.append(f"每章最少字数({min_words_per_chapter})不能大于最多字数({max_words_per_chapter})")
            suggestions["min_words_per_chapter"] = int(max_words_per_chapter * 0.4)

        is_valid = len(issues) == 0
        message = "参数配置合理" if is_valid else "；".join(issues)

        return is_valid, message, suggestions if suggestions else None
