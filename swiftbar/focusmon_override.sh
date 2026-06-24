#!/usr/bin/env bash
# focusmon_override.sh — SwiftBar helper: set or clear a manual hour override.
# Called by SwiftBar with positional args: <YYYY-MM-DD> <hour> <yes|no|clear>
#
# SwiftBar example:
#   bash=/path/focusmon_override.sh param1=2026-06-23 param2=13 param3=yes terminal=false refresh=true

export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"
cd "$HOME/PROJ/ASHANBH/personal_agents/focusmon/src" || exit 1
poetry run python override_hour.py "$@"
open "swiftbar://refreshplugin?name=focusmon.1m"
