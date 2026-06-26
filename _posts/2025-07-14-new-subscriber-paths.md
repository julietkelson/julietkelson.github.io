---
layout: post
title:  "New Subscriber Paths: the newsroom metric that measures what people pay for"
date:   2025-07-14 09:00:00 -0500
subtitle: "A metric I co-created at the Star Tribune to measure which content actually drives subscriptions — not just clicks, but the stories that move readers to pay."
description: "How New Subscriber Paths works, why it tracks subscription conversion better than session volume, and how it reshaped the News × Analytics partnership at the Star Tribune. By Juliet Kelson."
categories:
  - From Work
---

_Presented at [SRCCON 2025](https://drive.google.com/file/d/1yH-A4iYyqsf3s5wE0K5YkwasNUvM76KC/view). The numbers are proprietary, so the chart is anonymized. The method, and how it changed the Analytics–News relationship, are the parts worth sharing._

---

Most newsrooms measure content by clicks. A story does well, it gets a lot of pageviews; it does poorly, it doesn't. That's a useful signal for reach. It's a terrible signal for value, because the stories people *read* and the stories people *pay for* are not the same set.

I co-created New Subscriber Paths at the Star Tribune to measure the second one. The goal was a metric the newsroom could trust to answer a question dashboards weren't really answering: *what kinds of journalism actually drive subscriptions?*

This is how it works, and how it changed the way News and Analytics talk to each other.

---

## How it works

A **path** to subscription includes every article a reader viewed in the 30 days before they subscribed. Each new subscriber has one. The metric counts how often each article shows up across all of those paths.

In other words: a story's path count = the number of users who purchased a subscription in the 30 days after reading the story. That turns out to have a much tighter relationship with subscription conversion than session volume alone.

Once you have paths per story, articles can be tagged with levers — story archetype, topic, location, framing, discovery strategy, photos, video, galleries, content vertical — to look for patterns. The output of that analysis gives a view of what kinds of journalism people are actually willing to pay for, not just what they click on, and how different elements of that journalism affect acquisition. Something few other newsrooms are measuring.

Paths aren't a whole-picture metric. They don't measure retention, reach, engagement, or readers who can't afford to subscribe. They're a *conversion signal*, full stop. Discounted paywall offers also create noise unrelated to content, so those periods, among other features, should be controlled for when reporting and modeling expected paths.

## How we built it

GA and Piano data give us readership and subscription activity tied to an individual user, which is what makes the path possible: every subscriber's last 30 days of reading can be reconstructed and counted.

Pipelines running in GitHub Actions derive paths each day. A separate model running in the same workflow predicts a probability curve for how many paths a story *should* have, given its days since publish, content section, and the paywall intro offer that was in market at the time. The output gets bucketed based on how it aligns to expectations, and that bucketed view is what the newsroom sees. Buckets keep the conversation about whether a story performed against prediction, not whether it had a big number.

## The relationship part

This wasn't only an analytics project — it reshaped how News and Analytics work together. The process was collaborative from the start: editors helped define what they wanted to know, and we built the infrastructure and analysis to answer it. The result was a shared language for talking about content value that both teams actually trusted.

That last word is the one that mattered. Newsrooms are skeptical of analytics for good reasons — most of the metrics they see don't measure the journalism itself, and they've watched data get used as a stick instead of a carrot. Paths gave editors a number that lined up with their instincts about what was working, which meant they used it to inform their content strategy.

Trust didn't appear on its own. To introduce Paths, we sat down with every department in the newsroom and walked through the metric, what it measured, what it didn't, where the buckets came from. We trained editors and reporters on the dashboards directly, and held regular office hours so people could come in with a question, or with a pattern they were seeing, and ask whether it was real.

## How we iterated

Once Paths was live, the question shifted from *does it work?* to *what is it telling us?* The answer kept changing depending on which lever you looked at. So we ran deep dives, one question at a time, whenever curiosity from the newsroom or our team made one worth chasing.

When there was interest in multimedia, we pulled apart how photos, video, and galleries affect paths. When the question turned to graphics, we looked at data visualization and embedded charts the same way. We added topic and archetype modeling so editors could ask sharper questions: when writing about a given topic, do potential subscribers convert more when the story is written in feature style or inverted pyramid?

Each deep dive ended in a presentation and discussion with team leads and editors. The agenda was largely shaped by their questions. Paths wasn't a one-time finding the newsroom got a deck on and moved past. It was something they kept asking new questions of, and we kept answering them.

## Impact

The reporting metric and the way it informs content strategy contributed to:

- **~$1M** in annual subscriber revenue added above predictions each month
- **+3.1K new subscribers per month** above predictions since Paths began informing content strategy
- A **News × Analytics** working relationship that didn't exist in the same form before

The numbers are proprietary so the chart below runs without axes, but the shape is the point. How often an article appears across subscription paths is tightly correlated with the number of new subscribers who started reading it within 30 days.

<div class="work-chart-card" role="img" aria-label="Scatter plot showing a positive correlation between how often an article appeared in subscriber paths and the number of new subscribers, March 2021 through May 2024. Axis values are anonymized." style="max-width: 720px; margin: 34px auto;">
  <div class="work-chart-card__chart">
    <svg viewBox="0 0 280 150" aria-hidden="true">
      <text x="4" y="75" transform="rotate(-90 4 75)" font-family="var(--fn-mono)" font-size="7" text-anchor="middle" fill="var(--fn-ink2)">subscriptions</text>
      <text x="140" y="146" font-family="var(--fn-mono)" font-size="7" text-anchor="middle" fill="var(--fn-ink2)">number of times an article was in a path</text>
      <line x1="8" x2="272" y1="130" y2="130" stroke="var(--fn-ruleSoft)" stroke-width="1"/>
      <line x1="8" x2="272" y1="108" y2="108" stroke="var(--fn-ruleSoft)" stroke-width="0.75" stroke-dasharray="2 4"/>
      <line x1="8" x2="272" y1="86"  y2="86"  stroke="var(--fn-ruleSoft)" stroke-width="0.75" stroke-dasharray="2 4"/>
      <line x1="8" x2="272" y1="63"  y2="63"  stroke="var(--fn-ruleSoft)" stroke-width="0.75" stroke-dasharray="2 4"/>
      <line x1="8" x2="272" y1="41"  y2="41"  stroke="var(--fn-ruleSoft)" stroke-width="0.75" stroke-dasharray="2 4"/>
      <line x1="8" x2="272" y1="19"  y2="19"  stroke="var(--fn-ruleSoft)" stroke-width="0.75" stroke-dasharray="2 4"/>
      <line x1="68"  x2="68"  y1="12" y2="130" stroke="var(--fn-ruleSoft)" stroke-width="0.75" stroke-dasharray="2 4"/>
      <line x1="128" x2="128" y1="12" y2="130" stroke="var(--fn-ruleSoft)" stroke-width="0.75" stroke-dasharray="2 4"/>
      <line x1="188" x2="188" y1="12" y2="130" stroke="var(--fn-ruleSoft)" stroke-width="0.75" stroke-dasharray="2 4"/>
      <line x1="248" x2="248" y1="12" y2="130" stroke="var(--fn-ruleSoft)" stroke-width="0.75" stroke-dasharray="2 4"/>
      <polygon points="8,93 272,19 272,49 8,123" fill="var(--fn-forest)" fill-opacity="0.08"/>
      <line x1="8" y1="108" x2="272" y2="34" stroke="var(--fn-forest)" stroke-width="1.5" stroke-opacity="0.7"/>
      <circle cx="11.6"  cy="127.8" r="2" fill="var(--fn-forest)" fill-opacity="0.6"/>
      <circle cx="17.6"  cy="118.9" r="2" fill="var(--fn-forest)" fill-opacity="0.6"/>
      <circle cx="20"    cy="118.2" r="2" fill="var(--fn-forest)" fill-opacity="0.6"/>
      <circle cx="23.6"  cy="115.3" r="2" fill="var(--fn-forest)" fill-opacity="0.6"/>
      <circle cx="26"    cy="106.4" r="2" fill="var(--fn-forest)" fill-opacity="0.6"/>
      <circle cx="29.4"  cy="102.7" r="2" fill="var(--fn-forest)" fill-opacity="0.6"/>
      <circle cx="30.6"  cy="99"    r="2" fill="var(--fn-forest)" fill-opacity="0.6"/>
      <circle cx="32"    cy="107.9" r="2" fill="var(--fn-forest)" fill-opacity="0.6"/>
      <circle cx="34.4"  cy="67.4"  r="2" fill="var(--fn-forest)" fill-opacity="0.6"/>
      <circle cx="38"    cy="100.5" r="2" fill="var(--fn-forest)" fill-opacity="0.6"/>
      <circle cx="40.4"  cy="97.5"  r="2" fill="var(--fn-forest)" fill-opacity="0.6"/>
      <circle cx="44"    cy="95.3"  r="2" fill="var(--fn-forest)" fill-opacity="0.6"/>
      <circle cx="68"    cy="104.2" r="2" fill="var(--fn-forest)" fill-opacity="0.6"/>
      <circle cx="77.7"  cy="98.2"  r="2" fill="var(--fn-forest)" fill-opacity="0.6"/>
      <circle cx="92"    cy="101.9" r="2" fill="var(--fn-forest)" fill-opacity="0.6"/>
      <circle cx="118.5" cy="13"    r="2" fill="var(--fn-forest)" fill-opacity="0.6"/>
      <circle cx="125.8" cy="78.6"  r="2" fill="var(--fn-forest)" fill-opacity="0.6"/>
      <circle cx="128"   cy="77.1"  r="2" fill="var(--fn-forest)" fill-opacity="0.6"/>
      <circle cx="130.2" cy="62.3"  r="2" fill="var(--fn-forest)" fill-opacity="0.6"/>
      <circle cx="133.6" cy="60.1"  r="2" fill="var(--fn-forest)" fill-opacity="0.6"/>
      <circle cx="137"   cy="59.4"  r="2" fill="var(--fn-forest)" fill-opacity="0.6"/>
      <circle cx="142.5" cy="104.2" r="2" fill="var(--fn-forest)" fill-opacity="0.6"/>
      <circle cx="146"   cy="100.5" r="2" fill="var(--fn-forest)" fill-opacity="0.6"/>
      <circle cx="149.5" cy="82.3"  r="2" fill="var(--fn-forest)" fill-opacity="0.6"/>
      <circle cx="152"   cy="79.3"  r="2" fill="var(--fn-forest)" fill-opacity="0.6"/>
      <circle cx="161.6" cy="78.6"  r="2" fill="var(--fn-forest)" fill-opacity="0.6"/>
      <circle cx="167.6" cy="82.3"  r="2" fill="var(--fn-forest)" fill-opacity="0.6"/>
      <circle cx="170"   cy="31.1"  r="2" fill="var(--fn-forest)" fill-opacity="0.6"/>
      <circle cx="176"   cy="79.3"  r="2" fill="var(--fn-forest)" fill-opacity="0.6"/>
      <circle cx="185.7" cy="82.3"  r="2" fill="var(--fn-forest)" fill-opacity="0.6"/>
      <circle cx="206.1" cy="79.3"  r="2" fill="var(--fn-forest)" fill-opacity="0.6"/>
      <circle cx="260"   cy="67.4"  r="2" fill="var(--fn-forest)" fill-opacity="0.6"/>
    </svg>
  </div>
  <div class="work-chart-card__footer">
    <span class="work-chart-card__caption">articles in a path vs. new subscribers · Mar 2021–May 2024</span>
    <span class="fn-status-pill fn-status-pill--stripped">◐ numbers stripped</span>
  </div>
</div>

## What to read next

The fuller version of this work — including the modeling approach, the lever taxonomy, and the dashboards the newsroom now uses — is in the [SRCCON 2025 deck](https://drive.google.com/file/d/1yH-A4iYyqsf3s5wE0K5YkwasNUvM76KC/view).

If you work at a newsroom and want to compare notes on subscription metrics, [reach out](mailto:kelsonjuliet@gmail.com).
