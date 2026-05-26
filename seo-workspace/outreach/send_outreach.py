#!/usr/bin/env python3
"""
MeetLyra SEO Outreach Email Sender
Utility script to send personalized link-building emails using MeetLyra SMTP settings.
"""

import sys
import logging
import smtplib
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Add parent directory to sys.path to import content_machine config
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from content_machine.config import load_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("outreach_sender")

# Define prospects
PROSPECTS = {
    "superhuman": {
        "email": "editorial@superhuman.ai",
        "name": "Superhuman Team",
        "template": "superhuman-editorial-pitch.md",
        "description": "Pitching the Autonomous SEO Content Engine case study to Superhuman Newsletter."
    },
    "marketingbrew": {
        "email": "editors@marketingbrew.com",
        "name": "Marketing Brew Editors",
        "template": "marketingbrew-pitch.md",
        "description": "Pitching a GEO guest post column / interview to Marketing Brew."
    }
}

def load_template_body(template_name: str) -> str:
    template_path = Path(__file__).resolve().parent / "emails" / template_name
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found at: {template_path}")
    
    content = template_path.read_text()
    # Strip frontmatter/header sections (anything before the actual text body)
    if "---" in content:
        parts = content.split("---", 1)
        body = parts[1].strip()
    else:
        body = content.strip()
    return body

def send_outreach_email(target_key: str, custom_to: str = None) -> bool:
    if target_key not in PROSPECTS:
        logger.error(f"Unknown prospect key: {target_key}. Available keys: {list(PROSPECTS.keys())}")
        return False
        
    prospect = PROSPECTS[target_key]
    settings = load_settings()
    
    if not settings.smtp_host or not settings.smtp_username:
        logger.error("SMTP settings not configured in .env file (SMTP_HOST/SMTP_USERNAME is empty).")
        return False
        
    to_email = custom_to or prospect["email"]
    from_email = settings.smtp_from or settings.smtp_username
    
    try:
        raw_body = load_template_body(prospect["template"])
    except Exception as e:
        logger.error(f"Failed to load email template: {e}")
        return False
        
    # Extract subject from template markdown metadata if present
    subject = f"Collaboration Pitch from MeetLyra"
    template_content = (Path(__file__).resolve().parent / "emails" / prospect["template"]).read_text()
    for line in template_content.splitlines():
        if line.lower().startswith("*   **subject:**") or line.lower().startswith("subject:"):
            subject = line.split(":", 1)[1].strip().strip('"').strip("'")
            break
            
    # Format email message
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = from_email
    msg['To'] = to_email
    
    # Convert markdown-like blocks to a simple clean email layout
    html_body = f"""
    <html>
    <body style="font-family: -apple-system, BlinkMacSystemFont, Arial, sans-serif; line-height: 1.6; color: #333333; max-width: 600px; padding: 20px;">
        {raw_body.replace('\n', '<br/>').replace('> ', '<blockquote style="border-left: 3px solid #ccc; padding-left: 15px; margin: 10px 0; color: #666;">').replace('</blockquote><br/>', '</blockquote>')}
    </body>
    </html>
    """
    
    msg.attach(MIMEText(raw_body, 'plain'))
    msg.attach(MIMEText(html_body, 'html'))
    
    logger.info(f"Connecting to SMTP server {settings.smtp_host}:{settings.smtp_port}...")
    try:
        if settings.smtp_port == 465:
            server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=30)
        else:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30)
            server.ehlo()
            server.starttls()
            server.ehlo()
            
        if settings.smtp_password:
            server.login(settings.smtp_username, settings.smtp_password)
            
        logger.info(f"Sending email to {to_email} from {from_email}...")
        server.sendmail(from_email, to_email, msg.as_string())
        server.quit()
        logger.info("Outreach email sent successfully!")
        return True
    except Exception as exc:
        logger.error(f"Failed to send outreach email via SMTP: {exc}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 send_outreach.py [prospect_key] [--test-to recipient@domain.com]")
        print("Available prospects:")
        for k, v in PROSPECTS.items():
            print(f"  - {k}: {v['description']} (To: {v['email']})")
        sys.exit(1)
        
    prospect_key = sys.argv[1]
    test_recipient = None
    if "--test-to" in sys.argv:
        try:
            test_recipient = sys.argv[sys.argv.index("--test-to") + 1]
        except IndexError:
            logger.error("Missing email address after --test-to flag")
            sys.exit(1)
            
    send_outreach_email(prospect_key, test_recipient)
