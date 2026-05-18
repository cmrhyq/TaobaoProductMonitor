"""
Email sending service using SMTP.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from pathlib import Path

import structlog

from domain.entity.email import EmailSender

logger = structlog.get_logger(__name__)


class EmailService:
    def __init__(self, email_info: EmailSender):
        self.email_info = email_info

    def send(self) -> bool:
        """
        Send an email based on the configured EmailSender info.

        Returns:
            True if sent successfully, False otherwise.
        """
        stp = smtplib.SMTP()
        mm = MIMEMultipart("related")
        try:
            mm["From"] = self._format_address(self.email_info.email_sender)
            mm["To"] = self._format_address(self.email_info.email_receivers)
            mm["Subject"] = Header(self.email_info.email_theme, "utf-8")

            body = MIMEText(self.email_info.email_content, "html", "utf-8")
            mm.attach(body)

            if self.email_info.attachments:
                self._attach_files(mm, self.email_info.attachments)

            stp.connect(self.email_info.email_host, 25)
            stp.login(self.email_info.email_sender, self.email_info.email_license)
            stp.sendmail(
                self.email_info.email_sender,
                self.email_info.email_receivers,
                mm.as_string(),
            )
            logger.info(
                "Email sent",
                receiver=self.email_info.email_receivers,
                theme=self.email_info.email_theme,
            )
            return True
        except Exception as exc:
            logger.error("Email send failed", error=str(exc))
            return False
        finally:
            stp.quit()

    @staticmethod
    def _format_address(email_str: str) -> str:
        """Format email address(es) for MIME header."""
        if "," in email_str:
            parts = [f"{addr.split('@')[0]}<{addr}>" for addr in email_str.split(",") if addr.strip()]
            return ",".join(parts)
        return f"{email_str.split('@')[0]}<{email_str}>"

    @staticmethod
    def _attach_files(mm: MIMEMultipart, file_paths: str) -> None:
        """Attach file(s) to the email. Paths separated by commas."""
        for file_path in file_paths.split(","):
            file_path = file_path.strip()
            path = Path(file_path)
            if not path.exists():
                logger.warning("Attachment not found", path=file_path)
                continue
            attach = MIMEText(path.read_bytes(), "base64", "utf-8")
            attach["Content-Disposition"] = f'attachment; filename="{path.name}"'
            mm.attach(attach)
