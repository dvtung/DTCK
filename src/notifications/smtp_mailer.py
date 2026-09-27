"""SMTP Email Dispatcher supporting standard SSL, TLS, and Gmail App Passwords."""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

logger = logging.getLogger("dtck.notifications.mailer")


class SmtpMailer:
    """Delivers HTML email notifications using standard Python smtplib."""

    def __init__(
        self,
        *,
        smtp_server: str = "smtp.gmail.com",
        smtp_port: int = 587,
        sender_email: str,
        sender_password: str,
        sender_name: str = "DTCK Market Intel",
        use_tls: bool = True,
        use_ssl: bool = False,
        timeout: float = 20.0,
    ) -> None:
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.sender_email = sender_email
        self.sender_password = sender_password
        self.sender_name = sender_name
        self.use_tls = use_tls
        self.use_ssl = use_ssl
        self.timeout = timeout

    def send_email(
        self,
        *,
        to_email: str,
        subject: str,
        html_content: str,
    ) -> dict[str, Any]:
        """Send a single email message. Returns status dict."""
        if not self.sender_email or not self.sender_password:
            return {
                "success": False,
                "error": (
                    "Cấu hình tài khoản gửi Gmail (sender_email/sender_password) "
                    "chưa được thiết lập"
                ),
            }

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{self.sender_name} <{self.sender_email}>"
        msg["To"] = to_email

        # Attach HTML part
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        try:
            if self.use_ssl or self.smtp_port == 465:
                with smtplib.SMTP_SSL(
                    self.smtp_server, self.smtp_port, timeout=self.timeout
                ) as server:
                    server.login(self.sender_email, self.sender_password)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=self.timeout) as server:
                    if self.use_tls:
                        server.starttls()
                    server.login(self.sender_email, self.sender_password)
                    server.send_message(msg)

            logger.info("Email successfully sent to %s (subject: %s)", to_email, subject)
            return {"success": True, "recipient": to_email}
        except smtplib.SMTPAuthenticationError as exc:
            err = (
                "Lỗi xác thực SMTP: Vui lòng kiểm tra lại Email và Mật khẩu ứng dụng "
                f"(App Password) của Gmail. Chi tiết: {exc}"
            )
            logger.error(err)
            return {"success": False, "error": err}
        except Exception as exc:
            err = f"Lỗi gửi email: {type(exc).__name__}: {exc}"
            logger.exception(err)
            return {"success": False, "error": err}
