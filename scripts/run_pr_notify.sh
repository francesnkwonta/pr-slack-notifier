#!/bin/zsh
# Wrapper invoked by launchd (com.frances.pr-notify) to run the PR notifier
# on a reliable local schedule instead of GitHub Actions cron.
#
# - Puts Homebrew on PATH so `gh` and `python3` resolve.
# - Sources local secrets (SLACK_WEBHOOK_URL) from ~/.config/pr-notify/env.
# - GitHub auth comes from the local `gh` keyring login (no token needed here).
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

source "$HOME/.config/pr-notify/env"

cd "/Users/frances.nkwonta/Documents/GitHub/pr-slack-notifier"

exec python3 scripts/pr_notify.py
