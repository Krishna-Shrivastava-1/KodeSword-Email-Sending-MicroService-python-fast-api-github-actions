import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from pydantic import BaseModel, EmailStr
from typing import Optional

router = APIRouter(
    prefix="/email",
    tags=["Welcome Email"]
)

# Request Schema
class WelcomeEmailRequest(BaseModel):
    email: EmailStr
    name: Optional[str] = "there"


def send_welcome_email_task(user_email: str, user_name: str):
    """Background worker function that connects to Brevo SMTP and dispatches the welcome email."""
    smtp_server = "smtp-relay.brevo.com"
    smtp_port = 587
    smtp_user = os.getenv("BREVO_SMTP_USER")
    smtp_pass = os.getenv("BREVO_SMTP_PASS")
    
    sender_email = os.getenv("SUPPORT_EMAIL", "hello@kodesword.com")
    sender_header = formataddr(("KodeSword Team", sender_email))
    subject = f"Welcome to KodeSword, {user_name}! 🚀"

    # Fallback greeting if name is generic
    display_name = user_name.strip().title() if user_name and user_name.lower() != "there" else "there"

    # Clean HTML Template
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin: 0; padding: 0; background-color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: #f8fafc; padding: 30px 10px;">
            <tr>
                <td align="center">
                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width: 580px; background-color: #ffffff; border-radius: 12px; border: 1px solid #e2e8f0; padding: 32px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                        
                        <!-- Header Logo -->
                        <tr>
                            <td style="padding-bottom: 24px; border-bottom: 1px solid #f1f5f9;">
                                <img src="https://www.kodesword.com/kodeswordbanner.png" alt="KodeSword"  style="width:full; display: block; border: 0;" />
                            </td>
                        </tr>

                        <!-- Body Content -->
                        <tr>
                            <td style="padding-top: 24px; color: #1e293b; font-size: 15px; line-height: 1.6;">
                                <p style="font-size: 18px; font-weight: 600; color: #0f172a; margin-top: 0;">
                                    Hey {display_name},
                                </p>
                                <p style="margin-bottom: 16px;">
                                    Welcome to <strong>KodeSword</strong>! We are thrilled to have you join our developer platform.
                                </p>
                                <p style="margin-bottom: 20px;">
                                    Whether you are looking to explore verified direct-employer career opportunities, access structured technical resources, or stay updated with daily hiring trends, KodeSword is built to help you accelerate your growth.
                                </p>

                                <!-- Highlight Box -->
                                <div style="background-color: #f1f5f9; border-left: 4px solid #2563eb; padding: 16px; border-radius: 6px; margin: 24px 0;">
                                    <p style="margin: 0; font-size: 14px; color: #334155; font-weight: 500;">
                                        ⚡ <strong>Quick Tip:</strong> Keep an eye out for our daily job digest updates featuring active, direct-employer roles verified across top tech portals.
                                    </p>
                                </div>

                                <!-- Action Button -->
                                <div style="margin: 30px 0; text-align: left;">
                                    <a href="https://www.kodesword.com/jobs" target="_blank" style="background-color: #2563eb; color: #ffffff; text-decoration: none; padding: 12px 24px; border-radius: 8px; font-weight: 600; font-size: 14px; display: inline-block;">
                                        Explore KodeSword Jobs →
                                    </a>
                                </div>

                                <p style="margin-bottom: 24px;">
                                    If you ever have feedback, questions, or need assistance, simply reply directly to this email—our team is always here to help.
                                </p>

                                <p style="margin-bottom: 0; color: #475569;">
                                    Best regards,<br>
                                    <strong>The KodeSword Team</strong>
                                </p>
                            </td>
                        </tr>

                        <!-- Footer -->
                        <tr>
                            <td style="padding-top: 32px; border-top: 1px solid #f1f5f9; margin-top: 32px; text-align: center;">
                                <p style="font-size: 12px; color: #94a3b8; margin: 0; line-height: 1.5;">
                                    © KodeSword. All rights reserved.<br>
                                    You received this email because you created an account on KodeSword.<br>
                                    <a href="https://www.kodesword.com/unsubscribe" style="color: #64748b; text-decoration: underline;">Manage Preferences</a>
                                </p>
                            </td>
                        </tr>

                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    # Plain Text Fallback
    text_fallback = f"""Hey {display_name},

Welcome to KodeSword! We are thrilled to have you join our developer platform.

Whether you're looking to explore verified direct-employer career opportunities, access structured technical resources, or stay updated with daily hiring trends, KodeSword is built to help you accelerate your growth.

Explore active job listings: https://www.kodesword.com/jobs

If you ever have feedback or questions, feel free to reply directly to this email!

Best regards,
The KodeSword Team

Unsubscribe: https://www.kodesword.com/unsubscribe
"""

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)

            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = sender_header
            msg["To"] = user_email

            # Deliverability & Spam Filter Prevention Headers
            msg["List-Unsubscribe"] = "<https://www.kodesword.com/unsubscribe>"
            msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"

            msg.attach(MIMEText(text_fallback, "plain"))
            msg.attach(MIMEText(html_content, "html"))

            server.sendmail(sender_email, user_email, msg.as_string())
            print(f"Welcome email successfully sent to {user_email}")

    except Exception as e:
        print(f"Failed to send welcome email to {user_email}: {e}")


@router.post("/send-welcome", status_code=status.HTTP_202_ACCEPTED)
async def send_welcome(payload: WelcomeEmailRequest, background_tasks: BackgroundTasks):
    """
    Triggers the welcome email sending task asynchronously in the background.
    """
    background_tasks.add_task(send_welcome_email_task, payload.email, payload.name)
    
    return {
        "success": True,
        "message": f"Welcome email queued for {payload.email}"
    }