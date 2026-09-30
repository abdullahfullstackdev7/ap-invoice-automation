#!/usr/bin/env bash
# Downloads the FATURA dataset (Limam, Dhiaf, Kessentini; CC BY 4.0) from Zenodo,
# verifies its checksum, and extracts it into dataset/raw/.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RAW_DIR="${SCRIPT_DIR}/raw"
ZIP_URL="https://zenodo.org/records/10371464/files/FATURA2.zip?download=1"
ZIP_PATH="${RAW_DIR}/FATURA2.zip"
EXPECTED_MD5="4c9404462f22c5241eb1a290a02eb2a2"

mkdir -p "${RAW_DIR}"

echo "Downloading FATURA2.zip to ${ZIP_PATH} (resumable)..."
curl -L -C - --fail --retry 5 --retry-delay 10 -o "${ZIP_PATH}" "${ZIP_URL}"

echo "Verifying md5 checksum..."
if command -v md5sum >/dev/null 2>&1; then
  ACTUAL_MD5="$(md5sum "${ZIP_PATH}" | awk '{print $1}')"
else
  ACTUAL_MD5="$(md5 -q "${ZIP_PATH}")"
fi

if [ "${ACTUAL_MD5}" != "${EXPECTED_MD5}" ]; then
  echo "Checksum mismatch: expected ${EXPECTED_MD5}, got ${ACTUAL_MD5}" >&2
  echo "The download may be incomplete or corrupted. Re-run this script to resume." >&2
  exit 1
fi

echo "Checksum verified. Extracting..."
unzip -q -o "${ZIP_PATH}" -d "${RAW_DIR}"

echo "Done. FATURA extracted under ${RAW_DIR}"
