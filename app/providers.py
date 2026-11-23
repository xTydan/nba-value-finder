from dataclasses import dataclass
from datetime import datetime, timezone

@dataclass
class FeedStatus:
    provider: str
    available: bool
    checked_at: str
    message: str

class UnconfiguredProvider:
    def __init__(self, name: str, purpose: str):
        self.name, self.purpose = name, purpose
    def status(self):
        return FeedStatus(self.name, False, datetime.now(timezone.utc).isoformat(),
            f"{self.purpose} feed is not configured. No data will be fabricated.")
