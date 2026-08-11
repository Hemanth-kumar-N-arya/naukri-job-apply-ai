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
DELETE_SELECTOR = '[data-title="delete-resume"]'
UPLOAD_SELECTOR = '#attachCV'
RESUME_NAME_SELECTOR = '.resume-name-inline'


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
    """Clicks the delete icon and handles a confirmation dialog if one appears.
    Naukri's confirm dialog markup hasn't been confirmed yet -- this tries a
    few common patterns (Yes/Delete/Confirm buttons). If deletion doesn't
    actually happen, send me a screenshot of what appears after the click
    and I'll make this exact instead of a guess."""
    locator = page.locator(DELETE_SELECTOR).first
    try:
        locator.click(timeout=8000)
    except PWTimeout:
        print("  Delete icon not found or not clickable -- resume may already be absent.")
        return False
    time.sleep(1.5)

    clicked_confirm = safe_evaluate(page, """
        () => {
            const texts = ['yes', 'delete', 'confirm', 'ok', 'remove'];
            const btns = Array.from(document.querySelectorAll('button, div[role="button"], a'));
            const btn = btns.find(b => {
                const t = (b.innerText || '').trim().toLowerCase();
                return texts.includes(t);
            });
            if (btn) { btn.click(); return true; }
            return false;
        }
    """, default=False)
    if clicked_confirm:
        print("  Confirmed deletion via dialog.")
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
