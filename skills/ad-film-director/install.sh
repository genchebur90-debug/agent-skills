#!/usr/bin/env bash
#
# install.sh — install ad-film-director for Claude Code, Codex and Kimi CLI.
#
# The three hosts read skills from different directories. Rather than copying the
# skill three times, this symlinks one source of truth into each location, so a
# `git pull` updates every host at once.
#
# Usage:
#   ./install.sh                 # symlink into every detected host
#   ./install.sh --copy          # copy instead of symlink (Windows, or if preferred)
#   ./install.sh --project       # install into ./.agents/skills of the current repo
#   ./install.sh --check         # report what's installed and what's missing
#   ./install.sh --uninstall     # remove the links
#
set -euo pipefail

SKILL_NAME="ad-film-director"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

MODE="link"
SCOPE="user"
ACTION="install"

for arg in "$@"; do
  case "$arg" in
    --copy)      MODE="copy" ;;
    --link)      MODE="link" ;;
    --project)   SCOPE="project" ;;
    --user)      SCOPE="user" ;;
    --check)     ACTION="check" ;;
    --uninstall) ACTION="uninstall" ;;
    -h|--help)
      sed -n '3,18p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

# --- colours (skipped when not a terminal) ---------------------------------
if [ -t 1 ]; then
  B=$'\033[1m'; G=$'\033[32m'; Y=$'\033[33m'; R=$'\033[31m'; D=$'\033[2m'; N=$'\033[0m'
else
  B=""; G=""; Y=""; R=""; D=""; N=""
fi

ok()   { printf '%s✓%s %s\n' "$G" "$N" "$1"; }
warn() { printf '%s!%s %s\n' "$Y" "$N" "$1"; }
bad()  { printf '%s✗%s %s\n' "$R" "$N" "$1"; }
dim()  { printf '%s  %s%s\n' "$D" "$1" "$N"; }

# --- target directories ----------------------------------------------------
# User scope: each host's own conventional location. Kimi also reads the Claude
# and Codex paths, so it is covered by those, but we add its own for clarity.
targets=()
if [ "$SCOPE" = "project" ]; then
  targets+=("$PWD/.agents/skills")     # Codex + Kimi read this
  targets+=("$PWD/.claude/skills")     # Claude Code project scope
else
  targets+=("$HOME/.claude/skills")            # Claude Code
  targets+=("$HOME/.agents/skills")            # Codex + Kimi (shared convention)
  targets+=("$HOME/.config/agents/skills")     # Kimi preferred user path
fi

