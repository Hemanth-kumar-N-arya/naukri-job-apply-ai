@echo off
REM Runs the resume refresh from the correct folder regardless of what
REM directory Windows Task Scheduler starts in by default.
cd /d "%~dp0"
python naukri_refresh_resume.py >> refresh_log.txt 2>&1
