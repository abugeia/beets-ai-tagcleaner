# beets-ai-tagcleaner

A [beets](https://beets.io) plugin that cleans the **`artist`** and **`title`**
tags with a local LLM **before** the MusicBrainz autotagger runs — so messy
YouTube/streaming rips finally match.

## The problem

Tracks downloaded from YouTube often carry the full video title in their tags:

```
artist = "Benson Boone"
title  = "Benson Boone - Cry (Official Lyric Video)"
```

beets searches MusicBrainz with that polluted title, the distance is too high,
and the track is **skipped** — even though `Benson Boone - Cry` exists on
MusicBrainz with a perfect score.

## What it does

On `import_task_start` (before matching), the plugin asks an LLM to rewrite the
raw `artist`/`title` to clean values:

```
"Benson Boone" / "Benson Boone - Cry (Official Lyric Video)"  ->  "Benson Boone" / "Cry"
```

beets then matches normally and **MusicBrainz fills everything else** (album,
year, track number, cover art, MBIDs…). The LLM only touches the two search
fields, so it never invents catalogue data.

## Why not `beets-aisauce`?

`beets-aisauce` relies on function-calling (the `instructor` library in `TOOLS`
mode). Ollama's OpenAI-compatible endpoint does **not** return tool calls for
small local models, so it fails with `No tool calls found (mode: TOOLS)`.
This plugin uses plain **JSON mode** (`/api/generate` with `"format": "json"`),
which works reliably with models as small as `qwen2.5:3b`.

## Install

```bash
pip install git+https://github.com/abugeia/beets-ai-tagcleaner
```

## Configuration

```yaml
plugins:
  - aitagcleaner
  - musicbrainz   # the standard autotagger backend

aitagcleaner:
  url: http://localhost:11434/api/generate   # Ollama generate endpoint
  model: qwen2.5:3b                           # small & fast is enough
  timeout: 60
  auto: yes                                   # run automatically during import
  # prompt: "..."                             # override the cleaning prompt
```

Pull the model once: `ollama pull qwen2.5:3b`.

## Notes

- Requires a running Ollama (or any OpenAI-compatible endpoint honouring
  `{"format": "json"}`).
- Network/model errors never block the import — the track is left untouched.
- Best paired with the `chroma` plugin (acoustic fingerprinting) for tracks
  that have no usable tags at all.

## License

MIT
