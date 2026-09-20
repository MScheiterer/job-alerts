import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def format_email_body(jobs):
    by_company = {}
    for j in jobs:
        by_company.setdefault(j["company"], []).append(j)

    lines = []
    for company, company_jobs in sorted(by_company.items()):
        lines.append(f"{company}")
        for j in company_jobs:
            loc = j.get("location") or "location n/a"
            lines.append(f"  - {j['title']} ({loc})")
            lines.append(f"    Posted:       {j.get('posted', 'not listed')}")
            lines.append(f"    Compensation: {j.get('compensation', 'not listed')}")
            lines.append(f"    Start date:   {j.get('start_date', 'not listed')}")
            lines.append(f"    Duration:     {j.get('duration', 'not listed')}")
            lines.append(f"    Load:         {j.get('load', 'not listed')}")
            lines.append(f"    {j['url']}")
            lines.append("")
        lines.append("")
    return "\n".join(lines)


def send_email(new_jobs):
    if not new_jobs:
        return

    smtp_host = os.environ["SMTP_HOST"]
    smtp_port = int(os.environ.get("SMTP_PORT", 587))
    smtp_user = os.environ["SMTP_USER"]
    smtp_pass = os.environ["SMTP_PASS"]
    to_addr = os.environ.get("ALERT_TO", smtp_user)

    body = format_email_body(new_jobs)

    msg = MIMEMultipart()
    msg["Subject"] = f"{len(new_jobs)} new internship posting(s)"
    msg["From"] = smtp_user
    msg["To"] = to_addr
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, [to_addr], msg.as_string())
