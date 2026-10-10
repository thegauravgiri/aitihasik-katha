BLOCK_KEYWORDS = (
    "content_blocked", "input blocked", "request blocked", "blocked due to", "safety violation",
    "prohibited use", "filtered out", "could not be processed", "responsible ai", "rai_media_filtered",
)


class VideoBlockedError(RuntimeError):
    """The video model refused the scene or filtered the clip it made (a real person's likeness, a
    safety filter). Asking again the same way cannot help, so these are never retried."""


def is_block_error(exc: BaseException) -> bool:
    message = str(exc).lower()
    return any(keyword in message for keyword in BLOCK_KEYWORDS)
