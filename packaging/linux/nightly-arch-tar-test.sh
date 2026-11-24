#!/usr/bin/env bash
# Validate the staged Arch launcher without building or opening AniCraft.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
stage="$work/source"
dst="$work/dist"
base=anicraft-0.0.1-nightly.1-linux-x86_64
mkdir -p "$stage/bin" "$dst" "$work/extract"

# A local env+argv recorder stands in for the compiled binaries. It never opens a UI.
cat >"$stage/bin/anicraft" <<'RECORDER'
#!/bin/sh
printf 'XDG_CONFIG_HOME=<%s>\n' "${XDG_CONFIG_HOME:-}"
for arg in "$@"; do
  printf '<%s>\n' "$arg"
done
RECORDER
chmod 755 "$stage/bin/anicraft"
cp "$stage/bin/anicraft" "$stage/bin/anicraft-cli"

bash "$HERE/nightly-arch-tar.sh" "$stage" "$work/stage" "$dst" "$base"
tar -xzf "$dst/$base.tar.gz" -C "$work/extract"
bin="$work/extract/$base/bin"
# Simulate the existing Arch bin-tree copy and public launcher rename.
mkdir -p "$work/installed"
cp -R "$bin" "$work/installed/bin"
bin="$work/installed/bin"
mv "$bin/anicraft" "$bin/anicraft-nightly"
mv "$bin/anicraft-cli" "$bin/anicraft-nightly-cli"

[[ ! -e "$stage/bin/.anicraft-nightly" ]]
cmp "$stage/bin/anicraft" "$bin/.anicraft-nightly/anicraft"
cmp "$stage/bin/anicraft-cli" "$bin/anicraft-nightly-cli"
export HOME="$work/home with space"
unset XDG_DATA_HOME XDG_CONFIG_HOME
expect() {
  expected="$1"
  shift
  actual=$(PATH="$bin:$PATH" anicraft-nightly "$@")
  if [[ "$actual" != "$expected" ]]; then
    printf 'expected:\n%s\nactual:\n%s\n' "$expected" "$actual" >&2
    exit 1
  fi
}
expect "XDG_CONFIG_HOME=<$HOME/.local/share/anicraft-nightly>"
export XDG_DATA_HOME="$work/xdg with space"
expect "$(printf 'XDG_CONFIG_HOME=<%s>\n<%s>\n<%s>\n' "$XDG_DATA_HOME/anicraft-nightly" 'scene with spaces.anicraft' '--other-name.anicraft')" \
  'scene with spaces.anicraft' '--other-name.anicraft'
expect "$(printf 'XDG_CONFIG_HOME=<>\n<--version>\n')" --version
expect "$(printf 'XDG_CONFIG_HOME=<>\n<-V>\n')" -V

echo "PASS: Arch Nightly handoff isolates the profile and preserves launch arguments"
