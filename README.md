# DIY Job Auto-Apply (Naukri + LinkedIn)

A free alternative to Claude in Chrome's `apply-to-jobs` skill: a Playwright script
you run on your own machine, against your own accounts.

## Before you run this — read this once

Automating applications goes against Naukri's and LinkedIn's terms of service.
Both platforms can detect bot-like activity and have suspended accounts for it.
This script tries to reduce that risk (human login, realistic pacing, instant
stop on any CAPTCHA or rate-limit warning) but it cannot eliminate it. You're
running this against your own account, at your own discretion. If your job
search depends on that account staying in good standing, weigh that before
running a large batch unattended.

The other rule, non-negotiable regardless of the above: **the script never
sees or stores your password.** You log in by hand in a real browser window;
the script only reuses the resulting session.

## Setup

```bash
cd auto-apply
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

Get a free Gemini API key at https://aistudio.google.com/apikey (check current
free-tier limits there — they change) and set it:

```bash
export GEMINI_API_KEY="YOUR KEY HERE"   # Windows: set GEMINI_API_KEY=your-key-here
```

## Fill in your profile

Open `profile.yaml` and replace every placeholder with your real numbers —
notice period, CTC, target roles, work history. This file is the only source
of truth for every answer the script gives; nothing is invented beyond it.

## Capture a login session (once per site)

```bash
python login_capture.py naukri
python login_capture.py linkedin
```

A browser window opens. Log in by hand — password, 2FA, any CAPTCHA. Once
you're on the logged-in homepage, go back to the terminal and press Enter.
This creates `session_naukri.json` / `session_linkedin.json`. Re-run this
whenever a session expires (the apply scripts will tell you when that happens).

## Run it

```bash
python naukri_apply.py
python linkedin_apply.py
```

Start with `stop_after_n_applications: 5` in `profile.yaml` for the first run
on each site, and watch the browser window while it works, before trusting it
to run a longer batch unattended.

## What it does and doesn't handle

**Handles:** searching your target roles, filtering by company exclusions and
experience range, filling recurring fields (experience, notice period, CTC,
location, shift preference) from your profile, drafting open-text answers
with Gemini strictly from your profile, logging every outcome to
`applications_log.csv`.

**Stops and reports, rather than guessing, on:** CAPTCHAs, login prompts,
rate-limit warnings, radio/checkbox screening questions it can't map to your
profile automatically, and any screening question the profile genuinely
doesn't cover. These get logged as `stopped` or `skipped` with a reason — check
`applications_log.csv` after each run and either adjust `profile.yaml` or
handle that listing yourself.

**Doesn't handle:** LinkedIn multi-select checkboxes on the review page, resume
selection when multiple resumes are uploaded (it uses whatever's pre-selected),
or any site redesign that changes the CSS selectors above — both sites change
their markup periodically, and the selectors here will need updating when they do.

## Files

- `profile.yaml` — your facts, edit this first
- `login_capture.py` — one-time manual login per site
- `naukri_apply.py` — Naukri search + apply loop
- `linkedin_apply.py` — LinkedIn Easy Apply loop
- `common/profile.py` — loads and validates profile.yaml
- `common/gemini.py` — free-text answer drafting via free-tier Gemini
- `applications_log.csv` — created on first run, cumulative log of every outcome
