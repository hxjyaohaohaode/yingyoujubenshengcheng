"""
高质量Prompt模板引擎。
为所有AI生成端点提供深度、结构化、上下文感知的系统提示词和用户提示词。
确保生成内容具有：一致性、文学性、画面感、角色深度、互动影游适配性。
"""

import json

# ============================================================================
#  通用写作质量规范（所有创意类提示词共享）
# ============================================================================

CHINESE_WRITING_STANDARDS = """
【中文创意写作铁律】

1. **画面感三要素**：每个场景描述必须包含至少两种感官（光/味/声/触/温）
2. **动态叙述**：用动作推进剧情，禁止超过三句连续静态描写
3. **对白潜文本**：每句对白必须有"字面意思"与"真实意图"的落差（角色永远口是心非）
4. **节奏控制**：短句（<15字）制造紧张，长句（>30字）营造沉浸
5. **具象化**：抽象概念必须用具体物象承载（不写"悲伤"，写"手指抠进掌心"）
6. **叙事视角一致**：严格遵循指定的POV视角，不跳视角
7. **信息释放**：采用"冰山原则"，只写水面以上，水下留给读者/玩家推断
8. **中国网文黄金律**：每300字必须有新的信息增量（新动作/新对话/新发现）
"""

INTERACTIVE_GAME_WRITING = """
【互动影游剧本特殊要求】

1. **代入感**：主角的行动必须有明确的选择空间（即使不写出来，也要让读者感受到"此处可分支"）
2. **道德灰度**：每个重大抉择必须有好/坏两面的后果，不能有完美答案
3. **NPC深度**：配角不能只是工具人，每个NPC有自己的小算盘
4. **信息不对等**：不同角色掌握不同信息片段，玩家需要通过探索拼凑真相
5. **情感锚点**：每3-5个场景必须有一个情感重场（角色关系发生质的改变）
6. **分支预埋**：重要对白末尾暗示另一种可能（"如果你当时选了..."的既视感）
7. **环境叙事**：场景本身应当传达故事信息（用场景说故事，不只用字说故事）
"""

WORLD_CONFIG_CROSS_REFS = {
    "core_contradiction": ["constraints", "impossible"],
    "social_structure": ["core_contradiction", "history", "culture"],
    "tech_magic": ["core_contradiction", "constraints", "impossible"],
    "geography": ["social_structure", "history"],
    "history": ["core_contradiction", "social_structure"],
    "culture": ["social_structure", "history", "constraints"],
    "constraints": ["core_contradiction", "impossible"],
    "impossible": ["core_contradiction", "tech_magic", "constraints"],
}

WORLD_CONFIG_LABELS = {
    "core_contradiction": "核心矛盾",
    "social_structure": "社会结构",
    "tech_magic": "科技/魔法体系",
    "geography": "地理环境",
    "history": "历史",
    "culture": "文化",
    "constraints": "约束条件",
    "impossible": "不可能之事",
}


def build_world_gen_prompt(config_key: str, label: str, desc: str,
                           existing_world: dict | None = None,
                           current_value: str = "") -> tuple[str, str]:
    """
    世界观配置项生成提示词。
    返回 (system_prompt, user_prompt)
    当 current_value 非空时，进入"扩展/优化"模式，基于已有内容生成。
    """
    existing_context = ""
    if existing_world:
        existing_lines = []
        for k, v in existing_world.items():
            if v and isinstance(v, str) and v.strip():
                existing_lines.append(f"- {k}: {v}")
        if existing_lines:
            existing_context = "\n".join(existing_lines)

    cross_ref_context = ""
    cross_ref_keys = WORLD_CONFIG_CROSS_REFS.get(config_key, [])
    if cross_ref_keys and existing_world:
        cross_ref_lines = []
        for ref_key in cross_ref_keys:
            ref_val = existing_world.get(ref_key, "")
            if ref_val and isinstance(ref_val, str) and ref_val.strip():
                ref_label = WORLD_CONFIG_LABELS.get(ref_key, ref_key)
                cross_ref_lines.append(f"  ▸ {ref_label}（{ref_key}）：{ref_val}")
        if cross_ref_lines:
            cross_ref_context = "\n".join(cross_ref_lines)

    is_continuation = bool(current_value and current_value.strip())

    CROSS_REF_CONSTRAINT = f"""【⚠️ 交叉引用约束 — 必须遵守】
当前正在生成「{label}」配置项。根据世界观内部逻辑，此配置项与以下配置项存在强关联：
{chr(10).join(f"  ▸ {WORLD_CONFIG_LABELS.get(rk, rk)}（{rk}）" for rk in cross_ref_keys) if cross_ref_keys else "  （无交叉引用要求）"}
你**必须**在生成内容中显式引用上述关联配置项的核心设定，确保逻辑自洽。具体要求：
- 不得与关联配置项的设定产生矛盾
- 必须在正文中自然融入关联配置项的关键概念或具体细节
- 如果关联配置项之间本身存在张力/矛盾，应在本配置项中体现这种张力的后果"""

    INTERACTIVE_ADAPTABILITY = """【互动影游适配性 — 每个方案必须包含】
每个方案除了设定正文外，还必须包含以下三个维度的分析，确保世界观设定能直接服务于互动影游的玩法和叙事：

1. **【玩家选择影响】**：此设定如何影响玩家的选择空间？它为玩家提供了哪些新的决策维度？它限制了哪些选择？玩家的不同选择如何在此设定的框架下产生不同后果？（200-500字）

2. **【分支制造点】**：此设定可以制造哪些具体的分支/选择点？列出2-3个，每个需说明：选择情境、各选项及其后果、信息差如何影响选择。（每个50-150字）

3. **【信息层次】**：按"洋葱模型"三层描述此设定的信息分布：
   - 表层（普通NPC知道的）：大众认知版本，可能包含误解和偏见
   - 深层（内行人知道的）：专业人士/核心圈层的认知，接近但未触及终极真相
   - 核心（终极真相）：极少数人知晓的真相，足以颠覆表层认知"""

    OUTPUT_FORMAT = """【回答格式】
你必须在```json```代码块中输出严格的JSON数组，包含3个方案。每个方案是一个对象：
```json
[
  {
    "content": "设定正文（1000-3000字，有画面感和具体细节，必须显式引用关联配置项的核心设定）",
    "player_choice_impact": "【玩家选择影响】（200-500字，说明此设定如何影响玩家的选择空间和决策维度）",
    "branch_points": [
      "分支制造点1：选择情境+各选项及后果+信息差影响（50-150字）",
      "分支制造点2：选择情境+各选项及后果+信息差影响（50-150字）"
    ],
    "info_layers": {
      "surface": "表层信息（普通NPC知道的，100-300字）",
      "deep": "深层信息（内行人知道的，100-300字）",
      "core": "核心真相（终极真相，100-300字）"
    }
  }
]
```
不要输出JSON之外的任何内容。"""

    ANTI_TRUNCATION = """【重要：防止截断】
- 三个方案的总长度控制在 15000 字以内
- 每个方案优先保证完整性，宁可细节稍少，也不要写到一半突然中断
- 充分利用可用空间，写得越详细越好"""

    if is_continuation:
        system_prompt = f"""你是全球顶尖的虚构世界观设计师，曾为多部获奖互动影游构建世界观。你的设计兼具独创性、内在逻辑自洽性和戏剧张力。

{CHINESE_WRITING_STANDARDS}

【世界观设计铁律】
1. 每个设定必须回答三个问题：它如何影响角色行为？它如何制造冲突？它如何被打破？
2. 避免"全世界最强大帝国"之类的空泛设定，要具体到某个街角的气味
3. 好的世界观不是"展览品"，而是"发动机"——必须能直接驱动剧情
4. 设定必须满足"洋葱模型"：表层（普通人看到的）→ 深层（内行人知道的）→ 核心（只有极少数人知晓的终极真相）
5. 每一层信息都可以成为一个伏笔/反转/哇塞时刻的引爆点
6. **必须引用其他已锁定设定**：生成某个配置项时，必须显式引用已锁定的其他世界观设定，确保逻辑自洽，不得孤立创作

{CROSS_REF_CONSTRAINT}

{INTERACTIVE_ADAPTABILITY}

【⚠️ 续写模式 — 极其重要】
当前配置项「{label}」已经有内容了！你的任务是：
- 方案1：在现有内容基础上**深化和扩展**——补充更多具体细节、增加洋葱模型的深层设定、添加能直接驱动剧情的元素，保持与现有内容完全一致
- 方案2：在现有内容基础上**优化和重构**——保留核心设定不变，改善表述、强化戏剧张力、补充缺失的逻辑链条
- 方案3：提供一个**风格不同但世界观一致**的替代方案——必须与已有世界观的其他设定保持逻辑自洽

**绝对不能**生成与现有内容完全无关的全新设定！每个方案都必须能看出是从现有内容发展而来的。

{OUTPUT_FORMAT}

{ANTI_TRUNCATION}"""

        cross_ref_section = ""
        if cross_ref_context:
            cross_ref_section = f"""🔗 必须参考的关联设定（生成「{label}」时必须显式引用）：
{cross_ref_context}
━━━━━━━━━━━━━━━━━━━━━━"""

        user_prompt = f"""请为以下世界观配置项生成3个基于现有内容的扩展/优化方案：

━━━━━━━━━━━━━━━━━━━━━━
⚙️ 配置项：{label}
📝 功能说明：{desc}
━━━━━━━━━━━━━━━━━━━━━━
📝 当前已有内容（必须以此为基础扩展，不能抛弃）：
{current_value}
━━━━━━━━━━━━━━━━━━━━━━
{cross_ref_section}
{f"🌍 其他已设定的世界观（请保持一致性）：\n{existing_context}\n━━━━━━━━━━━━━━━━━━━━━━" if existing_context else ""}

【创作要求】
1. 每个方案必须以现有内容为基础，不能凭空创造全新的无关设定
2. 方案1要深化扩展：补充具体细节（人名、地名、机构名、数值），增加深层设定
3. 方案2要优化重构：保留核心不变，改善逻辑和表述，强化戏剧张力
4. 方案3可以风格不同，但必须与世界观其他设定兼容
5. 所有方案必须能直接衍生出角色动机和剧情冲突
6. 语言优美、有画面感、避免教科书式的枯燥罗列
7. **完整性优先**：每个方案必须有头有尾
8. **交叉引用**：每个方案的content中必须显式引用关联配置项的核心设定，不得孤立创作
9. **互动适配**：player_choice_impact、branch_points、info_layers必须与content中的设定严格对应，不能泛泛而谈

请直接输出JSON数组，不要添加任何解释。"""

    else:
        system_prompt = f"""你是全球顶尖的虚构世界观设计师，曾为多部获奖互动影游构建世界观。你的设计兼具独创性、内在逻辑自洽性和戏剧张力。

{CHINESE_WRITING_STANDARDS}

【世界观设计铁律】
1. 每个设定必须回答三个问题：它如何影响角色行为？它如何制造冲突？它如何被打破？
2. 避免"全世界最强大帝国"之类的空泛设定，要具体到某个街角的气味
3. 好的世界观不是"展览品"，而是"发动机"——必须能直接驱动剧情
4. 设定必须满足"洋葱模型"：表层（普通人看到的）→ 深层（内行人知道的）→ 核心（只有极少数人知晓的终极真相）
5. 每一层信息都可以成为一个伏笔/反转/哇塞时刻的引爆点
6. **必须引用其他已锁定设定**：生成某个配置项时，必须显式引用已锁定的其他世界观设定，确保逻辑自洽，不得孤立创作

{CROSS_REF_CONSTRAINT}

{INTERACTIVE_ADAPTABILITY}

{OUTPUT_FORMAT}

{ANTI_TRUNCATION}"""

        cross_ref_section = ""
        if cross_ref_context:
            cross_ref_section = f"""🔗 必须参考的关联设定（生成「{label}」时必须显式引用）：
{cross_ref_context}
━━━━━━━━━━━━━━━━━━━━━━"""

        user_prompt = f"""请为以下世界观配置项生成3个高质量的创新方案：

━━━━━━━━━━━━━━━━━━━━━━
⚙️ 配置项：{label}
📝 功能说明：{desc}
━━━━━━━━━━━━━━━━━━━━━━
{cross_ref_section}
{f"🌍 已有世界观设定（请保持一致性）：\n{existing_context}\n━━━━━━━━━━━━━━━━━━━━━━" if existing_context else ""}

【创作要求】
1. 每个方案必须包含可操作的、具体的设定细节（人名、地名、机构名、具体数值）
2. 设定要能直接衍生出角色动机和剧情冲突
3. 三个方案之间风格差异显著（如：暗黑写实 vs 浪漫史诗 vs 荒诞讽刺）
4. 适合互动影游的叙事需求——玩家需要通过探索逐步发现这些设定
5. 语言优美、有画面感、避免教科书式的枯燥罗列
6. **完整性优先**：每个方案必须有头有尾，不能写到一半中断。如果篇幅有限，宁可减少细节数量，也要保证方案是完整的
7. **交叉引用**：每个方案的content中必须显式引用关联配置项的核心设定，不得孤立创作
8. **互动适配**：player_choice_impact、branch_points、info_layers必须与content中的设定严格对应，不能泛泛而谈

请直接输出JSON数组，不要添加任何解释。"""

    return system_prompt, user_prompt


