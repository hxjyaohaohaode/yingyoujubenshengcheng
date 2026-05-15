from core.search.search_models import KnowledgeCard
from .intent_models import IntentResult


def assemble_knowledge_card(
    intent: IntentResult,
    search_cards: list[KnowledgeCard],
    upload_chunks: list[str] = None,
    max_tokens: int = 2000
) -> str:
    lines = []
    token_estimate = 0

    if intent and intent.genre:
        entry = f"**题材**: {intent.genre} | **风格**: {intent.style} | **时代**: {intent.era}"
        lines.append(entry)
        token_estimate += len(entry) // 3

    if search_cards:
        lines.append("\n### 搜索参考")
        for card in search_cards:
            card_text = card.to_prompt_text()
            card_tokens = len(card_text) // 3
            if token_estimate + card_tokens > max_tokens:
                break
            lines.append(card_text)
            token_estimate += card_tokens

    upload_chunks = upload_chunks or []
    if upload_chunks:
        lines.append("\n### 上传资料参考")
        for chunk in upload_chunks:
            chunk_tokens = len(chunk) // 3
            if token_estimate + chunk_tokens > max_tokens:
                break
            lines.append(f"- {chunk[:400]}")
            token_estimate += chunk_tokens

    return "\n".join(lines)