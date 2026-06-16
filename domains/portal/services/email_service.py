import asyncio
import logging
import smtplib
from email.message import EmailMessage
from config import get_settings

logger = logging.getLogger("devcore-portal")


class EmailService:
    def __init__(self):
        s = get_settings()
        self.host = s.smtp_host
        self.port = s.smtp_port
        self.user = s.smtp_user
        self.password = s.smtp_password

    def _send(self, to_email: str, link: str) -> bool:
        if not self.user or not self.password:
            logger.warning("SMTP not configured. Magic link email not sent.")
            return False

        message = EmailMessage()
        message["Subject"] = "Verify your DevCore account"
        message["From"] = self.user
        message["To"] = to_email
        message.set_content(
            f"Tap the link below on your phone to verify your account and open DevCore.\n\n{link}\n\n"
            f"This expires in 15 minutes. If you didn't request this, you can ignore this email."
        )
        message.add_alternative(
            f"""\
<html>
  <body style="font-family: -apple-system, Helvetica, Arial, sans-serif; background:#0f172a; padding:32px;">
    <div style="max-width:420px; margin:0 auto; background:#1e293b; border-radius:16px; padding:32px; text-align:center;">
      <h1 style="color:#fff; font-size:20px; margin:0 0 12px;">Verify your account</h1>
      <p style="color:#94a3b8; font-size:14px; line-height:20px; margin:0 0 24px;">
        Tap the button below on your phone to verify your account and open DevCore.
        If you don't have an account yet, one will be created automatically.
      </p>
      <a href="{link}"
         style="display:inline-block; background:#6366f1; color:#fff; text-decoration:none;
                font-weight:700; font-size:15px; padding:14px 32px; border-radius:12px;">
        Verify Account
      </a>
      <p style="color:#64748b; font-size:12px; margin:24px 0 0;">
        This expires in 15 minutes. If you didn't request this, you can ignore this email.
      </p>
    </div>
  </body>
</html>""",
            subtype="html",
        )

        try:
            with smtplib.SMTP(self.host, self.port) as server:
                server.starttls()
                server.login(self.user, self.password)
                server.send_message(message)
            return True
        except Exception as exc:
            logger.error(f"Failed to send magic link email: {exc}")
            return False

    async def send_magic_link(self, to_email: str, link: str) -> bool:
        return await asyncio.to_thread(self._send, to_email, link)
