#!/bin/sh
# AniCraft Nightly's launcher: one private profile and the flavor's launch protocol, for every
# Linux nightly format. The real program never starts without
#
#   --launch-profile nightly-v1 --profile-root <this profile> -- <the person's arguments>
#
# so nothing can move Nightly's preferences, Recovery, Logs, plug-ins, Templates, Commands,
# themes, thumbnails and guide cache (src/platform.rs) into stable's folders. The profile is a
# sibling of stable's data folder, never inside it and never containing it (src/profile_root.rs).
#
# The same file is installed as:
#   deb/rpm   /usr/bin/anicraft-nightly   (the real program in /usr/lib/anicraft-nightly/)
#   AppImage  $APPDIR/AppRun              (the real program in $APPDIR/usr/bin/)
#   Arch      bin/anicraft                (the real program in bin/.anicraft-nightly/)
#   Flatpak   /app/bin/anicraft-nightly   (the real program beside it)
#   nightly tar  anicraft-nightly         (the real program beside it)
set -eu
case "$0" in
  */*) self=$0 ;;
  *) self=$(command -v -- "$0" 2>/dev/null || printf '%s' "$0") ;;
esac
here=$(CDPATH= cd -- "$(dirname -- "$self")" && pwd)
self="$here/$(basename -- "$self")"

# Order matters: in a system install /usr/bin/anicraft is the *stable* program (the packages are
# co-installable), so the packaged lib path is tried before any same-named sibling.
real_bin=
for candidate in "$here/.anicraft-nightly/anicraft" "$here/../lib/anicraft-nightly/anicraft" "$here/anicraft" \
  "$here/usr/bin/anicraft"; do
  if [ -f "$candidate" ] && [ ! -L "$candidate" ] && ! [ "$candidate" -ef "$self" ]; then
    real_bin=$candidate
    break
  fi
done
if [ -z "$real_bin" ]; then
  echo 'anicraft-nightly: the AniCraft Nightly program is not where this launcher was installed' >&2
  exit 2
fi

profile_root="${XDG_DATA_HOME:-${HOME:?HOME is required to place the AniCraft Nightly profile}/.local/share}/anicraft-nightly/profile"

# `anicraft-nightly --version` answers the Launcher's own query form, before any profile exists.
if [ "$#" -eq 1 ] && { [ "$1" = "--version" ] || [ "$1" = "-V" ]; }; then
  exec "$real_bin" --launch-profile nightly-v1 --profile-root "$profile_root" "$1"
fi
exec "$real_bin" --launch-profile nightly-v1 --profile-root "$profile_root" -- "$@"
