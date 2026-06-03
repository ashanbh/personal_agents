#!/usr/bin/env bash
# SwiftBar plugin — refreshes every 5 minutes.
# Point SwiftBar's plugin folder to ~/PROJ/ASHANBH/personal_agents/focusmon/swiftbar/

# Ensure Homebrew and poetry are on PATH (SwiftBar runs in a minimal env)
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"

cd "$HOME/PROJ/ASHANBH/personal_agents/focusmon/src" || exit 1
exec poetry run python attn_daily.py --today --swiftbar 2>/dev/null
