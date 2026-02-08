---
layout: page
permalink: /repositories/
title: Repositories
nav: true
nav_order: 4
---

{% assign primary_user = site.data.repositories.github_users | first %}
{% if primary_user %}

## GitHub profile

<div class="repositories d-flex flex-wrap flex-md-row flex-column justify-content-center align-items-center">
  {% include repository/repo_user.liquid username=primary_user %}
</div>

---

{% endif %}

{% assign repo_cards = site.data.repositories.github_repos_metadata %}
{% if repo_cards == nil or repo_cards == empty %}
  {% assign repo_cards = site.data.repositories.github_repos %}
{% endif %}

{% if repo_cards %}

## GitHub Repositories

<div class="repositories d-flex flex-wrap flex-md-row flex-column justify-content-between align-items-center">
  {% for repo in repo_cards %}
    {% include repository/repo.liquid repository=repo %}
  {% endfor %}
</div>
{% endif %}
