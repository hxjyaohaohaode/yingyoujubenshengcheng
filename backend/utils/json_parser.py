import json
import re
import logging

logger = logging.getLogger(__name__)

def parse_llm_json(text: str, repair: bool = True) -> dict | list | None:
    if not text or not text.strip():
        return None
    text = text.strip()
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass
    json_block = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', text, re.DOTALL)
    if json_block:
        try:
            return json.loads(json_block.group(1).strip())
        except (json.JSONDecodeError, ValueError):
            pass
    brace_match = re.search(r'\{[\s\S]*\}', text)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except (json.JSONDecodeError, ValueError):
            pass
    bracket_match = re.search(r'\[[\s\S]*\]', text)
    if bracket_match:
        try:
            return json.loads(bracket_match.group(0))
        except (json.JSONDecodeError, ValueError):
            pass
    if repair:
        return _repair_and_parse(text)
    return None

def _repair_and_parse(text: str) -> dict | list | None:
    for fragment in re.finditer(r'[\{\[]', text):
        start = fragment.start()
        is_obj = text[start] == '{'
        depth = 0
        for i in range(start, len(text)):
            if text[i] in '{[':
                depth += 1
            elif text[i] in '}]':
                depth -= 1
                if depth == 0:
                    candidate = text[start:i+1]
                    try:
                        return json.loads(candidate)
                    except (json.JSONDecodeError, ValueError):
                        if is_obj and not candidate.rstrip().endswith('}'):
                            candidate += '}'
                        elif not is_obj and not candidate.rstrip().endswith(']'):
                            candidate += ']'
                        try:
                            return json.loads(candidate)
                        except (json.JSONDecodeError, ValueError):
                            break
    return None
