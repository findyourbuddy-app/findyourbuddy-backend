import html
import re
from app.config import get_settings

# Regex pattern for dangerous script/HTML tags and event handlers (XSS prevention)
DANGEROUS_HTML_PATTERN = re.compile(
    r"<[^>]*?>|javascript:|data:text/html|on\w+\s*=", re.IGNORECASE
)


def sanitize_text(text: str | None, max_length: int | None = None) -> str:
    """Sanitizes user text inputs by stripping script tags, removing HTML injection vector,
    and normalizing spaces to prevent XSS and malformed payload injection."""
    if not text:
        return ""

    # Strip dangerous HTML and script tags
    cleaned = DANGEROUS_HTML_PATTERN.sub("", text)

    # Escape HTML special chars to prevent inline HTML execution in Web/Mobile webviews
    cleaned = html.escape(cleaned, quote=True)

    # Strip null bytes and non-printable control characters
    cleaned = "".join(ch for ch in cleaned if ord(ch) >= 32 or ch in "\n\r\t")

    cleaned = cleaned.strip()

    if max_length and len(cleaned) > max_length:
        cleaned = cleaned[:max_length]

    return cleaned


def sanitize_search_query(query: str | None) -> str:
    """Escapes SQL LIKE wildcards (%, _) and special characters to prevent wildcard injection."""
    if not query:
        return ""

    sanitized = sanitize_text(query, max_length=100)
    # Escape % and _ for SQL LIKE queries
    sanitized = sanitized.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return sanitized


PROMPT_INJECTION_PATTERN = re.compile(
    r"(ignore\s+all\s+previous\s+instructions|system\s+prompt|you\s+are\s+now|override\s+instructions|assistant\s+instructions)",
    re.IGNORECASE,
)


def sanitize_prompt_input(text: str | None, max_length: int = 500) -> str:
    """Sanitizes text passed into LLM prompts to prevent prompt injection and instruction override attacks."""
    if not text:
        return ""
    cleaned = sanitize_text(text, max_length=max_length)
    cleaned = PROMPT_INJECTION_PATTERN.sub("[filtered]", cleaned)
    return cleaned


def validate_content_safety(text: str | None) -> tuple[bool, str | None]:
    """Validates user text against banned moderation keywords (profanity, spam, hate speech).
    Returns (is_safe, error_reason)."""
    if not text:
        return True, None

    settings = get_settings()
    banned_words = [
        word.strip().lower()
        for word in settings.moderation_banned_words.split(",")
        if word.strip()
    ]

    lower_text = text.lower()
    for banned in banned_words:
        if banned and banned in lower_text:
            return False, f"İçeriğinizde izin verilmeyen bir kelime tespit edildi ('{banned}')."

    return True, None
