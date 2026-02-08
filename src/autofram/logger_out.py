MAX_DISPLAY_LENGTH = 80


def truncate_for_display(text):
    """Truncate text to first line, max MAX_DISPLAY_LENGTH chars."""
    head = text[:MAX_DISPLAY_LENGTH + 1]
    endline = head.find("\n")
    if endline != -1:
        return f"{text[:endline]}..."
    if len(head) > MAX_DISPLAY_LENGTH:
        return f"{text[:MAX_DISPLAY_LENGTH]}..."
    return text
