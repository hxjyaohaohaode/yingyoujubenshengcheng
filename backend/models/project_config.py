import uuid
from sqlalchemy import Column, String, Integer, Float, JSON, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, UTC

from database import Base


class ProjectConfig(Base):
    __tablename__ = "project_configs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("projects.id"), unique=True, nullable=False)

    target_word_count = Column(Integer, default=50000, comment="目标总字数，范围1万-150万")

    genre = Column(String, default="", comment="体裁：悬疑/爱情/武侠/科幻/奇幻/恐怖/历史/玄幻/仙侠/推理")
    sub_genre = Column(String, default="", comment="子类型，如'古装悬疑'")
    core_contradiction = Column(String, default="", comment="核心矛盾/冲突的一句话描述")
    theme = Column(String, default="", comment="主题思想")
    tone = Column(String, default="neutral", comment="整体基调：dark/light/neutral/epic/intimate")

    chapter_count = Column(Integer, default=10, comment="目标章节数")
    min_words_per_chapter = Column(Integer, default=2000, comment="每章最少字数")
    max_words_per_chapter = Column(Integer, default=8000, comment="每章最多字数")
    scenes_per_chapter_min = Column(Integer, default=2, comment="每章最少场景数")
    scenes_per_chapter_max = Column(Integer, default=6, comment="每章最多场景数")

    target_ending_count = Column(Integer, default=3, comment="目标结局数量")
    max_branch_depth = Column(Integer, default=3, comment="分支最大深度")
    min_branches_per_choice = Column(Integer, default=2, comment="每个选择最少分支数")
    max_branches_per_choice = Column(Integer, default=4, comment="每个选择最多分支数")

    wow_moment_density = Column(Float, default=2.5, comment="每章爽点/哇塞时刻目标数")
    min_dialogue_ratio = Column(Float, default=0.20, comment="最低对白占比")
    max_narration_ratio = Column(Float, default=0.50, comment="最高叙述占比")

    narrative_pov = Column(String, default="third_person", comment="叙事视角：first_person/third_person/omniscient/multiple")
    writing_style = Column(String, default="", comment="写作风格，如'冷峻简约'、'华丽繁复'")
    language_complexity = Column(String, default="medium", comment="语言复杂度：simple/medium/complex")

    world_building_depth = Column(Integer, default=5, comment="世界观构建深度(1-10)")
    character_depth_target = Column(Integer, default=5, comment="角色立体度目标(1-10)")
    plot_complexity = Column(Integer, default=5, comment="情节复杂度(1-10)")

    commercial_fit = Column(String, default="", comment="目标平台适配：qidian/fanqie/zhihu/steam/wechat")
    target_audience = Column(String, default="", comment="目标人群描述")
    age_rating = Column(String, default="general", comment="年龄分级：general/teen/mature")

    enable_constraint_checking = Column(Boolean, default=True, comment="是否启用常识检查")
    enable_water_detection = Column(Boolean, default=True, comment="是否启用水文检测")
    enable_genre_alignment = Column(Boolean, default=True, comment="是否启用体裁对齐")
    enable_voice_consistency = Column(Boolean, default=True, comment="是否启用声音一致性")
    enable_conflict_tracking = Column(Boolean, default=True, comment="是否启用冲突追踪")
    enable_satisfaction_tracking = Column(Boolean, default=True, comment="是否启用爽点追踪")

    custom_evaluation_weights = Column(JSON, default=None, comment="自定义评估权重，如{'foreshadow_recovery': 0.2, ...}")
    custom_checker_rules = Column(JSON, default=None, comment="自定义检测规则")

    creator_prompt_template = Column(Text, default="", comment="自定义创作者Prompt模板")
    auditor_prompt_template = Column(Text, default="", comment="自定义审计师Prompt模板")

    language = Column(String, default="zh-CN", comment="输出语言")

    work_mode = Column(String, default="standard", comment="工作模式：light/standard/heavy")
    player_count = Column(String, default="single", comment="玩家模式：single/dual/multi")
    style = Column(String, default="", comment="风格标签")

    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    project = relationship("Project", back_populates="config")
