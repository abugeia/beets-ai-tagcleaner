# Bench

52 real tags taken from a music library, each with the expected result
(`cases.json`), in five categories:

| cat | what | expected |
|---|---|---|
| `clean` | tags already correct (accents, `’`, `‐`, version info) | **unchanged** |
| `deco` | YouTube decorations, `feat.` in the title | decorations removed, remix/edit kept |
| `swap` | artist and title swapped or merged | fixed |
| `soundcloud` | `title` holds the uploader's name | title taken from the file name |
| `empty` | no tags at all | everything from the file name |

`clean` is the one that matters: a cleaner that damages good tags is worse than
no cleaner.

## Run

`bench.py` talks to Ollama from inside the cluster and imports the prompt from
the plugin (a local `aitagcleaner.py` next to it wins over the one in the image,
so a change can be measured before it is built):

```bash
kubectl create cm bench -n ai --from-file=bench/bench.py --from-file=bench/cases.json \
  --from-file=beetsplug/aitagcleaner.py
# pod: image ghcr.io/abugeia/beets-ai-tagcleaner:latest, command python3 -u /s/bench.py,
# configmap mounted on /s ; env MODELS=a,b and PROMPTS=v1,v2 to compare
kubectl logs -n ai tagbench > bench/results.jsonl
uv run --no-project python bench/score.py bench x   # x = list the failures
```

## Results (2026-10-16, Ollama 0.40.3, CPU, 6 threads)

| model + prompt | clean kept | total | s/track |
|---|---|---|---|
| llama3.2:3b, v1 (tags only) | 7/21 | 18/52 | 1.2 |
| gemma3:4b, v1 | 19/21 | 28/52 | 2.3 |
| **gemma3:4b, v2 (tags + file name)** | **21/21** | 39/52 | 6.5 |
| qwen3.5:4b, v2 | 20/21 | 41/52 | 9.5 |
| gemma4:e2b / e4b | — | — | fail in a 5 GiB pod |

qwen3.5:4b scores higher but strips `(Axwell Remix)` or `(instrumental
version)`, which makes MusicBrainz match the wrong recording. gemma3:4b's
remaining misses are mostly `feat.` left in the title, which beets' `ftintitle`
puts back there anyway.
