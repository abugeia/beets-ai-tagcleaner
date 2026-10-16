import io
import json
from types import SimpleNamespace

import pytest

from beetsplug import aitagcleaner
from beetsplug.aitagcleaner import AITagCleaner, build_prompt


def test_build_prompt_includes_tags_and_filename():
    prompt = build_prompt("P", "Pink Floyd", "zembil", "Pink Floyd - Echoes_1 - zembil.mp3")
    assert prompt == (
        "P\nInput: artist='Pink Floyd' title='zembil' "
        "file='Pink Floyd - Echoes_1 - zembil.mp3'"
    )


@pytest.fixture
def plugin():
    return AITagCleaner()


def _item(artist, title, path=b"/music/x/Artist - Song (Official Video).mp3"):
    return SimpleNamespace(artist=artist, title=title, path=path)


def _fake_llm(monkeypatch, answer, seen=None):
    def urlopen(req, timeout):
        if seen is not None:
            seen.append(json.loads(req.data))
        body = {"response": json.dumps(answer)}
        return io.BytesIO(json.dumps(body).encode())

    monkeypatch.setattr(aitagcleaner.urllib.request, "urlopen", urlopen)


def test_sends_basename_and_rewrites_tags(plugin, monkeypatch):
    seen = []
    _fake_llm(monkeypatch, {"artist": "Artist", "title": "Song"}, seen)
    item = _item("", "")
    plugin._clean_item(item)
    assert (item.artist, item.title) == ("Artist", "Song")
    assert seen[0]["model"] == "gemma3:4b"
    assert seen[0]["prompt"].endswith(
        "file='Artist - Song (Official Video).mp3'"
    )


def test_incomplete_answer_leaves_tags(plugin, monkeypatch):
    _fake_llm(monkeypatch, {"artist": "Artist", "title": ""})
    item = _item("Artist", "Song (Official Video)")
    plugin._clean_item(item)
    assert item.title == "Song (Official Video)"


def test_llm_error_is_logged_as_warning(plugin, monkeypatch):
    def boom(req, timeout):
        raise OSError("connection refused")

    monkeypatch.setattr(aitagcleaner.urllib.request, "urlopen", boom)
    calls = []
    monkeypatch.setattr(plugin._log, "warning", lambda *a: calls.append(a))
    item = _item("Artist", "Song")
    plugin._clean_item(item)
    assert (item.artist, item.title) == ("Artist", "Song")
    assert calls and "connection refused" in str(calls[0][2])
