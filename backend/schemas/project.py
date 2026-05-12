from pydantic import BaseModel, Field, model_validator
from typing import Optional, Dict, List
from datetime import datetime

VALID_GENRES = {"悬疑", "爱情", "武侠", "科幻", "奇幻", "恐怖", "历史", "玄幻", "仙侠", "推理", "都市", "军事", "竞技", "轻小说", "二次元", "其他"}
VALID_TONES = {"dark", "light", "neutral", "epic", "intimate"}
VALID_POVS = {"first_person", "third_person", "omniscient", "multiple"}
VALID_COMPLEXITIES = {"simple", "medium", "complex"}
VALID_AGE_RATINGS = {"general", "teen", "mature"}
VALID_WORK_MODES = {"light", "standard", "heavy"}
VALID_PLAYER_COUNTS = {"single", "dual", "multi"}


class ProjectConfigSchema(BaseModel):
    target_word_count: int = Field(default=50000, ge=10000, le=1500000, description="目标总字数（1万-150万）")

    genre: str = Field(default="", description="体裁：悬疑/爱情/武侠/科幻/奇幻/恐怖/历史/玄幻/仙侠/推理")
    sub_genre: str = Field(default="", description="子类型")
    core_contradiction: str = Field(default="", description="核心冲突描述")
    theme: str = Field(default="", description="主题思想")
    tone: str = Field(default="neutral", description="整体基调")

    chapter_count: int = Field(default=10, ge=1, le=500, description="目标章节数")
    min_words_per_chapter: int = Field(default=2000, ge=500, le=50000)
    max_words_per_chapter: int = Field(default=8000, ge=1000, le=100000)
    scenes_per_chapter_min: int = Field(default=2, ge=1, le=20)
    scenes_per_chapter_max: int = Field(default=6, ge=1, le=50)

    target_ending_count: int = Field(default=3, ge=1, le=20, description="目标结局数量")
    max_branch_depth: int = Field(default=3, ge=1, le=10, description="最大分支深度")
    min_branches_per_choice: int = Field(default=2, ge=1, le=10)
    max_branches_per_choice: int = Field(default=4, ge=1, le=20)

    wow_moment_density: float = Field(default=2.5, ge=0.5, le=10.0, description="每章爽点目标数")
    min_dialogue_ratio: float = Field(default=0.20, ge=0.0, le=0.80, description="最低对白占比")
    max_narration_ratio: float = Field(default=0.50, ge=0.0, le=0.90, description="最高叙述占比")

    narrative_pov: str = Field(default="third_person", description="叙事视角")
    writing_style: str = Field(default="", description="写作风格描述")
    language_complexity: str = Field(default="medium", description="语言复杂度")

    world_building_depth: int = Field(default=5, ge=1, le=10)
    character_depth_target: int = Field(default=5, ge=1, le=10)
    plot_complexity: int = Field(default=5, ge=1, le=10)

    commercial_fit: str = Field(default="", description="目标平台")
    target_audience: str = Field(default="", description="目标人群")
    age_rating: str = Field(default="general")

    enable_constraint_checking: bool = True
    enable_water_detection: bool = True
    enable_genre_alignment: bool = True
    enable_voice_consistency: bool = True
    enable_conflict_tracking: bool = True
    enable_satisfaction_tracking: bool = True

    custom_evaluation_weights: Optional[Dict[str, float]] = None
    custom_checker_rules: Optional[Dict] = None

    creator_prompt_template: str = ""
    auditor_prompt_template: str = ""

    language: str = "zh-CN"

    work_mode: str = Field(default="standard", description="工作模式：light/standard/heavy")
    player_count: str = Field(default="single", description="玩家模式：single/dual/multi")
    style: str = Field(default="", description="风格标签")

    @model_validator(mode="after")
    def validate_config_consistency(self):
        if self.min_words_per_chapter > self.max_words_per_chapter:
            raise ValueError(
                f"每章最少字数({self.min_words_per_chapter})不能大于最多字数({self.max_words_per_chapter})"
            )

        if self.scenes_per_chapter_min > self.scenes_per_chapter_max:
            raise ValueError(
                f"每章最少场景数({self.scenes_per_chapter_min})不能大于最多场景数({self.scenes_per_chapter_max})"
            )

        if self.min_branches_per_choice > self.max_branches_per_choice:
            raise ValueError(
                f"最少分支数({self.min_branches_per_choice})不能大于最多分支数({self.max_branches_per_choice})"
            )

        min_possible_words = self.chapter_count * self.min_words_per_chapter
        max_possible_words = self.chapter_count * self.max_words_per_chapter

        if self.target_word_count < min_possible_words * 0.5:
            min_available = min_possible_words
            raise ValueError(
                f"目标总字数({self.target_word_count:,}字)远低于章节可容纳的最低字数"
                f"({min_available:,}字 = {self.chapter_count}章 × {self.min_words_per_chapter}字/章)。"
                f"请减少章节数或提高目标字数。"
            )

        if self.target_word_count > max_possible_words * 1.2:
            max_available = max_possible_words
            raise ValueError(
                f"目标总字数({self.target_word_count:,}字)超出章节可容纳的最高字数"
                f"({max_available:,}字 = {self.chapter_count}章 × {self.max_words_per_chapter}字/章)。"
                f"请增加章节数或降低目标字数。"
            )

        if self.genre and self.genre not in VALID_GENRES:
            valid_list = "、".join(sorted(VALID_GENRES))
            raise ValueError(
                f"体裁'{self.genre}'不在推荐列表中。可选体裁：{valid_list}"
            )

        if self.tone and self.tone not in VALID_TONES:
            valid_list = "、".join(VALID_TONES)
            raise ValueError(
                f"基调'{self.tone}'无效。可选：{valid_list}"
            )

        if self.narrative_pov and self.narrative_pov not in VALID_POVS:
            valid_list = "、".join(VALID_POVS)
            raise ValueError(
                f"叙事视角'{self.narrative_pov}'无效。可选：{valid_list}"
            )

        if self.language_complexity and self.language_complexity not in VALID_COMPLEXITIES:
            valid_list = "、".join(VALID_COMPLEXITIES)
            raise ValueError(
                f"语言复杂度'{self.language_complexity}'无效。可选：{valid_list}"
            )

        if self.age_rating and self.age_rating not in VALID_AGE_RATINGS:
            valid_list = "、".join(VALID_AGE_RATINGS)
            raise ValueError(
                f"年龄分级'{self.age_rating}'无效。可选：{valid_list}"
            )

        if self.work_mode and self.work_mode not in VALID_WORK_MODES:
            valid_list = "、".join(VALID_WORK_MODES)
            raise ValueError(
                f"工作模式'{self.work_mode}'无效。可选：{valid_list}"
            )

        if self.player_count and self.player_count not in VALID_PLAYER_COUNTS:
            valid_list = "、".join(VALID_PLAYER_COUNTS)
            raise ValueError(
                f"玩家模式'{self.player_count}'无效。可选：{valid_list}"
            )

        if self.min_dialogue_ratio > self.max_narration_ratio:
            raise ValueError(
                f"最低对白占比({self.min_dialogue_ratio})不能高于最高叙述占比({self.max_narration_ratio})，"
                f"二者代表不同维度，建议最低对白占比 < 最高叙述占比。"
            )

        if self.max_branch_depth > 1 and self.target_ending_count < 2:
            raise ValueError(
                f"当分支深度 > 1 时，目标结局数应 ≥ 2（当前为{self.target_ending_count}）。"
                f"单结局剧本请设置分支深度为1。"
            )

        if self.target_word_count <= 50000 and self.world_building_depth >= 8:
            raise ValueError(
                f"字数较少({self.target_word_count:,}字)时世界观构建深度不宜过高"
                f"({self.world_building_depth})，建议 ≤ 7。"
            )

        if self.target_word_count >= 300000 and self.world_building_depth <= 3:
            raise ValueError(
                f"长篇小说({self.target_word_count:,}字)建议世界观构建深度 ≥ 4，"
                f"当前为{self.world_building_depth}。"
            )

        return self


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="项目名称")
    description: str = Field(default="", description="项目描述")
    template_id: Optional[str] = Field(default=None, description="模板ID")
    config: ProjectConfigSchema = Field(default_factory=ProjectConfigSchema, description="项目配置")


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    config: Optional[ProjectConfigSchema] = None


class ProjectResponse(BaseModel):
    id: str
    name: str
    description: str
    status: str
    template_id: Optional[str] = None
    config: Optional[ProjectConfigSchema] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProjectListResponse(BaseModel):
    projects: List[ProjectResponse]
    total: int
