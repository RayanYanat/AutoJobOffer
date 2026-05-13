from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Job:
    """Represents a single job posting."""

    job_id: str  # Unique ID (from source or generated hash)
    title: str
    company: str
    location: str
    url: str
    posted_date: Optional[str] = None
    contract_type: Optional[str] = None  # CDI, CDD, Stage, Alternance...
    seniority: Optional[str] = None
    department: Optional[str] = None
    source: str = ""  # Which scraper found it

    @property
    def unique_key(self) -> str:
        """Unique identifier to avoid duplicates."""
        return f"{self.company}::{self.job_id}"

    def to_telegram_message(self) -> str:
        """Format job as a Telegram HTML message."""
        parts = [
            f"<b>{self.title}</b>",
            f"\U0001F3E2 {self.company}",
            f"\U0001F4CD {self.location}",
        ]
        if self.contract_type:
            parts.append(f"\U0001F4CB {self.contract_type}")
        if self.seniority:
            parts.append(f"\U0001F4CA {self.seniority}")
        if self.posted_date:
            parts.append(f"\U0001F4C5 {self.posted_date}")
        parts.append(f"\n\U0001F517 <a href=\"{self.url}\">Voir l'offre</a>")
        return "\n".join(parts)
