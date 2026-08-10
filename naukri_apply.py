"""
Naukri auto-apply. Requires session_naukri.json from login_capture.py.

Usage:
    python naukri_apply.py

Stops immediately and reports if it hits a CAPTCHA, a login prompt, or a
rate-limit warning. Never attempts to solve any of those — that's the point.
"""
import csv
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

from common.profile import Profile
from common import llm

SESSION_FILE = "session_naukri.json"
LOG_FILE = "applications_log.csv"

STOP_PHRASES = [
    "too many requests", "unusual activity", "verify you are human",
    "captcha", "temporarily blocked", "please try again later and reduce",
]


def log_row(row: list):
    new_file = not Path(LOG_FILE).exists()
    with open(LOG_FILE, "a", newline="") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(["timestamp", "source", "title", "company", "status", "reason"])
        w.writerow(row)


def passes_filters(card: dict, profile: Profile, role: str) -> tuple[bool, str]:
    title = (card.get("title") or "").lower()
    company = (card.get("company") or "").lower()

    required_keywords = profile.data.get("role_required_keywords", {}).get(role)
    if not required_keywords:
        # sensible default: every significant word in the searched role, minus
        # generic terms that would match almost anything
        generic = {"engineer", "developer", "administrator", "analyst", "senior", "junior", "lead"}
        required_keywords = [w for w in role.lower().split() if w not in generic]
    if required_keywords and not any(kw.lower() in title for kw in required_keywords):
        return False, f"title doesn't match role keywords ({role})"

    for excl in profile.company_exclude:
        if excl.lower() in company:
            return False, f"company excluded ({excl})"

    if profile.company_include_only:
        if not any(inc.lower() in company for inc in profile.company_include_only):
            return False, "not in include-only list"

    # crude experience-range check from the card text, e.g. "2-5 Yrs"
    exp_text = card.get("exp") or ""
    digits = [int(s) for s in exp_text.replace("Yrs", "").replace("yrs", "")
              .replace("-", " ").split() if s.isdigit()]
    if len(digits) >= 2:
        lo, hi = digits[0], digits[-1]
        if hi < profile.seniority_floor_years or lo > profile.seniority_ceiling_years:
            return False, f"experience range mismatch ({exp_text})"

    return True, ""


def enumerate_cards(page):
    """Reads real job cards off the search results page.

    Naukri's card wrapper is div.srp-jobtuple-wrapper with a data-job-id
    attribute — that attribute is the reliable marker; filter/promo widgets
    on the same page don't have it, so filtering on [data-job-id] avoids
    picking up non-job elements.
    """
    return page.evaluate("""
        () => Array.from(document.querySelectorAll('.srp-jobtuple-wrapper[data-job-id]'))
          .map((c, i) => ({
            i,
            jobId: c.getAttribute('data-job-id'),
            title: c.querySelector('a.title')?.innerText.trim(),
            href: c.querySelector('a.title')?.href,
            company: c.querySelector('a.comp-name, .comp-dtls-wrap a')?.innerText.trim(),
            exp: c.querySelector('.expwdth')?.innerText,
            location: c.querySelector('.locWdth')?.innerText,
          }))
          .filter(c => c.title && c.href)
    """)


def check_apply_button(page) -> str:
    """Returns 'external', 'native', or 'none' based on the detail page's apply button.

    Both buttons use stable, non-hashed identifiers confirmed from real pages:
    external listings show id="company-site-button" ("Apply on company site"),
    native listings show id="apply-button" ("Apply"). Matching on these ids
    rather than Naukri's CSS-module hashed classes, since the hashed part
    changes per build but these ids don't.
    """
    if page.query_selector('#company-site-button'):
        return "external"
    if page.query_selector('#apply-button'):
        return "native"
    return "none"


def _js_click_send(page) -> bool:
    """Clicks Naukri's screening-chat Send/Save control. It's a <div class="sendMsg">,
    not a <button> — confirmed from real markup, where the send-message element is
    always a div with that class, not a button. A JS click also bypasses the
    chatbot_Overlay div that sits visually on top of it and blocks Playwright's
    normal actionability-checked .click()."""
    return page.evaluate(
        """() => {
            const el = document.querySelector('.sendMsg');
            if (!el) return false;
            el.click();
            return true;
        }"""
    )


def click_native_apply(page):
    page.evaluate(
        """() => {
            const btn = document.getElementById('apply-button');
            if (btn) btn.click();
        }"""
    )


def page_has_stop_signal(page) -> str | None:
    text = page.inner_text("body").lower()
    for phrase in STOP_PHRASES:
        if phrase in text:
            return phrase
    if "login" in page.url and "naukri.com/nlogin" in page.url:
        return "session expired / login prompt"
    return None


class StopRun(Exception):
    """Something genuinely dangerous or account-risking happened — CAPTCHA,
    login expired, rate-limit warning. Halts the entire run immediately."""


class SkipJob(Exception):
    """This one listing can't be completed automatically — a screening
    question the profile doesn't cover, or an options question needing a
    human choice. Logs it and moves on to the next listing; does NOT stop
    the run."""


