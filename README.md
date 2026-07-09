# julietkelson.github.io

## Now Playing (aggregated listening banner on /music/)

The `/music/` page shows the average vibe of my last 50 Spotify plays,
updated by a GitHub Actions cron every 5 minutes.

### One-time setup

1. Create a Spotify app at
   [developer.spotify.com](https://developer.spotify.com/dashboard). The
   dashboard requires the app owner to have Spotify Premium. Set the
   redirect URI to `http://127.0.0.1:3000` (no trailing slash), and check
   only the **Web API** box under APIs used.

2. Obtain a refresh token locally:

   ```bash
   SPOTIFY_CLIENT_ID='your-client-id' SPOTIFY_CLIENT_SECRET='your-client-secret' python3 scripts/get_refresh_token.py
   ```

   Approve the browser prompt when it opens. The script prints a refresh
   token between two `====` lines.

3. Add these repo secrets under Settings → Secrets and variables → Actions:

   - `SPOTIFY_CLIENT_ID`
   - `SPOTIFY_CLIENT_SECRET`
   - `SPOTIFY_REFRESH_TOKEN`

4. Trigger the workflow once manually via the Actions tab to confirm.
   Subsequent runs happen automatically every 5 minutes.

### Data artifacts

Written to `data/` by the cron. All are safe to commit.

- `now-playing.json` — internal snapshot of the most recent run.
- `history.json` — rolling last 500 plays / 30 days.
- `aggregates.json` — precomputed averages the page reads.
- `features-cache.json` — per-track ReccoBeats cache; keeps runs fast.

### Local dry run

To see what the pipeline would write without touching any files:

```bash
SPOTIFY_CLIENT_ID='...' SPOTIFY_CLIENT_SECRET='...' SPOTIFY_REFRESH_TOKEN='...' python3 scripts/now_playing.py --dry-run
```

### Rotating the client secret

Rotate the Spotify client secret any time you suspect it's leaked
(Settings → View client secret → Rotate) and update the GitHub Actions
secret with the new value. Existing refresh tokens continue to work.
