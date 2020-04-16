---
layout: page
title: COVID Diaries
permalink: /covid/
---

*This is a series of posts [From Quarantine](https://julietkelson.github.io/covid/).  Most posts from quarantine are prompted by Aisling Quigley's Data Storytelling class at Macalester College.*

<div id="archives">
  <div class="archive-group">
    {% capture category_name %}{{ category | first }}{% endcapture %}
    {% for post in site.categories['From Quarantine'] %}
    <article class="archive-item">
      <!-- <h4><a href="{{ site.baseurl }}{{ post.url }}">{{post.title}}</a></h4> -->
      {% include post_block.html %}
    </article>
    {% endfor %}
  </div>
</div>