# --- check -----------------------------------------------------------------
if [ "$ACTION" = "check" ]; then
  printf '%sad-film-director — install status%s\n\n' "$B" "$N"
  printf 'source: %s\n\n' "$SRC"
  for t in "${targets[@]}"; do
    dest="$t/$SKILL_NAME"
    if [ -L "$dest" ]; then
      ok "$dest ${D}→ $(readlink "$dest")${N}"
    elif [ -d "$dest" ]; then
      ok "$dest ${D}(copy)${N}"
    else
      dim "not installed: $dest"
    fi
  done

  printf '\n%sdependencies%s\n' "$B" "$N"
  for tool in python3 ffmpeg ffprobe; do
    if command -v "$tool" >/dev/null 2>&1; then
      ok "$tool"
    else
      case "$tool" in
        python3) bad "$tool — required for all scripts" ;;
        *)       warn "$tool — needed for assembly and export" ;;
      esac
    fi
  done

  printf '\n%ssibling skills%s\n' "$B" "$N"
  found_ve=""
  for d in "$PWD/video-editor" \
           "$HOME/.claude/skills/video-editor-skill/video-editor" \
           "$HOME/.agents/skills/video-editor-skill/video-editor" \
           "$HOME/.codex/skills/video-editor-skill/video-editor"; do
    [ -f "$d/playbook.py" ] && found_ve="$d" && break
  done
  if [ -n "$found_ve" ]; then ok "video-editor ${D}$found_ve${N}"
  else
    warn "video-editor not found — assembly will be draft quality"
    dim "npx skills add genchebur90-debug/video-editor-skill -g"
  fi

  found_w=""
  for d in "$HOME/.claude/skills/watch" "$HOME/.agents/skills/watch" \
           "$HOME/.codex/skills/watch" \
           "$HOME"/.claude/plugins/cache/claude-video/watch/*/skills/watch; do
    [ -f "$d/scripts/watch.py" ] && found_w="$d" && break
  done
  if [ -n "$found_w" ]; then ok "watch ${D}$found_w${N}"
  else
    warn "watch not found — cannot visually review generated ads"
    dim "npx skills add bradautomates/claude-video -g"
  fi

  printf '\n%sconfig%s\n' "$B" "$N"
  if [ -f "$SRC/fleet.yaml" ]; then
    ok "fleet.yaml present"
  else
    warn "fleet.yaml missing — using fleet.example.yaml defaults"
    dim "cp $SRC/fleet.example.yaml $SRC/fleet.yaml && \$EDITOR \$_"
  fi
  exit 0
fi

# --- uninstall -------------------------------------------------------------
if [ "$ACTION" = "uninstall" ]; then
  printf '%sRemoving %s%s\n\n' "$B" "$SKILL_NAME" "$N"
  removed=0
  for t in "${targets[@]}"; do
    dest="$t/$SKILL_NAME"
    if [ -L "$dest" ]; then
      rm "$dest"; ok "unlinked $dest"; removed=$((removed+1))
    elif [ -d "$dest" ]; then
      rm -rf "$dest"; ok "removed $dest"; removed=$((removed+1))
    fi
  done
  [ "$removed" -eq 0 ] && dim "nothing was installed"
  exit 0
fi

# --- install ---------------------------------------------------------------
printf '%sInstalling %s%s\n\n' "$B" "$SKILL_NAME" "$N"
printf 'source: %s\nmethod: %s (%s scope)\n\n' "$SRC" "$MODE" "$SCOPE"

if [ ! -f "$SRC/SKILL.md" ]; then
  bad "SKILL.md not found in $SRC — run this from inside the skill directory"
  exit 1
fi

installed=0
for t in "${targets[@]}"; do
  dest="$t/$SKILL_NAME"
  mkdir -p "$t"

  if [ -L "$dest" ]; then
    current="$(readlink "$dest")"
    if [ "$current" = "$SRC" ]; then
      ok "already linked: $dest"; installed=$((installed+1)); continue
    fi
    rm "$dest"
  elif [ -e "$dest" ]; then
    backup="$dest.backup.$(date +%Y%m%d%H%M%S)"
    mv "$dest" "$backup"
    warn "existing install moved to $backup"
  fi

  if [ "$MODE" = "link" ]; then
    if ln -s "$SRC" "$dest" 2>/dev/null; then
      ok "linked $dest"; installed=$((installed+1))
    else
      warn "symlink failed, copying instead"
      cp -R "$SRC" "$dest" && ok "copied $dest" && installed=$((installed+1))
    fi
  else
    cp -R "$SRC" "$dest" && ok "copied $dest" && installed=$((installed+1))
  fi
done

if [ "$installed" -eq 0 ]; then
  bad "nothing was installed"
  exit 1
fi

chmod +x "$SRC"/scripts/*.py 2>/dev/null || true

# --- next steps ------------------------------------------------------------
printf '\n%sNext steps%s\n\n' "$B" "$N"

if [ ! -f "$SRC/fleet.yaml" ]; then
  printf '%s1.%s Describe your generation platforms:\n' "$B" "$N"
  dim "cp $SRC/fleet.example.yaml $SRC/fleet.yaml"
  dim "\$EDITOR $SRC/fleet.yaml"
  printf '\n'
fi

printf '%s2.%s Verify the install:\n' "$B" "$N"
dim "$SRC/install.sh --check"
printf '\n'
printf '%s3.%s Restart your agent host so it picks up the new skill.\n' "$B" "$N"
printf '\n'
printf '%s4.%s Then just ask for an ad:\n' "$B" "$N"
dim '"Make me three Reels ads for this shampoo" (attach a product photo)'
printf '\n'

if command -v ffmpeg >/dev/null 2>&1; then :; else
  warn "ffmpeg is not installed — assembly and export will not work"
  dim "macOS: brew install ffmpeg   ·   Debian/Ubuntu: sudo apt install ffmpeg"
  printf '\n'
fi

printf '%sOptional but recommended%s — these do specialist work this skill delegates:\n' "$B" "$N"
dim "npx skills add genchebur90-debug/video-editor-skill -g   # post-production"
dim "npx skills add bradautomates/claude-video -g             # visual review"
printf '\n'
