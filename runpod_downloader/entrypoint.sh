#!/bin/sh
set -eu

case "${H3_DOWNLOAD_TIMEOUT_SECONDS:-7200}" in
  *[!0-9]*|'') echo "H3_DOWNLOAD_TIMEOUT_SECONDS must be an integer" >&2; exit 64 ;;
esac

if [ "${H3_DOWNLOAD_TIMEOUT_SECONDS:-7200}" -gt 7200 ]; then
  echo "H3_DOWNLOAD_TIMEOUT_SECONDS cannot exceed 7200" >&2
  exit 64
fi

exec timeout "${H3_DOWNLOAD_TIMEOUT_SECONDS:-7200}" /usr/local/bin/download-models.sh
