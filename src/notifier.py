import time
import logging
import requests
from typing import List
from .models import Job

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Send job alerts via Telegram Bot API to multiple recipients."""

    API_BASE = "https://api.telegram.org/bot{token}"
    MAX_MESSAGE_LENGTH = 4096

    def __init__(self, token: str, chat_ids: str):
        """
        Args:
            token: Telegram bot token
            chat_ids: Comma-separated chat IDs (e.g. "123456,789012")
        """
        self.token = token
        self.chat_ids = [cid.strip() for cid in chat_ids.split(",") if cid.strip()]
        self.base_url = self.API_BASE.format(token=token)

    def _send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Send a message to ALL registered chat IDs."""
        success = True
        for chat_id in self.chat_ids:
            try:
                resp = requests.post(
                    f"{self.base_url}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": text,
                        "parse_mode": parse_mode,
                        "disable_web_page_preview": True,
                    },
                    timeout=15,
                )
                if resp.status_code == 429:
                    retry_after = resp.json().get("parameters", {}).get("retry_after", 5)
                    logger.warning(f"Rate limited for {chat_id}, waiting {retry_after}s")
                    time.sleep(retry_after)
                    self._send_to_one(chat_id, text, parse_mode)
                elif resp.status_code != 200:
                    logger.error(f"Telegram send to {chat_id} failed: HTTP {resp.status_code}")
                    success = False
            except Exception as e:
                logger.error(f"Telegram send to {chat_id} failed: {e}")
                success = False
            time.sleep(0.3)  # Small delay between recipients
        return success

    def _send_to_one(self, chat_id: str, text: str, parse_mode: str = "HTML") -> bool:
        """Send a message to a single chat ID (used for retries)."""
        try:
            resp = requests.post(
                f"{self.base_url}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                    "disable_web_page_preview": True,
                },
                timeout=15,
            )
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Telegram retry to {chat_id} failed: {e}")
            return False

    def send_new_jobs(self, jobs: List[Job]):
        """Send notifications for new job postings."""
        if not jobs:
            return

        # Group jobs by company for cleaner notifications
        by_company: dict[str, list[Job]] = {}
        for job in jobs:
            by_company.setdefault(job.company, []).append(job)

        for company, company_jobs in by_company.items():
            header = f"\U0001F514 <b>{len(company_jobs)} nouvelle(s) offre(s) — {company}</b>\n"
            header += "━" * 30 + "\n\n"

            # Send in batches to respect message size limits
            current_message = header
            for job in company_jobs:
                job_text = job.to_telegram_message() + "\n\n"

                if len(current_message) + len(job_text) > self.MAX_MESSAGE_LENGTH:
                    self._send_message(current_message)
                    current_message = header
                    time.sleep(0.5)

                current_message += job_text

            if current_message != header:
                self._send_message(current_message)
                time.sleep(0.5)

    def send_summary(self, total_checked: int, total_new: int, errors: List[str]):
        """Send a daily summary."""
        text = f"\U0001F4CA <b>Résumé du scan</b>\n\n"
        text += f"Sources vérifiées : {total_checked}\n"
        text += f"Nouvelles offres : {total_new}\n"
        if errors:
            text += f"\n⚠️ Erreurs ({len(errors)}):\n"
            for err in errors[:5]:
                text += f"  • {err}\n"
        self._send_message(text)

    def test_connection(self) -> bool:
        """Test if the bot can send messages to all recipients."""
        return self._send_message(
            f"✅ Bot connecté ! Alertes actives pour {len(self.chat_ids)} destinataire(s)."
        )
