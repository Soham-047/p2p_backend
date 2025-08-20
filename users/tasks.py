from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import certifi
import ssl
from decouple import config

def get_env(key, default=None, cast=str, required=False):
    """
    Get environment variable via python-decouple.
    """
    try:
        value = config(key, default=default, cast=cast)
        if required and value is None:
            raise RuntimeError(f"Required environment variable '{key}' not set.")
        return value
    except Exception as e:
        raise ValueError(f"Failed to fetch environment variable '{key}': {e}")
    

@shared_task
def send_registration_email(subject, message, to_email):
    try:
        api_key = config("EMAIL_API_KEY")
        from_email = config("EMAIL_ID", default="noreply@yourdomain.com")

        message_to_send = Mail(
            from_email=from_email,
            to_emails=to_email,
            subject=subject,
            plain_text_content=message,
        )

        sg = SendGridAPIClient(api_key)
        sg.client._session.verify = certifi.where()
        sg.send(message_to_send)

        return f"Email sent to {to_email}"
    except Exception as e:
        return str(e)
    
@shared_task
def log_user_activity(user_id, activity):
    """Store or log user actions (placeholder for DB/log integration)"""
    print(f"User {user_id}: {activity}")
