import imapclient
import email
import os
import logging
import tempfile
import subprocess
import smtplib
import time
import re
from email.message import EmailMessage
from email.header import decode_header
import io

# Logging setup
log_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger()
logger.setLevel(logging.INFO)

console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
logger.addHandler(console_handler)

file_handler = logging.FileHandler("email2print.log")
file_handler.setFormatter(log_formatter)
logger.addHandler(file_handler)


# Helper to get env variables
def get_env_var(name, required=False, default=None):
    val = os.getenv(name)
    if val is None or val == "":
        if required:
            logger.error(f"Missing required environment variable: {name}")
            raise ValueError(f"Missing required environment variable: {name}")
        return default
    return val

# Environment Configuration
EMAIL_ACCOUNT = get_env_var("EMAIL_ACCOUNT", required=True)
EMAIL_PASSWORD = get_env_var("EMAIL_PASSWORD", required=True)

SMTP_USERNAME = get_env_var("SMTP_USERNAME", default=EMAIL_ACCOUNT)
SMTP_PASSWORD = get_env_var("SMTP_PASSWORD", default=EMAIL_PASSWORD)
FROM_ADDRESS   = get_env_var("FROM_ADDRESS", default=EMAIL_ACCOUNT)

SMTP_SERVER = get_env_var("SMTP_SERVER", required=True)
SMTP_PORT = int(get_env_var("SMTP_PORT", required=True))

PRINTER_NAME = get_env_var("PRINTER_NAME", required=True)

SLEEP_TIME = int(get_env_var("SLEEP_TIME", default=60))
CONFIRM_SUBJECT = get_env_var("CONFIRM_SUBJECT", default="Your Print Job Confirmation")
ALLOWED_ATTACHMENT_TYPES = [ext.strip().lower() for ext in get_env_var("ALLOWED_ATTACHMENT_TYPES", default="").split(",") if ext]
ALLOWED_RECIPIENTS = [addr.strip().lower() for addr in get_env_var("ALLOWED_RECIPIENTS", default="").split(",") if addr]
DETAILED_CONFIRMATION = get_env_var("DETAILED_CONFIRMATION", default="false").lower() == "true"

def decode_mime_words(s):
    if not s:
        return ""
    return ''.join(
        part.decode(enc or 'utf-8') if isinstance(part, bytes) else part
        for part, enc in decode_header(s)
    )

def is_mostly_html_blank(html):
    cleaned = re.sub(r"<[^>]+>", "", html or "").strip()
    return cleaned == ""

def print_file(file_path):
    try:
        subprocess.run(["lp", "-d", PRINTER_NAME, file_path], check=True)
        logger.info(f"Sent to printer: {PRINTER_NAME} - File: {file_path}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Printing failed for {file_path}: {e}")
        return False

def send_confirmation_email(to_email, log_text, printed_files):
    msg = EmailMessage()
    msg["Subject"] = CONFIRM_SUBJECT
    msg["From"] = FROM_ADDRESS
    msg["To"] = to_email

    if DETAILED_CONFIRMATION:
        msg.set_content(f"Your print job was processed:\n\n{log_text}")
    else:
        lines = [
            f"{time.strftime('%Y-%m-%d %H:%M:%S')} – Your file '{fname}' was printed on printer '{PRINTER_NAME}'"
            for fname in printed_files
        ]
        msg.set_content("\n".join(lines) if lines else "No files were printed.")

    try:
        logger.info(f"Sending confirmation email to {to_email}")
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=20) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)
        logger.info("Confirmation email sent.")
    except Exception as e:
        logger.error(f"Error sending confirmation email: {e}")

def process_email(msg):
    from_addr = email.utils.parseaddr(msg.get("From"))[1].lower()
    subject = decode_mime_words(msg.get("Subject", "(No Subject)"))
    printed_files = []

    if ALLOWED_RECIPIENTS and from_addr not in ALLOWED_RECIPIENTS:
        logger.warning(f"Sender {from_addr} not in ALLOWED_RECIPIENTS. Skipping print.")
        return

    log_stream = io.StringIO()
    stream_handler = logging.StreamHandler(log_stream)
    stream_handler.setFormatter(log_formatter)
    logger.addHandler(stream_handler)

    logger.info(f"Processing email from: {from_addr}")
    logger.info(f"Subject: {subject}")
    printed_any = False

    for part in msg.walk():
        content_type = part.get_content_type()
        filename = part.get_filename()
        payload = part.get_payload(decode=True)

        if not payload or payload.strip() == b"":
            logger.warning(f"{'Attachment' if filename else 'Email body'} ({content_type}) is empty. Skipping print.")
            continue

        if filename:
            filename = decode_mime_words(filename)
            suffix = os.path.splitext(filename)[1].lower().lstrip(".")

            if ALLOWED_ATTACHMENT_TYPES and suffix not in ALLOWED_ATTACHMENT_TYPES:
                logger.warning(f"Attachment '{filename}' type .{suffix} not allowed. Skipping.")
                continue

            with tempfile.NamedTemporaryFile(delete=False, suffix=f".{suffix}") as tmpfile:
                tmpfile.write(payload)
                tmpfile_path = tmpfile.name

            logger.info(f"Printing attachment: {tmpfile_path}")
            if print_file(tmpfile_path):
                printed_any = True
                printed_files.append(filename)
            os.remove(tmpfile_path)
            logger.info(f"Deleted temporary file: {tmpfile_path}")

        elif content_type in ["text/plain", "text/html"]:
            if content_type == "text/html" and is_mostly_html_blank(payload.decode(errors="ignore")):
                logger.warning(f"HTML email body is blank after stripping tags. Skipping.")
                continue

            with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmpfile:
                tmpfile.write(payload)
                tmpfile_path = tmpfile.name

            logger.info(f"Printing email body: {tmpfile_path}")
            if print_file(tmpfile_path):
                printed_any = True
                printed_files.append(f"EmailBody-{content_type}")
            os.remove(tmpfile_path)
            logger.info(f"Deleted temporary file: {tmpfile_path}")

    if not printed_any:
        logger.warning("No printable content found in this email.")

    stream_handler.flush()
    logger.removeHandler(stream_handler)
    send_confirmation_email(from_addr, log_stream.getvalue(), printed_files)
    log_stream.close()

def main_loop():
    while True:
        logger.info("Starting email2print script")
        try:
            with imapclient.IMAPClient(os.getenv("IMAP_SERVER"), ssl=True, port=int(os.getenv("IMAP_PORT"))) as client:
                client.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
                client.select_folder("INBOX")
                messages = client.search(["UNSEEN"])
                logger.info(f"Found {len(messages)} unseen messages")

                if messages:
                    for uid, msg_data in client.fetch(messages, "RFC822").items():
                        raw_email = msg_data[b"RFC822"]
                        msg = email.message_from_bytes(raw_email)
                        process_email(msg)
                        client.add_flags(uid, [b"\\Seen"])
                else:
                    logger.info("No new messages.")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")

        logger.info(f"Sleeping {SLEEP_TIME}s...")
        time.sleep(SLEEP_TIME)

if __name__ == "__main__":
    print(f"Monitoring inbox: {EMAIL_ACCOUNT}")
    print(f"Printing to printer: {PRINTER_NAME}")
    print(f"Scan interval: {SLEEP_TIME} seconds")
    logger.info(f"Starting email2print with inbox: {EMAIL_ACCOUNT}, printer: {PRINTER_NAME}, scan interval: {SLEEP_TIME}s")
    main_loop()
