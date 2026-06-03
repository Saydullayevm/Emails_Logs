from flask import Flask, request, Response, jsonify
import csv
import os
import time

app = Flask(__name__)

OPENS_LOG = "opens_log.csv"
SENT_LOG = "sent_log.csv"

TRANSPARENT_GIF = (
    b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00'
    b'\xff\xff\xff\x00\x00\x00\x21\xf9\x04\x00\x00\x00\x00'
    b'\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02'
    b'\x44\x01\x00\x3b'
)

def append_csv(filepath, row, header):
    file_exists = os.path.isfile(filepath)
    with open(filepath, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(header)
        writer.writerow(row)

@app.route("/track/open")
def track_open():
    tracking_id = request.args.get("id", "unknown")
    ip = request.remote_addr
    append_csv(OPENS_LOG,
               [tracking_id, time.strftime("%Y-%m-%d %H:%M:%S"), ip],
               ["tracking_id", "opened_at", "ip"])
    return Response(TRANSPARENT_GIF, mimetype="image/gif",
                    headers={"Cache-Control": "no-store, no-cache, must-revalidate"})

@app.route("/track/sent", methods=["POST"])
def track_sent():
    """Called by send_emails.py after each successful send."""
    data = request.get_json()
    append_csv(SENT_LOG,
               [data["tracking_id"], data["email"], data["name"], data["pharmacy_name"], data["sent_at"]],
               ["tracking_id", "email", "name", "pharmacy_name", "sent_at"])
    return jsonify({"ok": True})

@app.route("/report")
def report():
    sent = {}
    if os.path.isfile(SENT_LOG):
        with open(SENT_LOG, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                sent[row["tracking_id"]] = row

    opens = {}
    if os.path.isfile(OPENS_LOG):
        with open(OPENS_LOG, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                tid = row["tracking_id"]
                opens.setdefault(tid, []).append(row["opened_at"])

    rows = ""
    for tid, info in sent.items():
        open_times = opens.get(tid, [])
        open_count = len(open_times)
        first_open = open_times[0] if open_times else "—"
        status = f"Opened {open_count}x time(s) (first: {first_open})" if open_count else "Not opened"
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
  <h2>Email Tracking Report</h2>
  <div class="summary">
    Sent: <strong>{total}</strong> &nbsp;|&nbsp;
    Opened: <strong>{opened}</strong> &nbsp;|&nbsp;
    Open rate: <strong>{rate}</strong>
  </div>
  <table>
    <thead><tr>
      <th>Name</th><th>Email</th><th>Pharmacy</th><th>Sent At</th><th>Opening Status</th>
    </tr></thead>
    <tbody>{rows}</tbody>
  </table>
</body>
</html>"""
    return html

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
