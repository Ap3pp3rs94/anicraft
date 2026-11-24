#!/bin/sh
set -eu

real_bin="$(dirname "$0")/.anicraft-nightly/anicraft"
if [ "${1:-}" = "--version" ] || [ "${1:-}" = "-V" ]; then
  exec "$real_bin" "$@"
fi
profile_base="${XDG_DATA_HOME:-${HOME:?HOME is required}/.local/share}"
export XDG_CONFIG_HOME="$profile_base/anicraft-nightly"
exec "$real_bin" "$@"
