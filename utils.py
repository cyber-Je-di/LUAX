import re
from flask_mail import Message
from flask import current_app

def is_valid_email(email):
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(pattern, email) is not None

def send_email(recipient, subject, message):
    if not is_valid_email(recipient):
        return
    try:
        mail = current_app.extensions.get('mail')
        email_msg = Message(subject=subject, body=message, sender=current_app.config['MAIL_USERNAME'], recipients=[recipient])
        mail.send(email_msg)
    except Exception as e:
        print(f"Email send failed: {e}")
