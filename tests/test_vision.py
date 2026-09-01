"""Tests for awerouter.vision (pure image-bridge logic)."""

from awerouter.vision import (
    CAPTION_SYSTEM,
    CaptionCache,
    build_caption_body,
    cache_key,
    collect_images,
    image_key,
    parse_caption_response,
    replace_images,
)


def _img(data="aW1nMQ=="):
    return {"type": "image", "source": {
        "type": "base64", "media_type": "image/png", "data": data}}


class TestImageKey:
    def test_anthropic_base64(self):
        assert image_key("anthropic", _img()) == image_key("anthropic", _img())

    def test_anthropic_different_data_differs(self):
        assert image_key("anthropic", _img()) != image_key("anthropic", _img("eHg="))

    def test_anthropic_missing_source(self):
        assert image_key("anthropic", {"type": "image"}) is None

    def test_openai_chat_data_url(self):
        a = {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAA"}}
        b = {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAA"}}
        assert image_key("openai-chat", a) == image_key("openai-chat", b)

    def test_responses_string_url(self):
        assert image_key("openai-responses", {"type": "input_image", "image_url": "x"})

    def test_cache_key_includes_model(self):
        assert cache_key("p", "m1", "h") != cache_key("p", "m2", "h")


class TestCollectImages:
    def test_dedup_across_messages(self):
        img = {"type": "image_url", "image_url": {"url": "data:1"}}
        body = {"messages": [
            {"role": "user", "content": [img]},
            {"role": "user", "content": [dict(img), {"type": "text", "text": "hi"}]},
        ]}
        assert len(collect_images(body, "openai-chat")) == 1

    def test_responses_items(self):
        body = {"input": [
            {"role": "user", "content": [
                {"type": "input_text", "text": "look"},
                {"type": "input_image", "image_url": "data:1"},
            ]},
        ]}
        assert len(collect_images(body, "openai-responses")) == 1

    def test_no_images(self):
        assert collect_images({"messages": [{"role": "user", "content": "hi"}]},
                              "openai-chat") == []


class TestReplaceImages:
    def test_anthropic_replaces_in_order(self):
        body = {"messages": [{"role": "user", "content": [
            _img(), {"type": "text", "text": "q"}, _img("eHg=")]}]}
        k1, k2 = image_key("anthropic", _img()), image_key("anthropic", _img("eHg="))
        replaced = replace_images(body, "anthropic", "sf-flash",
                                  {k1: "cap one", k2: "cap two"})
        assert replaced == 2
        content = body["messages"][0]["content"]
        assert all(p["type"] == "text" for p in content)
        assert content[0]["text"].startswith("[Image 1, transcribed by sf-flash]")
        assert "cap one" in content[0]["text"]
        assert "cap two" in content[2]["text"]
        assert content[1]["text"] == "q"  # untouched neighbor

    def test_openai_chat(self):
        part = {"type": "image_url", "image_url": {"url": "data:1"}}
        body = {"messages": [{"role": "user", "content": [part]}]}
        replace_images(body, "openai-chat", "m",
                       {image_key("openai-chat", part): "cap"})
        assert body["messages"][0]["content"][0]["type"] == "text"

    def test_responses(self):
        part = {"type": "input_image", "image_url": "data:1"}
        body = {"input": [{"role": "user", "content": [part]}]}
        replace_images(body, "openai-responses", "m",
                       {image_key("openai-responses", part): "cap"})
        assert body["input"][0]["content"][0]["type"] == "input_text"

    def test_missing_caption_leaves_image(self):
        body = {"messages": [{"role": "user", "content": [_img()]}]}
        assert replace_images(body, "anthropic", "m", {}) == 0
        assert body["messages"][0]["content"][0]["type"] == "image"


class TestCaptionBodies:
    def test_anthropic_shape(self):
        b = build_caption_body("anthropic", "sf", _img())
        assert b["model"] == "sf"
        assert b["system"] == CAPTION_SYSTEM
        assert b["messages"][0]["content"][0]["type"] == "image"

    def test_openai_chat_shape(self):
        part = {"type": "image_url", "image_url": {"url": "data:1"}}
        b = build_caption_body("openai-chat", "sf", part)
        assert b["messages"][0]["role"] == "system"

    def test_responses_shape(self):
        part = {"type": "input_image", "image_url": "data:1"}
        b = build_caption_body("openai-responses", "sf", part)
        assert b["instructions"] == CAPTION_SYSTEM


class TestParseCaption:
    def test_anthropic(self):
        assert parse_caption_response("anthropic", {"content": [
            {"type": "text", "text": "hello"}]}) == "hello"

    def test_openai_chat_string(self):
        assert parse_caption_response("openai-chat", {
            "choices": [{"message": {"content": "hi"}}]}) == "hi"

    def test_openai_chat_parts(self):
        assert parse_caption_response("openai-chat", {
            "choices": [{"message": {"content": [
                {"type": "text", "text": "a"}, {"type": "text", "text": "b"}]}}]}) == "a\nb"

    def test_responses_output_items(self):
        assert parse_caption_response("openai-responses", {
            "output": [{"content": [{"type": "output_text", "text": "yo"}]}]}) == "yo"

    def test_empty_is_none(self):
        for proto in ("anthropic", "openai-chat", "openai-responses"):
            assert parse_caption_response(proto, {}) is None


class TestCaptionCache:
    def test_put_get(self):
        c = CaptionCache(maxsize=2)
        c.put("a", "1")
        assert c.get("a") == "1"
        assert c.get("b") is None

    def test_fifo_evict(self):
        c = CaptionCache(maxsize=2)
        c.put("a", "1")
        c.put("b", "2")
        c.put("c", "3")
        assert c.get("a") is None
        assert c.get("c") == "3"
