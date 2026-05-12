"""
完整剧本生成引擎

提供从大纲到完整剧本的端到端生成能力。
核心流程:
1. 根据大纲规划场景框架
2. 按顺序生成每个场景的完整内容
3. 确保场景间的因果连续性和伏笔回收
"""

from .engine import ScriptGenerationEngine

__all__ = ["ScriptGenerationEngine"]
