"""
元素闭环检查器 - 检测场景中未注册的元素（角色名、地点名、物品名、组织名）。
"""

import re
from typing import FrozenSet, List, Pattern, Set


_LOCATION_SUFFIXES: FrozenSet[str] = frozenset({
    '\u57ce', '\u5c71', '\u6d77', '\u56fd', '\u5dde', '\u5e9c', '\u9547',
    '\u8c37', '\u6797', '\u6cb3', '\u6e56', '\u6c5f', '\u5c9b', '\u754c',
    '\u5bab', '\u6bbf', '\u9601', '\u697c', '\u5802', '\u95e8', '\u6d1e',
    '\u5cf0', '\u5cad', '\u539f', '\u91ce', '\u6cbc', '\u6f6d', '\u6eaa',
    '\u6cc9', '\u5ca9', '\u5d16', '\u5761', '\u575e', '\u585e', '\u5173',
    '\u9640', '\u5c4b', '\u5e84', '\u5be8', '\u90a6', '\u9091', '\u90fd',
    '\u90ca', '\u9645', '\u8303', '\u57df', '\u5883', '\u56ed', '\u82d1',
    '\u9636', '\u5854', '\u7891', '\u5821',
})

_ORG_SUFFIXES: FrozenSet[str] = frozenset({
    '\u6d3e', '\u95e8', '\u5e2e', '\u6559', '\u4f1a', '\u76df', '\u65cf',
    '\u5b97', '\u5bfa', '\u5e99', '\u5bab', '\u9662', '\u5e9c', '\u5c40',
    '\u53f8', '\u6240', '\u793e', '\u56e2', '\u961f', '\u90e8', '\u574a',
    '\u5802', '\u9601', '\u697c', '\u8c37', '\u5e84',
})

_ITEM_KEY_MORPHEMES: FrozenSet[str] = frozenset({
    '\u5251', '\u5200', '\u67aa', '\u68cd', '\u97ad', '\u9524', '\u65a7',
    '\u621f', '\u5f13', '\u5f29', '\u76fe', '\u7532', '\u4e39', '\u836f',
    '\u7b26', '\u8bc0', '\u7ecf', '\u5178', '\u672f', '\u6cd5', '\u529f',
    '\u5b9d', '\u5668', '\u7389', '\u73e0', '\u77f3', '\u9f0e', '\u949f',
    '\u7434', '\u7b1b', '\u7b59', '\u4ee4', '\u724c', '\u5370', '\u9501',
    '\u9525', '\u94a9', '\u7ef3', '\u74f6', '\u7089', '\u821f', '\u8f66',
    '\u5e18', '\u5e1c', '\u8863', '\u888d', '\u51a0', '\u9774', '\u6247',
    '\u676f', '\u76c8', '\u76d8', '\u955c', '\u7b3a', '\u949c',
})

_FAMILY_NAMES_RE: Pattern[str] = re.compile(
    r'['
    r'\u674e\u738b\u5f20\u5218\u9648\u6768\u8d75\u9ec4\u5468\u5434'
    r'\u5f90\u5b59\u80e1\u6731\u9ad8\u6797\u4f55\u90ed\u9a6c\u7f57'
    r'\u6881\u5b8b\u90d1\u8c22\u97e9\u5510\u51af\u4e8e\u8463\u8427'
    r'\u7a0b\u66f9\u8881\u9093\u8bb8\u5085\u6c88\u66fe\u5f6d\u5415'
    r'\u82cf\u5362\u848b\u8521\u8d3e\u4e01\u9b4f\u859b\u53f6\u960e'
    r'\u4f59\u6f58\u675c\u6234\u590f\u949f\u6c6a\u7530\u4efb\u59dc'
    r'\u8303\u65b9\u77f3\u59da\u8c2d\u5ed6\u90b9\u718a\u91d1\u9646'
    r'\u90dd\u5b54\u767d\u5d14\u5eb7\u6bdb\u90b1\u79e6\u6c5f\u53f2'
    r'\u987e\u4faf\u90b5\u5b5f\u9f99\u4e07\u6bb5\u96f7\u94b1\u6c64'
    r'\u5c39\u9ece\u6613\u5e38\u6b66\u4e54\u8d3a\u8d56\u9f9a\u6587'
    r']'
)
_FAMILY_NAME_PATTERN: Pattern[str] = re.compile(
    r'(?:' + _FAMILY_NAMES_RE.pattern + r'[\u4e00-\u9fff]{1,2})'
    r'(?=[\uff0c\u3002\uff01\uff1f\u3001\uff1b\uff1a'
    r'\u201c\u201d\u2018\u2019\u2026\u2014\s]|$)'
)


def _has_item_keyword(word: str) -> bool:
    return any(ch in _ITEM_KEY_MORPHEMES for ch in word)


def _has_location_suffix(word: str) -> bool:
    return word[-1] in _LOCATION_SUFFIXES if word else False


def _has_org_suffix(word: str) -> bool:
    return word[-1] in _ORG_SUFFIXES if word else False


