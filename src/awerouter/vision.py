"""Image bridge: give a text-only pro model vision by having the multimodal
flash destination transcribe images, then replacing image blocks with the
transcription text before routing/forwarding.

Pure logic only — content keys, caption prompts, per-protocol body building
and response parsing, in-place rewriting, and the caption cache. The upstream
caption call itself lives in server.py with the other I/O.
"""

import hashlib
import json

CAPTION_SYSTEM = (
    "You transcribe images for a text-only coding assistant. "
    "Transcribe ALL visible text verbatim (code, UI labels, error messages, "
    "paths). Then describe layout, UI elements, and notable visual details. "
    "Be complete but not verbose. Output only the transcription and description."
)

CAPTION_USER_TEXT = "Transcribe this image for a text-only assistant."

# {n} = 1-based image index in the request, {model} = captioning model id.
IMAGE_PLACEHOLDER = "[Image {n}, transcribed by {model}]\n{caption}"

MAX_CAPTION_TOKENS = 2048

_IMAGE_TYPES = ("image", "image_url", "input_image")


def image_key(protocol: str, part: dict) -> "str | None":
    """Stable content key for an image part (protocol-specific shape)."""
    if protocol == "anthropic":
        src = part.get("source")
        if not isinstance(src, dict):
            return None
        if src.get("type") == "base64":
            raw = f"{src.get('media_type', '')}|{src.get('data', '')}"
        else:
            raw = json.dumps(src, sort_keys=True, ensure_ascii=False)
    else:  # openai-chat {"image_url": {"url": ...}} / responses {"image_url": "..."}
        url = part.get("image_url")
        if isinstance(url, dict):
            url = url.get("url", "")
        if not isinstance(url, str) or not url:
            return None
        raw = url
    return hashlib.sha256(raw.encode("utf-8", "replace")).hexdigest()


def cache_key(provider: str, model: str, image_hash: str) -> str:
    """Caption-cache key: image content + who captioned it (a model switch
    must not serve another model's transcription)."""
    return f"{provider}/{model}:{image_hash}"


def collect_images(body: dict, protocol: str) -> "list[dict]":
    """All distinct image parts in the request, first-appearance order."""
    seen: set = set()
    found: list[dict] = []

    def scan(parts):
        for part in parts:
            if isinstance(part, dict) and part.get("type") in _IMAGE_TYPES:
                key = image_key(protocol, part)
                if key and key not in seen:
                    seen.add(key)
                    found.append(part)

    if protocol == "openai-responses":
        for item in body.get("input") or []:
            if isinstance(item, dict) and isinstance(item.get("content"), list):
                scan(item["content"])
    else:
        for msg in body.get("messages") or []:
            if isinstance(msg, dict) and isinstance(msg.get("content"), list):
                scan(msg["content"])
    return found


def replace_images(body: dict, protocol: str, model: str, captions: dict) -> int:
    """Rewrite image blocks in place to caption text blocks.

    captions maps image_key -> transcription. Returns the number of replaced
    parts; a part without a caption stays untouched (defensive — the caller
    only invokes this with a complete map).
    """
    count = 0
    replaced = 0

    def text_part(text: str) -> dict:
        if protocol == "openai-responses":
            return {"type": "input_text", "text": text}
        return {"type": "text", "text": text}

    def swap(parts):
        nonlocal count, replaced
        for i, part in enumerate(parts):
            if not (isinstance(part, dict) and part.get("type") in _IMAGE_TYPES):
                continue
            count += 1
            key = image_key(protocol, part)
            caption = captions.get(key) if key else None
            if caption is None:
                continue
            parts[i] = text_part(IMAGE_PLACEHOLDER.format(
                n=count, model=model, caption=caption))
            replaced += 1

    if protocol == "openai-responses":
        for item in body.get("input") or []:
            if isinstance(item, dict) and isinstance(item.get("content"), list):
                swap(item["content"])
    else:
        for msg in body.get("messages") or []:
            if isinstance(msg, dict) and isinstance(msg.get("content"), list):
                swap(msg["content"])
    return replaced


def build_caption_body(protocol: str, model: str, image_part: dict) -> dict:
    """Minimal same-protocol body asking `model` to transcribe one image."""
    if protocol == "anthropic":
        return {
            "model": model,
            "max_tokens": MAX_CAPTION_TOKENS,
            "system": CAPTION_SYSTEM,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "image", "source": image_part.get("source")},
                    {"type": "text", "text": CAPTION_USER_TEXT},
                ],
            }],
        }
    if protocol == "openai-chat":
        return {
            "model": model,
            "max_tokens": MAX_CAPTION_TOKENS,
            "messages": [
                {"role": "system", "content": CAPTION_SYSTEM},
                {"role": "user", "content": [
                    dict(image_part),
                    {"type": "text", "text": CAPTION_USER_TEXT},
                ]},
            ],
        }
    return {  # openai-responses
        "model": model,
        "instructions": CAPTION_SYSTEM,
        "input": [{
            "role": "user",
            "content": [
                dict(image_part),
                {"type": "input_text", "text": CAPTION_USER_TEXT},
            ],
        }],
    }


def parse_caption_response(protocol: str, body: dict) -> "str | None":
    """Assistant text out of a non-streaming caption response (None = empty)."""
    if protocol == "anthropic":
        parts = [b.get("text", "") for b in body.get("content") or []
                 if isinstance(b, dict) and b.get("type") == "text"]
        return "\n".join(p for p in parts if p) or None
    if protocol == "openai-chat":
        msg = ((body.get("choices") or [{}])[0].get("message") or {})
        content = msg.get("content")
        if isinstance(content, str):
            return content or None
        if isinstance(content, list):
            parts = [p.get("text", "") for p in content
                     if isinstance(p, dict) and p.get("type") == "text"]
            return "\n".join(p for p in parts if p) or None
        return None
    parts = []  # openai-responses: output items carry output_text parts
    for item in body.get("output") or []:
        if not isinstance(item, dict):
            continue
        for part in item.get("content") or []:
            if isinstance(part, dict) and part.get("type") in ("output_text", "text"):
                parts.append(part.get("text", ""))
    return "\n".join(p for p in parts if p) or None


class CaptionCache:
    """Content-addressed caption cache: cache_key -> transcription.

    Process-lifetime only (a restart re-transcribes each distinct image once).
    Bounded FIFO; keys are hashes and values short texts, so memory is small.
    """

    def __init__(self, maxsize: int = 128):
        self._maxsize = maxsize
        self._data: "dict[str, str]" = {}

    def get(self, key: str) -> "str | None":
        return self._data.get(key)

    def put(self, key: str, caption: str) -> None:
        if key in self._data:
            return
        if len(self._data) >= self._maxsize:
            self._data.pop(next(iter(self._data)))
        self._data[key] = caption


CAPTIONS = CaptionCache()
