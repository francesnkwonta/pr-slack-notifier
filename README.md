# pr-slack-notifier

Personal poller that watches **your** open GitHub PRs and posts to a Slack
channel when one is **approved**, **commented on**, or becomes **ready to merge**.

Runs entirely in GitHub Actions on a cron — nothing runs on your laptop, and
nothing is added to the repos you're contributing to.

## How it works

- `.github/workflows/pr-notify.yml` runs every ~10 minutes.
- `scripts/pr_notify.py` searches `is:open is:pr author:<you> org:<org>`, then
  compares each PR against the last run's saved state and posts one Slack
  message per new event.
- Dedupe state lives in `actions/cache` (rolling key) — no commit noise.
- The **first run seeds state silently** so you don't get a backlog blast.

## Setup

1. **Create the Slack incoming webhook** pointing at your private channel and
   copy the URL. (https://api.slack.com/messaging/webhooks)

2. **Create a GitHub token** with read access to your org's PRs. Ibotta uses
   SSO, so **authorize the token for the Ibotta org** after creating it:
   - Classic token: `repo` scope, then click **Configure SSO → Authorize** for Ibotta.
   - Or fine-grained: org `Ibotta`, Pull requests → Read-only.

3. **Add both as repo secrets** (Settings → Secrets and variables → Actions):
   - `GH_PAT` — the token from step 2
   - `SLACK_WEBHOOK_URL` — the webhook from step 1

4. **Confirm the workflow is on the default branch.** Scheduled workflows only
   fire from the repo's default branch.

5. Trigger a manual run (Actions → PR Slack Notifier → Run workflow) to seed
   state. The next run onward will send notifications.

## Tuning

- Change the poll frequency via the `cron` line in the workflow.
- Change who/what is watched via the `PR_AUTHOR` / `PR_SEARCH_ORG` env vars in
  the workflow, or set `PR_SEARCH_ORG` to a single repo by editing the search
  query in `scripts/pr_notify.py`.
