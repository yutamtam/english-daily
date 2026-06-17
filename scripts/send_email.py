import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_email(to: str, subject: str, body: str, html: str | None = None) -> None:
    gmail_user = os.environ.get("GMAIL_USER")
    gmail_password = os.environ.get("GMAIL_APP_PASSWORD")

    if not gmail_user or not gmail_password:
        print("  ! Email skipped: GMAIL_USER or GMAIL_APP_PASSWORD not set")
        return

    if html:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = gmail_user
        msg["To"] = to
        msg.attach(MIMEText(body, "plain", "utf-8"))
        msg.attach(MIMEText(html, "html", "utf-8"))
    else:
        msg = MIMEText(body, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = gmail_user
        msg["To"] = to

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(gmail_user, gmail_password)
        server.sendmail(gmail_user, [to], msg.as_bytes())
