# beets, prêt pour le tagging de rips YouTube :
#   1) patch du bug MusicBrainz #6066 (paramètre `alias` parasite) appliqué au build
#   2) le plugin aitagcleaner installé depuis ce dépôt
#
# Base pinnée par digest = lscr.io/linuxserver/beets:latest au 2026-06-17 (beets 2.11.0).
FROM lscr.io/linuxserver/beets@sha256:bb73b8be1142a7b22e13d6f76f986bec99e60761a967714b098f8d766f88ca37

# 1) Patch #6066 : retire `, "alias": name` de la recherche de recordings.
#    Le grep final fait ÉCHOUER le build si le motif n'est plus là (garde-fou : si
#    beets corrige le bug en amont, le build casse et on réévalue le patch).
RUN MB="$(ls /lsiopy/lib/python*/site-packages/beetsplug/musicbrainz.py)" && \
    sed -i 's/, "alias": name//' "$MB" && \
    grep -q '{"artist": artist, "recording": name}' "$MB"

# 2) Installe le plugin depuis les sources du dépôt.
COPY pyproject.toml README.md /tmp/plugin/
COPY beetsplug /tmp/plugin/beetsplug
RUN /lsiopy/bin/pip install --no-cache-dir /tmp/plugin && rm -rf /tmp/plugin
