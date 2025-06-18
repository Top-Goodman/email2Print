# 📧 Email2Print

**Email2Print** is a lightweight, containerized service that turns your printer into an email-accessible device. Just send an email with attachments or text, and it will automatically print for you!

Purchased a new pritner recently to find out HP decommisioned their HPePrint service. So I felt a need to build my own. Planning to publish this as a docker image with some customizable settings.

Perfect for:
- Home automation fans
- Remote workers
- Teachers printing from anywhere
- Family members who don’t want to fuss with file uploads

---

## 🛠️ How It Works

1. The script connects to an email inbox via IMAP.
2. It scans for new emails with text or attachments.
3. Optionally verifies that the sender is allowed.
4. Prints supported file types or the email body.
5. Sends an email confirmation to the sender.

---

## 📦 Features

- ✅ Works with any IMAP email (Gmail, Outlook, etc.)
- ✅ Prints `.pdf`, `.txt`, `.docx`, and more
- ✅ Skips empty messages and blank attachments
- ✅ Sends a confirmation email after printing
- ✅ Optional detailed logging in confirmation
- ✅ Dockerized – Easy to deploy
- ✅ Supports separate email accounts for receiving and sending

---

## 🧰 Requirements

- Python 3.8+
- A printer connected and recognized by CUPS (Linux/macOS)
- A Docker environment (for containerized use)

---
