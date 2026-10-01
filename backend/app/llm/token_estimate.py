CHARS_PER_TOKEN_ESTIMATE = 4


def estimate_tokens(text: str) -> int:
    """char/4 approximation, per Plan.md section 6.1. Good enough to size
    prompts and refuse oversize ones without pulling in a tokenizer model.
    """
    return max(1, len(text) // CHARS_PER_TOKEN_ESTIMATE)


def trim_to_token_budget(text: str, max_tokens: int) -> str:
    max_chars = max_tokens * CHARS_PER_TOKEN_ESTIMATE
    if len(text) <= max_chars:
        return text
    return text[:max_chars]
