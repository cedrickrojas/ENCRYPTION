from __future__ import annotations

from datetime import datetime


class ActivityLog:
    """In-memory safe metadata log; secrets and content never enter it."""

    def __init__(self) -> None:
        self.entries: list[dict[str, str]] = []

    def add(self, operation: str, item: str, success: bool) -> None:
        self.entries.insert(0, {"operation": operation, "item": item, "status": "Success" if success else "Failed", "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
        del self.entries[30:]
