"""Gmail reporting: JSON-only email via the Gmail API (PRD_gmail_reporting).

The real Google client is imported lazily and only used when no ``sender`` is
injected, so tests (and the heuristic MVP) never need credentials or the
``gmail`` extra. The email body is the serialized JSON report and nothing else.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from cop_thief.shared.gatekeeper import ApiGatekeeper


class GmailReporter:
    """Sends one JSON-only report email through the API Gatekeeper."""

    def __init__(
        self,
        recipient: str,
        gatekeeper: ApiGatekeeper,
        *,
        credentials_file: str = "credentials.json",
        token_file: str = "token.json",
        scopes: list[str] | None = None,
        sender: Callable[[str, str], str] | None = None,
    ) -> None:
        self.recipient = recipient
        self._gatekeeper = gatekeeper
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.scopes = scopes or ["https://www.googleapis.com/auth/gmail.send"]
        self._sender = sender

    def send(self, report: dict[str, Any]) -> str:
        """Send ``report`` as a JSON-only email body; return the message id."""
        body = json.dumps(report)  # JSON ONLY — no extra text
        send_fn = self._sender or self._real_send
        return self._gatekeeper.execute(send_fn, self.recipient, body)

    def _real_send(self, to: str, body: str) -> str:  # pragma: no cover - needs OAuth
        """Send via the Gmail API (requires the ``gmail`` extra + OAuth files)."""
        import base64
        from email.message import EmailMessage

        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        creds = None
        from pathlib import Path

        if Path(self.token_file).exists():
            creds = Credentials.from_authorized_user_file(self.token_file, self.scopes)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, self.scopes
                )
                creds = flow.run_local_server(port=0)
            Path(self.token_file).write_text(creds.to_json(), encoding="utf-8")

        message = EmailMessage()
        message["To"] = to
        message["Subject"] = "Cop & Thief match report"
        message.set_content(body)  # body is the JSON report only
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        service = build("gmail", "v1", credentials=creds)
        sent = service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return sent["id"]
