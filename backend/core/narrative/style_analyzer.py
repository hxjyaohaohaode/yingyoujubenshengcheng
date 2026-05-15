"""
写作风格分析器
- 分析句式特征（长短句比例、平均句长）
- 分析对话密度（对话占比、人均对话量）
- 分析描写比例（环境描写/动作描写/心理描写）
"""
import re
from dataclasses import dataclass, field


@dataclass
class StyleProfile:
    avg_sentence_length: float = 0.0
    dialogue_ratio: float = 0.0
    description_ratio: float = 0.0
    action_ratio: float = 0.0
    inner_monologue_ratio: float = 0.0
    long_sentence_ratio: float = 0.0
    tone_keywords: list[str] = field(default_factory=list)
    narrative_pov: str = "third_person"
    summary: str = ""


def analyze_style(text: str, context: str = "") -> StyleProfile:
    profile = StyleProfile()
    total_chars = len(text)
    if total_chars == 0:
        return profile

    sentences = re.split(r'[。！？!?\n]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    if sentences:
        total_sentence_len = sum(len(s) for s in sentences)
        profile.avg_sentence_length = total_sentence_len / len(sentences)
        long_sentences = [s for s in sentences if len(s) > 30]
        profile.long_sentence_ratio = len(long_sentences) / len(sentences)

    dialogue_pattern = re.findall(r'["""].*?["""]|「.*?」|『.*?』', text)
    if dialogue_pattern:
        dialogue_chars = sum(len(d) for d in dialogue_pattern)
        profile.dialogue_ratio = dialogue_chars / total_chars

    action_verbs = r'走|跑|跳|拿|放|推|拉|打|踢|抓|握|抱|看|听|说|笑|哭|点|转|拍|敲|挥|举|扔|摔|冲|撞|追|逃|爬|蹲|站|坐|躺|翻|写|画|唱|吃|喝'
    action_pattern = re.findall(action_verbs, text)
    if action_pattern:
        profile.action_ratio = len(action_pattern) / (total_chars / 10)

    if re.search(r'我[^\n]{0,5}(?:想|觉得|认为|感到|看见|听见)', text):
        profile.narrative_pov = "first_person"

    tone_words = {
        '悬疑': r'诡异|奇怪|不对劲|秘密|隐藏|黑暗|阴影',
        '浪漫': r'温柔|心动|甜蜜|爱情|浪漫|拥抱|亲吻',
        '紧张': r'紧张|恐惧|害怕|危险|紧急|急促|快',
        '悲伤': r'悲伤|难过|泪水|哭泣|离别|失落',
        '激昂': r'热血|斗志|勇气|力量|胜利|冲刺|呐喊',
    }
    for tone, pattern in tone_words.items():
        if re.search(pattern, text):
            profile.tone_keywords.append(tone)

    profile.summary = (
        f"平均句长{profile.avg_sentence_length:.1f}字，"
        f"对话占比{profile.dialogue_ratio*100:.1f}%，"
        f"长句比例{profile.long_sentence_ratio*100:.1f}%，"
        f"叙事视角：{'第一人称' if profile.narrative_pov == 'first_person' else '第三人称'}"
    )

    return profile


def get_style_guide(style: StyleProfile) -> str:
    parts = []
    if style.avg_sentence_length > 0:
        if style.avg_sentence_length > 25:
            parts.append(f"使用长句为主（平均句长约{style.avg_sentence_length:.0f}字），文风偏向描写和铺陈")
        else:
            parts.append(f"使用短句为主（平均句长约{style.avg_sentence_length:.0f}字），文风简洁明快")
    if style.dialogue_ratio > 0.05:
        parts.append(f"对话在文本中占比约{style.dialogue_ratio*100:.0f}%，{'多' if style.dialogue_ratio > 0.1 else '适量'}使用对话推进剧情")
    if style.tone_keywords:
        parts.append(f"整体语气偏向：{'、'.join(style.tone_keywords)}")
    if style.narrative_pov:
        pov_text = "第一人称" if style.narrative_pov == "first_person" else "第三人称"
        parts.append(f"使用{pov_text}叙事视角")
    return "。".join(parts) + "。"