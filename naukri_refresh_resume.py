"""
Removes and re-uploads your Naukri resume, to keep your profile showing as
recently active. Requires session_naukri.json from login_capture.py.

Usage:
    python naukri_refresh_resume.py

Designed to be run by Windows Task Scheduler at fixed times, not left
running continuously -- see README for the schtasks setup.
"""
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

from common.profile import Profile

SESSION_FILE = "session_naukri.json"
PROFILE_URL = "https://www.naukri.com/mnjuser/profile"

# Confirmed real markup (from your Naukri profile page):
#   Delete icon:  <span data-title="delete-resume">...</span>
#   Upload input: <input type="file" id="attachCV">
# Scoped to .attachCV specifically -- that's the real container wrapping the
# whole resume block (confirmed from your page's markup). Scoping the delete
# click to inside this container, rather than a bare page-wide data-title
# match, is what prevents it from ever being able to touch the profile
# photo section or anything else on the page, even if Naukri happens to
# reuse similar icon markup elsewhere.
DELETE_SELECTOR = '.attachCV [data-title="delete-resume"]'
UPLOAD_SELECTOR = '.attachCV #attachCV'
RESUME_NAME_SELECTOR = '.attachCV .resume-name-inline'


def safe_evaluate(page, script, arg=None, default=None):
    try:
        return page.evaluate(script, arg) if arg is not None else page.evaluate(script)
    except Exception as e:
        print(f"  (page.evaluate failed, continuing anyway: {e})")
        return default


def get_current_resume_name(page) -> str | None:
    el = page.query_selector(RESUME_NAME_SELECTOR)
    if not el:
        return None
    try:
        return el.inner_text().strip()
    except Exception:
        return None


def delete_resume(page) -> bool:
    """Clicks the delete icon and confirms via the resume-specific dialog.

    Confirmed real markup: the confirmation box has class
    "confirmationBox profileSummaryConfirmation" with a Delete button
    (class "btn-dark-ot") inside it. Scoping the click to specifically
    that box -- rather than searching the whole page for any button whose
    text says "Delete" -- is what fixes it from also triggering the
    profile-photo delete button, which apparently sits in the page's DOM
    too and could get matched by a page-wide text search."""
    locator = page.locator(DELETE_SELECTOR).first
    try:
        locator.click(timeout=8000)
    except PWTimeout:
        print("  Delete icon not found or not clickable -- resume may already be absent.")
        return False
    time.sleep(1.5)

    clicked_confirm = safe_evaluate(page, """
        () => {
            const box = document.querySelector('.confirmationBox.profileSummaryConfirmation');
            if (!box) return false;
            const btn = box.querySelector('button.btn-dark-ot');
            if (!btn) return false;
            btn.click();
            return true;
        }
    """, default=False)
    if clicked_confirm:
        print("  Confirmed deletion via the resume dialog.")
    else:
        print("  No resume confirmation dialog appeared (may have deleted directly, or nothing to delete).")
    time.sleep(2)
    return True


def upload_resume(page, resume_path: Path) -> bool:
    try:
        page.set_input_files(UPLOAD_SELECTOR, str(resume_path))
    except PWTimeout:
        print("  Upload input not found within timeout.")
        return False
    time.sleep(4)  # give Naukri's parser a moment to process the file
    return True


def run():
    profile = Profile.load()
    if not Path(SESSION_FILE).exists():
        raise SystemExit(f"{SESSION_FILE} not found. Run: python login_capture.py naukri")

    resume_filename = profile.data.get("resume_file_name")
    if not resume_filename:
        raise SystemExit("resume_file_name is not set in profile.yaml.")

    resume_path = Path(resume_filename)
    if not resume_path.is_absolute():
        resume_path = Path(__file__).resolve().parent / resume_filename
    if not resume_path.exists():
        raise SystemExit(
            f"Resume file not found at {resume_path}. "
            f"Put your resume in this project folder with the exact filename "
            f"set in profile.yaml's resume_file_name."
        )

    with sync_playwright() as p:
        browser_mode = profile.data.get("browser_mode", "minimized")
        if browser_mode == "headless":
            browser = p.chromium.launch(headless=True)
        elif browser_mode == "minimized":
            browser = p.chromium.launch(headless=False, args=["--start-minimized"])
        else:
            browser = p.chromium.launch(headless=False)

        context = browser.new_context(storage_state=SESSION_FILE)
        page = context.new_page()
        page.goto(PROFILE_URL)

        try:
            page.wait_for_selector(RESUME_NAME_SELECTOR, timeout=15000)
        except PWTimeout:
            print("Couldn't find the resume section on the profile page — "
                  "check that session_naukri.json is still valid (session may have "
                  "expired; re-run login_capture.py naukri if so).")
            browser.close()
            sys.exit(1)

        before_name = get_current_resume_name(page)
        print(f"Current resume on file: {before_name}")

        if not delete_resume(page):
            print("Could not delete the existing resume — stopping without uploading, "
                  "to avoid ending up with two resumes on the profile.")
            browser.close()
            sys.exit(1)

        if not upload_resume(page, resume_path):
            print("Upload failed after deletion — your profile may currently have "
                  "NO resume attached. Check it manually as soon as possible.")
            browser.close()
            sys.exit(1)

        page.reload()
        try:
            page.wait_for_selector(RESUME_NAME_SELECTOR, timeout=15000)
            after_name = get_current_resume_name(page)
            print(f"Resume after refresh: {after_name}")
            if after_name:
                print("Refresh complete.")
            else:
                print("WARNING: no resume name detected after upload — check manually.")
        except PWTimeout:
            print("WARNING: couldn't confirm the resume re-appeared after upload — check manually.")

        browser.close()


if __name__ == "__main__":
    run()
