---
layout: post
title:  "Did we cover it? Building a search gap detector for newsrooms"
date:   2026-06-25 09:00:00 -0500
subtitle: "A pipeline that flags trending Google searches, checks whether your newsroom covered them, and measures the gap."
description: "A search gap detector for newsrooms — detects trending Google queries, matches them to published articles with Snowflake Cortex, and surfaces editorial gaps. By Juliet Kelson."
categories:
  - From Work
---

_Code and full documentation on [GitHub](https://github.com/julietkelson/trend-tracker)._

---

Google Search Console tells you which searches lead readers to your site. Your CMS tells you what you published. What it doesn't tell you is if those two things overlap — whether readers were searching for something your newsroom didn't write about.

That question is the whole point of this project. I built a pipeline at the Star Tribune that detects rising search queries, checks whether we published a story on the topic, and measures the gap if we did.

Here's how it works, what I learned building it, and how to run it yourself.

---

## The problem

On any given day, thousands of Google searches send readers to startribune.com. Some of those queries spike because something happened in the news — a Timberwolves playoff run, a wildfire near Ely, a storm rolling into the Twin Cities. When impressions on a query triple their normal level for two days in a row, that's a signal: readers want coverage.

The question is whether we provided it. And answering it required a pipeline like this one.

## Trend detection

The first step is finding the spikes. For each search query in Google Search Console, I compute a 14-day rolling average of daily impressions — what "normal" looks like for that query. Then I compare each day's actual impressions to that baseline.

If a query hits 3× its baseline for two consecutive days, it's flagged as a trend onset. That consecutive-days requirement filters out noise: a single day spike is often a data artifact or a one-off news event. Two days in a row suggests real, sustained reader interest. There's also an impression floor — queries below 50 daily impressions are excluded, so we're not flagging "trends" where the count goes from 2 to 6.

```python
# Rolling 14-day mean, shifted one day forward (no lookahead bias)
baseline   = pivot.rolling(window=14, min_periods=3).mean().shift(1)
spike_ratio = pivot / baseline.replace(0, float("nan"))
is_spiking  = (spike_ratio >= 3.0) & (pivot >= 50)
```

The 14-day window captures two full weekly cycles, which matters because search volume has weekly patterns — news queries tend to spike on weekdays and quiet on weekends. A shorter window would mistake Tuesday for trending.

## Matching trends to articles

Once I have a list of trending queries, I need to check whether we published something. The naive approach — exact string matching — fails immediately. A reader searching "Wolves" won't match an article with "Timberwolves" in the headline. "Ant" won't match "Anthony Edwards." Jaccard similarity on keywords gets you part of the way there. (Quick refresher: Jaccard scores how much two phrases overlap, from 0 to 1 — the words they share divided by the total unique words across both.) But it has a precision problem: lower the threshold to catch more matches and you start pulling in articles that share a word but not a topic.

I ended up with a two-stage approach.

**Stage 1: Jaccard pre-filter.** For each trending query, I tokenize the query and every article headline + URL slug from a three-week window around the trend onset (7 days before through 14 days after). Any article that scores at least 0.05 Jaccard similarity with the query makes the candidate list. This is loose by design — the point is to catch near-misses like "Wolves" articles for a "timberwolves" query, not to make a final decision.

**Stage 2: Cortex confirmation.** The candidate list goes to Snowflake Cortex COMPLETE (`mistral-7b`) in a single batched SQL call. The prompt template is parameterized on two env vars — `PUBLICATION_NAME` and `PUBLICATION_LOCATION` — so any paper can drop in its own brand:

```
The {publication_name} is a {publication_location} newspaper.
A reader searched for "{query}".
Did the {publication_name} publish an article specifically about this topic?
Headline: "{headline}"
Section: {section}
Answer yes or no.
```

Cortex says yes or no. Only yes candidates make it into the results. The whole thing costs under a tenth of a cent per pipeline run.

If Cortex is unavailable, the pipeline falls back to a stricter Jaccard threshold (0.15) so it never crashes — it just becomes slightly less generous.

## A case study in false positives

The first version of the Cortex prompt didn't include the article's section or anything about the publication. It just asked: "Did this paper publish an article about this topic?"

That broke on "anthony edwards." A reader searching for Anthony Edwards is almost certainly looking for the Timberwolves point guard. But a News-section piece with "Anthony Fauci" in the headline shares the token "anthony" with the query — Jaccard flagged it as a candidate, and the underspecified prompt confirmed it as a match.

The fix was two lines: add the publication's geography and add the article's section. With that context, Cortex correctly rejects a News article about a public health official for a query that almost certainly means a basketball player.

```python
prompt = (
    f"The {PUBLICATION_NAME} is a {PUBLICATION_LOCATION} newspaper. "
    f"A reader searched for \"{query}\". "
    f"Did the {PUBLICATION_NAME} publish an article specifically about this topic?\n"
    f"Headline: \"{headline}\"\n"
    f"Section: {section}\n"
    f"Answer yes or no."
)
```

The lesson: LLMs can do good binary classification on short prompts, but they need enough context to resolve ambiguity. "Did we write about X?" is underspecified. "Did this regional paper's Sports section cover the search query X?" is not.

## What the output looks like

Each pipeline run writes one row per trending query × matching article into a table called `TREND_PUBLISH_GAP`. The repo's [synthetic example](https://github.com/julietkelson/trend-tracker/blob/main/examples/sample_output.csv) has 12 trending queries for a fictional local newsroom — 7 covered, 5 not. Here's a slice:

| Query | Spike | Headline | Gap (hrs) | Status |
|---|---|---|---|---|
| city council vote | 4.2× | City Council Approves Downtown Redevelopment Plan… | -96 | `ahead_of_trend` |
| state fair tickets | 5.1× | State Fair Tickets Go On Sale Next Week… | -24 | `within_3_days` |
| mayor press conference | 3.8× | Mayor Outlines Budget Priorities Ahead of Council Vote | -6 | `same_day_before` |
| local election results | 4.5× | Tuesday's Election Results: Three Incumbents Hold Seats | 12 | `within_24h` |
| zoning meeting | 3.4× | Planning Commission Tables Decision on West Side Rezoning | 96 | `within_week` |
| restaurant week | 4.0× | — | — | `no_coverage` |
| playoff schedule | 5.5× | — | — | `no_coverage` |

Each row is a finding the pipeline is asking the newsroom to react to.

- **Negative gap hours** mean the story published *before* readers started searching — coverage was ahead of the trend. The reporting was already there when readers came looking.
- **Small positive gap hours** mean the newsroom moved quickly once the trend started.
- **`no_coverage`** means the trend fired but nothing matched, even after Cortex. These are the gaps the pipeline exists to surface.

The categorical `GAP_STATUS` values are bucketed from `GAP_HOURS`:

| Status | Definition |
|---|---|
| `ahead_of_trend` | Published 3+ days before the trend peaked |
| `proactive` | Published 1–3 days before |
| `same_day_before` | Published same day, before peak |
| `within_24h` | Published within 24 hours of peak |
| `within_3_days` | Published within 72 hours |
| `within_week` | Published 1–7 days after |
| `late` | Published more than a week after |
| `no_coverage` | No matching article found |

The point of these buckets isn't to grade a newsroom — `ahead_of_trend` isn't always praise (the coverage may have *driven* the interest, or demand was already building below the spike threshold), and `no_coverage` isn't always failure (some trends shouldn't be covered, and the matcher misses things even with the LLM pass). The buckets are there so dashboards can filter, and so editors can ask the right follow-up question for each row instead of treating all "gaps" the same.

