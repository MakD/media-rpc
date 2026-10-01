import os
from urllib.parse import urlsplit

# discord limits for rich presence links
MAX_BUTTONS = 2
MAX_BUTTON_LABEL_LENGTH = 32
MAX_BUTTON_URL_LENGTH = 512
MAX_DETAILS_URL_LENGTH = 256

USE_MEDIA_LINKS = os.getenv("USE_MEDIA_LINKS", "False").lower() == "true"


def is_safe_url(url, max_length):
    """Only allow plain http(s) links without credentials, since everyone who sees the presence can open them."""
    if not isinstance(url, str) or not url or len(url) > max_length:
        return False
    if any(c.isspace() or not c.isprintable() for c in url):
        return False
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    return parts.scheme in ("http", "https") and bool(parts.hostname) and "@" not in parts.netloc


def make_button(label, url):
    label = label.strip() if isinstance(label, str) else ""
    if not label or len(label) > MAX_BUTTON_LABEL_LENGTH:
        return None
    if not is_safe_url(url, MAX_BUTTON_URL_LENGTH):
        return None
    return {"label": label, "url": url}


def load_custom_buttons():
    buttons = []
    for i in range(1, MAX_BUTTONS + 1):
        label = os.getenv(f"DISCORD_BUTTON_{i}_LABEL", "")
        url = os.getenv(f"DISCORD_BUTTON_{i}_URL", "").strip()
        if not label and not url:
            continue
        button = make_button(label, url)
        if button:
            buttons.append(button)
        else:
            print(
                f"Ignoring DISCORD_BUTTON_{i}: the label must be 1-{MAX_BUTTON_LABEL_LENGTH} characters "
                f"and the url must be an http(s) link of at most {MAX_BUTTON_URL_LENGTH} characters"
            )
    return buttons


CUSTOM_BUTTONS = load_custom_buttons()


def add_links(activity, links):
    """
    Add the custom buttons and, if USE_MEDIA_LINKS is enabled, the links for the playing media to the activity.
    Custom buttons come first, media links fill the remaining button slots,
    and the first media link is also opened when clicking the title.
    """
    media_buttons = []
    if USE_MEDIA_LINKS and links:
        for link in links:
            button = make_button(link.get("label"), link.get("url"))
            if button:
                media_buttons.append(button)
        if media_buttons and is_safe_url(media_buttons[0]["url"], MAX_DETAILS_URL_LENGTH):
            activity["details_url"] = media_buttons[0]["url"]

    buttons = (CUSTOM_BUTTONS + media_buttons)[:MAX_BUTTONS]
    if buttons:
        activity["buttons"] = buttons
    return activity
