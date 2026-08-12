"""
Browser Interface

Every browser implementation (Playwright, Android, WebView, etc.)
must inherit from this class.

The AI engine should NEVER directly call Playwright APIs.
Instead, it only talks to Browser.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional


class Browser(ABC):

    @abstractmethod
    def start(self) -> None:
        """Start browser"""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Close browser"""
        pass

    @abstractmethod
    def open(self, url: str) -> None:
        """Navigate to URL"""
        pass

    @abstractmethod
    def click(self, selector: str) -> None:
        """Click element"""
        pass

    @abstractmethod
    def fill(self, selector: str, value: str) -> None:
        """Fill textbox"""
        pass

    @abstractmethod
    def press(self, selector: str, key: str) -> None:
        """Press keyboard key"""
        pass

    @abstractmethod
    def wait(self, selector: str, timeout: int = 30000) -> None:
        """Wait until selector appears"""
        pass

    @abstractmethod
    def exists(self, selector: str) -> bool:
        """Check if selector exists"""
        pass

    @abstractmethod
    def text(self, selector: str) -> str:
        """Read element text"""
        pass

    @abstractmethod
    def attribute(self, selector: str, name: str) -> Optional[str]:
        """Read HTML attribute"""
        pass

    @abstractmethod
    def evaluate(self, script: str, arg: Any = None):
        """Execute JavaScript"""
        pass

    @abstractmethod
    def screenshot(self, path: str) -> None:
        """Take screenshot"""
        pass

    @abstractmethod
    def save_session(self, path: str) -> None:
        """Save cookies/session"""
        pass

    @abstractmethod
    def load_session(self, path: str) -> None:
        """Load cookies/session"""
        pass