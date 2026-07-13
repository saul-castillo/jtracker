# JTracker

JTracker checks official ATS feeds hourly, ranks hardware internships, and opens assigned GitHub issues for new matches. GitHub then sends the account's normal email notification.

Current live coverage: SpaceX, Anduril, Astranis, Neuralink, and Zoox. Company-specific Workday connectors for the semiconductor list are the next expansion.

## Start it

In GitHub Actions, open **Hourly internship tracker**, select **Run workflow**, enable **Send a test notification only**, and run it. The schedule runs at 17 minutes past every hour and creates nothing when no new match exists.

No external service or user-managed secret is required. The workflow uses GitHub's short-lived built-in token.

## Local test

    pip install -r requirements.txt
    python tracker.py --dry-run
