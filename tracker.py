from flask import Flask, request, Response, jsonify
import csv
import os
import io
import time

app = Flask(__name__)

OPENS_LOG = "opens_log.csv"
SENT_LOG  = "sent_log.csv"

BOT_UA_FRAGMENTS = [
    "googleimageproxy",       
    "google image proxy",
    "safelinks",              
    "mimecast",               
    "proofpoint",
    "barracuda networks",
    "symantec.cloud",
    "ironport",
    "messagelabs",
    "postini",
    "spamhaus",
    "feedfetcher",
    "preview.mail.ru",
]

BOT_UA_EXACT = [
    "mozilla/5.0",  
]

def is_bot(user_agent: str) -> bool:
    ua = user_agent.lower()
    return any(frag in ua for frag in BOT_UA_FRAGMENTS)

def log_open(tracking_id, ip, user_agent):
    file_exists = os.path.isfile(OPENS_LOG)
    with open(OPENS_LOG, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["tracking_id", "opened_at", "ip", "user_agent"])
        writer.writerow([tracking_id, time.strftime("%Y-%m-%d %H:%M:%S"), ip, user_agent])

def load_sent():
    sent = {}
    if os.path.isfile(SENT_LOG):
        with open(SENT_LOG, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                sent[row["tracking_id"]] = row
    return sent

def load_opens():
    opens = {}
    if os.path.isfile(OPENS_LOG):
        with open(OPENS_LOG, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                tid = row["tracking_id"]
                opens.setdefault(tid, []).append(row["opened_at"])
    return opens

def get_sent_time(tracking_id):
    """Return the sent_at timestamp for a tracking_id, or None."""
    if os.path.isfile(SENT_LOG):
        with open(SENT_LOG, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row["tracking_id"] == tracking_id:
                    return row["sent_at"]
    return None

TRANSPARENT_GIF = (
    b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00'
    b'\xff\xff\xff\x00\x00\x00\x21\xf9\x04\x00\x00\x00\x00'
    b'\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02'
    b'\x44\x01\x00\x3b'
)


@app.route("/track/open")
def track_open():
    tracking_id = request.args.get("id", "unknown")
    ip          = request.remote_addr
    user_agent  = request.headers.get("User-Agent", "")
    now_str     = time.strftime("%Y-%m-%d %H:%M:%S")

    if is_bot(user_agent):
        print(f"[BOT SKIPPED] id={tracking_id} ua={user_agent[:80]}")
        return Response(TRANSPARENT_GIF, mimetype="image/gif",
                        headers={"Cache-Control": "no-store, no-cache, must-revalidate"})


    sent_at = get_sent_time(tracking_id)
    if sent_at and now_str < sent_at:
        print(f"[PRE-FETCH SKIPPED] open at {now_str} but sent at {sent_at} — id={tracking_id}")
        return Response(TRANSPARENT_GIF, mimetype="image/gif",
                        headers={"Cache-Control": "no-store, no-cache, must-revalidate"})

    log_open(tracking_id, ip, user_agent)
    print(f"[OPEN LOGGED] id={tracking_id} ip={ip} ua={user_agent[:60]}")

    return Response(TRANSPARENT_GIF, mimetype="image/gif",
                    headers={"Cache-Control": "no-store, no-cache, must-revalidate"})

@app.route("/track/sent", methods=["POST"])
def track_sent():
    data = request.get_json(force=True)
    file_exists = os.path.isfile(SENT_LOG)
    with open(SENT_LOG, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["tracking_id", "email", "name", "pharmacy_name", "sent_at"])
        writer.writerow([
            data.get("tracking_id", ""),
            data.get("email", ""),
            data.get("name", ""),
            data.get("pharmacy_name", ""),
            data.get("sent_at", ""),
        ])
    return jsonify({"status": "ok"})


@app.route("/download/sent")
def download_sent():
    if not os.path.isfile(SENT_LOG):
        return "No sent_log.csv yet.", 404
    with open(SENT_LOG, "r", encoding="utf-8") as f:
        content = f.read()
    return Response(content, mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=sent_log.csv"})

@app.route("/download/opens")
def download_opens():
    sent  = load_sent()
    opens = load_opens()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Pharmacy Name", "First Opened At", "Times Opened"])
    for tid, open_times in opens.items():
        pharmacy_name = sent.get(tid, {}).get("pharmacy_name", "Unknown")
        writer.writerow([pharmacy_name, open_times[0], len(open_times)])
    output.seek(0)
    return Response(output.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=opens_log.csv"})

@app.route("/download/report")
def download_report():
    sent  = load_sent()
    opens = load_opens()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Name", "Email", "Pharmacy", "Sent At", "Open Count", "First Open", "Status"])
    for tid, info in sent.items():
        open_times = opens.get(tid, [])
        open_count = len(open_times)
        first_open = open_times[0] if open_times else ""
        status     = "Opened" if open_count else "Not Opened"
        writer.writerow([info["name"], info["email"], info["pharmacy_name"],
                         info["sent_at"], open_count, first_open, status])
    output.seek(0)
    return Response(output.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=email_report.csv"})


@app.route("/report")
def report():
    sent  = load_sent()
    opens = load_opens()

    rows = ""
    for tid, info in sent.items():
        open_times = opens.get(tid, [])
        open_count = len(open_times)
        first_open = open_times[0] if open_times else "—"
        if open_count:
            status = f'<span class="opened">Opened {open_count}x (first: {first_open})</span>'
        else:
            status = '<span class="not-opened">Not opened</span>'
        rows += f"""
        <tr>
            <td>{info['name']}</td>
            <td>{info['email']}</td>
            <td>{info['pharmacy_name']}</td>
            <td>{info['sent_at']}</td>
            <td>{status}</td>
        </tr>"""

    total  = len(sent)
    opened = sum(1 for tid in sent if tid in opens)
    rate   = f"{(opened/total*100):.1f}%" if total else "N/A"

    html = f"""<!DOCTYPE html>
<html>
<head>
  <title>Email Tracking Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; padding: 24px; background: #f9f9f9; }}
    h2   {{ margin-bottom: 6px; }}
    .summary {{ margin-bottom: 18px; font-size: 15px; color: #333; }}
    .btn-row {{ margin-bottom: 20px; display: flex; gap: 10px; flex-wrap: wrap; }}
    .btn {{
      display: inline-block; padding: 9px 18px; border-radius: 6px;
      font-size: 14px; font-weight: 600; text-decoration: none; cursor: pointer; border: none;
    }}
    .btn-green {{ background: #1a73e8; color: #fff; }}
    .btn-green:hover {{ background: #1558b0; }}
    .btn-gray  {{ background: #e0e0e0; color: #333; }}
    .btn-gray:hover  {{ background: #c8c8c8; }}
    table {{ border-collapse: collapse; width: 100%; background: #fff;
             box-shadow: 0 1px 4px rgba(0,0,0,.08); border-radius: 8px; overflow: hidden; }}
    th, td {{ border: 1px solid #e0e0e0; padding: 9px 14px; text-align: left; font-size: 14px; }}
    th {{ background: #f4f4f4; font-weight: 700; }}
    tr:hover td {{ background: #f0f6ff; }}
    .opened     {{ color: #1a7a3c; font-weight: 600; }}
    .not-opened {{ color: #b00020; }}
  </style>
</head>
<body>
  <h2>Email Tracking Report</h2>
  <div class="summary">
    Sent: <strong>{total}</strong> &nbsp;|&nbsp;
    Opened: <strong>{opened}</strong> &nbsp;|&nbsp;
    Open rate: <strong>{rate}</strong>
  </div>
  <div class="btn-row">
    <a class="btn btn-green" href="/download/report">Download Report (Google Sheets / Excel)</a>
    <a class="btn btn-gray"  href="/download/sent">sent_log.csv</a>
    <a class="btn btn-gray"  href="/download/opens">opens_log.csv</a>
  </div>
  <table>
    <thead><tr>
      <th>Name</th><th>Email</th><th>Pharmacy</th><th>Sent At</th><th>Opening Status</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <p style="margin-top:16px; font-size:12px; color:#999;">
    Auto-refreshes every 60s &nbsp;·&nbsp;
    <a href="/report" style="color:#999;">Refresh now</a>
  </p>
  <script>setTimeout(() => location.reload(), 60000);</script>
</body>
</html>"""
    return html

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