def build_character_gen_prompt(world_context: str, genre: str,
                                existing_chars: list | None = None,
                                character_count: int = 0,
                                world_core_contradiction: str = "",
                                world_constraints: str = "",
                                world_impossible: str = "") -> tuple[str, str]:
    """
    角色生成提示词。
    支持两种模式：
    - 全新生成：existing_chars 为空时，生成完整角色阵容
    - 续写补充：existing_chars 非空时，只生成补充角色，必须与已有角色形成关联

    世界观深度绑定参数：
    - world_core_contradiction: 世界观核心矛盾，角色的核心动机必须直接回应此矛盾
    - world_constraints: 世界观约束条件，角色的行为约束必须与此一致
    - world_impossible: 世界观不可能事项，角色绝对不能做出违反此设定的事
    """
    is_continuation = bool(existing_chars and len(existing_chars) > 0)

    existing_context = ""
    if existing_chars:
        existing_lines = []
        for c in existing_chars:
            parts = [f"- {c.get('name', '?')} ({c.get('role_type', '?')}): 动机={c.get('core_goal', '?')}"]
            if c.get('core_fear'):
                parts.append(f"  恐惧={c['core_fear']}")
            if c.get('background'):
                parts.append(f"  背景={c['background']}")
            if c.get('surface_image'):
                parts.append(f"  表面={c['surface_image']}")
            if c.get('true_self'):
                parts.append(f"  真实={c['true_self']}")
            if c.get('dark_secret'):
                parts.append(f"  秘密={c['dark_secret']}")
            if c.get('arc_description'):
                parts.append(f"  弧线={c['arc_description']}")
            if c.get('relationship_hooks'):
                hooks = c['relationship_hooks']
                if isinstance(hooks, list):
                    hook_strs = [f"{h.get('target_role', '?')}({h.get('relation_type', '?')})" for h in hooks if isinstance(h, dict)]
                    if hook_strs:
                        parts.append(f"  关系={', '.join(hook_strs)}")
            existing_lines.append("\n".join(parts))
        if existing_lines:
            existing_context = "\n\n".join(existing_lines)

    existing_names = [c.get('name', '') for c in (existing_chars or []) if c.get('name')]
    existing_role_types = [c.get('role_type', '') for c in (existing_chars or []) if c.get('role_type')]

    world_binding_block = ""
    if world_core_contradiction or world_constraints or world_impossible:
        world_binding_lines = []
        if world_core_contradiction:
            world_binding_lines.append(f"  ▸ 核心矛盾：{world_core_contradiction}")
        if world_constraints:
            world_binding_lines.append(f"  ▸ 约束条件：{world_constraints}")
        if world_impossible:
            world_binding_lines.append(f"  ▸ 不可能事项：{world_impossible}")
        world_binding_block = f"""【⚠️ 世界观深度绑定 — 强制约束，必须遵守】
角色的每一个维度都必须与世界观深度关联，不得脱离世界观孤立设计：
{chr(10).join(world_binding_lines)}

1. **核心动机绑定**：每个角色的core_goal必须直接回应世界观的核心矛盾——角色要么在维护这个矛盾的现状，要么在试图打破它，要么在矛盾中求生。绝不能出现与核心矛盾无关的动机。
2. **暗秘密绑定**：每个角色的dark_secret必须与世界观的深层/核心设定有关——秘密的揭露必须能引发对世界观的重新认知，而不仅仅是个人隐私。
3. **行为约束绑定**：每个角色的behavior_never必须与世界观的约束条件/不可能事项一致——在这个世界中不可能发生的事，角色也绝对不可能做。behavior_conditional中触发条件必须受世界观约束条件的限制。"""

    if is_continuation:
        additional_count = max(3, character_count - len(existing_chars)) if character_count > len(existing_chars) else max(3, min(8, len(existing_chars)))
        target_count = additional_count

        missing_roles = []
        all_role_types = {'protagonist', 'antagonist', 'love_interest', 'mentor', 'rival', 'wildcard', 'sidekick', 'foil'}
        present_roles = set(existing_role_types)
        missing_roles = list(all_role_types - present_roles)

        system_prompt = f"""你是全球顶级的角色设计师，擅长为互动影游创造真实、立体、有内在矛盾的角色群像。你的角色不是"设定卡"，而是"活生生的人"。

{CHINESE_WRITING_STANDARDS}

{INTERACTIVE_GAME_WRITING}

【⚠️ 续写模式 — 极其重要】
项目中已经有 {len(existing_chars)} 个角色了！你的任务是生成 **补充角色**，不是重新生成整个阵容！

你必须做到：
1. **只生成新增角色**，绝对不能重复生成已有角色
2. **新角色必须与已有角色产生关联**——每个新角色的 relationship_hooks 必须引用已有角色名字
3. **填补阵容空缺**——如果缺少反派、挚爱等关键角色类型，优先补充
4. **扩展关系网络**——新角色要能与已有角色形成新的三角关系、暗线关系、信息差
5. **保持世界观一致性**——新角色的背景、动机必须与已有世界观和已有角色的故事兼容

已有角色名：{', '.join(existing_names)}
已有角色类型：{', '.join(existing_role_types) if existing_role_types else '无'}
缺少的角色类型：{', '.join(missing_roles) if missing_roles else '基本齐全，可自由补充'}

{world_binding_block}

【角色设计铁律】
1. **内在矛盾**：每个角色必须有一个"想要的"和一个"害怕的"，两者形成不可调和的张力
2. **三层构造**：表层印象 → 真实自我 → 终极秘密
3. **行为语言**：不说"他是一个善良的人"，而说"他在深夜给流浪猫留半份便当"
4. **关系势能**：每两个角色之间都有"未完成的事件"
5. **成长弧线**：角色必须有明确的"开始状态"和"潜在终局状态"
6. **说话风格化**：每个角色有独特的口头禅、句式偏好
7. **阵营分化**：角色之间必须有利益阵营的对立和交叉
8. **信息差设计**：不同角色掌握不同信息片段

【回答格式】
严格的JSON数组，在```json```代码块中：
```json
[
  {{
    "name": "中文角色名（2-4字，绝对不能与已有角色重名）",
    "role_type": "protagonist|antagonist|love_interest|mentor|rival|wildcard|sidekick|foil",
    "core_goal": "最想要的东西（一句话）",
    "core_fear": "最害怕发生的事（一句话）",
    "background": "背景故事（800-2000字，必须包含至少一个具体创伤事件和一次人生转折，且与已有角色的背景有交集或对照）",
    "surface_image": "表层印象（200-500字）",
    "true_self": "真实自我（200-500字）",
    "dark_secret": "不为人知的秘密（100-300字，必须能直接引爆剧情）",
    "personality_traits": "3-5个性格关键词",
    "language_style": "说话风格描述",
    "catchphrase": "标志性口头禅",
    "arc_description": "角色弧线描述（500-1500字）",
    "behavior_inevitable": ["必然会做的事1", "必然会做的事2"],
    "behavior_never": ["绝对不会做的事1", "绝对不会做的事2"],
    "behavior_conditional": ["在XX条件下会做的事"],
    "relationship_hooks": [
      {{"target_role": "已有角色名（必须引用已有角色）", "relation_type": "关系类型", "hook": "关系线索/未完成事件"}},
      {{"target_role": "另一个已有角色名", "relation_type": "关系类型", "hook": "关系线索"}}
    ]
  }}
]
```"""

        user_prompt = f"""请在已有角色基础上，生成 {target_count} 个补充角色：

━━━━━━━━━━━━━━━━━━━━━━
🎭 题材/体裁：{genre or '未指定'}
━━━━━━━━━━━━━━━━━━━━━━
{f"🌍 世界观背景：\n{world_context}\n━━━━━━━━━━━━━━━━━━━━━━" if world_context else ""}
👥 已有角色（{len(existing_chars)}个，新角色必须与它们产生关联）：
{existing_context}
━━━━━━━━━━━━━━━━━━━━━━

【创作要求】
1. 生成{target_count}个**补充角色**，绝对不能与已有角色重名或重复
2. 每个新角色的 relationship_hooks 中至少有2个引用已有角色的名字
3. 新角色必须填补阵容空缺（缺少的类型优先）
4. 新角色与已有角色之间要形成新的戏剧冲突和信息差
5. 每个角色的core_goal和core_fear要形成自我矛盾
6. background必须有具体事件，且与已有角色背景有交集或对照
7. surface_image和true_self必须形成反差
8. arc_description必须完整
9. **完整性优先**：所有字段必须填写完整
10. **世界观深度绑定**：每个角色的core_goal必须直接回应世界观核心矛盾；dark_secret必须与世界观的深层/核心设定关联；behavior_never必须与世界观约束条件/不可能事项一致

请直接输出JSON数组，不要添加任何解释。"""

    else:
        target_count = max(8, min(15, character_count)) if character_count else 8

        system_prompt = f"""你是全球顶级的角色设计师，擅长为互动影游创造真实、立体、有内在矛盾的角色群像。你的角色不是"设定卡"，而是"活生生的人"。

{CHINESE_WRITING_STANDARDS}

{INTERACTIVE_GAME_WRITING}

{world_binding_block}

【角色设计铁律】
1. **内在矛盾**：每个核心角色必须有一个"想要的"和一个"害怕的"，两者形成不可调和的张力
2. **三层构造**：表层印象（他人看到的）→ 真实自我（只有亲密者知道的）→ 终极秘密（连自己都可能不知道的）
3. **行为语言**：不说"他是一个善良的人"，而说"他在深夜给流浪猫留半份便当"
4. **关系势能**：每两个角色之间都有"未完成的事件"——旧账、秘密、误会、欠债
5. **成长弧线**：角色不能一直不变，必须有明确的"开始状态"和"潜在终局状态"
6. **说话风格化**：每个角色有独特的口头禅、句式偏好、语速、用词范围
7. **阵营分化**：角色之间必须有利益阵营的对立和交叉，不能所有人都在同一阵线
8. **信息差设计**：不同角色掌握不同信息片段，这些信息差本身就是剧情驱动力

【阵容设计要求】
- 必须生成 **{target_count}个** 角色，覆盖以下角色类型：
  - 1个主角（protagonist）：有道德灰色地带，不是完美英雄
  - 1个反派/对手（antagonist）：有令人同情的动机，不是纯粹的恶
  - 1个挚爱/羁绊角色（love_interest）：与主角有深层情感纠葛
  - 1-2个导师/盟友（mentor/sidekick）：各有自己的小算盘
  - 1-2个暗线角色（wildcard/rival）：立场不明，可能倒向任何一方
  - 0-1个对照角色（foil）：与主角形成镜像对比
- 角色之间必须形成至少3组三角关系（如：A爱B，B爱C，C恨A）
- 每个角色至少与3个其他角色有直接关系
- 必须存在至少2组隐藏关系（表面上看似无关，实际有深层联系）

【回答格式】
严格的JSON数组，在```json```代码块中：
```json
[
  {{
    "name": "中文角色名（2-4字）",
    "role_type": "protagonist|antagonist|love_interest|mentor|rival|wildcard|sidekick|foil",
    "core_goal": "最想要的东西（一句话，如：找到杀害师父的真正凶手）",
    "core_fear": "最害怕发生的事（一句话，如：发现自己才是真正的凶手）",
    "background": "背景故事（800-2000字，必须包含至少一个具体创伤事件和一次人生转折）",
    "surface_image": "表层印象（他人眼中的TA，200-500字，如：冷静果断的执法者，从不犹豫）",
    "true_self": "真实自我（只有亲密者知道的，200-500字，如：深夜会反复检查门锁，害怕被抛弃）",
    "dark_secret": "不为人知的秘密（100-300字，必须能直接引爆剧情）",
    "personality_traits": "3-5个性格关键词（如：偏执、重情义、口是心非）",
    "language_style": "说话风格描述（如：言简意赅，每句不超过15字；或：喜欢用典故，说话文绉绉）",
    "catchphrase": "标志性口头禅",
    "arc_description": "角色弧线描述（500-1500字，包含：起点状态→关键转折→潜在终局，如：从盲目忠诚到发现真相后的信仰崩塌，最终选择以自我牺牲完成救赎）",
    "behavior_inevitable": ["必然会做的事1", "必然会做的事2"],
    "behavior_never": ["绝对不会做的事1", "绝对不会做的事2"],
    "behavior_conditional": ["在XX条件下会做的事"],
    "relationship_hooks": [
      {{"target_role": "与哪个角色的关系", "relation_type": "关系类型", "hook": "关系线索/未完成事件"}}
    ]
  }}
]
```"""

        user_prompt = f"""请为以下项目创建完整的角色阵容：

━━━━━━━━━━━━━━━━━━━━━━
🎭 题材/体裁：{genre or '未指定（请自行选择最适合的题材方向）'}
━━━━━━━━━━━━━━━━━━━━━━
{f"🌍 世界观背景：\n{world_context}\n━━━━━━━━━━━━━━━━━━━━━━" if world_context else "🌍 世界观：未设定（请自行为角色设计一个引人入胜的世界背景）\n━━━━━━━━━━━━━━━━━━━━━━"}

【创作要求】
1. 生成{target_count}个角色，形成完整的角色阵容
2. 角色之间要有天然的戏剧冲突（利益冲突、价值观冲突、信息不对等）
3. 每个角色的core_goal和core_fear要形成自我矛盾
4. background必须有具体的事件/创伤/转折点，不能只有性格描述
5. surface_image和true_self必须形成反差
6. arc_description必须完整描述角色从起点到终点的变化轨迹
7. relationship_hooks中每个角色至少与3个其他角色有关系线索
8. 必须包含至少3组三角关系和2组隐藏关系
9. 适合互动影游：主角有道德灰色地带，对手有令人同情的动机
10. **完整性优先**：所有字段必须填写完整，不能留空或写一半中断。如果总角色数较多，每个角色的background和arc_description可适当精简，但必须保证有头有尾
11. **世界观深度绑定**：每个角色的core_goal必须直接回应世界观核心矛盾；dark_secret必须与世界观的深层/核心设定关联；behavior_never必须与世界观约束条件/不可能事项一致

请直接输出JSON数组，不要添加任何解释。"""

    return system_prompt, user_prompt


