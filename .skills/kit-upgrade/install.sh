#!/usr/bin/env bash
# Install the kit-upgrade skill into an existing Kit project so an AI assistant
# can load it there. Copies SKILL.md, README.md, procedures/, and references/
# (not this installer) into <target>/<dest-kind>/kit-upgrade/.
#
# Usage:
#   ./install.sh /path/to/your-kit-project [dest-kind]
#     dest-kind defaults to ".skills" (this repo's convention).
#     Use ".claude/skills" for repos that follow the Claude Code skills layout.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # .../.skills/kit-upgrade
TARGET="${1:-}"
DEST_KIND="${2:-.skills}"

if [ -z "$TARGET" ]; then
  echo "Usage: $0 /path/to/your-kit-project [.skills|.claude/skills]" >&2
  exit 1
fi
if [ ! -d "$TARGET" ]; then
  echo "Error: target project directory not found: $TARGET" >&2
  exit 1
fi

DEST="$TARGET/$DEST_KIND/kit-upgrade"
mkdir -p "$DEST"
cp "$SRC/SKILL.md" "$SRC/README.md" "$DEST/"
# Copy the bundled dirs idempotently: replace each in place so a re-install does not
# nest it (cp -R of a dir into an existing dir would create e.g. references/references).
for sub in references procedures; do
  rm -rf "$DEST/$sub"
  cp -R "$SRC/$sub" "$DEST/"
done

echo "Installed kit-upgrade skill to: $DEST"
echo "Next: point your AI assistant at $DEST/SKILL.md and ask it to upgrade the project."
