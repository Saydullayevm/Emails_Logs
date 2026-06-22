import csv
import smtplib
import time
import os
import uuid
import signal
import atexit
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

GMAIL_ADDRESS      = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
FROM_NAME          = os.getenv("FROM_NAME")
TRACKING_SERVER    = os.getenv("TRACKING_SERVER")

RATE_LIMIT_SECONDS = 45
LOCAL_SENT_LOG     = "sent_log.csv"

_already_saved = False  

def auto_download_on_exit():
    """Called automatically whenever the script stops — Ctrl+C or normal end."""
    global _already_saved
    if _already_saved:
        return
    _already_saved = True

    print("\n\n Script stopped — auto-downloading reports from Render...")
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    saved = []

    for endpoint, filename in [
        ("/download/opens", f"opens_log_{timestamp}.csv"),
        ("/download/report", f"email_report_{timestamp}.csv"),
    ]:
        try:
            r = requests.get(f"{TRACKING_SERVER}{endpoint}", timeout=10)
            if r.status_code == 200 and r.text.strip():
                with open(filename, "w", encoding="utf-8", newline="") as f:
                    f.write(r.text)
                saved.append(filename)
                print(f"Saved → {filename}")
            elif r.status_code == 404:
                print(f"{endpoint} — no data on Render yet, skipping.")
            else:
                print(f"{endpoint} returned {r.status_code}, skipping.")
        except Exception as e:
            print(f"Could not fetch {endpoint}: {e}")

    if saved:
        print(f"\n Files saved in your project folder:")
        for f in saved:
            print(f"     {os.path.abspath(f)}")
        print("   → Open email_report_*.csv directly in Google Sheets (File → Import → Upload)\n")
    else:
        print("Nothing downloaded (Render may have no data yet).\n")

atexit.register(auto_download_on_exit)
signal.signal(signal.SIGTERM, lambda *_: auto_download_on_exit())

def save_sent_locally(tracking_id, email, name, pharmacy_name, sent_at):
    file_exists = os.path.isfile(LOCAL_SENT_LOG)
    with open(LOCAL_SENT_LOG, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["tracking_id", "email", "name", "pharmacy_name", "sent_at"])
        writer.writerow([tracking_id, email, name, pharmacy_name, sent_at])
    print(f"Logged locally → {LOCAL_SENT_LOG}")

def log_sent_to_server(tracking_id, email, name, pharmacy_name, sent_at):
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

print(f"Sending to {len(leads)} leads...")
print(f"Reports will auto-download if you press Ctrl+C or the script finishes.\n")

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
    msg["Subject"] = f"Rx4Route Partnership with {lead['pharmacy_name']}"
    msg.attach(MIMEText(html, "html"))

    server.sendmail(GMAIL_ADDRESS, lead["email"], msg.as_string())
    print(f"[{i}/{len(leads)}] Sent → {lead['email']} | id: {tracking_id}")

    save_sent_locally(tracking_id, lead["email"], lead["name"], lead["pharmacy_name"], sent_at)
    log_sent_to_server(tracking_id, lead["email"], lead["name"], lead["pharmacy_name"], sent_at)

    if i < len(leads):
        print(f"Waiting {RATE_LIMIT_SECONDS}s before next send...\n")
        time.sleep(RATE_LIMIT_SECONDS)

server.quit()
print(f"\nAll done. {len(leads)} emails sent.")