def build_relation_network_prompt(world_context: str, genre: str,
                                   characters: list,
                                   world_core_contradiction: str = "",
                                   world_constraints: str = "",
                                   world_impossible: str = "") -> tuple[str, str]:
    """
    关系网络生成提示词 — 为已有角色生成复杂、深层、有戏剧张力的人物关系网络。
    包含：三角关系、暗线关系、信息差、隐藏关系、关系弧线、引爆点。
    核心升级：
    - 关系密度不低于60%（N个角色至少N*(N-1)/2*0.6条关系）
    - 信息不对称结构化（a_knows_about_b / b_knows_about_a）
    - 暗线关系占比不低于20%
    - 关系弧线预规划（方向+引爆点+里程碑）
    """
    char_list = []
    for c in characters:
        char_list.append(
            f"【{c.get('name', '?')}】({c.get('role_type', '?')})\n"
            f"  动机: {c.get('core_goal', '未设定')}\n"
            f"  恐惧: {c.get('core_fear', '未设定')}\n"
            f"  表面: {c.get('surface_image', '未设定')}\n"
            f"  真实: {c.get('true_self', '未设定')}\n"
            f"  秘密: {c.get('dark_secret', '未设定')}"
        )
    char_context = "\n\n".join(char_list)

    n = len(characters)
    max_possible_relations = n * (n - 1) // 2
    min_relations = max(n * 2, int(max_possible_relations * 0.6))
    min_hidden_relations = max(2, int(min_relations * 0.2))

    world_binding_block = ""
    if world_core_contradiction or world_constraints or world_impossible:
        world_binding_lines = []
        if world_core_contradiction:
            world_binding_lines.append(f"  ▸ 核心矛盾：{world_core_contradiction}")
        if world_constraints:
            world_binding_lines.append(f"  ▸ 约束条件：{world_constraints}")
        if world_impossible:
            world_binding_lines.append(f"  ▸ 不可能事项：{world_impossible}")
        world_binding_block = f"""【⚠️ 世界观深度绑定 — 关系网络必须与世界观深度关联】
{chr(10).join(world_binding_lines)}

1. 关系的成因必须根植于世界观核心矛盾——角色之间的冲突、联盟、操控都应是对核心矛盾不同立场的体现
2. 暗线关系的秘密必须与世界观的深层/核心设定有关——揭露暗线应引发对世界观的重新认知
3. 引爆点条件必须受世界观约束条件限制——不可能事项不能作为引爆条件
4. 关系弧线的变化方向必须与世界观矛盾的发展趋势一致"""

    system_prompt = f"""你是全球顶级的人物关系网络设计师，专精为互动影游构建复杂、多层、有戏剧张力的人物关系网。
你的关系网络不是简单的"谁认识谁"，而是一张充满暗流、秘密、利益纠葛和情感债务的网。

{CHINESE_WRITING_STANDARDS}

{INTERACTIVE_GAME_WRITING}

{world_binding_block}

【关系网络设计铁律】
1. **密度法则（硬性要求）**：{n}个角色之间最多可形成{max_possible_relations}条关系，**至少需要{min_relations}条关系（密度≥60%）**，形成密集的关系网
2. **三角关系**：至少3组三角关系（A→B→C→A，形成情感/利益/信息的闭环）
3. **暗线关系（硬性要求）**：至少{min_hidden_relations}条关系为暗线类型（secret_ally/hidden_enemy/blackmailer/informant等），占关系总数≥20%
4. **信息不对称（硬性要求）**：每条关系必须包含结构化的信息不对称——A知道B什么、B知道A什么，且信息必须不对称（双方掌握的信息量和深度不同）
5. **关系弧线预规划（硬性要求）**：每条关系必须标注预期变化方向和引爆点条件
6. **关系层次**：每对角色之间可以有多重关系（如：表面是同僚，暗地是恋人，实际是仇敌的后代）
7. **引爆点**：至少3条关系的trust或favor接近引爆点（≤20），随时可能爆发冲突
8. **权力结构**：关系网络中必须有明确的权力流动（谁操控谁、谁依赖谁、谁欠谁）
9. **互锁效应**：改变任何一条关系，都会像多米诺骨牌一样影响其他关系

【关系类型扩展】
除了常见关系（亲属/恋人/挚友/宿敌/师徒/同僚/对手/陌路/仰慕/背叛/守护/操控），
还必须包含以下高级关系类型（暗线关系必须使用这些类型）：
- secret_ally: 秘密盟友（表面无关，暗中合作）
- hidden_enemy: 隐藏仇敌（表面友好，暗中对抗）
- debtor: 债务人（欠对方人情/性命/承诺）
- blackmailer: 要挟者（掌握对方把柄）
- informant: 线人/告密者（向对方出卖信息）
- surrogate: 替身/影子（与对方有某种替代关系）
- former_bond: 昔日羁绊（曾经亲密，如今疏远/对立）
- information_broker: 信息掮客（掌握并交易对方的信息）

【回答格式】
严格的JSON数组，在```json```代码块中：
```json
[
  {{
    "char_a_name": "角色A名称",
    "char_b_name": "角色B名称",
    "relation_type": "关系类型（从上述类型中选择）",
    "trust": 0-100（信任度，≤20为引爆点级别）,
    "favor": 0-100（好感度，≤20为引爆点级别）,
    "surface_description": "表面关系描述（他人看到的关系，200-500字）",
    "deep_description": "深层关系描述（真实的关系状态，200-500字）",
    "info_asymmetry": {{
      "a_knows_about_b": "A知道关于B的核心信息/秘密（必须具体，不能泛泛而谈，50-200字）",
      "b_knows_about_a": "B知道关于A的核心信息/秘密（必须与A知道的不对称，50-200字）"
    }},
    "is_hidden": true或false（是否为暗线关系，暗线关系必须为true）,
    "arc_direction": "improving|deteriorating|stable（关系弧线预期变化方向）",
    "trigger_condition": "引爆点条件描述（当XX事件发生时，信任度/好感度骤变，50-200字）",
    "arc_milestones": [
      {{"chapter": 章节序号, "event": "里程碑事件描述", "trust_change": 信任度变化值（如-30）, "favor_change": 好感度变化值（如-20）}},
      {{"chapter": 章节序号, "event": "另一个里程碑事件", "trust_change": 变化值, "favor_change": 变化值}}
    ],
    "relation_arc": "关系弧线（初始→关键事件→可能走向，200-500字）",
    "detonator": "引爆条件（什么事件会让这条关系彻底破裂或反转，100-300字）"
  }}
]
```"""

    user_prompt = f"""请为以下角色生成完整的关系网络：

━━━━━━━━━━━━━━━━━━━━━━
🎭 题材：{genre or '未指定'}
━━━━━━━━━━━━━━━━━━━━━━
{f"🌍 世界观：\n{world_context}\n━━━━━━━━━━━━━━━━━━━━━━" if world_context else ""}
👥 角色列表（{n}个）：
{char_context}
━━━━━━━━━━━━━━━━━━━━━━

【创作要求 — 硬性指标】
1. **关系密度≥60%**：生成至少{min_relations}条关系（{n}个角色最多{max_possible_relations}条，需达到60%密度）
2. **暗线关系≥20%**：至少{min_hidden_relations}条关系的is_hidden为true，relation_type使用secret_ally/hidden_enemy/blackmailer/informant等暗线类型
3. **信息不对称**：每条关系的info_asymmetry必须填写，且a_knows_about_b和b_knows_about_a的信息量和深度必须不对称
4. **关系弧线**：每条关系必须填写arc_direction（improving/deteriorating/stable）和trigger_condition
5. **弧线里程碑**：每条关系至少2个arc_milestones，标注章节、事件、信任度/好感度变化值

【创作要求 — 质量指标】
6. 包含至少3组三角关系
7. 至少3条关系的trust或favor ≤ 20（引爆点级别）
8. 关系之间要互锁——改变一条会影响其他
9. 确保关系网络与世界观和角色动机高度一致
10. **完整性优先**：所有字段必须填写完整，JSON结构必须正确闭合，不能写到一半中断

请直接输出JSON数组，不要添加任何解释。"""

    return system_prompt, user_prompt

