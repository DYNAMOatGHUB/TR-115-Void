"""
Email service for sending carbon reports automatically upon generation.
Sends PDF reports via SMTP with configurable recipients.
"""

import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.utils import formatdate
from email.encoders import encode_base64
from datetime import datetime


def send_report_email(
    pdf_path: str,
    recipient_email: str,
    company_name: str = "Unknown",
    total_emissions_kg: float = 0.0,
) -> dict:
    """
    Send carbon emissions report via email.
    
    Args:
        pdf_path: Path to the PDF report file
        recipient_email: Email address to send to
        company_name: Company/entity name for the report
        total_emissions_kg: Total emissions for subject line context
    
    Returns:
        dict with success status and message
    """
    
    # Get SMTP credentials from environment
    smtp_server = os.environ.get("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    sender_email = os.environ.get("SENDER_EMAIL")
    sender_password = os.environ.get("SENDER_PASSWORD")
    
    # If no email credentials, silently pass (optional feature)
    if not sender_email or not sender_password:
        return {
            "success": False,
            "message": "Email service not configured. Set SMTP_SERVER, SENDER_EMAIL, SENDER_PASSWORD env vars."
        }
    
    try:
        # Create message
        msg = MIMEMultipart()
        msg["From"] = sender_email
        msg["To"] = recipient_email
        msg["Date"] = formatdate(localtime=True)
        msg["Subject"] = f"Carbon Emissions Report - {company_name}"
        
        # Email body
        body = f"""
Dear Stakeholder,

Your carbon emissions audit report has been generated successfully.

Company/Entity: {company_name}
Total Emissions: {total_emissions_kg:,.2f} kg CO2e
Generated: {datetime.now().strftime('%B %d, %Y at %H:%M %Z')}

The detailed ESG-ready report is attached as a PDF. This comprehensive analysis includes:
- Executive summary with scope breakdown
- Emissions by activity category
- Line-item calculations with source citations
- Reduction recommendations with priority scoring
- Methodology and data source references

Please review the attached report and contact us with any questions.

Best regards,
Carbon Intelligence Platform
https://carbon-intelligence.dev
---
This is an automated report delivery. Do not reply to this email.
"""
        
        msg.attach(MIMEText(body, "plain"))
        
        # Attach PDF
        if os.path.exists(pdf_path):
            with open(pdf_path, "rb") as attachment:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment.read())
                encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    f"attachment; filename= {company_name}_carbon_report.pdf",
                )
                msg.attach(part)
        
        # Send email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
        
        return {
            "success": True,
            "message": f"Report sent to {recipient_email}"
        }
    
    except smtplib.SMTPAuthenticationError:
        return {
            "success": False,
            "message": "Email authentication failed. Check SENDER_EMAIL and SENDER_PASSWORD."
        }
    except smtplib.SMTPException as e:
        return {
            "success": False,
            "message": f"SMTP error: {str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Email send failed: {str(e)}"
        }


def should_send_email() -> bool:
    """Check if email service is configured."""
    return bool(os.environ.get("SENDER_EMAIL") and os.environ.get("SENDER_PASSWORD"))