def extract_proper_nouns(text: str) -> Set[str]:
    """
    从中文剧本中提取疑似专有名词。
    策略：
      1. 提取书名号、引号、方括号内的内容。
      2. 用常见姓氏+1~2字匹配人物名。
      3. 对文本做标点/空格分词，筛选含地点尾字、组织尾字、物品关键字的分词片段。
    """
    candidates: Set[str] = set()

    quote_patterns: List[str] = [
        r'\u300a([^\u300b]+)\u300b',
        r'\u201c([^\u201d]+)\u201d',
        r'\u2018([^\u2019]+)\u2019',
        r'\u3010([^\u3011]+)\u3011',
        r'\u300c([^\u300d]+)\u300d',
        r'\u300e([^\u300f]+)\u300f',
    ]
    for pattern in quote_patterns:
        for match in re.findall(pattern, text):
            clean = match.strip()
            if re.search(r'[\u4e00-\u9fff]', clean):
                candidates.add(clean)

    for match in _FAMILY_NAME_PATTERN.finditer(text):
        name = match.group().rstrip(
            '\uff0c\u3002\uff01\uff1f\u3001\uff1b\uff1a'
            '\u201c\u201d\u2018\u2019\u2026\u2014 \t'
        )
        if len(name) >= 2:
            candidates.add(name)

    han_chars = [ch for ch in text if '\u4e00' <= ch <= '\u9fff']
    non_proper_common: FrozenSet[str] = frozenset({
        '\u6211\u4eec', '\u4ed6\u4eec', '\u4f60\u4eec', '\u81ea\u5df1',
        '\u4ec0\u4e48', '\u600e\u4e48', '\u4e3a\u4ec0\u4e48', '\u53ef\u4ee5',
        '\u6ca1\u6709', '\u5df2\u7ecf', '\u8fd8\u662f', '\u4f46\u662f',
        '\u56e0\u4e3a', '\u6240\u4ee5', '\u5982\u679c', '\u867d\u7136',
        '\u800c\u4e14', '\u7136\u540e', '\u4e0d\u8fc7', '\u53ea\u662f',
        '\u8fd9\u4e2a', '\u90a3\u4e2a', '\u8fd9\u4e9b', '\u90a3\u4e9b',
        '\u4e00\u4e2a', '\u4e00\u79cd', '\u4e00\u4e0b', '\u4e0d\u662f',
        '\u4e0d\u4f1a', '\u4e0d\u80fd', '\u4e0d\u8981', '\u77e5\u9053',
        '\u89c9\u5f97', '\u53ef\u80fd', '\u5e94\u8be5', '\u9700\u8981',
        '\u5f00\u59cb', '\u7ee7\u7eed', '\u51fa\u6765', '\u8d77\u6765',
        '\u56de\u6765', '\u8fc7\u53bb', '\u8fc7\u6765', '\u8fdb\u53bb',
        '\u8fdb\u884c', '\u6240\u6709', '\u4e00\u5207', '\u4efb\u4f55',
        '\u4e00\u6837', '\u4e00\u8d77', '\u4e00\u76f4', '\u4e00\u5b9a',
        '\u975e\u5e38', '\u771f\u7684', '\u73b0\u5728', '\u521a\u624d',
        '\u4ee5\u540e', '\u4ee5\u524d', '\u7a81\u7136', '\u7ec8\u4e8e',
        '\u9a6c\u4e0a', '\u7acb\u523b', '\u6162\u6162',
        '\u8fd9\u91cc', '\u90a3\u91cc', '\u54ea\u91cc',
        '\u91cc\u9762', '\u5916\u9762', '\u4e0a\u9762', '\u4e0b\u9762',
        '\u65c1\u8fb9', '\u524d\u9762',
        '\u770b\u89c1', '\u542c\u5230', '\u611f\u89c9',
        '\u53d1\u73b0', '\u8ba4\u4e3a', '\u5e0c\u671b', '\u51c6\u5907',
        '\u51b3\u5b9a', '\u9009\u62e9',
        '\u4e8b\u60c5', '\u95ee\u9898', '\u65f6\u95f4', '\u5730\u65b9',
        '\u4e1c\u897f', '\u673a\u4f1a', '\u5173\u7cfb', '\u7ed3\u679c',
        '\u529e\u6cd5',
        '\u4f3c\u4e4e', '\u4eff\u4f5b', '\u5ffd\u7136', '\u4ecd\u7136',
        '\u59cb\u7ec8', '\u7eb7\u7eb7', '\u987f\u65f6', '\u5f7b\u5e95',
        '\u5b8c\u5168',
        '\u8bf4\u8bdd', '\u56de\u7b54', '\u544a\u8bc9', '\u95ee\u9053',
        '\u63a5\u7740', '\u8bf4\u9053', '\u7b11\u9053', '\u70b9\u5934',
        '\u6447\u5934', '\u5bf9\u7740', '\u671d\u7740', '\u7ad9\u5728',
        '\u5750\u5728', '\u8d70\u5230', '\u6765\u5230', '\u8d70\u51fa',
        '\u8d70\u8fdb', '\u770b\u53bb',
    })
    for wlen in (2, 3, 4):
        for i in range(len(han_chars) - wlen + 1):
            word = ''.join(han_chars[i:i + wlen])
            if word in non_proper_common:
                continue
            ok = False
            if _has_item_keyword(word):
                ok = True
            if _has_location_suffix(word):
                ok = True
            if _has_org_suffix(word):
                ok = True
            if ok:
                candidates.add(word)

    return candidates


def check_element_closure(
    scene_text: str,
    registered: Set[str]
) -> dict:
    """
    检测场景文本中是否存在未注册的专有名词。

    Args:
        scene_text: 场景文本内容。
        registered: 已注册的元素名称集合。

    Returns:
        {"pass": bool, "unregistered": list[str]}
    """
    found = extract_proper_nouns(scene_text)
    unregistered: List[str] = []

    for noun in found:
        if noun not in registered and not any(
            noun in reg or reg in noun for reg in registered
        ):
            unregistered.append(noun)

    return {
        "pass": len(unregistered) == 0,
        "unregistered": unregistered,
    }