def build_chapter_outline_prompt(project_name: str, genre: str, tone: str,
                                  target_chapters: int, existing_chapters: list,
                                  world_context: str,
                                  character_context: str = "",
                                  target_words: int = 500000,
                                  foreshadow_context: str = "",
                                  world_config_items: dict | None = None) -> tuple[str, str]:
    """
    章节大纲设计提示词（重构版）。
    支持两种模式：
    - 全新生成：existing_chapters 为空时，设计完整大纲
    - 续写补充：existing_chapters 非空时，只生成后续章节，必须与已有章节自然衔接

    新增能力：
    - 每章2-5个节（section），节遵循漏斗模型排列
    - 每个节包含：标题/目标字数/情感目标/涉及角色/伏笔任务/互动选择设计
    - 章节关联世界观设定（worldview_refs）
    - 章节标注聚焦角色及关系变化预期（focus_characters）
    - 章节标注伏笔任务（埋设/强化/回收）
    - 字数根据项目目标字数和章节数自动分配
    """
    is_continuation = bool(existing_chapters and len(existing_chapters) > 0)

    words_per_chapter = max(3000, target_words // max(target_chapters, 1))

    world_config_context = ""
    if world_config_items:
        config_lines = []
        for key, value in world_config_items.items():
            label = WORLD_CONFIG_LABELS.get(key, key)
            if value and isinstance(value, str) and value.strip():
                config_lines.append(f"  ▸ {label}（{key}）：{value[:300]}")
        if config_lines:
            world_config_context = "\n".join(config_lines)

    SECTION_STRUCTURE = f"""【节（Section）结构要求 — 每章必须包含2-5个节】

每章必须划分为2-5个节，每个节是章节内的叙事单元。节的排列必须遵循**漏斗模型**：

1. **开头节（exploration，自由探索）**：1-2个节
   - branch_type = "exploration"
   - 自由探索世界、收集信息、建立角色关系
   - 互动选择偏向信息获取和关系建立
   - 允许玩家自由探索，不施加时间压力

2. **中段节（decision，关键抉择）**：1-2个节
   - branch_type = "decision"
   - 面临道德困境或关键抉择
   - 互动选择具有重大后果，影响后续剧情走向
   - 信息差在此处发挥最大作用

3. **结尾节（convergence，汇入主线）**：1个节
   - branch_type = "convergence"
   - 不同选择的结果汇入主线
   - 揭示本章核心冲突的阶段性结果
   - 设置章末钩子，驱动玩家进入下一章

每个节必须包含以下字段：
- title：节标题
- word_target：目标字数（所有节的word_target之和应≈{words_per_chapter}字）
- emotion_target：情感目标值（0-10）
- focus_characters：涉及角色列表
- foreshadow_tasks：伏笔任务列表（标注动作：plant埋设/reinforce强化/reclaim回收）
- choices：互动选择设计（2-4个选项，遵循"道德灰度"原则：没有完美答案，每个选择都有代价）

【互动选择设计规范 — 必须遵守】

每个选项必须包含以下完整字段：
- text：选项文本（玩家看到的选项描述）
- consequence_direct：直接后果（选择后立即发生的结果，100-200字）
- consequence_indirect：间接后果（选择后中期显现的连锁反应，100-200字）
- consequence_long_term：远期后果（选择后在后续章节中逐步暴露的深层影响，100-200字）
- character_impact：角色影响数组 [{{"character_id": "角色名", "trust_change": -10~+10, "affection_change": -10~+10, "description": "影响描述"}}]
- is_hidden：是否为隐藏选项（布尔值，默认false）
- hidden_condition：隐藏选项触发条件（仅当is_hidden=true时填写，描述什么条件下此选项才会出现）
- moral_alignment：道德倾向（good/neutral/evil/gray之一，标注此选择的道德色彩）

选择设计铁律：
1. **道德灰度原则**：每个决策节至少2个选项，没有完美答案——好选择有隐性代价，坏选择有合理动机
2. **后果链推演**：每个选项的三层后果（直接→间接→远期）必须形成因果递进链，不能断裂
3. **角色影响差异化**：不同选项对同一角色的影响必须显著不同，对同一选项不同角色的影响必须方向各异
4. **隐藏选项**：每个关键决策节（branch_type=decision）必须包含1个隐藏选项（is_hidden=true），隐藏选项通常是"第三条路"——跳出二元对立的创造性解法
5. **分支层级控制**：选择导致的分支层级控制在3-4级以内，避免分支爆炸
6. **信息差利用**：玩家在不同信息掌握程度下会做出不同选择，选项设计要考虑信息不对称"""

    WORLD_BINDING = """【世界观深度绑定 — 章节必须与世界观设定关联】

1. **worldview_refs（世界观引用）**：每章必须标注引用了哪些世界观配置项，说明如何引用
   - 格式：[{{"config_key": "social_structure", "description": "本章通过主角进入贵族区展现社会阶层的不可逾越"}}]
   - 必须至少引用2个世界观配置项
   - 引用必须具体，不能泛泛而谈

2. **核心冲突绑定**：每章的core_conflict必须根植于世界观核心矛盾

3. **约束遵守**：章节事件不得违反世界观约束条件和不可能事项"""

    CHARACTER_FOCUS = """【聚焦角色与关系变化 — 章节必须标注】

1. **focus_characters（聚焦角色）**：每章必须标注2-4个聚焦角色
   - 格式：[{{"name": "角色名", "relation_change": "与主角从怀疑转为试探性信任"}}]
   - 每个聚焦角色必须标注预期关系变化方向
   - 关系变化必须与本章事件有因果关系

2. **角色弧线推进**：每章至少有一个角色发生状态变化（获得新信息/改变立场/暴露秘密）

3. **信息差利用**：不同角色在本章掌握的信息必须不对称"""

    FORESHADOW_TASK = """【伏笔任务标注 — 章节必须标注】

每章的foreshadow_tasks必须标注具体的伏笔操作：
- 格式：[{{"foreshadow_name": "伏笔名称", "action": "plant|reinforce|reclaim", "description": "具体操作描述"}}]
- plant（埋设）：在本章首次植入伏笔线索
- reinforce（强化）：在本章再次暗示已有伏笔
- reclaim（回收）：在本章揭露伏笔真相

伏笔节奏要求：
- 每2-3章埋设新伏笔（plant）
- 每1-2章强化已有伏笔（reinforce）
- 每4-6章回收旧伏笔（reclaim）
- 章节末尾的节优先安排伏笔强化或回收"""

    CHAPTER_WORD_DISTRIBUTION = f"""【字数自动分配】

项目目标总字数：{target_words}字
目标章节数：{target_chapters}章
每章平均字数：约{words_per_chapter}字

字数分配原则：
- 开头章（第1-2章）可适当多分配（建立世界观和角色）
- 中间章节按平均字数分配
- 高潮章节可适当多分配（情感重场需要更多篇幅）
- 结尾章可适当多分配（收束伏笔和角色弧线）
- 每章内各节的word_target之和应等于该章的总目标字数"""

    OUTPUT_FORMAT = f"""【输出格式 - 严格的JSON】
在```json```代码块中：
```json
{{
  "overall_structure": "整体结构分析（300-800字，说明叙事弧线、伏笔节奏、角色弧线推进计划）",
  "outline": [
    {{
      "chapter_number": 1,
      "title": "章节标题",
      "summary": "章节摘要（200-500字，必须引用世界观设定）",
      "core_conflict": "本章核心冲突（200-500字）",
      "emotion_target": 1-10,
      "word_target": {words_per_chapter},
      "worldview_refs": [
        {{"config_key": "social_structure", "description": "如何引用此世界观设定"}}
      ],
      "focus_characters": [
        {{"name": "角色名", "relation_change": "预期关系变化"}}
      ],
      "foreshadow_tasks": [
        {{"foreshadow_name": "伏笔名称", "action": "plant|reinforce|reclaim", "description": "具体操作描述"}}
      ],
      "turning_points": ["关键转折点"],
      "hook": "章末钩子",
      "sections": [
        {{
          "section_number": 1,
          "title": "节标题",
          "branch_type": "exploration|decision|convergence",
          "word_target": 3000,
          "emotion_target": 1-10,
          "focus_characters": ["涉及角色1", "涉及角色2"],
          "foreshadow_tasks": [
            {{"foreshadow_name": "伏笔名称", "action": "plant|reinforce|reclaim", "description": "具体操作描述"}}
          ],
          "choices": [
            {{
              "text": "选项文本",
              "consequence_direct": "直接后果（选择后立即发生，100-200字）",
              "consequence_indirect": "间接后果（中期显现的连锁反应，100-200字）",
              "consequence_long_term": "远期后果（后续章节逐步暴露的深层影响，100-200字）",
              "character_impact": [
                {{"character_id": "角色名", "trust_change": -10~+10, "affection_change": -10~+10, "description": "影响描述"}}
              ],
              "is_hidden": false,
              "hidden_condition": "隐藏选项触发条件（仅is_hidden=true时填写）",
              "moral_alignment": "good|neutral|evil|gray"
            }}
          ],
          "summary": "节内容摘要（100-300字）"
        }}
      ]
    }}
  ]
}}
```

【节排列漏斗模型示例】
3节排列：exploration → decision → convergence
4节排列：exploration → exploration → decision → convergence
5节排列：exploration → exploration → decision → decision → convergence"""

    if is_continuation:
        existing_details = []
        for ch in existing_chapters:
            parts = [f"第{ch.get('chapter_number', ch.get('number', '?'))}章「{ch.get('title', '未命名')}」"]
            if ch.get('core_conflict') or ch.get('summary'):
                parts.append(f"  核心冲突: {ch.get('core_conflict', ch.get('summary', '未设定'))}")
            if ch.get('emotion_target') is not None:
                parts.append(f"  情感目标: {ch.get('emotion_target')}/10")
            if ch.get('key_turning_points') or ch.get('turning_points'):
                tp = ch.get('key_turning_points') or ch.get('turning_points') or []
                if isinstance(tp, list) and tp:
                    parts.append(f"  转折点: {', '.join(str(t) for t in tp)}")
            if ch.get('foreshadow_tasks'):
                ft = ch.get('foreshadow_tasks')
                if isinstance(ft, list) and ft:
                    parts.append(f"  伏笔: {', '.join(str(t) for t in ft)}")
            if ch.get('hook'):
                parts.append(f"  章末钩子: {ch['hook']}")
            if ch.get('key_characters') or ch.get('focus_characters'):
                kc = ch.get('key_characters') or ch.get('focus_characters') or []
                if isinstance(kc, list) and kc:
                    parts.append(f"  聚焦角色: {', '.join(str(c) for c in kc)}")
            existing_details.append("\n".join(parts))
        existing_info = "\n\n".join(existing_details)

        last_chapter = existing_chapters[-1] if existing_chapters else {}
        last_ch_num = last_chapter.get('chapter_number', last_chapter.get('number', len(existing_chapters)))
        additional_chapters = max(3, target_chapters - int(last_ch_num))

        system_prompt = f"""你是中国顶尖的互动影游剧本结构师，你的"三幕十五节"和"五幕波浪"理论被业界广泛采用。

{CHINESE_WRITING_STANDARDS}

{INTERACTIVE_GAME_WRITING}

【⚠️ 续写模式 — 极其重要】
项目中已经有 {len(existing_chapters)} 章了！你的任务是**只生成后续章节**，不是重新设计整个大纲！

你必须做到：
1. **只生成第{int(last_ch_num) + 1}章及之后的章节**，绝对不能重新生成已有章节
2. **严格承接已有章节的叙事线**——新章节的核心冲突必须由已有章节的未解决张力自然催生
3. **延续角色发展弧线**——角色在已有章节中的状态变化必须在新章节中体现
4. **延续伏笔系统**——已有章节中埋下的伏笔必须在新章节中适时强化或回收
5. **保持情感曲线连贯**——新章节的情感目标必须与已有章节形成合理的波浪起伏

【章节大纲设计铁律】
1. **波浪理论**：情感曲线必须是起伏的（高峰→低谷→更高峰→更深低谷→终极巅峰）
2. **因果链**：每一章必须由上一章的事件（或未解决的张力）自然催生
3. **伏笔节奏**：每2-3章埋新伏笔，每4-6章回收旧伏笔
4. **角色成长阶梯**：每章主角必须获得/失去某样东西（信息/盟友/能力/代价）
5. **哇塞时刻分布**：关键反转点均匀分布（不能全挤在结尾）
6. **钩子法则**：每章结尾必须有"明天一定要继续看"的钩子

{SECTION_STRUCTURE}

{WORLD_BINDING}

{CHARACTER_FOCUS}

{FORESHADOW_TASK}

{CHAPTER_WORD_DISTRIBUTION}

{OUTPUT_FORMAT}"""

        foreshadow_section = ""
        if foreshadow_context:
            foreshadow_section = f"""🔮 待处理伏笔（新章节必须安排这些伏笔的埋设/强化/回收）：
{foreshadow_context}
━━━━━━━━━━━━━━━━━━━━━━"""

        world_config_section = ""
        if world_config_context:
            world_config_section = f"""⚙️ 世界观配置项（章节worldview_refs必须引用这些配置项）：
{world_config_context}
━━━━━━━━━━━━━━━━━━━━━━"""

        user_prompt = f"""请在已有章节基础上，生成后续章节大纲：

━━━━━━━━━━━━━━━━━━━━━━
📖 项目：{project_name}
🎭 题材：{genre or '未指定'}
🎨 基调：{tone or '未指定'}
📐 已有：{len(existing_chapters)}章 → 目标：{target_chapters}章（需补充约{additional_chapters}章）
📝 目标总字数：{target_words}字（每章约{words_per_chapter}字）
━━━━━━━━━━━━━━━━━━━━━━
{world_context}
━━━━━━━━━━━━━━━━━━━━━━
{f"👥 角色信息：\n{character_context}\n━━━━━━━━━━━━━━━━━━━━━━" if character_context else ""}
{world_config_section}
{foreshadow_section}
📋 已有章节详情（新章节必须严格承接这些内容）：
{existing_info}
━━━━━━━━━━━━━━━━━━━━━━

【创作要求】
1. 只生成第{int(last_ch_num) + 1}章到第{target_chapters}章的大纲，绝对不要重新生成已有章节
2. 第{int(last_ch_num) + 1}章的核心冲突必须由第{int(last_ch_num)}章的未解决张力直接催生
3. 新章节必须延续已有章节中的角色发展弧线和伏笔线索
4. 情感曲线必须与已有章节形成连贯的波浪起伏
5. 每章必须包含2-5个节，节排列遵循漏斗模型
6. 每章必须标注worldview_refs（至少引用2个世界观配置项）
7. 每章必须标注focus_characters（2-4个聚焦角色及关系变化预期）
8. 每章必须标注foreshadow_tasks（伏笔的埋设/强化/回收）
9. 每个节必须包含互动选择设计（choices字段，2-4个选项，每个选项必须包含text/consequence_direct/consequence_indirect/consequence_long_term/character_impact/is_hidden/hidden_condition/moral_alignment完整字段）
10. 关键决策节（branch_type=decision）必须包含1个隐藏选项（is_hidden=true）
11. 选择设计遵循道德灰度原则：没有完美答案，每个选择都有代价
12. summary必须引用世界观设定

请直接输出JSON，不要输出任何其他内容。"""

    else:
        system_prompt = f"""你是中国顶尖的互动影游剧本结构师，你的"三幕十五节"和"五幕波浪"理论被业界广泛采用。

{CHINESE_WRITING_STANDARDS}

{INTERACTIVE_GAME_WRITING}

【章节大纲设计铁律】
1. **波浪理论**：情感曲线必须是起伏的（高峰→低谷→更高峰→更深低谷→终极巅峰）
2. **因果链**：每一章必须由上一章的事件（或未解决的张力）自然催生
3. **伏笔节奏**：每2-3章埋新伏笔，每4-6章回收旧伏笔
4. **角色成长阶梯**：每章主角必须获得/失去某样东西（信息/盟友/能力/代价）
5. **哇塞时刻分布**：关键反转点均匀分布（不能全挤在结尾）
6. **钩子法则**：每章结尾必须有"明天一定要继续看"的钩子

{SECTION_STRUCTURE}

{WORLD_BINDING}

{CHARACTER_FOCUS}

{FORESHADOW_TASK}

{CHAPTER_WORD_DISTRIBUTION}

{OUTPUT_FORMAT}"""

        foreshadow_section = ""
        if foreshadow_context:
            foreshadow_section = f"""🔮 待处理伏笔（章节必须安排这些伏笔的埋设/强化/回收）：
{foreshadow_context}
━━━━━━━━━━━━━━━━━━━━━━"""

        world_config_section = ""
        if world_config_context:
            world_config_section = f"""⚙️ 世界观配置项（章节worldview_refs必须引用这些配置项）：
{world_config_context}
━━━━━━━━━━━━━━━━━━━━━━"""

        user_prompt = f"""请为以下互动影游项目设计完整的章节大纲：

━━━━━━━━━━━━━━━━━━━━━━
📖 项目：{project_name}
🎭 题材：{genre or '未指定'}
🎨 基调：{tone or '未指定'}
📐 目标：{target_chapters}章
📝 目标总字数：{target_words}字（每章约{words_per_chapter}字）
━━━━━━━━━━━━━━━━━━━━━━
{world_context}
━━━━━━━━━━━━━━━━━━━━━━
{f"👥 角色信息：\n{character_context}\n━━━━━━━━━━━━━━━━━━━━━━" if character_context else ""}
{world_config_section}
{foreshadow_section}

【创作要求】
1. 设计{target_chapters}章完整大纲，每章包含2-5个节
2. 每章必须标注worldview_refs（至少引用2个世界观配置项）
3. 每章必须标注focus_characters（2-4个聚焦角色及关系变化预期）
4. 每章必须标注foreshadow_tasks（伏笔的埋设/强化/回收）
5. 每个节必须包含互动选择设计（choices字段，2-4个选项，每个选项必须包含text/consequence_direct/consequence_indirect/consequence_long_term/character_impact/is_hidden/hidden_condition/moral_alignment完整字段）
6. 关键决策节（branch_type=decision）必须包含1个隐藏选项（is_hidden=true）
7. 选择设计遵循道德灰度原则：没有完美答案，每个选择都有代价，分支层级控制在3-4级以内
8. 节排列遵循漏斗模型：exploration → decision → convergence
9. summary必须引用世界观设定
10. 必须符合经典叙事结构（三幕或五幕）
11. 每3-5章设定一个情感巅峰
12. 章与章之间有明确的因果递进
13. 充分利用可用空间，每章核心冲突写得越详细越好

请直接输出JSON，不要输出任何其他内容。"""

    return system_prompt, user_prompt


# ============================================================================
#  场景生成升级标准（互动影游场景必须遵守）
# ============================================================================

SCENE_GEN_UPGRADED_STANDARDS = """
【场景生成升级标准 — 互动影游场景必须遵守】

## 1. 场景叙述标准
- 叙述必须包含画面感+感官描写，至少涵盖两种感官（视觉、听觉、嗅觉、触觉、味觉）
- 感官描写必须服务于叙事目的，不能为描写而描写
- 每个场景必须标注使用了哪些感官（sensory_tags字段）
- 视觉：光影、色彩、空间、运动
- 听觉：环境音、对白音色、沉默的质感
- 嗅觉：气味是最强的记忆触发器，用气味唤起角色和读者的情感
- 触觉：温度、质感、疼痛、风、雨
- 味觉：食物、血、泪水、灰尘

## 2. 对白标准
- 每句对白必须包含潜台词：字面意思与真实意图之间存在落差（角色永远口是心非）
- 每句对白必须反映角色的语言风格和口头禅
- 每句对白必须标注：说话角色(char)、台词文本(text)、潜台词(subtext)、语言风格(language_style)、口头禅引用(catchphrase_ref)
- 不同角色的说话方式必须有区分度：句式长短、用词范围、语速、语气词

## 3. 互动选择标准
- 每个场景必须包含2-3个互动选项
- 每个选项必须包含三层后果推演：
  - consequence_direct：直接后果（选择后立即发生的结果）
  - consequence_indirect：间接后果（中期显现的连锁反应）
  - consequence_long_term：远期后果（远期逐步暴露的深层影响）
- 每个选项必须标注道德倾向(moral_alignment)：good/neutral/evil/gray
- 遵循道德灰度原则：没有完美答案，每个选择都有代价
- 好选择有隐性代价，坏选择有合理动机

## 4. 伏笔操作标准
- 每个伏笔操作必须标注操作类型(op)：plant（埋设）/reinforce（强化）/reveal（揭露）
- 每个伏笔操作必须标注涉及的伏笔ID(fs_id)
- 每个伏笔操作必须标注关联的世界观设定(worldview_ref)：config_key+描述
- 每个伏笔操作必须包含具体的文本实现方式(text_implementation)：如何在叙述/对白/动作中埋设伏笔
  - 在叙述中埋设：通过环境描写、感官细节暗示
  - 在对白中埋设：通过双关语、口误、回避话题暗示
  - 在动作中埋设：通过角色下意识动作、异常行为暗示

## 5. 因果链标准
- 因果链必须包含完整五环节：
  - preconditions：前置条件（来自前序场景或世界观设定的具体叙事内容）
  - catalyst：催化剂（触发本场景核心事件的具体叙事内容）
  - direct_result：直接结果（本场景中立即产生的具体叙事结果）
  - indirect_result：间接结果（本场景后中期显现的具体叙事影响）
  - far_result：远期结果（远期逐步暴露的具体叙事影响）
- 每个环节必须有具体的叙事内容，不能是抽象概括
- 前置条件必须来自前序场景或世界观设定
- 因果链必须与互动选择的后果推演形成呼应

## 6. 上下文引用标准
- 场景生成必须引用前2个场景的完整文本（叙述+对白+动作+伏笔操作+选择+因果链）
- 场景生成必须引用世界观设定
- 场景生成必须引用角色当前状态（位置、情感、已知信息、关系变化）
- 场景生成必须引用伏笔任务清单（待埋设/强化/回收的伏笔）
- 所有上下文信息必须在Prompt中完整注入，确保场景与全局叙事的连贯性
"""


def build_scene_gen_prompt(
    world_context: str,
    character_states: str,
    previous_scenes: str,
    chapter_info: str,
    scene_code: str,
    scene_type: str,
    emotion_target: int,
    location: str,
    weather: str,
    foreshadow_tasks: str,
    word_constraints: str = "",
    wow_requirements: str = "",
    rag_context: str = "",
    genre: str = "",
    style: str = "",
) -> tuple[str, str]:
    """
    场景生成提示词（升级版）。
    返回 (system_prompt, user_prompt)

    升级内容：
    - 场景叙述必须包含画面感+感官描写（至少两种感官）
    - 对白必须包含潜台词+角色语言风格+口头禅标注
    - 互动选择必须包含2-3选项+三层后果推演+道德倾向
    - 伏笔操作必须标注操作类型+伏笔ID+世界观关联+文本实现方式
    - 因果链必须包含五环节+具体叙事内容
    - 场景生成必须引用前2场景全文+世界观+角色状态+伏笔任务
    """
    system_prompt = f"""你是全球顶尖的互动影游场景编剧，你的场景文字让玩家"忘记自己在玩游戏"。

{CHINESE_WRITING_STANDARDS}

{INTERACTIVE_GAME_WRITING}

{SCENE_GEN_UPGRADED_STANDARDS}

【场景写作生死线——违反任何一条，作品直接报废】
1. **narration必须是完整的小说正文**，读者不需要任何补充说明就能沉浸其中。像金庸、古龙、刘慈欣那样写环境、写动作、写心理、写氛围。
2. **dialogue必须是角色实际说出口的完整台词**，不是"他说了关于XX的事"这种间接叙述。
3. **你必须真正"写"场景，不是"描述"场景**——禁止输出大纲、摘要、设定说明、分镜脚本。

【输出JSON格式 — 必须严格遵守】
```json
{{{{
  "narration": "完整的小说式场景叙述正文（必须包含画面感+至少两种感官描写：视觉、听觉、嗅觉、触觉、味觉）",
  "sensory_tags": ["使用的感官类型，如：视觉", "听觉"],
  "dialogue": [
    {{{{
      "char": "角色名",
      "text": "角色实际说出的完整台词",
      "subtext": "潜台词/真实意图（字面意思与真实意图的落差）",
      "language_style": "该角色的语言风格标注（如：言简意赅/文绉绉/口语化）",
      "catchphrase_ref": "口头禅引用（如有，标注口头禅内容；无则填空字符串）"
    }}}}
  ],
  "actions": ["关键动作描写1", "关键动作描写2", "关键动作描写3"],
  "foreshadow_ops": [
    {{{{
      "fs_id": "伏笔ID",
      "op": "plant/reinforce/reveal",
      "content": "具体内容描述",
      "worldview_ref": "关联的世界观设定（config_key+描述，如：social_structure-社会阶层不可逾越）",
      "text_implementation": "文本实现方式（如何在叙述/对白/动作中埋设此伏笔，如：通过角色A闻到异常气味暗示XX）"
    }}}}
  ],
  "choices": [
    {{{{
      "id": "A",
      "text": "选项文本",
      "consequence_direct": "直接后果（选择后立即发生的结果，100-200字）",
      "consequence_indirect": "间接后果（中期显现的连锁反应，100-200字）",
      "consequence_long_term": "远期后果（远期逐步暴露的深层影响，100-200字）",
      "moral_alignment": "good/neutral/evil/gray",
      "next_scene": "下一场景编号"
    }}}}
  ],
  "causal_chain": {{{{
    "preconditions": ["前置条件1（具体叙事内容，来自前序场景或世界观设定）", "前置条件2"],
    "catalyst": "催化剂（触发本场景核心事件的具体叙事内容）",
    "direct_result": "直接结果（本场景中立即产生的具体叙事结果）",
    "indirect_result": "间接结果（本场景后中期显现的具体叙事影响）",
    "far_result": "远期结果（远期逐步暴露的具体叙事影响）"
  }}}},
  "emotion_level": 1-10,
  "suggestions": ["下一场景可关注的发展线索..."]
}}}}
```

【正确vs错误的例子】
❌ 错误 narration："场景发生在酒馆，主角和反派对峙。"
✅ 正确 narration："酒馆的灯笼在穿堂风里摇晃，把两人的影子撕成碎片。主角的手指扣在腰间的剑柄上，指节发白。空气中弥漫着劣质麦酒和汗渍的酸味。'你来了。'他说，声音比想象中稳。"

❌ 错误 dialogue：{{"char": "角色A", "text": "我对你很失望", "subtext": "我对你很失望"}}
✅ 正确 dialogue：{{"char": "角色A", "text": "这杯酒我敬你——敬你当年在雪地里给我那块干粮。", "subtext": "我记得你的恩情，但你也欠我一条命", "language_style": "言简意赅，每句不超过15字", "catchphrase_ref": "敬你"}}

❌ 错误 choices：{{"id": "A", "text": "帮助他", "consequence": "他感谢你"}}
✅ 正确 choices：{{"id": "A", "text": "将情报交给盟友", "consequence_direct": "盟友立即发动突袭，救出人质但损失惨重", "consequence_indirect": "敌方开始怀疑内部有叛徒，加强审查", "consequence_long_term": "盟友因这次行动获得的关键位置，在最终决战中成为决定性力量", "moral_alignment": "good"}}

❌ 错误 foreshadow_ops：{{"fs_id": "FS001", "op": "plant", "content": "暗示角色B的真实身份"}}
✅ 正确 foreshadow_ops：{{"fs_id": "FS001", "op": "plant", "content": "暗示角色B的真实身份", "worldview_ref": "history-百年前的流放事件", "text_implementation": "在叙述中描写角色B下意识触摸左耳的旧伤疤——与百年前流放者标记的传说吻合"}}

❌ 错误 causal_chain：{{"preconditions": ["前序事件"], "catalyst": "发生了什么", "direct_result": "结果", "indirect_result": "间接结果", "far_result": "远期结果"}}
✅ 正确 causal_chain：{{"preconditions": ["角色A在前一场景中获得了密室的钥匙", "世界观设定中百年流放者的后裔隐藏在贵族中"], "catalyst": "角色B在酒馆中下意识触摸左耳旧伤疤，被角色A注意到", "direct_result": "角色A开始怀疑角色B的身份，但选择不动声色", "indirect_result": "角色A开始暗中调查角色B的背景，导致两人关系出现裂痕", "far_result": "角色B的真实身份揭露，引发贵族阶层的权力重组"}}

【绝对禁止】
- narration写成"场景概述"、"剧情提要"、"分镜说明"或"设定描述"
- dialogue写成"角色讨论了XX问题"这种间接叙述
- 用 bullet points 或编号列表代替文学描写
- 输出类似"本场景主要讲述..."的元描述
- 对白没有潜台词（字面意思=真实意图）
- 互动选择只有单一后果，没有三层推演
- 互动选择缺少道德倾向标注
- 伏笔操作缺少世界观关联或文本实现方式
- 因果链环节用抽象概括代替具体叙事内容

【必须遵守】
- narration 必须是完整的文学性叙述文字，要像出版小说一样有画面感
- narration 必须包含至少两种感官描写（视觉/听觉/嗅觉/触觉/味觉），并在sensory_tags中标注
- dialogue 必须是完整的对话，每句台词都要有潜台词，不同角色说话方式必须有区分度
- 每句对白必须标注说话角色的语言风格(language_style)和口头禅引用(catchphrase_ref)
- 互动选择必须包含2-3个选项，每个选项有三层后果推演和道德倾向标注
- 伏笔操作必须标注操作类型(op)、伏笔ID(fs_id)、世界观关联(worldview_ref)和文本实现方式(text_implementation)
- 因果链五环节都必须有具体叙事内容，不能是抽象概括
- 叙事必须符合世界观设定，不得出现矛盾内容
- 角色行为必须与其性格、动机、语言风格一致，每个角色的口头禅和说话方式必须体现
- 与前序场景保持因果连续性，自然衔接——角色在哪里、在做什么、知道什么信息必须延续
- 精准控制篇幅，确保内容充实有深度，总字数必须达到字数要求
- 场景结尾必须暗示后续发展的可能性（分支预埋）
- 如果前序场景有角色受伤/获得信息/关系变化，本场景必须体现这些变化

【自检清单——输出前确认】
□ narration读起来像小说正文，不是摘要
□ dialogue是角色直接说出的台词，不是描述
□ narration包含至少两种感官描写，sensory_tags已标注
□ 每句对白都有潜台词标注，且潜台词与字面意思存在落差
□ 每句对白都标注了语言风格和口头禅引用
□ 互动选择有2-3个选项，每个有三层后果推演和道德倾向
□ 伏笔操作有操作类型、伏笔ID、世界观关联和文本实现方式
□ 因果链五环节都有具体叙事内容
□ 把narration和dialogue连起来读，是一个完整的、有画面感的场景
□ 达到了字数要求"""

    user_prompt = f"""请为以下互动影游项目撰写一个完整的场景：

━━━━━━━━━━━━━━━━━━━━━━
🎭 题材/风格：{genre} / {style}
━━━━━━━━━━━━━━━━━━━━━━
🌍 世界观设定：
{world_context}
━━━━━━━━━━━━━━━━━━━━━━
👥 角色详细档案：
{character_states}
━━━━━━━━━━━━━━━━━━━━━━
📖 前序场景全文（必须严格保持叙事连续性——角色位置、情感状态、已知信息必须自然衔接）：
{previous_scenes}
━━━━━━━━━━━━━━━━━━━━━━
📚 章节上下文：
{chapter_info}
━━━━━━━━━━━━━━━━━━━━━━
🎬 本场景任务：
- 场景编号: {scene_code}
- 场景类型: {scene_type}
- 情感目标: {emotion_target}/10
- 地点: {location}
- 天气: {weather}
- 伏笔任务: {foreshadow_tasks}
━━━━━━━━━━━━━━━━━━━━━━
{wow_requirements}
{word_constraints}
{f"📚 参考素材：\\n{rag_context}\\n━━━━━━━━━━━━━━━━━━━━━━" if rag_context else ""}

请直接输出JSON，不要输出任何其他内容。"""

    return system_prompt, user_prompt


def build_wow_plan_prompt(foreshadow_context: str, character_context: str,
                           core_truth: str = "", worldview_context: str = "") -> tuple[str, str]:
    """
    哇塞时刻（伏笔回收/反转）方案提示词。
    升级版：5种创意类型、4维评分、核心真相关联路径、回望线索设计。
    每条伏笔保留2-3个最优方案供用户选择。
    """
    core_truth_block = ""
    if core_truth and core_truth.strip():
        core_truth_block = f"""【⚠️ 核心真相绑定 — 强制约束，必须遵守】
本项目的核心真相：
{core_truth}

1. **关联路径强制**：每个哇塞方案必须标注与核心真相的关联路径（truth_connection_path），说明该方案如何从核心真相反推而来、揭露核心真相的哪个层面
2. **回望线索强制**：每个哇塞方案必须包含"回望线索"设计（retrospective_clues）——玩家在揭晓后回顾前文时能发现的3-5个暗示，这些暗示在首次阅读时不会引起注意，但揭晓后回看会恍然大悟
3. **真相递进**：方案的揭露不能一次性揭示全部核心真相，必须设计为逐步逼近的递进路径"""

    worldview_block = ""
    if worldview_context and worldview_context.strip():
        worldview_block = f"""【⚠️ 世界观上下文 — 方案必须与世界观自洽】
{worldview_context}

1. 每个方案的逻辑必须在世界观框架内自洽，不得违反世界观约束条件和不可能事项
2. 方案中的反转/揭露必须能引发对世界观设定的重新认知
3. 方案中涉及的能力、技术、魔法等必须与世界观设定一致"""

    system_prompt = f"""你是"哇塞时刻"首席设计师，你的反转方案曾被玩家称为"让我把手柄摔了"级别的震撼。

{CHINESE_WRITING_STANDARDS}

{INTERACTIVE_GAME_WRITING}

{core_truth_block}

{worldview_block}

【哇塞时刻设计铁律】
1. **"原来如此"时刻**：反转必须在揭晓的瞬间让玩家/读者觉得"早就该想到"（但之前没想到）
2. **代价**：每次反转必须有代价——角色失去/获得/改变，没有代价的反转是廉价的
3. **连锁反应**：一个好的反转不只是"揭露"，而是改变整个故事的走向
4. **回望价值**：反转揭晓后，玩家回顾前文必须能发现被忽略的线索，产生"原来早有暗示"的震撼
5. **核心真相关联**：每个哇塞方案必须与核心真相有明确的逻辑链条，不是孤立的反转

【5种创意类型 — 每个方案必须选择其一】
1. **反转（reversal）**：颠覆玩家对角色/事件/关系的既有认知。例：你以为的受害者其实是幕后推手
2. **信息差（info_gap）**：利用角色/玩家之间的信息不对称制造震撼。例：玩家以为全知全能，实则被刻意投喂了片面信息
3. **角色弧光（character_arc）**：角色在极端压力下展现出完全不同的一面，颠覆玩家预期。例：懦弱者在关键时刻做出最勇敢的选择
4. **世界观颠覆（worldview_shatter）**：揭露世界运行规则的真相，让玩家重新理解整个故事。例：这个世界本身就是一场实验
5. **情感核弹（emotion_bomb）**：不靠信息反转，靠情感关系的极致爆发制造冲击。例：最信任的人为保护主角而选择被误解一生

【4维评分标准 — 每个方案必须自评，且必须达标】
| 维度 | 范围 | 达标线 | 说明 |
|------|------|--------|------|
| 可预测性（predictability） | 3-7 | 3-7 | 过低=太明显无惊喜，过高=突兀无铺垫，最佳区间5-6 |
| 情感冲击（emotional_impact） | 1-10 | ≥8 | 方案揭晓时对玩家/角色的情感震撼程度 |
| 逻辑自洽（logical_coherence） | 1-10 | ≥8 | 方案在世界观和已有剧情框架内是否完全说得通 |
| 回望价值（retrospective_value） | 1-10 | ≥7 | 玩家回看前文时能发现的暗示数量和清晰度 |

评分不达标的方案必须修改后重新提交，不可输出不达标方案。"""

    user_prompt = f"""请为以下伏笔设计2-3个震撼级别的"哇塞时刻"回收方案：

━━━━━━━━━━━━━━━━━━━━━━
🔮 伏笔详情：
{foreshadow_context}
━━━━━━━━━━━━━━━━━━━━━━
{f'👤 相关角色：\n{character_context}\n━━━━━━━━━━━━━━━━━━━━━━' if character_context else ''}
{f'🔮 核心真相：\n{core_truth}\n━━━━━━━━━━━━━━━━━━━━━━' if core_truth and core_truth.strip() else ''}
{f'🌍 世界观上下文：\n{worldview_context}\n━━━━━━━━━━━━━━━━━━━━━━' if worldview_context and worldview_context.strip() else ''}

【输出格式 - 严格的JSON】
在```json```代码块中：
```json
[
  {{
    "creative_type": "reversal|info_gap|character_arc|worldview_shatter|emotion_bomb",
    "creative_type_label": "反转|信息差|角色弧光|世界观颠覆|情感核弹",
    "title": "方案名称（一句话，如：谁才是真正的叛徒？）",
    "summary": "核心设定描述（500-1500字，必须具体到场景、角色、事件）",
    "truth_connection_path": "与核心真相的关联路径（200-500字，说明该方案如何从核心真相反推、揭露核心真相的哪个层面）",
    "retrospective_clues": [
      "回望线索1：在前文第X章/场景中的暗示描述（50-150字，首次阅读时不显眼，揭晓后回看恍然大悟）",
      "回望线索2：另一处暗示描述",
      "回望线索3：又一处暗示描述"
    ],
    "setup_needed": "需要在前文预埋哪些线索（100-300字）",
    "emotional_impact_desc": "对角色和读者的情感冲击描述（100-300字）",
    "consequence": "揭晓后如何改变故事走向（100-300字）",
    "scores": {{
      "predictability": 3-7（可预测性，3=完全出乎意料但有铺垫，7=有一定可预测性），
      "emotional_impact": 1-10（情感冲击，必须≥8），
      "logical_coherence": 1-10（逻辑自洽，必须≥8），
      "retrospective_value": 1-10（回望价值，必须≥7）
    }},
    "overall_score": 1-100（综合冲击力，由4维评分加权计算）
  }}
]
```

【创作要求 — 硬性指标】
1. 每条伏笔生成2-3个方案，供用户选择最优方案
2. 每个方案的creative_type必须从5种类型中选择，且同一伏笔的多个方案尽量覆盖不同类型
3. 4维评分必须达标：可预测性3-7、情感冲击≥8、逻辑自洽≥8、回望价值≥7
4. truth_connection_path必须明确说明与核心真相的逻辑链条
5. retrospective_clues必须提供3-5个具体的回望线索，标注在前文的大致位置
6. summary必须具体到场景、角色、事件，不能泛泛而谈

【创作要求 — 质量指标】
7. 方案之间风格差异显著（如：一个走反转路线，一个走情感核弹路线）
8. 每个方案必须在世界观框架内逻辑自洽
9. 回望线索必须自然融入前文，不能是生硬的"此处有伏笔"式标注
10. 方案揭晓后必须能改变故事的走向，不能只是"哦原来如此"就结束了

请直接输出JSON数组，不要输出任何其他内容。"""

    return system_prompt, user_prompt


def build_full_audit_prompt(project_info: dict, stats: dict,
                             issues_summary: str) -> tuple[str, str]:
    """
    全局项目审计提示词。
    """
    system_prompt = f"""你是互动影游项目的首席制作人，负责对项目进行全局质量审计。你的审计报告直接影响项目的发布决策。

【审计维度（满分100）】
A. 故事核心理念（concept）
B. 角色立体度（characters）
C. 世界观深度（world_building）
D. 叙事节奏（pacing）
E. 伏笔系统健康度（foreshadow_network）
F. 互动适配质量（interactivity）
G. 总体完成度（completion）"""

    user_prompt = f"""请对以下互动影游项目进行全局质量审计：

═══════════════════════════════════════════
📖 项目概况
═══════════════════════════════════════════
{json.dumps(project_info, ensure_ascii=False, indent=2)}
═══════════════════════════════════════════
📊 项目统计
═══════════════════════════════════════════
{json.dumps(stats, ensure_ascii=False, indent=2)}
═══════════════════════════════════════════
⚠️ 已知问题
═══════════════════════════════════════════
{issues_summary or '无显著问题报告'}
═══════════════════════════════════════════

请以严格的JSON格式返回审计结果。"""

    return system_prompt, user_prompt


def build_foreshadow_design_prompt(
    core_truth: str,
    core_contradiction: str,
    world_settings: dict,
    characters: list,
    chapter_outlines: list,
    chapter_count: int = 20,
) -> tuple[str, str]:
    """
    三层伏笔体系设计提示词。
    从核心真相反推，设计全剧级/章节级/场景级三层伏笔，
    每条伏笔包含三层含义、世界观关联、角色关联、伏笔间关联、回收路径。
    """
    world_parts = []
    for key, label in [
        ("core_contradiction", "核心矛盾"),
        ("social_structure", "社会结构"),
        ("tech_magic", "科技/魔法体系"),
        ("geography", "地理环境"),
        ("history", "历史背景"),
        ("culture", "文化习俗"),
        ("constraints", "约束条件"),
        ("impossible", "不可能事项"),
    ]:
        val = world_settings.get(key, "")
        if val and isinstance(val, str) and val.strip():
            world_parts.append(f"  ▸ {label}（{key}）：{val}")
    world_context = "\n".join(world_parts) if world_parts else "  （世界观尚未详细设定）"

    char_lines = []
    for i, c in enumerate(characters or []):
        parts = [f"  {i+1}. 【{c.get('name', '?')}】({c.get('role_type', '未设定')})"]
        if c.get("core_goal"):
            parts.append(f"     核心动机：{c['core_goal']}")
        if c.get("core_fear"):
            parts.append(f"     核心恐惧：{c['core_fear']}")
        if c.get("surface_image"):
            parts.append(f"     表层印象：{c['surface_image']}")
        if c.get("true_self"):
            parts.append(f"     真实自我：{c['true_self']}")
        if c.get("dark_secret"):
            parts.append(f"     隐藏秘密：{c['dark_secret']}")
        char_lines.append("\n".join(parts))
    character_context = "\n\n".join(char_lines) if char_lines else "  （暂无角色设计）"

    chapter_lines = []
    for ch in chapter_outlines or []:
        ch_num = ch.get("chapter_number", ch.get("number", "?"))
        ch_title = ch.get("title", "")
        ch_summary = ch.get("summary", ch.get("outline", ch.get("core_conflict", "")))
        chapter_lines.append(f"  第{ch_num}章「{ch_title}」：{ch_summary}")
    chapter_context = "\n".join(chapter_lines) if chapter_lines else "  （暂无章节大纲）"

    system_prompt = f"""你是全球顶级的悬疑/剧情架构师，精通伏笔设计与回收。你曾为多部获奖互动影游设计伏笔网络，你的设计让玩家在回看时"恍然大悟"。

{CHINESE_WRITING_STANDARDS}

{INTERACTIVE_GAME_WRITING}

【核心真相反推逻辑 — 必须遵守】
你的设计必须从核心真相出发，反向推导如何向玩家逐步揭露：
1. **先确定核心真相**：核心真相是什么？它如何颠覆玩家的初始认知？
2. **设计揭露路径**：从核心真相出发，设计3-5个关键揭露节点，每个节点揭露一部分真相
3. **反推伏笔**：每个揭露节点需要哪些伏笔来支撑？这些伏笔在何时埋设？何时强化？何时回收？
4. **三层含义**：每条伏笔必须同时承载三层含义——表面层（普通观众能感知的）、深层层（细心观众能发现的）、真相层（与核心真相直接关联的）
5. **回收率规划**：核心伏笔（全剧级+章节级）的回收率不得低于80%，即至少80%的伏笔必须有明确的plant→reinforce→reveal完整路径

【三层伏笔体系 — 数量硬性要求】

### 第一层：全剧级伏笔（Global Level，5-8条）
- 埋设点在全剧前10%，回收点在全剧后20%
- 每条伏笔在全剧中需有3-5次强化（reinforce）
- 每条伏笔必须具备三层结构（surface_layer/deep_layer/truth_layer）
- 必须包含 wow_factor：描述回看前文恍然大悟的全新体验
- 必须与核心真相直接关联

### 第二层：章节级伏笔（Chapter Level，20-30条）
- 跨越3-5个章节，在A埋设、B强化、C回收
- 看似无关紧要的细节，实则为关键线索
- 必须与世界观设定或角色动机深度关联

### 第三层：场景级伏笔（Scene Level，60-100条）
- 在单一章节内完成埋设与回收
- 形式：双关语、环境描写的隐藏线索、角色行为的矛盾细节
- 为全剧级和章节级伏笔提供强化素材

【伏笔关联体系 — 四类关联】
每条伏笔必须标注与其他伏笔的关联关系：
- DEPENDS_ON：本伏笔的成立依赖目标伏笔先被埋设
- SUPPORTS：本伏笔为目标伏笔提供支撑线索
- ENABLES：本伏笔回收后才能启用目标伏笔
- CONFLICTS_WITH：本伏笔与目标伏笔存在张力/矛盾（制造戏剧冲突）

【世界观与角色深度绑定 — 强制要求】
1. 每条伏笔必须标注关联的世界观设定（config_key + 描述）
2. 每条伏笔必须标注关联的角色（character_id/名称 + 描述）
3. 伏笔的truth_layer必须与世界观深层设定或角色隐藏秘密直接关联
4. 伏笔的surface_layer不得与世界观约束条件矛盾

【回收路径规划 — 每条伏笔必须标注】
- plant_location：埋设位置（格式"章节.节"，如"3.2"表示第3章第2节）
- reinforce_locations：强化位置列表（格式同上，全剧级3-5个，章节级1-3个）
- reveal_location：揭露位置（格式同上）
- reclaim_status：回收状态（planted/reinforced/revealed/unplanted）

【哇塞方案预设计】
每条全剧级和章节级伏笔必须预设计2-3个"哇塞时刻"方案：
- 每个方案包含：type（反转类型）、title（方案名称）、summary（核心设定）、emotional_impact（情感冲击）、score（冲击力1-100）

【回答格式 — 严格的JSON】
在```json```代码块中输出：
```json
{{
  "design_philosophy": "从核心真相反推的设计思路（300-800字）",
  "revelation_path": [
    {{"node": "揭露节点1", "description": "揭露内容描述", "chapter_location": "章节位置"}},
    {{"node": "揭露节点2", "description": "揭露内容描述", "chapter_location": "章节位置"}}
  ],
  "foreshadows": [
    {{
      "name": "伏笔名称",
      "foreshadow_tier": "global | chapter | scene",
      "surface_layer": "表面层含义（普通观众能感知的，100-300字）",
      "deep_layer": "深层层含义（细心观众能发现的，100-300字）",
      "truth_layer": "真相层含义（与核心真相直接关联，100-300字）",
      "worldview_refs": [{{"config_key": "social_structure", "description": "如何关联此世界观设定"}}],
      "character_refs": [{{"character_name": "角色名", "description": "如何关联此角色"}}],
      "foreshadow_links": [{{"target_foreshadow_name": "目标伏笔名", "link_type": "DEPENDS_ON | SUPPORTS | ENABLES | CONFLICTS_WITH"}}],
      "plant_location": "3.1",
      "reinforce_locations": ["5.2", "8.3", "12.1"],
      "reveal_location": "18.2",
      "reclaim_status": "unplanted",
      "wow_factor": "回看体验描述（仅全剧级/章节级需要）",
      "wow_plans": [
        {{"type": "身份反转|信息反转|情境反转|情感爆发|多线交汇|真相揭露", "title": "方案名称", "summary": "核心设定（200-500字）", "emotional_impact": "情感冲击描述", "score": 85}}
      ]
    }}
  ],
  "stats": {{
    "global_count": 0,
    "chapter_count": 0,
    "scene_count": 0,
    "total_count": 0,
    "reclaim_rate": "0%"
  }}
}}
```

【重要：防止截断】
- 伏笔总数可能在85-138条之间，请确保完整性
- 场景级伏笔可以适当精简描述（每条50-150字即可），但必须包含三层含义和关联数据
- 优先保证全剧级和章节级伏笔的完整性和深度
- 如果篇幅有限，场景级伏笔数量可以适当减少，但全剧级和章节级必须达标"""

    user_prompt = f"""请为以下互动影游项目设计完整的三层伏笔体系：

━━━━━━━━━━━━━━━━━━━━━━
🔮 核心真相：{core_truth or '未设定'}
⚡ 核心矛盾：{core_contradiction or '未设定'}
📐 总章节数：{chapter_count}
━━━━━━━━━━━━━━━━━━━━━━
🌍 世界观设定：
{world_context}
━━━━━━━━━━━━━━━━━━━━━━
👥 角色列表：
{character_context}
━━━━━━━━━━━━━━━━━━━━━━
📖 章节大纲：
{chapter_context}
━━━━━━━━━━━━━━━━━━━━━━

【创作要求 — 硬性指标】
1. **全剧级伏笔5-8条**：每条必须与核心真相直接关联，必须有3-5个reinforce_locations
2. **章节级伏笔20-30条**：每条必须与世界观设定或角色动机深度关联
3. **场景级伏笔60-100条**：每条必须包含三层含义，可以适当精简描述
4. **回收率≥80%**：核心伏笔（全剧级+章节级）必须有完整的plant→reinforce→reveal路径
5. **四类关联**：伏笔之间必须建立DEPENDS_ON/SUPPORTS/ENABLES/CONFLICTS_WITH关联
6. **世界观绑定**：每条伏笔必须标注worldview_refs
7. **角色绑定**：每条伏笔必须标注character_refs
8. **哇塞方案**：全剧级和章节级伏笔必须预设计2-3个wow_plans

【创作要求 — 质量指标】
9. 从核心真相反推，设计揭露路径（revelation_path）
10. 伏笔之间形成网络而非孤立存在
11. 每条伏笔的三层含义之间必须有逻辑递进关系
12. 场景级伏笔要为上级伏笔提供强化素材
13. **完整性优先**：所有字段必须填写完整，JSON结构必须正确闭合

请直接输出JSON，不要输出任何其他内容。"""

    return system_prompt, user_prompt
