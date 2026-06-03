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

GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
FROM_NAME = os.getenv("FROM_NAME")
TRACKING_SERVER = os.getenv("TRACKING_SERVER")  

RATE_LIMIT_SECONDS = 60

def load_template(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def inject_tracking_pixel(html, tracking_id):
    pixel = f'<img src="{TRACKING_SERVER}/track/open?id={tracking_id}" width="1" height="1" style="display:none;border:0;" alt="" />'
    if "</body>" in html:
        return html.replace("</body>", f"{pixel}\n</body>")
    return html + pixel

def log_sent_to_server(tracking_id, email, name, pharmacy_name, sent_at):
    try:
        requests.post(f"{TRACKING_SERVER}/track/sent", json={
            "tracking_id": tracking_id,
            "email": email,
            "name": name,
            "pharmacy_name": pharmacy_name,
            "sent_at": sent_at
        }, timeout=5)
    except Exception as e:
        print(f"  Warning: could not log to server: {e}")

template = load_template("email_template.html")

server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)

with open("leads.csv", newline="", encoding="utf-8") as file:
    leads = list(csv.DictReader(file))

for lead in leads:
    tracking_id = str(uuid.uuid4())
    sent_at = time.strftime("%Y-%m-%d %H:%M:%S")

    html = template \
        .replace("{{name}}", lead["name"]) \
        .replace("{{pharmacy_name}}", lead["pharmacy_name"]) \
        .replace("{{from_name}}", FROM_NAME)

    html = inject_tracking_pixel(html, tracking_id)

    msg = MIMEMultipart("alternative")
    msg["From"] = f"{FROM_NAME} <{GMAIL_ADDRESS}>"
    msg["To"] = lead["email"]
    msg["Subject"] = f"Demo Website For {lead['pharmacy_name']}"
    msg.attach(MIMEText(html, "html"))

    server.sendmail(GMAIL_ADDRESS, lead["email"], msg.as_string())
    print(f"Sent to {lead['email']} | tracking_id: {tracking_id}")

    log_sent_to_server(tracking_id, lead["email"], lead["name"], lead["pharmacy_name"], sent_at)

    time.sleep(RATE_LIMIT_SECONDS)

server.quit()
