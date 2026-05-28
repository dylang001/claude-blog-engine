import logging
from content_machine.config import load_settings
from content_machine.reporter import EmailReporter

# Enable logging to see connection details
logging.basicConfig(level=logging.INFO)

def main():
    settings = load_settings()
    print("SMTP settings:")
    print(f"Host: {settings.smtp_host}")
    print(f"Port: {settings.smtp_port}")
    print(f"User: {settings.smtp_user}")
    print(f"From: {settings.smtp_from}")
    print(f"To: {settings.smtp_to}")
    
    reporter = EmailReporter(settings)
    success = reporter.send_daily_report()
    print(f"Daily report sending status: {success}")

if __name__ == '__main__':
    main()
