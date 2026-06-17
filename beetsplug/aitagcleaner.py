"""Clean the artist/title tags with a local LLM before matching.

This beets plugin sends the *raw* ``artist`` and ``title`` tags of each
imported track to an LLM (Ollama, or any OpenAI-compatible ``/api/generate``
endpoint) and rewrites them to clean values **before** the MusicBrainz
autotagger runs. This rescues the very common case of YouTube/streaming rips
whose ``title`` tag is the full video title, e.g.
``"Benson Boone - Cry (Official Lyric Video)"`` -> ``"Cry"``.

It only rewrites ``artist`` and ``title`` -- the two fields the autotagger
searches on. Everything else (album, year, track number, cover art, MBIDs...)
is filled by MusicBrainz once the match succeeds, so the LLM never invents
catalogue data.

Why another plugin? ``beets-aisauce`` relies on function-calling (the
``instructor`` library in ``TOOLS`` mode), which Ollama's OpenAI-compatible
endpoint does not return for small local models. This plugin uses plain JSON
mode instead, which works reliably with models as small as ``qwen2.5:3b``.
"""

import json
import urllib.request

from beets.plugins import BeetsPlugin

DEFAULT_PROMPT = (
    "You clean music metadata coming from YouTube/streaming downloads. "
    "Given a raw artist and title, return the real performing artist and the "
    "clean song title. Remove decorations such as (Official Video), "
    "(Official Audio), (Lyric Video), (Visualizer), [ ... ] brackets, "
    "'Remaster'/'Remastered' + year, and channel names; move any 'feat.'/'ft.' "
    "credit OUT of the title. Keep the original accents and diacritics. "
    "Never invent information. Reply ONLY with compact JSON: "
    '{"artist": "...", "title": "..."}.'
)


class AITagCleaner(BeetsPlugin):
    def __init__(self):
        super().__init__()
        self.config.add(
            {
                # Ollama native generate endpoint (or any OpenAI-compatible one
                # that honours {"format": "json"}).
                "url": "http://localhost:11434/api/generate",
                "model": "qwen2.5:3b",
                "prompt": DEFAULT_PROMPT,
                "timeout": 60,
                "auto": True,
            }
        )
        if self.config["auto"].get(bool):
            self.register_listener("import_task_start", self._on_task_start)

    # -- LLM call -----------------------------------------------------------
    def _ask(self, artist, title):
        payload = {
            "model": self.config["model"].as_str(),
            "prompt": "%s\nRaw: artist=%r title=%r"
            % (self.config["prompt"].as_str(), artist, title),
            "stream": False,
            "format": "json",
            "options": {"temperature": 0},
        }
        req = urllib.request.Request(
            self.config["url"].as_str(),
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(
            req, timeout=self.config["timeout"].get(int)
        ) as resp:
            body = json.load(resp)
        data = json.loads(body["response"])
        return data.get("artist"), data.get("title")

    # -- item handling ------------------------------------------------------
    def _clean_item(self, item):
        try:
            artist, title = self._ask(item.artist, item.title)
        except Exception as exc:  # network/model issues must never block import
            self._log.debug("ai-tagcleaner: skipped ({0})", exc)
            return
        if artist and title and (artist != item.artist or title != item.title):
            self._log.info(
                "ai-tagcleaner: {0!r}/{1!r} -> {2!r}/{3!r}",
                item.artist,
                item.title,
                artist,
                title,
            )
            item.artist = artist
            item.title = title

    def _on_task_start(self, task, session):
        # Album import exposes `.items`; singleton import exposes `.item`.
        items = getattr(task, "items", None)
        if items is None:
            item = getattr(task, "item", None)
            items = [item] if item is not None else []
        for item in items:
            self._clean_item(item)
