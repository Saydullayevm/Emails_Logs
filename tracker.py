from flask import Flask, request, send_file, Response
import csv
import os
import io
import time

app = Flask(__name__)

OPENS_LOG = "opens_log.csv"

def log_open(tracking_id, ip):
    file_exists = os.path.isfile(OPENS_LOG)
    with open(OPENS_LOG, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["tracking_id", "opened_at", "ip"])
        writer.writerow([tracking_id, time.strftime("%Y-%m-%d %H:%M:%S"), ip])

# 1x1 transparent GIF in bytes
TRANSPARENT_GIF = (
    b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00'
    b'\xff\xff\xff\x00\x00\x00\x21\xf9\x04\x00\x00\x00\x00'
    b'\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02'
    b'\x44\x01\x00\x3b'
)

@app.route("/track/open")
def track_open():
    tracking_id = request.args.get("id", "unknown")
    ip = request.remote_addr
    log_open(tracking_id, ip)
    return Response(TRANSPARENT_GIF, mimetype="image/gif",
                    headers={"Cache-Control": "no-store, no-cache, must-revalidate"})

@app.route("/report")
def report():
    """Quick HTML report: joins sent_log + opens_log"""
    sent = {}
    if os.path.isfile("sent_log.csv"):
        with open("sent_log.csv", newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                sent[row["tracking_id"]] = row

    opens = {}
    if os.path.isfile(OPENS_LOG):
        with open(OPENS_LOG, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                tid = row["tracking_id"]
                if tid not in opens:
                    opens[tid] = []
                opens[tid].append(row["opened_at"])

    rows = ""
    for tid, info in sent.items():
        open_times = opens.get(tid, [])
        open_count = len(open_times)
        first_open = open_times[0] if open_times else "—"
        status = f"✅ {open_count}x (first: {first_open})" if open_count else "❌ Not opened"
        rows += f"""
        <tr>
            <td>{info['name']}</td>
            <td>{info['email']}</td>
            <td>{info['pharmacy_name']}</td>
            <td>{info['sent_at']}</td>
            <td>{status}</td>
        </tr>"""

    total = len(sent)
    opened = sum(1 for tid in sent if tid in opens)
    rate = f"{(opened/total*100):.1f}%" if total else "N/A"

    html = f"""<!DOCTYPE html>
<html>
<head>
  <title>Email Tracking Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; padding: 20px; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ddd; padding: 8px 12px; text-align: left; }}
    th {{ background: #f4f4f4; }}
    tr:hover {{ background: #fafafa; }}
    .summary {{ margin-bottom: 20px; font-size: 16px; }}
  </style>
</head>
<body>
  <h2>📬 Email Tracking Report</h2>
  <div class="summary">
    Sent: <strong>{total}</strong> &nbsp;|&nbsp;
    Opened: <strong>{opened}</strong> &nbsp;|&nbsp;
    Open rate: <strong>{rate}</strong>
  </div>
  <table>
    <thead><tr>
      <th>Name</th><th>Email</th><th>Pharmacy</th><th>Sent At</th><th>Opens</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>
</body>
</html>"""
    return html

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)