def answer_screening_chat(page, profile: Profile, job_context: str, applied_count: list):
    """Handles Naukri's post-apply screening chat drawer, if it appears."""
    answers = profile.answer_library()
    try:
        page.wait_for_selector('[contenteditable="true"], [contenteditable=""]', timeout=4000)
    except PWTimeout:
        return  # no screening chat for this listing

    for _ in range(15):  # hard cap on questions per listing so a stuck loop can't run forever
        stop = page_has_stop_signal(page)
        if stop:
            raise StopRun(f"stop signal during screening chat: {stop}")

        bubbles = page.query_selector_all('.botMsg')
        if not bubbles:
            break
        question = bubbles[-1].inner_text().strip()
        if not question:
            break

        lower_q = question.lower()
        answered = False
        for key, val in answers.items():
            if key.replace("_", " ") in lower_q or key.split("_")[0] in lower_q:
                _fill_freetext(page, val)
                answered = True
                break

        if not answered:
            # radio/checkbox options question, or genuinely open-ended
            options = page.query_selector_all('input[type=radio], input[type=checkbox]')
            if options:
                # leave radio selection to a human-reviewed default: skip and flag
                raise SkipJob(f"unhandled options question, needs review: {question[:120]}")
            draft = llm.draft_answer(question, profile.data, job_context)
            if draft.startswith("[NEEDS_HUMAN_INPUT"):
                raise SkipJob(f"profile gap: {draft}")
            _fill_freetext(page, draft)

        _js_click_send(page)
        time.sleep(1.5)


def _fill_freetext(page, text: str):
    page.evaluate(
        """(text) => {
            const ed = document.querySelector('[id^="userInput"], [contenteditable="true"]');
            if (!ed) return;
            ed.focus();
            document.execCommand('insertText', false, text);
        }""",
        text,
    )


def run():
    profile = Profile.load()
    if not Path(SESSION_FILE).exists():
        raise SystemExit(f"{SESSION_FILE} not found. Run: python login_capture.py naukri")

    applied = 0
    with sync_playwright() as p:
        browser_mode = profile.data.get("browser_mode", "visible")
        if browser_mode == "headless":
            browser = p.chromium.launch(headless=True, slow_mo=150)
        elif browser_mode == "minimized":
            browser = p.chromium.launch(headless=False, slow_mo=150, args=["--start-minimized"])
        else:
            browser = p.chromium.launch(headless=False, slow_mo=150)
        context = browser.new_context(storage_state=SESSION_FILE)
        page = context.new_page()

        for role in profile.target_roles:
            if applied >= profile.stop_after_n_applications:
                break
            slug = role.lower().replace(" ", "-")
            exp_param = int(profile.total_experience_years)  # Naukri's experience filter takes a whole number
            url = (
                f"https://www.naukri.com/{slug}-jobs"
                f"?experience={exp_param}"
                f"&jobAge={profile.job_freshness_days}"
            )
            print(f"\n--- Searching: {role} ({url}) ---")
            page.goto(url)
            try:
                page.wait_for_selector('.srp-jobtuple-wrapper[data-job-id]', timeout=10000)
            except PWTimeout:
                pass  # either genuinely no results, or a stop signal — checked next
            time.sleep(1)

            stop = page_has_stop_signal(page)
            if stop:
                print(f"STOPPING: {stop}")
                log_row([datetime.now(), "naukri", "-", "-", "stopped", stop])
                break

            cards = enumerate_cards(page)
            print(f"Found {len(cards)} job cards for this search.")
            for card in cards:
                if applied >= profile.stop_after_n_applications:
                    break

                ok, reason = passes_filters(card, profile, role)
                if not ok:
                    log_row([datetime.now(), "naukri", card.get("title"),
                              card.get("company"), "skipped", reason])
                    print(f"Skipped: {card.get('title')} @ {card.get('company')} — {reason}")
                    continue

                try:
                    page.goto(card["href"])
                    time.sleep(2)

                    stop = page_has_stop_signal(page)
                    if stop:
                        raise StopRun(f"stop signal: {stop}")

                    apply_state = check_apply_button(page)
                    if apply_state == "external":
                        log_row([datetime.now(), "naukri", card.get("title"),
                                  card.get("company"), "skipped", "external apply"])
                        print(f"Skipped: {card.get('title')} @ {card.get('company')} — external apply")
                        continue
                    if apply_state == "none":
                        log_row([datetime.now(), "naukri", card.get("title"),
                                  card.get("company"), "skipped", "no apply button found"])
                        print(f"Skipped: {card.get('title')} @ {card.get('company')} — no apply button found")
                        continue

                    click_native_apply(page)
                    time.sleep(2)

                    answer_screening_chat(page, profile, f"{card.get('title')} at {card.get('company')}", [applied])

                    applied += 1
                    log_row([datetime.now(), "naukri", card.get("title"),
                              card.get("company"), "applied", ""])
                    print(f"Applied: {card.get('title')} @ {card.get('company')} ({applied} total)")

                except SkipJob as e:
                    log_row([datetime.now(), "naukri", card.get("title"),
                              card.get("company"), "skipped", str(e)])
                    print(f"Skipped: {card.get('title')} @ {card.get('company')} — {e}")
                    continue

                except StopRun as e:
                    print(f"STOPPING: {e}")
                    log_row([datetime.now(), "naukri", card.get("title"),
                              card.get("company"), "stopped", str(e)])
                    browser.close()
                    return

                time.sleep(profile.pace_seconds_between_actions)
                try:
                    page.goto(url)  # back to the search results before the next card
                    time.sleep(1.5)
                except Exception:
                    pass  # non-fatal — the next loop iteration will re-navigate anyway

        browser.close()

    print(f"\nDone. {applied} applications submitted this run. See {LOG_FILE} for the full log.")


if __name__ == "__main__":
    run()
