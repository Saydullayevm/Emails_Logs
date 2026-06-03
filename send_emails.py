import csv
import smtplib
import time
import os
import uuid
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

GMAIL_ADDRESS      = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
FROM_NAME          = os.getenv("FROM_NAME")
TRACKING_SERVER    = os.getenv("TRACKING_SERVER")

RATE_LIMIT_SECONDS = 60

LOCAL_SENT_LOG = "sent_log.csv"

def save_sent_locally(tracking_id, email, name, pharmacy_name, sent_at):
    """Write each sent email to a local sent_log.csv in your project folder."""
    file_exists = os.path.isfile(LOCAL_SENT_LOG)
    with open(LOCAL_SENT_LOG, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["tracking_id", "email", "name", "pharmacy_name", "sent_at"])
        writer.writerow([tracking_id, email, name, pharmacy_name, sent_at])
    print(f"Logged locally → {LOCAL_SENT_LOG}")

def log_sent_to_server(tracking_id, email, name, pharmacy_name, sent_at):
    """Also post to Render so the web report stays up to date."""
    try:
        r = requests.post(f"{TRACKING_SERVER}/track/sent", json={
            "tracking_id": tracking_id,
            "email": email,
            "name": name,
            "pharmacy_name": pharmacy_name,
            "sent_at": sent_at,
        }, timeout=5)
        print(f"Logged to Render (status {r.status_code})")
    except Exception as e:
        print(f"Could not log to Render: {e}")

def load_template(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def inject_tracking_pixel(html, tracking_id):
    pixel = (
        f'<img src="{TRACKING_SERVER}/track/open?id={tracking_id}" '
        f'width="1" height="1" style="display:none;border:0;" alt="" />'
    )
    if "</body>" in html:
        return html.replace("</body>", f"{pixel}\n</body>")
    return html + pixel

template = load_template("email_template.html")

server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)

with open("leads.csv", newline="", encoding="utf-8") as file:
    leads = list(csv.DictReader(file))

print(f"Sending to {len(leads)} leads...\n")

for i, lead in enumerate(leads, 1):
    tracking_id = str(uuid.uuid4())
    sent_at     = time.strftime("%Y-%m-%d %H:%M:%S")

    html = (template
            .replace("{{name}}", lead["name"])
            .replace("{{pharmacy_name}}", lead["pharmacy_name"])
            .replace("{{from_name}}", FROM_NAME))

    html = inject_tracking_pixel(html, tracking_id)

    msg = MIMEMultipart("alternative")
    msg["From"]    = f"{FROM_NAME} <{GMAIL_ADDRESS}>"
    msg["To"]      = lead["email"]
    msg["Subject"] = f"Demo Website For {lead['pharmacy_name']}"
    msg.attach(MIMEText(html, "html"))

    server.sendmail(GMAIL_ADDRESS, lead["email"], msg.as_string())
    print(f"[{i}/{len(leads)}] Sent → {lead['email']} | id: {tracking_id}")

    save_sent_locally(tracking_id, lead["email"], lead["name"], lead["pharmacy_name"], sent_at)
    log_sent_to_server(tracking_id, lead["email"], lead["name"], lead["pharmacy_name"], sent_at)

    if i < len(leads):
        print(f"Waiting {RATE_LIMIT_SECONDS}s before next send...\n")
        time.sleep(RATE_LIMIT_SECONDS)

server.quit()
print(f"\nDone. Check {LOCAL_SENT_LOG} in your project folder.")
print(f"Live report: {TRACKING_SERVER}/report")
