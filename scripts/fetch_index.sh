#!/usr/bin/env sh
#
# Downloads the prebuilt ChromaDB vector index published by the daily ingestion
# workflow, so the runtime image does not have to carry it (and git does not
# have to store it).
#
# No-op if an index is already present, which keeps local development working
# after you have run the ingestion pipeline yourself.
#
# Environment:
#   INDEX_URL     Override the download URL entirely.
#   INDEX_REPO    owner/repo to pull the release asset from.
#   INDEX_TAG     Release tag holding the asset (default: data-latest).
#   GITHUB_TOKEN  Required only if the repository is private.

set -eu

INDEX_REPO="${INDEX_REPO:-esvar-kn/Mutual-Fund-FAQ-Assistant}"
INDEX_TAG="${INDEX_TAG:-data-latest}"
INDEX_URL="${INDEX_URL:-https://github.com/${INDEX_REPO}/releases/download/${INDEX_TAG}/chromadb.tar.gz}"

DB_DIR="data/chromadb"

# chroma.sqlite3 is the marker: an empty directory is not a usable index.
if [ -f "${DB_DIR}/chroma.sqlite3" ]; then
    echo "[fetch_index] Existing index found at ${DB_DIR}, skipping download."
    exit 0
fi

echo "[fetch_index] No index present. Downloading from ${INDEX_URL}"
mkdir -p "${DB_DIR}"

# Download to a temp file first so a failed transfer cannot leave a half-written
# archive that later extracts into a corrupt index.
TMP_ARCHIVE="$(mktemp)"
trap 'rm -f "${TMP_ARCHIVE}"' EXIT

if [ -n "${GITHUB_TOKEN:-}" ]; then
    set -- -H "Authorization: Bearer ${GITHUB_TOKEN}"
else
    set --
fi

if ! curl -fsSL --retry 3 --retry-delay 2 "$@" -o "${TMP_ARCHIVE}" "${INDEX_URL}"; then
    echo "[fetch_index] ERROR: could not download the index." >&2
    echo "[fetch_index] Run 'python -m src.ingestion.ingestion' to build one locally," >&2
    echo "[fetch_index] or check that release '${INDEX_TAG}' exists in ${INDEX_REPO}." >&2
    exit 1
fi

tar -xzf "${TMP_ARCHIVE}" -C "$(dirname "${DB_DIR}")"

if [ ! -f "${DB_DIR}/chroma.sqlite3" ]; then
    echo "[fetch_index] ERROR: archive extracted but ${DB_DIR}/chroma.sqlite3 is missing." >&2
    exit 1
fi

echo "[fetch_index] Index ready at ${DB_DIR}."
