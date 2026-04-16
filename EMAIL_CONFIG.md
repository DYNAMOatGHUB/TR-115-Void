# Email Configuration for Automatic Report Delivery

## Overview
The Carbon Intelligence Platform can automatically send generated PDF reports to stakeholders via email. This feature is **optional** and requires SMTP configuration.

## Setup Instructions

### 1. Gmail Configuration (Recommended)

For Gmail users, you'll need to use an **App Password** (not your regular password):

1. Enable 2-Factor Authentication on your Google Account
2. Visit: https://myaccount.google.com/apppasswords
3. Generate an app-specific password for "Mail" on "Windows PC" (or your platform)
4. Copy the 16-character password

### 2. Set Environment Variables

Add the following to your `.env` file or export them in your shell:

```bash
# Gmail SMTP Configuration
export SMTP_SERVER="smtp.gmail.com"
export SMTP_PORT="587"
export SENDER_EMAIL="your-email@gmail.com"
export SENDER_PASSWORD="xxxx xxxx xxxx xxxx"  # 16-char app password from step 1
```

### 3. Other SMTP Providers

If using a different email provider, adjust these settings:

**Outlook/Microsoft 365:**
```bash
export SMTP_SERVER="smtp.office365.com"
export SMTP_PORT="587"
export SENDER_EMAIL="your-email@outlook.com"
export SENDER_PASSWORD="your-password"
```

**AWS SES (Simple Email Service):**
```bash
export SMTP_SERVER="email-smtp.us-east-1.amazonaws.com"  # your region
export SMTP_PORT="587"
export SENDER_EMAIL="verified-sender@yourdomain.com"
export SENDER_PASSWORD="your-ses-password"
```

**Custom SMTP Server:**
```bash
export SMTP_SERVER="mail.example.com"
export SMTP_PORT="587"  # or 25, 465 depending on your server
export SENDER_EMAIL="sender@example.com"
export SENDER_PASSWORD="your-password"
```

## Usage

1. Launch the app and upload a document
2. Enter recipient email address in the "Email Address (optional)" field
3. Click "Analyze Emissions"
4. Once the report is generated, it will be sent automatically to the provided email address

## Features

- **Automatic Delivery**: Report sent immediately upon generation
- **Professional Email**: Includes executive summary in email body + PDF attachment
- **Graceful Fallback**: If email fails, analysis continues; error displayed to user
- **Silent Opt-Out**: Leave email field blank to skip sending

## Troubleshooting

### "Email service not configured" error
- Verify environment variables are set correctly
- Check that `SENDER_EMAIL` and `SENDER_PASSWORD` are exported

### "Email authentication failed"
- Verify credentials are correct (especially for Gmail app passwords)
- Check that SMTP_SERVER and SMTP_PORT match your provider
- Ensure sender email is verified with your SMTP provider

### "SMTP Connection error"
- Verify firewall/network allows outbound SMTP (port 587 or 25/465)
- Check that SMTP_SERVER hostname is correct
- Some networks block port 25; use port 587 instead

### Email not received
- Check spam/junk folder
- Verify recipient email is correct
- Check provided email domain reputation (spam filters)
- Review SMTP provider's delivery logs

## Security Notes

- **Never commit credentials to git**: Use `.env` files or secrets manager
- **Use app-specific passwords**: Avoid putting main account passwords in environment
- **Enable STARTTLS**: Connections use port 587 with encryption
- **Sanitize emails**: User-provided email addresses are validated as basic email format

## Testing

To test email configuration without analyzing a document:

```python
from services.email_service import send_report_email

# Test with a dummy PDF
result = send_report_email(
    pdf_path="/path/to/test.pdf",
    recipient_email="test@example.com",
    company_name="Test Company",
    total_emissions_kg=1000.0
)
print(result)
```

## Disabling Email

Email feature is entirely optional. Simply:
- Don't set SMTP environment variables, OR
- Leave the email field blank in the UI

The application will function normally without email configuration.
