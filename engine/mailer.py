"""Optional outgoing mail for the school referral note (off unless the host sets the SMTP settings).

Two independent switches, both read from the environment so no address or password is stored in the project:

- SMTP_USER + SMTP_PASSWORD: the system may send the referral note for a student who asks it to
  (app.py /api/school-referral/send). Without them nothing is ever sent.
- DEMO_COUNSELING_EMAIL: a stand-in mailbox shown, clearly labelled as a demo, for schools whose counseling
  office email the team has not verified. It is not a school address and must be left empty on a real site.
"""
import os
import re
import smtplib
import ssl
from email.message import EmailMessage

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
TIMEOUT = 10  # seconds; the student is waiting on the page


def _address(name):
    value = os.environ.get(name, "").strip()
    return value if EMAIL.fullmatch(value) else ""


def demo_recipient():
    """The stand-in mailbox for a demo, or "" when none is set."""
    return _address("DEMO_COUNSELING_EMAIL")


def settings():
    """SMTP settings, or None when sending is not set up."""
    user = os.environ.get("SMTP_USER", "").strip()
    password = os.environ.get("SMTP_PASSWORD", "")
    sender = _address("SMTP_FROM") or (user if EMAIL.fullmatch(user) else "")
    if not (user and password and sender):
        return None
    try:
        port = int(os.environ.get("SMTP_PORT", "587"))
    except ValueError:
        port = 587
    return {"host": os.environ.get("SMTP_HOST", "smtp.gmail.com").strip() or "smtp.gmail.com", "port": port,
            "user": user, "password": password, "sender": sender}


def configured():
    return settings() is not None


def send(to, subject, body, reply_to=""):
    """Send one plain-text mail. Raises RuntimeError when sending is not set up, OSError / smtplib.SMTPException
    when the mail server refuses or cannot be reached."""
    conf = settings()
    if conf is None:
        raise RuntimeError("mail is not configured")
    if not EMAIL.fullmatch(to or ""):
        raise ValueError("invalid recipient")
    message = EmailMessage()
    message["From"] = conf["sender"]
    message["To"] = to
    message["Subject"] = subject
    if EMAIL.fullmatch(reply_to or ""):
        message["Reply-To"] = reply_to
    message.set_content(body)
    context = ssl.create_default_context()
    if conf["port"] == 465:
        server = smtplib.SMTP_SSL(conf["host"], conf["port"], timeout=TIMEOUT, context=context)
    else:
        server = smtplib.SMTP(conf["host"], conf["port"], timeout=TIMEOUT)
    with server:
        if conf["port"] != 465:
            server.starttls(context=context)
        server.login(conf["user"], conf["password"])
        server.send_message(message)
