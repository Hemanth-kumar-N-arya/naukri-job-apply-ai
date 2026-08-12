from playwright.sync_api import sync_playwright

from browser.browser import Browser


class PlaywrightBrowser(Browser):

    def __init__(self):

        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None