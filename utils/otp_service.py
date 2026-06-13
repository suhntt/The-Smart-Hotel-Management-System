import random
import logging
from flask import current_app, session
from flask_mail import Message, Mail

# Global mail instance, will be initialized in app.py
mail = Mail()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Temporary in-memory OTP register for fallback verification
_dev_otp_store = {}

def generate_otp():
    """Generates a random 6-digit OTP."""
    return str(random.randint(100000, 999999))

def send_otp_email(recipient_email, otp):
    """
    Sends an OTP to the customer's email.
    If SMTP settings are not set, it prints the OTP to console
    and stores it in a developer registry for display/bypass in the front-end.
    """
    # Store for local debugging bypass
    _dev_otp_store[recipient_email] = otp
    
    subject = "Verify Your Smart Hotel Account"
    body = f"""
    Hello,
    
    Thank you for choosing Smart Hotel Booking.
    Your One Time Password (OTP) for registration / account access is:
    
    {otp}
    
    This OTP is valid for 10 minutes. Please do not share it with anyone.
    
    Best regards,
    Smart Hotel Management Team
    """
    
    # Try sending live mail
    try:
        if not current_app.config.get('MAIL_USERNAME'):
            raise Exception("SMTP Username is empty. Running in Demo/Simulation Mode.")
            
        msg = Message(
            subject=subject,
            recipients=[recipient_email],
            body=body,
            sender=current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@smarthotel.com')
        )
        mail.send(msg)
        logger.info(f"OTP email sent successfully to {recipient_email}")
        return True, "Email sent"
    except Exception as e:
        logger.warning(f"Mail delivery failed: {str(e)}")
        logger.info(f"\n========================================\n"
                    f"  DEVELOPER OTP FOR {recipient_email}:\n"
                    f"  ---> {otp} <---\n"
                    f"========================================\n")
        return False, f"Demo Mode: OTP logged to server console: {otp}"

def verify_otp_code(email, code):
    """
    Verifies the provided OTP code against the developer store or session.
    """
    stored_otp = _dev_otp_store.get(email)
    if stored_otp and stored_otp == str(code).strip():
        # Clear after single successful verify
        _dev_otp_store.pop(email, None)
        return True
    return False

def send_booking_confirmation_email(recipient_email, booking):
    """
    Sends a booking confirmation email after successful payment.
    """
    subject = f"Booking Confirmation - GrandStay Hotel (ID: {booking.id})"
    body = f"""
    Hello {booking.user.name},
    
    Your payment has been successfully processed!
    Your booking for {booking.room.category} is confirmed.
    
    Check-In Date: {booking.check_in_date.strftime('%d %b %Y')}
    Check-Out Date: {booking.check_out_date.strftime('%d %b %Y')}
    Amount Paid: ₹{booking.total_amount:,.2f}
    
    Please carry your physical Aadhaar Card during check-in for instant verification at our reception desk.
    
    Thank you for choosing GrandStay Hotel.
    """
    
    try:
        if not current_app.config.get('MAIL_USERNAME'):
            raise Exception("SMTP Username is empty. Running in Demo/Simulation Mode.")
            
        msg = Message(
            subject=subject,
            recipients=[recipient_email],
            body=body,
            sender=current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@smarthotel.com')
        )
        mail.send(msg)
        logger.info(f"Booking confirmation email sent to {recipient_email}")
        return True
    except Exception as e:
        logger.warning(f"Booking email delivery failed: {str(e)}")
        logger.info(f"\n========================================\n"
                    f"  DEVELOPER BOOKING EMAIL TO {recipient_email}:\n{body}\n"
                    f"========================================\n")
        return False

