# Root conftest: makes pytest put the repo root on sys.path so tests import
# bakeoff/research/... as `python3 -m unittest discover -s tests` does.
# ponytail: kept here instead of pyproject.toml, which is hash-pinned in source manifests.

# Frozen executed-source copies under research/ hold historical test files; never collect them.
collect_ignore_glob = ["research/*", "release-staging/*", "models/*", "build/*"]