The pipeline also publishes a `TRENDING_NOT_COVERED` view that filters to just the last fourteen days of uncovered trends — that's the one you'd look at before an editorial meeting.

## Cost

Cortex COMPLETE with `mistral-7b` runs at fractions of a cent per pipeline run. Cortex is only called for candidates that clear the Jaccard pre-filter, so the call volume stays small. At roughly thirty trending queries per run with a handful of candidates each — daily cadence — the annual Cortex bill lands under $0.40. Warehouse compute is shared with whatever Snowflake usage your team already has, so it adds little to the bill.

## Running it yourself

The full code is on [GitHub](https://github.com/julietkelson/trend-tracker). It ships in two flavors:

- **Snowflake** — `pipeline.py`, `gsc_pull.py`, `load_gsc_csv.py`. The production-tested path. Uses Snowflake Cortex `COMPLETE` for the LLM step.
- **BigQuery** — the same scripts with `_bigquery` suffixes. A mirror that has not been run end-to-end; useful as a starting point if BQ is your warehouse, with `ML.GENERATE_TEXT` against a remote Gemini model standing in for Cortex. Expect to debug.

The Snowflake setup, in brief:

```bash
git clone https://github.com/julietkelson/trend-tracker
cd trend-tracker
pip install -r requirements.txt
cp .env.example .env
# fill in your Snowflake + GSC credentials and your publication context
python gsc_pull.py --backfill   # or load_gsc_csv.py for the CSV path
python pipeline.py
```

A few pieces worth calling out:

**Publication context is parameterized.** `PUBLICATION_NAME` and `PUBLICATION_LOCATION` in `.env` get spliced into the Cortex prompt. That's the same fix from the false-positives section earlier — instead of hardcoding "Minnesota newspaper," the matcher learns *your* paper's geography and brand at runtime. Generic prompts confuse Anthony Edwards for Anthony Fauci; brand-aware ones don't.

**Your CMS table.** Article matching reads from a Snowflake table named in `ARC_TABLE`. The shipped `load_arc()` assumes Arc Publishing columns; if your CMS exports look different, that one function is where to adjust. Required fields are documented in the README.

**Evergreen sections** like Obituaries, Games, and Weather are excluded from the gap analysis by default, since they aren't news-driven. Override the list in `pipeline.py` for your sections.

**Tests.** A `pytest` suite runs against mocked warehouse connections, so trend detection and matching logic can be verified without credentials.

## What's next

The repo ships both ingestion paths: `gsc_pull.py` uses a GCP service account against the Search Console API, and `load_gsc_csv.py` works off the GSC UI export for one-off retrospectives. The piece still missing is scheduling. A production deployment would need key-pair auth (`SNOWFLAKE_AUTHENTICATOR=snowflake_jwt`) instead of SSO, and a real scheduler — Airflow, cron, whatever your org runs — to fire daily before an editorial meeting.

If you build something similar for your newsroom, [reach out](mailto:kelsonjuliet@gmail.com) and let me know how it goes!
