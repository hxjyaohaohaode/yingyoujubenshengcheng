"""
测试智能参数推荐引擎
验证不同字数规模下的推荐参数合理性
"""

import pytest
from core.script_generator.config_recommender import ConfigRecommender


class TestConfigRecommender:
    """测试参数推荐器"""

    def test_scale_tiers(self):
        """测试字数规模分级"""
        assert ConfigRecommender.get_scale_tier(1) == ("微型", "micro")
        assert ConfigRecommender.get_scale_tier(5) == ("短篇", "short")
        assert ConfigRecommender.get_scale_tier(15) == ("中篇", "medium")
        assert ConfigRecommender.get_scale_tier(50) == ("长篇", "long")
        assert ConfigRecommender.get_scale_tier(100) == ("超长篇", "epic")
        assert ConfigRecommender.get_scale_tier(150) == ("史诗", "saga")
        assert ConfigRecommender.get_scale_tier(200) == ("史诗", "saga")

    def test_150_wan_recommendation(self):
        """测试150万字的推荐参数"""
        rec = ConfigRecommender.recommend(target_word_count=1_500_000, genre="悬疑")

        # 章节数应该足够多
        assert rec.chapter_count >= 100, f"150万字项目章节数应≥100，实际为{rec.chapter_count}"
        # 每章最大字数应足够大
        assert rec.max_words_per_chapter >= 10000, f"150万字项目每章最大字数应≥10000，实际为{rec.max_words_per_chapter}"
        # 结局数应足够多
        assert rec.target_ending_count >= 5, f"150万字项目结局数应≥5，实际为{rec.target_ending_count}"
        # 分支深度应较深
        assert rec.max_branch_depth >= 4, f"150万字项目分支深度应≥4，实际为{rec.max_branch_depth}"
        # 爽点密度应合理
        assert 2.0 <= rec.wow_moment_density <= 5.0, f"爽点密度应在2-5之间，实际为{rec.wow_moment_density}"
        # 世界观深度应较高
        assert rec.world_building_depth >= 6, f"150万字项目世界观深度应≥6，实际为{rec.world_building_depth}"

        # 验证容量是否足够
        max_capacity = rec.chapter_count * rec.max_words_per_chapter
        assert max_capacity >= 1_500_000, f"最大容量({max_capacity})应≥目标字数(1,500,000)"

        print(f"\n150万字悬疑推荐:")
        print(f"  章节数: {rec.chapter_count}")
        print(f"  每章字数: {rec.min_words_per_chapter}-{rec.max_words_per_chapter}")
        print(f"  结局数: {rec.target_ending_count}")
        print(f"  分支深度: {rec.max_branch_depth}")
        print(f"  爽点密度: {rec.wow_moment_density}/章")
        print(f"  预计场景数: {rec.estimated_total_scenes}")
        print(f"  预计爽点数: {rec.estimated_wow_moments}")
        print(f"  说明: {rec.reasoning}")

    def test_10_wan_recommendation(self):
        """测试10万字的推荐参数"""
        rec = ConfigRecommender.recommend(target_word_count=100_000, genre="爱情")

        # 10万字应为中篇规模
        assert 15 <= rec.chapter_count <= 40, f"10万字项目章节数应在15-40之间，实际为{rec.chapter_count}"
        assert rec.target_ending_count >= 2, f"10万字项目结局数应≥2，实际为{rec.target_ending_count}"
        assert rec.max_branch_depth >= 2, f"10万字项目分支深度应≥2，实际为{rec.max_branch_depth}"

        max_capacity = rec.chapter_count * rec.max_words_per_chapter
        assert max_capacity >= 100_000, f"最大容量({max_capacity})应≥目标字数(100,000)"

        print(f"\n10万字爱情推荐:")
        print(f"  章节数: {rec.chapter_count}")
        print(f"  结局数: {rec.target_ending_count}")
        print(f"  分支深度: {rec.max_branch_depth}")

    def test_1_wan_recommendation(self):
        """测试1万字的推荐参数"""
        rec = ConfigRecommender.recommend(target_word_count=10_000)

        # 1万字应为微型项目
        assert rec.chapter_count >= 3, f"1万字项目章节数应≥3，实际为{rec.chapter_count}"
        assert rec.max_branch_depth <= 2, f"1万字项目分支深度应≤2，实际为{rec.max_branch_depth}"

        max_capacity = rec.chapter_count * rec.max_words_per_chapter
        assert max_capacity >= 10_000, f"最大容量({max_capacity})应≥目标字数(10,000)"

    def test_genre_effects(self):
        """测试体裁对推荐的影响"""
        rec_suspense = ConfigRecommender.recommend(target_word_count=500_000, genre="悬疑")
        rec_love = ConfigRecommender.recommend(target_word_count=500_000, genre="爱情")
        rec_wuxia = ConfigRecommender.recommend(target_word_count=500_000, genre="武侠")

        # 悬疑应该有更多结局（推理路径多）
        assert rec_suspense.target_ending_count >= rec_wuxia.target_ending_count, \
            "悬疑类结局数应≥武侠类"

        # 爱情应该有更多结局（CP组合多）
        assert rec_love.target_ending_count >= rec_suspense.target_ending_count, \
            "爱情类结局数应≥悬疑类"

        # 武侠应该有更高爽点密度
        assert rec_wuxia.wow_moment_density >= rec_love.wow_moment_density, \
            "武侠类爽点密度应≥爱情类"

        print(f"\n50万字不同体裁对比:")
        print(f"  悬疑: {rec_suspense.chapter_count}章, {rec_suspense.target_ending_count}结局, 爽点{rec_suspense.wow_moment_density}")
        print(f"  爱情: {rec_love.chapter_count}章, {rec_love.target_ending_count}结局, 爽点{rec_love.wow_moment_density}")
        print(f"  武侠: {rec_wuxia.chapter_count}章, {rec_wuxia.target_ending_count}结局, 爽点{rec_wuxia.wow_moment_density}")

    def test_validation_valid_config(self):
        """测试有效配置的校验"""
        is_valid, message, suggestions = ConfigRecommender.validate_and_adjust(
            target_word_count=500_000,
            chapter_count=80,
            min_words_per_chapter=3000,
            max_words_per_chapter=15000,
            target_ending_count=5,
            max_branch_depth=4,
        )

        assert is_valid, f"有效配置应通过校验，但得到: {message}"
        assert suggestions is None, "有效配置不应有建议调整"

    def test_validation_insufficient_capacity(self):
        """测试容量不足的校验"""
        is_valid, message, suggestions = ConfigRecommender.validate_and_adjust(
            target_word_count=1_500_000,
            chapter_count=10,
            min_words_per_chapter=2000,
            max_words_per_chapter=8000,
            target_ending_count=3,
            max_branch_depth=3,
        )

        assert not is_valid, "容量不足应不通过校验"
        assert "超出" in message or "容量" in message, f"错误信息应提到容量问题，实际为: {message}"
        assert suggestions is not None, "应提供调整建议"
        assert "max_words_per_chapter" in suggestions or "chapter_count" in suggestions

    def test_validation_branch_depth_mismatch(self):
        """测试分支深度与结局数不匹配的校验"""
        is_valid, message, suggestions = ConfigRecommender.validate_and_adjust(
            target_word_count=100_000,
            chapter_count=20,
            min_words_per_chapter=2000,
            max_words_per_chapter=10000,
            target_ending_count=1,
            max_branch_depth=3,
        )

        assert not is_valid, "分支深度>1但结局数=1应不通过校验"
        assert "结局" in message, f"错误信息应提到结局数，实际为: {message}"

    def test_validation_epic_project_needs_more_endings(self):
        """测试史诗级项目需要足够结局数"""
        is_valid, message, suggestions = ConfigRecommender.validate_and_adjust(
            target_word_count=1_500_000,
            chapter_count=150,
            min_words_per_chapter=5000,
            max_words_per_chapter=20000,
            target_ending_count=2,
            max_branch_depth=5,
        )

        # 150万字只有2个结局应该被警告
        assert not is_valid or "建议" in message, "史诗级项目结局过少应被警告"

    def test_work_mode_effects(self):
        """测试工作模式对推荐的影响"""
        rec_light = ConfigRecommender.recommend(target_word_count=500_000, work_mode="light")
        rec_standard = ConfigRecommender.recommend(target_word_count=500_000, work_mode="standard")
        rec_heavy = ConfigRecommender.recommend(target_word_count=500_000, work_mode="heavy")

        # heavy模式应该有更深的分支和更复杂的情节
        assert rec_heavy.max_branch_depth >= rec_standard.max_branch_depth, \
            "heavy模式分支深度应≥standard模式"
        assert rec_heavy.plot_complexity >= rec_standard.plot_complexity, \
            "heavy模式情节复杂度应≥standard模式"

        # light模式应该更简单
        assert rec_light.max_branch_depth <= rec_standard.max_branch_depth, \
            "light模式分支深度应≤standard模式"

        print(f"\n工作模式对比(50万字):")
        print(f"  light: {rec_light.max_branch_depth}层分支, 复杂度{rec_light.plot_complexity}")
        print(f"  standard: {rec_standard.max_branch_depth}层分支, 复杂度{rec_standard.plot_complexity}")
        print(f"  heavy: {rec_heavy.max_branch_depth}层分支, 复杂度{rec_heavy.plot_complexity}")

    def test_player_count_effects(self):
        """测试玩家模式对推荐的影响"""
        rec_single = ConfigRecommender.recommend(target_word_count=300_000, player_count="single")
        rec_dual = ConfigRecommender.recommend(target_word_count=300_000, player_count="dual")
        rec_multi = ConfigRecommender.recommend(target_word_count=300_000, player_count="multi")

        # 多人模式应该有更多结局
        assert rec_multi.target_ending_count >= rec_dual.target_ending_count >= rec_single.target_ending_count, \
            "多人模式结局数应≥双人模式≥单人模式"

        print(f"\n玩家模式对比(30万字):")
        print(f"  single: {rec_single.target_ending_count}结局")
        print(f"  dual: {rec_dual.target_ending_count}结局")
        print(f"  multi: {rec_multi.target_ending_count}结局")

    def test_all_scales_capacity_sufficient(self):
        """测试所有规模推荐的容量都足够"""
        test_cases = [
            (10_000, "1万字"),
            (50_000, "5万字"),
            (100_000, "10万字"),
            (300_000, "30万字"),
            (500_000, "50万字"),
            (1_000_000, "100万字"),
            (1_500_000, "150万字"),
        ]

        for word_count, label in test_cases:
            rec = ConfigRecommender.recommend(target_word_count=word_count)
            max_capacity = rec.chapter_count * rec.max_words_per_chapter
            min_capacity = rec.chapter_count * rec.min_words_per_chapter

            assert max_capacity >= word_count, \
                f"{label}: 最大容量({max_capacity})应≥目标字数({word_count})"
            assert min_capacity <= word_count * 2, \
                f"{label}: 最小容量({min_capacity})不应远超目标字数({word_count})"

            print(f"{label}: {rec.chapter_count}章 × {rec.max_words_per_chapter}字 = {max_capacity:,}字容量 ✓")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
