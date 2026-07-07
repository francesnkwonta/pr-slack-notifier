#!/usr/bin/env python3
"""Personal PR watcher: poll GitHub for your open PRs and post Slack
notifications when they are approved, commented on, or become ready to merge.

State is kept in state/pr-notify-state.json so each event only fires once.
The very first run seeds state silently (no backlog blast).

Env:
  GH_TOKEN          GitHub token with read access to the target org's PRs (used by `gh`)
  SLACK_WEBHOOK_URL Slack incoming webhook URL
  PR_AUTHOR         GitHub login whose PRs to watch (default: francesnkwonta)
  PR_SEARCH_ORG     Org to scope the search to (default: Ibotta)
"""

import json
import os
import subprocess
import sys
import urllib.request

STATE_PATH = os.path.join("state", "pr-notify-state.json")
SLACK_WEBHOOK_URL = os.environ["SLACK_WEBHOOK_URL"]
PR_AUTHOR = os.environ.get("PR_AUTHOR", "francesnkwonta")
PR_SEARCH_ORG = os.environ.get("PR_SEARCH_ORG", "Ibotta")

GRAPHQL = """
query($q: String!) {
  search(query: $q, type: ISSUE, first: 50) {
    nodes {
      ... on PullRequest {
        number
        title
        url
        mergeStateStatus
        repository { nameWithOwner }
        reviews(last: 50) {
          nodes { id state author { login } }
        }
        comments(last: 50) {
          nodes { id author { login } }
        }
        reviewThreads(last: 50) {
          nodes {
            comments(last: 50) {
              nodes { id author { login } }
            }
          }
        }
      }
    }
  }
}
"""


def run_query():
    q = f"is:open is:pr author:{PR_AUTHOR} org:{PR_SEARCH_ORG} archived:false"
    result = subprocess.run(
        ["gh", "api", "graphql", "-f", f"query={GRAPHQL}", "-F", f"q={q}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print("gh api graphql failed:", result.stderr, file=sys.stderr)
        sys.exit(1)
    return json.loads(result.stdout)["data"]["search"]["nodes"]


def load_state():
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH) as f:
            return json.load(f), False
    return {}, True  # first run


def save_state(state):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2, sort_keys=True)


def post_slack(text):
    payload = json.dumps({"text": text}).encode()
    req = urllib.request.Request(
        SLACK_WEBHOOK_URL, data=payload, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        if resp.status != 200:
            print("Slack post failed:", resp.status, file=sys.stderr)


def pr_link(pr):
    repo = pr["repository"]["nameWithOwner"]
    return f"{repo}#{pr['number']} ({pr['url']})"


def collect_comment_ids(pr):
    """All comment IDs on the PR not authored by you."""
    ids = set()
    for c in pr["comments"]["nodes"]:
        if c["author"] and c["author"]["login"] != PR_AUTHOR:
            ids.add(c["id"])
    for thread in pr["reviewThreads"]["nodes"]:
        for c in thread["comments"]["nodes"]:
            if c["author"] and c["author"]["login"] != PR_AUTHOR:
                ids.add(c["id"])
    return ids


def approval_reviews(pr):
    """Map of review id -> author login for APPROVED reviews."""
    out = {}
    for r in pr["reviews"]["nodes"]:
        if r["state"] == "APPROVED" and r["author"]:
            out[r["id"]] = r["author"]["login"]
    return out


def main():
    state, first_run = load_state()
    prs = run_query()
    new_state = {}
    events = []

    for pr in prs:
        key = f"{pr['repository']['nameWithOwner']}#{pr['number']}"
        prev = state.get(key, {})

        approvals = approval_reviews(pr)
        comment_ids = collect_comment_ids(pr)
        is_ready = pr.get("mergeStateStatus") == "CLEAN"

        seen_approvals = set(prev.get("approvals", []))
        seen_comments = set(prev.get("comments", []))
        ready_notified = prev.get("ready_notified", False)

        if not first_run:
            for rid, author in approvals.items():
                if rid not in seen_approvals:
                    events.append(
                        f":white_check_mark: *{author}* approved {pr_link(pr)} — {pr['title']}"
                    )
            new_comments = comment_ids - seen_comments
            if new_comments:
                events.append(
                    f":speech_balloon: {len(new_comments)} new comment(s) on {pr_link(pr)} — {pr['title']}"
                )
            if is_ready and not ready_notified:
                events.append(
                    f":rocket: Ready to merge: {pr_link(pr)} — {pr['title']}"
                )

        new_state[key] = {
            "approvals": sorted(approvals.keys()),
            "comments": sorted(comment_ids),
            "ready_notified": is_ready,  # reset to False automatically when it leaves CLEAN
        }

    for msg in events:
        post_slack(msg)

    save_state(new_state)

    if first_run:
        print(f"First run: seeded state for {len(new_state)} PR(s), no notifications sent.")
    else:
        print(f"Checked {len(new_state)} PR(s), sent {len(events)} notification(s).")


if __name__ == "__main__":
    main()
