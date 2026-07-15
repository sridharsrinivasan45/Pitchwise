# Here are your Instructions
# PitchWise 🏏

> **Cricket, Explained.**

PitchWise is an explainable cricket analytics platform inspired by products like **FotMob** and **SofaScore**.

Instead of only displaying scorecards and statistics, PitchWise helps answer the question:

> **Why did this match unfold the way it did?**

The platform transforms ball-by-ball IPL data into explainable match narratives using contextual analytics, win probability models and player impact ratings.

---

# Live Demo

🔗 Live Application:
https://ball-genius.emergent.host/?utm_source=share
---

# The Problem

Modern cricket platforms are excellent at showing **what happened**.

They are much less effective at explaining **why it happened**.

A scorecard can tell you that a player scored 65 runs.

It cannot tell you whether those runs actually increased the team's chances of winning.

PitchWise attempts to bridge that gap.

---

# Key Features

### 📈 Match Autopsy

Instead of showing only a scoreboard, every match is translated into an explainable story.

Each match includes:

- Match Verdict
- Turning Point
- Momentum Timeline
- Contextual Player Ratings

---

### ⚡ Win Probability Engine

Every ball updates the estimated probability of each team winning.

This allows the application to identify:

- Turning points
- Momentum shifts
- High-pressure overs
- Match-defining moments

---

### 👤 Contextual Player Ratings

Players are rated using contextual impact rather than traditional averages.

The rating engine considers:

- Match situation
- Pressure
- Phase of innings
- Win Probability Added (WPA)
- Batting and bowling contribution

Career ratings use the engine's aggregation methodology instead of averaging bounded match ratings.

---

### 📖 Explainable AI Narrator

Every match includes an evidence-grounded explanation layer.

The narrator:

- never invents facts
- only explains engine-computed evidence
- verifies every numerical statement before display
- falls back to deterministic templates if verification fails

---

### ⏳ Time Machine

Browse IPL history from 2008 onwards.

Features include:

- search
- filtering
- sorting
- historical navigation
- contextual match summaries

---

### 🧑 Player Explorer

Explore every IPL player's career.

Includes:

- career impact rating
- batting and bowling records
- contextual performance
- explainable rating breakdowns

---

# Technology Stack

Frontend

- React
- TailwindCSS

Backend

- FastAPI
- Python

Database

- MongoDB

Analytics

- Custom Python analytics engine

---

# Architecture

```
React Frontend
        │
        ▼
FastAPI Backend
        │
        ▼
MongoDB
        │
        ▼
Analytics Engine
        │
        ▼
Evidence Builder
        │
        ▼
Narration & Explainability Layer
```

---

# Engineering Highlights

- Explainable player rating system
- Ball-by-ball Win Probability model
- Explainable AI narration
- Historical IPL archive
- Dynamic momentum engine
- Context-aware player rankings
- Modular analytics architecture
- FastAPI REST API
- Responsive React frontend

---

# Design Philosophy

PitchWise is designed as a **post-match analysis platform**, not another live score application.

The goal is to help fans understand:

- when a match changed
- why it changed
- which players actually influenced the result

Every feature is built around one principle:

> **Cricket, Explained.**

---

# Roadmap

- Ask PitchWise (grounded natural language analyst)
- Historical match similarity engine
- Shareable match "Receipt Cards"
- Player evolution tracking
- Improved visual storytelling
- Additional international cricket support

---


# Project Status

Current Version: **v1.0**

✅ Historical IPL archive

✅ Win Probability engine

✅ Explainable player ratings

✅ Match narration

✅ Responsive UI

🚧 Ask PitchWise

🚧 Historical similarity engine

---

# Author

**S. Sridhar**

PGDM Candidate | Great Lakes Institute of Management

Interested in:

- Sports Analytics
- Product Management
- Data Analytics
- AI Applications in Sport

LinkedIn:
https://www.linkedin.com/in/sridhar1207/
---

If you found this project interesting, feel free to connect or leave feedback.