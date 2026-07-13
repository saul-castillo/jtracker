# JTracker

JTracker checks official ATS feeds hourly, ranks hardware internships, and emails new matches through Brevo.

Current live coverage: SpaceX, Anduril, Astranis, Neuralink, and Zoox. Company-specific Workday connectors for the semiconductor list are the next expansion.

## Start it

In GitHub Actions, open **Hourly internship tracker**, select **Run workflow**, enable **Send a test email only**, and run it. The schedule runs at 17 minutes past every hour and sends nothing when no new match exists.

The repository secret `BREVO_API_KEY` must be configured. Never commit the key.

## Local test

    pip install -r requirements.txt
    python tracker.py --dry-run
