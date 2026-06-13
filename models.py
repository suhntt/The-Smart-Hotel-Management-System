from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import json

db = SQLAlchemy()

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(15), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_verified = db.Column(db.Boolean, default=False)  # For Email OTP verification
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    bookings = db.relationship('Booking', backref='user', lazy=True)
    food_orders = db.relationship('FoodOrder', backref='user', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
        
    def get_id(self):
        # Prefix user ID to distinguish from admin
        return f"user_{self.id}"

class Admin(db.Model, UserMixin):
    __tablename__ = 'admins'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(50), default='admin')  # admin, receptionist
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
        
    def get_id(self):
        # Prefix admin ID to distinguish from user
        return f"admin_{self.id}"

class Room(db.Model):
    __tablename__ = 'rooms'
    
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50), nullable=False)  # Standard, Deluxe, Executive, Family, Suite
    price_per_night = db.Column(db.Float, nullable=False)
    amenities = db.Column(db.String(500), nullable=False)  # Comma-separated
    max_guests = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='Available')  # Available, Occupied, Maintenance
    description = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(255), nullable=True)
    
    bookings = db.relationship('Booking', backref='room', lazy=True)

class Booking(db.Model):
    __tablename__ = 'bookings'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'), nullable=False)
    check_in_date = db.Column(db.Date, nullable=False)
    check_out_date = db.Column(db.Date, nullable=False)
    guests_count = db.Column(db.Integer, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    payment_status = db.Column(db.String(20), default='Pending')  # Pending, Paid, Refunded
    status = db.Column(db.String(20), default='Booked')  # Booked, Checked-in, Checked-out, Cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    payments = db.relationship('Payment', backref='booking', lazy=True)
    aadhaar_record = db.relationship('AadhaarRecord', backref='booking', uselist=False, lazy=True)
    verification_logs = db.relationship('VerificationLog', backref='booking', lazy=True)

class Payment(db.Model):
    __tablename__ = 'payments'
    
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.id'), nullable=True)
    food_order_id = db.Column(db.Integer, db.ForeignKey('food_orders.id'), nullable=True)
    order_id = db.Column(db.String(100), nullable=False)  # Razorpay Order ID
    payment_id = db.Column(db.String(100), nullable=True)  # Razorpay Payment ID
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='Pending')  # Pending, Captured, Failed
    service_type = db.Column(db.String(20), nullable=False)  # RoomBooking, FoodOrder
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class AadhaarRecord(db.Model):
    __tablename__ = 'aadhaar_records'
    
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.id'), nullable=False)
    aadhaar_number = db.Column(db.String(20), nullable=False)  # Stored encrypted or plain for demo
    aadhaar_image_path = db.Column(db.String(255), nullable=False)
    face_image_path = db.Column(db.String(255), nullable=False)
    verification_status = db.Column(db.String(20), default='Pending')  # Pending, Verified, Failed

class VerificationLog(db.Model):
    __tablename__ = 'verification_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.id'), nullable=False)
    scanned_aadhaar_number = db.Column(db.String(20), nullable=True)
    scanned_name = db.Column(db.String(100), nullable=True)
    confidence_score = db.Column(db.Float, nullable=True)
    face_match_score = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(20), nullable=False)  # VERIFIED, FAILED
    verified_by = db.Column(db.String(100), nullable=True)  # Name/ID of receptionist
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class FoodMenu(db.Model):
    __tablename__ = 'food_menu'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)  # Starters, Main Course, Desserts, Beverages
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_available = db.Column(db.Boolean, default=True)
    image_url = db.Column(db.String(255), nullable=True)

class FoodOrder(db.Model):
    __tablename__ = 'food_orders'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    items_json = db.Column(db.Text, nullable=False)  # List of {item_id, name, qty, price}
    total_amount = db.Column(db.Float, nullable=False)
    payment_status = db.Column(db.String(20), default='Pending')  # Pending, Paid, Refunded
    delivery_status = db.Column(db.String(20), default='Ordered')  # Ordered, Cooking, Out for Delivery, Delivered
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    payments = db.relationship('Payment', backref='food_order', lazy=True)
    
    @property
    def items(self):
        return json.loads(self.items_json)
