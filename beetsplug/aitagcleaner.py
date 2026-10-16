"""Clean the artist/title tags with a local LLM before matching.

This beets plugin sends the *raw* ``artist`` and ``title`` tags of each
imported track, plus its file name, to an LLM (Ollama, or any OpenAI-compatible ``/api/generate``
endpoint) and rewrites them to clean values **before** the MusicBrainz
autotagger runs. This rescues the very common case of YouTube/streaming rips
whose ``title`` tag is the full video title, e.g.
``"Benson Boone - Cry (Official Lyric Video)"`` -> ``"Cry"``. The file name
rescues tracks whose tags are empty or wrong (e.g. SoundCloud rips where
``title`` holds the uploader's name).

It only rewrites ``artist`` and ``title`` -- the two fields the autotagger
searches on. Everything else (album, year, track number, cover art, MBIDs...)
is filled by MusicBrainz once the match succeeds, so the LLM never invents
catalogue data.

Why another plugin? ``beets-aisauce`` relies on function-calling (the
``instructor`` library in ``TOOLS`` mode), which Ollama's OpenAI-compatible
endpoint does not return for small local models. This plugin uses plain JSON
mode instead, which works reliably with small local models (``gemma3:4b`` by default).
"""

import json
import os
import urllib.request

from beets.plugins import BeetsPlugin
from beets.util import displayable_path

# Benchmarked on 52 real tags (see bench/): with gemma3:4b it leaves every
# already-clean tag untouched. Re-run the bench before changing it.
DEFAULT_PROMPT = (
    'You fix music file metadata. You get the current artist and title tags (they may be correct, empty, decorated, swapped, or wrong) and the file name. Return the performing artist and the song title.\n'
    'Rules:\n'
    '1. If the tags already look like a correct artist and song title, return them EXACTLY as given (same spelling, case, accents, punctuation). Do not "improve" them.\n'
    '2. If the tags are empty, decorated or wrong, use the file name. Common file name shapes: "Artist - Title", "NN - Title", "[Artist] (Album) NN Title", and SoundCloud "Artist - Title_123456 - uploader" where the part after the long number is the UPLOADER, never the title.\n'
    '3. Remove decorations: (Official Video), (Official Audio), (Lyric Video), (HQ Audio), [HD], [128], track numbers, website or channel names, file extensions.\n'
    '4. Keep remix, mix, edit, live or version info that belongs to the song, e.g. "(Axwell Remix)", "(Radio Edit)".\n'
    '5. Move any "feat."/"ft." credit OUT of the title.\n'
    '6. Never translate, never add words, never guess a title that appears nowhere in the input. Keep accents and diacritics.\n'
    'Examples:\n'
    "Input: artist='' title='' file='Daft Punk - Around the World (Official Video).mp3'\n"
    '{"artist": "Daft Punk", "title": "Around the World"}\n'
    "Input: artist='Burial' title='hyperdub' file='Burial - Archangel_123456 - hyperdub.mp3'\n"
    '{"artist": "Burial", "title": "Archangel"}\n'
    "Input: artist='Édith Piaf' title='La vie en rose' file='La vie en rose.m4a'\n"
    '{"artist": "Édith Piaf", "title": "La vie en rose"}\n'
    "Input: artist='Orelsan' title='La pluie feat. Stromae' file='Orelsan - La pluie feat. Stromae.mp3'\n"
    '{"artist": "Orelsan", "title": "La pluie"}\n'
    'Reply ONLY with compact JSON: {"artist": "...", "title": "..."}.\n'
)


def build_prompt(prompt, artist, title, filename):
    """Prompt sent to the LLM; also imported by bench/bench.py."""
    return "%s\nInput: artist=%r title=%r file=%r" % (prompt, artist, title, filename)


class AITagCleaner(BeetsPlugin):
    def __init__(self):
        super().__init__()
        self.config.add(
            {
                # Ollama native generate endpoint (or any OpenAI-compatible one
                # that honours {"format": "json"}).
                "url": "http://localhost:11434/api/generate",
                "model": "gemma3:4b",
                "prompt": DEFAULT_PROMPT,
                "timeout": 60,
                "auto": True,
            }
        )
        if self.config["auto"].get(bool):
            self.register_listener("import_task_start", self._on_task_start)

    # -- LLM call -----------------------------------------------------------
    def _ask(self, artist, title, filename):
        payload = {
            "model": self.config["model"].as_str(),
            "prompt": build_prompt(
                self.config["prompt"].as_str(), artist, title, filename
            ),
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
        filename = os.path.basename(displayable_path(item.path))
        try:
            artist, title = self._ask(item.artist, item.title, filename)
        except Exception as exc:  # network/model issues must never block import
            # warning, not debug: a missing model or an OOM must show in the logs.
            self._log.warning("ai-tagcleaner: skipped {0!r} ({1})", filename, exc)
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
