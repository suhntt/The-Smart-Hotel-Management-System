import os
import json
from datetime import datetime, timedelta
import razorpay

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_mail import Mail

# Import Config, DB, models and utils
from config import Config
from models import db, User, Admin, Room, Booking, Payment, AadhaarRecord, VerificationLog, FoodMenu, FoodOrder
from utils.otp_service import mail, generate_otp, send_otp_email, verify_otp_code, send_booking_confirmation_email
from utils.ocr_engine import extract_aadhaar_info
from utils.face_engine import verify_faces

app = Flask(__name__)
app.config.from_object(Config)

# Ensure upload folders exist
for folder in [app.config['AADHAAR_UPLOAD_DIR'], app.config['FACE_UPLOAD_DIR'], app.config['TEMP_DIR']]:
    os.makedirs(folder, exist_ok=True)

# Initialize database and mail
db.init_app(app)
mail.init_app(app)

# Initialize Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Initialize Razorpay Client (safe initialization)
try:
    razorpay_client = razorpay.Client(auth=(app.config['RAZORPAY_KEY_ID'], app.config['RAZORPAY_KEY_SECRET']))
except Exception as e:
    app.logger.warning(f"Could not initialize Razorpay client (using mock payment fallback): {str(e)}")
    razorpay_client = None

# Custom user loader to handle User and Admin tables
@login_manager.user_loader
def load_user(user_id):
    if user_id.startswith('admin_'):
        admin_db_id = int(user_id.split('_')[1])
        return Admin.query.get(admin_db_id)
    elif user_id.startswith('user_'):
        user_db_id = int(user_id.split('_')[1])
        return User.query.get(user_db_id)
    return None

# Custom Jinja filters
@app.template_filter('from_json')
def from_json_filter(value):
    return json.loads(value)

# Context processor to inject config variables into templates
@app.context_processor
def inject_config():
    return {
        'RAZORPAY_KEY_ID': app.config['RAZORPAY_KEY_ID'],
        'SIMULATE_AI': app.config.get('SIMULATE_AI', False),
        'datetime': datetime,
        'today': datetime.today().date()
    }

# File Upload helper
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


# ==========================================
# 0. DATABASE SEEDING
# ==========================================
def seed_database():
    with app.app_context():
        db.create_all()
        
        # Check if default admin exists
        if not Admin.query.filter_by(username='admin').first():
            admin = Admin(username='admin', email='admin@smarthotel.com', role='admin')
            admin.set_password('admin123')
            db.session.add(admin)
            
            receptionist = Admin(username='receptionist', email='reception@smarthotel.com', role='receptionist')
            receptionist.set_password('recep123')
            db.session.add(receptionist)
            
        # Check if rooms exist, if not seed default rooms
        if not Room.query.first():
            rooms_to_seed = [
                Room(category='Standard Room', price_per_night=1500.0, amenities='Double Bed, AC, Free Wi-Fi, TV, Geyser', max_guests=2, status='Available', description='Comfortable and affordable standard room equipped with modern amenities.', image_url='/static/img/rooms/standard.jpg'),
                Room(category='Deluxe Room', price_per_night=2500.0, amenities='Queen Bed, AC, Free Wi-Fi, TV, Mini Fridge, Geyser', max_guests=2, status='Available', description='Spacious deluxe room offering elegant decor and comfortable seating area.', image_url='/static/img/rooms/deluxe.jpg'),
                Room(category='Executive Room', price_per_night=4000.0, amenities='King Bed, AC, Premium Toiletries, Safe, TV, Mini Fridge, Work Desk', max_guests=3, status='Available', description='Designed for business travelers, includes a desk, premium styling and pool views.', image_url='/static/img/rooms/executive.jpg'),
                Room(category='Family Room', price_per_night=5500.0, amenities='2 Double Beds, Large AC Room, Interconnected Options, Smart TV, Fridge', max_guests=4, status='Available', description='Perfect room for families of four. Features spacious lounging and double beds.', image_url='/static/img/rooms/family.jpg'),
                Room(category='Suite Room', price_per_night=8000.0, amenities='King Bed, Separate Living Room, Bath Tub, Balcony, Bar Desk, Free Airport Pick-up', max_guests=3, status='Available', description='Luxurious suite featuring private living quarters, premium views, and upscale bathroom amenities.', image_url='/static/img/rooms/suite.jpg')
            ]
            db.session.add_all(rooms_to_seed)
            
        # Seed food menu items
        if not FoodMenu.query.first():
            foods_to_seed = [
                FoodMenu(name='Paneer Butter Masala', category='Main Course', price=280.0, description='Soft paneer cubes cooked in rich tomato and butter gravy.', is_available=True, image_url='/static/img/food/paneer.jpg'),
                FoodMenu(name='Chicken Biryani', category='Main Course', price=320.0, description='Aromatic basmati rice cooked with succulent chicken and herbs.', is_available=True, image_url='/static/img/food/biryani.jpg'),
                FoodMenu(name='Garlic Bread with Cheese', category='Starters', price=150.0, description='Toasted bread slices topped with garlic butter and melted cheese.', is_available=True, image_url='/static/img/food/garlic_bread.jpg'),
                FoodMenu(name='Chocolate Lava Cake', category='Desserts', price=180.0, description='Warm chocolate cake with a gooey, molten chocolate center.', is_available=True, image_url='/static/img/food/lava_cake.jpg'),
                FoodMenu(name='Fresh Lime Soda', category='Beverages', price=90.0, description='Refreshing carbonated beverage flavored with lime and mint.', is_available=True, image_url='/static/img/food/lime_soda.jpg'),
                FoodMenu(name='Spring Rolls', category='Starters', price=160.0, description='Crispy pastry sheets filled with sauteed mixed vegetables.', is_available=True, image_url='/static/img/food/spring_rolls.jpg')
            ]
            db.session.add_all(foods_to_seed)
            
        db.session.commit()


# ==========================================
# 1. AUTHENTICATION ROUTES (MODULE 1)
# ==========================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.get_id().startswith('admin_'):
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user_type = request.form.get('user_type', 'customer') # customer or staff
        
        if user_type == 'staff':
            admin = Admin.query.filter_by(username=email).first() or Admin.query.filter_by(email=email).first()
            if admin and admin.check_password(password):
                login_user(admin)
                flash('Logged in successfully as Staff!', 'success')
                return redirect(url_for('admin_dashboard'))
            else:
                flash('Invalid staff credentials.', 'danger')
        else:
            user = User.query.filter_by(email=email).first()
            if user and user.check_password(password):
                if not user.is_verified:
                    # Redirect to OTP verification page
                    session['pending_verify_email'] = user.email
                    otp = generate_otp()
                    send_otp_email(user.email, otp)
                    flash('Please verify your email address. OTP has been sent.', 'info')
                    return redirect(url_for('otp_verify'))
                    
                login_user(user)
                flash('Logged in successfully!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid email or password.', 'danger')
                
    return render_template('login.html')

@app.route('/register', methods=['POST'])
def register():
    name = request.form.get('name')
    email = request.form.get('email')
    phone = request.form.get('phone')
    password = request.form.get('password')
    
    # Check if user exists
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        flash('Email address already registered.', 'danger')
        return redirect(url_for('login'))
        
    user = User(name=name, email=email, phone=phone)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    
    # Send OTP
    otp = generate_otp()
    session['pending_verify_email'] = email
    success, msg = send_otp_email(email, otp)
    
    flash(f'Registration successful! {msg}. Please enter the OTP below.', 'success')
    return redirect(url_for('otp_verify'))

@app.route('/otp-verify', methods=['GET', 'POST'])
def otp_verify():
    email = session.get('pending_verify_email')
    if not email:
        flash('No verification session found. Please login.', 'warning')
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        otp_code = request.form.get('otp')
        user = User.query.filter_by(email=email).first()
        
        if user and verify_otp_code(email, otp_code):
            user.is_verified = True
            db.session.commit()
            login_user(user)
            session.pop('pending_verify_email', None)
            flash('Email verified and logged in successfully!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid OTP code. Please try again.', 'danger')
            
    return render_template('otp_verify.html', email=email)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('login'))

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        if user:
            otp = generate_otp()
            session['forgot_password_email'] = email
            send_otp_email(email, otp)
            flash('OTP sent to your email. Please verify to reset password.', 'info')
            return redirect(url_for('reset_password'))
        else:
            flash('No account found with this email.', 'danger')
    return render_template('forgot_password.html')

@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    email = session.get('forgot_password_email')
    if not email:
        flash('Invalid password reset session.', 'warning')
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        otp = request.form.get('otp')
        new_password = request.form.get('new_password')
        
        user = User.query.filter_by(email=email).first()
        if user and verify_otp_code(email, otp):
            user.set_password(new_password)
            db.session.commit()
            session.pop('forgot_password_email', None)
            flash('Password reset successful. Please login.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Invalid OTP or user not found.', 'danger')
            
    return render_template('reset_password.html', email=email)

@app.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    if current_user.get_id().startswith('admin_'):
        flash('Admins cannot update customer profile details.', 'warning')
        return redirect(url_for('admin_dashboard'))
        
    name = request.form.get('name')
    phone = request.form.get('phone')
    password = request.form.get('password')
    
    user = User.query.get(current_user.id)
    user.name = name
    user.phone = phone
    
    if password:
        user.set_password(password)
        
    db.session.commit()
    flash('Profile updated successfully!', 'success')
    return redirect(url_for('dashboard'))


# ==========================================
# 2. ROOM BOOKING SYSTEM (MODULE 2 & 3)
# ==========================================

@app.route('/')
def index():
    rooms = Room.query.filter_by(status='Available').all()
    # Simple formatting of amenities list
    for room in rooms:
        room.amenity_list = [a.strip() for a in room.amenities.split(',')]
    return render_template('index.html', rooms=rooms)

@app.route('/search', methods=['GET'])
def search_rooms():
    check_in = request.args.get('check_in')
    check_out = request.args.get('check_out')
    guests = request.args.get('guests', 1, type=int)
    
    if not check_in or not check_out:
        flash('Please select check-in and check-out dates to search.', 'warning')
        return redirect(url_for('index'))
        
    try:
        in_date = datetime.strptime(check_in, '%Y-%m-%d').date()
        out_date = datetime.strptime(check_out, '%Y-%m-%d').date()
    except ValueError:
        flash('Invalid date format. Please use the date picker.', 'warning')
        return redirect(url_for('index'))
    
    if in_date >= out_date or in_date < datetime.today().date():
        flash('Please choose valid future dates (check-out must be after check-in).', 'warning')
        return redirect(url_for('index'))

        
    # Query rooms that fit guest requirements
    matching_rooms = Room.query.filter(Room.max_guests >= guests).all()
    
    available_rooms = []
    for room in matching_rooms:
        # Check for date collisions with bookings that are already booked/checked-in
        collision = Booking.query.filter(
            Booking.room_id == room.id,
            Booking.status.in_(['Booked', 'Checked-in']),
            Booking.check_in_date < out_date,
            Booking.check_out_date > in_date
        ).first()
        
        if not collision:
            room.amenity_list = [a.strip() for a in room.amenities.split(',')]
            available_rooms.append(room)
            
    return render_template('index.html', rooms=available_rooms, check_in=check_in, check_out=check_out, guests=guests)

@app.route('/room/<int:room_id>')
def room_details(room_id):
    room = Room.query.get_or_404(room_id)
    room.amenity_list = [a.strip() for a in room.amenities.split(',')]
    
    check_in = request.args.get('check_in', '')
    check_out = request.args.get('check_out', '')
    guests = request.args.get('guests', 1, type=int)
    
    nights = 1
    if check_in and check_out:
        try:
            in_date = datetime.strptime(check_in, '%Y-%m-%d').date()
            out_date = datetime.strptime(check_out, '%Y-%m-%d').date()
            nights = max(1, (out_date - in_date).days)
        except ValueError:
            nights = 1
        
    base_amount = room.price_per_night * nights
    total_amount = round(base_amount * 1.12, 2)  # 12% tax included
    
    return render_template('room_details.html', room=room, check_in=check_in, check_out=check_out,
                           guests=guests, nights=nights, total_amount=total_amount)


@app.route('/book/<int:room_id>', methods=['POST'])
@login_required
def book_room(room_id):
    if current_user.get_id().startswith('admin_'):
        flash('Staff accounts cannot book rooms.', 'danger')
        return redirect(url_for('index'))
        
    room = Room.query.get_or_404(room_id)
    
    check_in = request.form.get('check_in')
    check_out = request.form.get('check_out')
    guests = request.form.get('guests', 1, type=int)
    aadhaar_num = request.form.get('aadhaar_number')
    
    if not check_in or not check_out or not aadhaar_num:
        flash('All booking fields are required.', 'danger')
        return redirect(url_for('room_details', room_id=room.id))
        
    in_date = datetime.strptime(check_in, '%Y-%m-%d').date()
    out_date = datetime.strptime(check_out, '%Y-%m-%d').date()
    nights = max(1, (out_date - in_date).days)
    total_amount = room.price_per_night * nights
    
    # 1. Double check room availability for double-booking prevention
    collision = Booking.query.filter(
        Booking.room_id == room.id,
        Booking.status.in_(['Booked', 'Checked-in']),
        Booking.check_in_date < out_date,
        Booking.check_out_date > in_date
    ).first()
    
    if collision:
        flash('This room was unfortunately booked by another user in the meantime. Please select other dates or rooms.', 'danger')
        return redirect(url_for('index'))
        
    # 2. File Upload Validations
    if 'aadhaar_image' not in request.files or 'face_image' not in request.files:
        flash('Both Aadhaar Card image and User Photograph are required.', 'danger')
        return redirect(url_for('room_details', room_id=room.id, check_in=check_in, check_out=check_out, guests=guests))
        
    aadhaar_file = request.files['aadhaar_image']
    face_file = request.files['face_image']
    
    if aadhaar_file.filename == '' or face_file.filename == '':
        flash('Selected files cannot be empty.', 'danger')
        return redirect(url_for('room_details', room_id=room.id, check_in=check_in, check_out=check_out, guests=guests))
        
    if not (allowed_file(aadhaar_file.filename) and allowed_file(face_file.filename)):
        flash('Invalid file format. Only PNG, JPG, and JPEG are allowed.', 'danger')
        return redirect(url_for('room_details', room_id=room.id, check_in=check_in, check_out=check_out, guests=guests))
        
    # 3. Create Booking
    booking = Booking(
        user_id=current_user.id,
        room_id=room.id,
        check_in_date=in_date,
        check_out_date=out_date,
        guests_count=guests,
        total_amount=total_amount,
        payment_status='Pending',
        status='Booked'
    )
    db.session.add(booking)
    db.session.commit() # Save to generate booking.id
    
    # 4. Save uploaded images
    aadhaar_ext = aadhaar_file.filename.rsplit('.', 1)[1].lower()
    face_ext = face_file.filename.rsplit('.', 1)[1].lower()
    
    aadhaar_filename = f"booking_{booking.id}_aadhaar.{aadhaar_ext}"
    face_filename = f"booking_{booking.id}_face.{face_ext}"
    
    aadhaar_path = os.path.join(app.config['AADHAAR_UPLOAD_DIR'], aadhaar_filename)
    face_path = os.path.join(app.config['FACE_UPLOAD_DIR'], face_filename)
    
    aadhaar_file.save(aadhaar_path)
    face_file.save(face_path)
    
    # Save Aadhaar Record Details
    aadhaar_record = AadhaarRecord(
        booking_id=booking.id,
        aadhaar_number=aadhaar_num,
        aadhaar_image_path=f"/static/uploads/aadhaar/{aadhaar_filename}",
        face_image_path=f"/static/uploads/faces/{face_filename}",
        verification_status='Pending'
    )
    db.session.add(aadhaar_record)
    db.session.commit()
    
    # Redirect to Checkout
    return redirect(url_for('checkout', service_type='RoomBooking', item_id=booking.id))


# ==========================================
# 3. ONLINE PAYMENTS (MODULE 6)
# ==========================================

@app.route('/checkout/<string:service_type>/<int:item_id>')
@login_required
def checkout(service_type, item_id):
    amount = 0.0
    description = ""
    
    if service_type == 'RoomBooking':
        booking = Booking.query.get_or_404(item_id)
        if booking.user_id != current_user.id:
            flash('Unauthorized access to booking payment details.', 'danger')
            return redirect(url_for('dashboard'))
        amount = booking.total_amount
        description = f"Room Booking ID #{booking.id} - {booking.room.category}"
    elif service_type == 'FoodOrder':
        order = FoodOrder.query.get_or_404(item_id)
        if order.user_id != current_user.id:
            flash('Unauthorized access to food payment details.', 'danger')
            return redirect(url_for('dashboard'))
        amount = order.total_amount
        description = f"Food Order ID #{order.id}"
    else:
        flash('Invalid payment service type.', 'danger')
        return redirect(url_for('dashboard'))
        
    # Generate Razorpay Order
    razorpay_order_id = "mock_order_" + str(datetime.now().timestamp()).replace('.', '')
    
    if razorpay_client and not app.config.get('RAZORPAY_KEY_ID').startswith('rzp_test_sample'):
        try:
            # Razorpay expects amount in paise (1 INR = 100 paise)
            data = {
                "amount": int(amount * 100),
                "currency": "INR",
                "receipt": f"receipt_id_{item_id}",
                "payment_capture": 1
            }
            order_res = razorpay_client.order.create(data=data)
            razorpay_order_id = order_res['id']
        except Exception as e:
            app.logger.error(f"Razorpay Order generation failed: {str(e)}")
            
    # Save pending Payment log
    payment = Payment(
        booking_id=item_id if service_type == 'RoomBooking' else None,
        food_order_id=item_id if service_type == 'FoodOrder' else None,
        order_id=razorpay_order_id,
        amount=amount,
        status='Pending',
        service_type=service_type
    )
    db.session.add(payment)
    db.session.commit()
    
    return render_template(
        'checkout.html',
        service_type=service_type,
        item_id=item_id,
        amount=amount,
        description=description,
        order_id=razorpay_order_id,
        customer_name=current_user.name,
        customer_email=current_user.email,
        customer_phone=current_user.phone
    )

@app.route('/payment/callback', methods=['POST'])
@login_required
def payment_callback():
    payload = request.get_json()
    if not payload:
        return jsonify({"success": False, "error": "Invalid payload"}), 400
        
    service_type = payload.get('service_type')
    item_id = payload.get('item_id')
    razorpay_order_id = payload.get('razorpay_order_id')
    razorpay_payment_id = payload.get('razorpay_payment_id')
    razorpay_signature = payload.get('razorpay_signature')
    
    payment = Payment.query.filter_by(order_id=razorpay_order_id).first()
    if not payment:
        return jsonify({"success": False, "error": "Payment transaction not found"}), 404
        
    # Signature Verification
    signature_valid = True
    
    # If not in simulation/test mode with dummy keys, verify signature
    if razorpay_client and not app.config.get('RAZORPAY_KEY_ID').startswith('rzp_test_sample'):
        try:
            params_dict = {
                'razorpay_order_id': razorpay_order_id,
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_signature': razorpay_signature
            }
            razorpay_client.utility.verify_payment_signature(params_dict)
            signature_valid = True
        except Exception as e:
            app.logger.error(f"Razorpay Signature Verification Failed: {str(e)}")
            signature_valid = False
            
    if signature_valid:
        payment.status = 'Captured'
        payment.payment_id = razorpay_payment_id
        
        if service_type == 'RoomBooking':
            booking = Booking.query.get(item_id)
            booking.payment_status = 'Paid'
            send_booking_confirmation_email(booking.user.email, booking)
        elif service_type == 'FoodOrder':
            order = FoodOrder.query.get(item_id)
            order.payment_status = 'Paid'
            
        db.session.commit()
        return jsonify({"success": True})
    else:
        payment.status = 'Failed'
        db.session.commit()
        return jsonify({"success": False, "error": "Signature verification failed"}), 400

@app.route('/payment/status')
@login_required
def payment_status():
    status = request.args.get('status', 'failure')
    service_type = request.args.get('service_type')
    item_id = request.args.get('item_id', type=int)
    
    details = {}
    if service_type == 'RoomBooking':
        booking = Booking.query.get(item_id)
        details = {
            "title": "Room Booking",
            "item_name": booking.room.category if booking else "Hotel Room",
            "amount": booking.total_amount if booking else 0.0,
            "id": booking.id if booking else 0
        }
    elif service_type == 'FoodOrder':
        order = FoodOrder.query.get(item_id)
        details = {
            "title": "Food Order",
            "item_name": f"Food Items Ordered ({len(order.items)} items)" if order else "Restaurant Food",
            "amount": order.total_amount if order else 0.0,
            "id": order.id if order else 0
        }
        
    return render_template('payment_status.html', status=status, service_type=service_type, details=details)

@app.route('/invoice/download/<int:payment_id>')
@login_required
def download_invoice(payment_id):
    pmt = Payment.query.get_or_404(payment_id)
    # Validate authorization
    if pmt.booking and pmt.booking.user_id != current_user.id:
        flash('Unauthorized invoice access.', 'danger')
        return redirect(url_for('dashboard'))
    elif pmt.food_order and pmt.food_order.user_id != current_user.id:
        flash('Unauthorized invoice access.', 'danger')
        return redirect(url_for('dashboard'))
        
    # Render a premium printable invoice page
    return render_template('invoice_print.html', payment=pmt)


# ==========================================
# 4. CUSTOMER DASHBOARD (MODULE 7)
# ==========================================

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.get_id().startswith('admin_'):
        return redirect(url_for('admin_dashboard'))
        
    bookings = Booking.query.filter_by(user_id=current_user.id).order_by(Booking.created_at.desc()).all()
    food_orders = FoodOrder.query.filter_by(user_id=current_user.id).order_by(FoodOrder.created_at.desc()).all()
    
    # Calculate payments list
    payments = Payment.query.join(Booking, Payment.booking_id == Booking.id, isouter=True)\
                           .join(FoodOrder, Payment.food_order_id == FoodOrder.id, isouter=True)\
                           .filter((Booking.user_id == current_user.id) | (FoodOrder.user_id == current_user.id))\
                           .order_by(Payment.created_at.desc()).all()
                           
    return render_template('dashboard.html', bookings=bookings, food_orders=food_orders, payments=payments)

@app.route('/dashboard/pass/<int:booking_id>')
@login_required
def checkin_pass(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if booking.user_id != current_user.id:
        flash('Unauthorized pass request.', 'danger')
        return redirect(url_for('dashboard'))
        
    if booking.status != 'Checked-in':
        flash('Digital check-in pass is only available after receptionist face/Aadhaar verification.', 'warning')
        return redirect(url_for('dashboard'))
        
    return render_template('checkin_pass.html', booking=booking)


# ==========================================
# 5. RESTAURANT & FOOD ORDERING SYSTEM (MODULE 5)
# ==========================================

@app.route('/food-menu')
@login_required
def food_menu():
    items = FoodMenu.query.filter_by(is_available=True).all()
    
    # Group items by category for frontend UI tabs
    categories = {}
    for item in items:
        if item.category not in categories:
            categories[item.category] = []
        categories[item.category].append(item)
        
    return render_template('food_menu.html', categories=categories)

@app.route('/food-menu/order', methods=['POST'])
@login_required
def order_food():
    if current_user.get_id().startswith('admin_'):
        return jsonify({"success": False, "error": "Admins cannot order food"}), 400
        
    payload = request.get_json()
    cart = payload.get('cart')
    total_amount = payload.get('total_amount', 0.0)
    
    if not cart or len(cart) == 0:
        return jsonify({"success": False, "error": "Cart is empty"}), 400
        
    # Build items JSON
    order_items = []
    for item in cart:
        menu_item = FoodMenu.query.get(item['id'])
        if menu_item and menu_item.is_available:
            order_items.append({
                "item_id": menu_item.id,
                "name": menu_item.name,
                "price": menu_item.price,
                "qty": item['qty']
            })
            
    if not order_items:
        return jsonify({"success": False, "error": "No valid available items in order"}), 400
        
    food_order = FoodOrder(
        user_id=current_user.id,
        items_json=json.dumps(order_items),
        total_amount=total_amount,
        payment_status='Pending',
        delivery_status='Ordered'
    )
    
    db.session.add(food_order)
    db.session.commit()
    
    # Return redirect parameters to payment
    return jsonify({
        "success": True,
        "redirect_url": url_for('checkout', service_type='FoodOrder', item_id=food_order.id)
    })

@app.route('/food-order/track/<int:order_id>')
@login_required
def track_food_order(order_id):
    order = FoodOrder.query.get_or_404(order_id)
    if order.user_id != current_user.id:
        flash('Unauthorized access to food tracking.', 'danger')
        return redirect(url_for('dashboard'))
        
    return render_template('track_food.html', order=order)


# ==========================================
# 6. ADMIN & STAFF DASHBOARD (MODULE 8 & 9)
# ==========================================

@app.route('/admin')
@login_required
def admin_dashboard():
    if not current_user.get_id().startswith('admin_'):
        flash('Access denied. Staff clearance required.', 'danger')
        return redirect(url_for('index'))
        
    # Metrics
    total_customers = User.query.count()
    total_rooms = Room.query.count()
    occupied_rooms = Room.query.filter_by(status='Occupied').count()
    occupancy_rate = (occupied_rooms / total_rooms * 100) if total_rooms > 0 else 0
    
    # Revenue (Room bookings + food orders that are paid)
    room_rev = db.session.query(db.func.sum(Booking.total_amount)).filter_by(payment_status='Paid').scalar() or 0.0
    food_rev = db.session.query(db.func.sum(FoodOrder.total_amount)).filter_by(payment_status='Paid').scalar() or 0.0
    total_revenue = room_rev + food_rev
    
    # Operational counts
    today_date = datetime.today().date()
    today_bookings = Booking.query.filter_by(check_in_date=today_date).count()
    
    # Today's actual checkins (successful logs today)
    today_checkins = VerificationLog.query.filter(
        db.func.date(VerificationLog.created_at) == today_date,
        VerificationLog.status == 'VERIFIED'
    ).count()
    
    pending_verifications = Booking.query.join(AadhaarRecord)\
                                         .filter(AadhaarRecord.verification_status == 'Pending')\
                                         .filter(Booking.status == 'Booked').count()
                                         
    # Recent Bookings list
    recent_bookings = Booking.query.order_by(Booking.created_at.desc()).limit(5).all()
    
    # Recent Food Orders
    recent_food_orders = FoodOrder.query.order_by(FoodOrder.created_at.desc()).limit(5).all()
    
    return render_template(
        'admin/dashboard.html',
        total_revenue=total_revenue,
        total_customers=total_customers,
        occupancy_rate=round(occupancy_rate, 1),
        today_bookings=today_bookings,
        today_checkins=today_checkins,
        pending_verifications=pending_verifications,
        recent_bookings=recent_bookings,
        recent_food_orders=recent_food_orders
    )

# Manage Rooms CRUD
@app.route('/admin/rooms', methods=['GET', 'POST'])
@login_required
def admin_manage_rooms():
    if not current_user.get_id().startswith('admin_'):
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        action = request.form.get('action')
        category = request.form.get('category')
        price = request.form.get('price', type=float)
        amenities = request.form.get('amenities')
        max_guests = request.form.get('max_guests', type=int)
        description = request.form.get('description')
        
        # Room image seeding or mock paths
        image_url = '/static/img/rooms/standard.jpg'
        if 'standard' in category.lower():
            image_url = '/static/img/rooms/standard.jpg'
        elif 'deluxe' in category.lower():
            image_url = '/static/img/rooms/deluxe.jpg'
        elif 'executive' in category.lower():
            image_url = '/static/img/rooms/executive.jpg'
        elif 'family' in category.lower():
            image_url = '/static/img/rooms/family.jpg'
        elif 'suite' in category.lower():
            image_url = '/static/img/rooms/suite.jpg'
            
        if action == 'add':
            room = Room(category=category, price_per_night=price, amenities=amenities, max_guests=max_guests, description=description, image_url=image_url)
            db.session.add(room)
            flash('Room added successfully!', 'success')
        elif action == 'edit':
            room_id = request.form.get('room_id', type=int)
            room = Room.query.get(room_id)
            if room:
                room.category = category
                room.price_per_night = price
                room.amenities = amenities
                room.max_guests = max_guests
                room.description = description
                flash('Room updated successfully!', 'success')
        elif action == 'delete':
            room_id = request.form.get('room_id', type=int)
            room = Room.query.get(room_id)
            if room:
                db.session.delete(room)
                flash('Room deleted successfully!', 'success')
                
        db.session.commit()
        return redirect(url_for('admin_manage_rooms'))
        
    rooms = Room.query.all()
    return render_template('admin/manage_rooms.html', rooms=rooms)

# Manage Bookings
@app.route('/admin/bookings')
@login_required
def admin_manage_bookings():
    if not current_user.get_id().startswith('admin_'):
        return redirect(url_for('index'))
        
    bookings = Booking.query.order_by(Booking.created_at.desc()).all()
    return render_template('admin/manage_bookings.html', bookings=bookings)

# Process Check-Out
@app.route('/admin/checkout/<int:booking_id>', methods=['POST'])
@login_required
def admin_checkout_booking(booking_id):
    if not current_user.get_id().startswith('admin_'):
        return redirect(url_for('index'))
        
    booking = Booking.query.get_or_404(booking_id)
    if booking.status == 'Checked-in':
        booking.status = 'Checked-out'
        # Free up the room
        booking.room.status = 'Available'
        db.session.commit()
        flash(f'Guest checked out. Booking #{booking.id} closed and {booking.room.category} is now Available.', 'success')
    else:
        flash('Cannot check out this booking as it is not currently checked-in.', 'danger')
        
    return redirect(url_for('admin_manage_bookings'))

# Manage Customers
@app.route('/admin/customers')
@login_required
def admin_manage_customers():
    if not current_user.get_id().startswith('admin_'):
        return redirect(url_for('index'))
        
    customers = User.query.all()
    return render_template('admin/manage_customers.html', customers=customers)

# Manage Food Menu CRUD
@app.route('/admin/food', methods=['GET', 'POST'])
@login_required
def admin_manage_food():
    if not current_user.get_id().startswith('admin_'):
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        action = request.form.get('action')
        name = request.form.get('name')
        category = request.form.get('category')
        price = request.form.get('price', type=float)
        description = request.form.get('description')
        is_available = 'is_available' in request.form
        
        # Simple dynamic mock image selection based on category
        image_url = '/static/img/food/paneer.jpg'
        if 'starter' in category.lower():
            image_url = '/static/img/food/spring_rolls.jpg'
        elif 'beverage' in category.lower():
            image_url = '/static/img/food/lime_soda.jpg'
        elif 'dessert' in category.lower():
            image_url = '/static/img/food/lava_cake.jpg'
            
        if action == 'add':
            food = FoodMenu(name=name, category=category, price=price, description=description, is_available=is_available, image_url=image_url)
            db.session.add(food)
            flash('Food item added successfully!', 'success')
        elif action == 'edit':
            food_id = request.form.get('food_id', type=int)
            food = FoodMenu.query.get(food_id)
            if food:
                food.name = name
                food.category = category
                food.price = price
                food.description = description
                food.is_available = is_available
                flash('Food item updated successfully!', 'success')
        elif action == 'delete':
            food_id = request.form.get('food_id', type=int)
            food = FoodMenu.query.get(food_id)
            if food:
                db.session.delete(food)
                flash('Food item deleted successfully!', 'success')
                
        db.session.commit()
        return redirect(url_for('admin_manage_food'))
        
    food_items = FoodMenu.query.all()
    return render_template('admin/manage_food.html', food_items=food_items)

# Admin payments view
@app.route('/admin/payments')
@login_required
def admin_manage_payments():
    if not current_user.get_id().startswith('admin_'):
        return redirect(url_for('index'))
    payments = Payment.query.order_by(Payment.created_at.desc()).all()
    return render_template('admin/manage_payments.html', payments=payments)

# Admin food orders view and update state
@app.route('/admin/food-orders', methods=['GET', 'POST'])
@login_required
def admin_food_orders():
    if not current_user.get_id().startswith('admin_'):
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        order_id = request.form.get('order_id', type=int)
        new_status = request.form.get('status')
        order = FoodOrder.query.get(order_id)
        if order:
            order.delivery_status = new_status
            db.session.commit()
            flash(f"Order #{order_id} status updated to '{new_status}'", 'success')
        return redirect(url_for('admin_food_orders'))
        
    orders = FoodOrder.query.order_by(FoodOrder.created_at.desc()).all()
    return render_template('admin/manage_food_orders.html', orders=orders)


# ==========================================
# 7. SMART CHECK-IN VERIFICATION LOGIC (MODULE 4)
# ==========================================

@app.route('/admin/checkin-verify', methods=['GET'])
@login_required
def admin_checkin_verify_page():
    if not current_user.get_id().startswith('admin_'):
        return redirect(url_for('index'))
        
    booking_id = request.args.get('booking_id', type=int)
    booking = None
    if booking_id:
        booking = Booking.query.get(booking_id)
        
    # Fetch bookings that are paid and ready for check-in
    pending_bookings = Booking.query.filter_by(status='Booked', payment_status='Paid').all()
        
    return render_template('admin/verify_checkin.html', booking=booking, pending_bookings=pending_bookings)

@app.route('/admin/checkin-verify/search', methods=['POST'])
@login_required
def admin_verify_search_booking():
    query = request.form.get('query')
    if not query:
        flash('Please enter an Aadhaar Number or Booking ID.', 'warning')
        return redirect(url_for('admin_checkin_verify_page'))
        
    # Search by Booking ID or Aadhaar Number
    booking = None
    if query.isdigit() and len(query) < 8:
        booking = Booking.query.get(int(query))
    else:
        # Search by Aadhaar Number in AadhaarRecord
        aadhaar_rec = AadhaarRecord.query.filter_by(aadhaar_number=query).first()
        if aadhaar_rec:
            booking = aadhaar_rec.booking
            
    if not booking:
        flash('No matching booking found.', 'danger')
        return redirect(url_for('admin_checkin_verify_page'))
        
    return redirect(url_for('admin_checkin_verify_page', booking_id=booking.id))

@app.route('/admin/checkin-verify/ocr/<int:booking_id>', methods=['POST'])
@login_required
def admin_verify_ocr(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    
    # Receptionist uploads a scan of physical Aadhaar card OR captures it via webcam
    if 'scanned_aadhaar' not in request.files:
        return jsonify({"success": False, "error": "No scanned Aadhaar image uploaded"}), 400
        
    scanned_file = request.files['scanned_aadhaar']
    if scanned_file.filename == '':
        return jsonify({"success": False, "error": "Empty file name"}), 400
        
    # Save scanned image to temp folder
    filename = f"scan_booking_{booking.id}.jpg"
    temp_path = os.path.join(app.config['TEMP_DIR'], filename)
    scanned_file.save(temp_path)
    
    # Process with OCR
    # Force simulation if config SIMULATE_AI is set, or request parameter requests simulation
    simulate = app.config.get('SIMULATE_AI', False) or (request.args.get('simulate') == 'true')
    ocr_result = extract_aadhaar_info(temp_path, simulate=simulate)
    
    if not ocr_result.get('success'):
        return jsonify({"success": False, "error": ocr_result.get('error', 'OCR Extraction failed')})
        
    scanned_number = ocr_result.get('aadhaar_number')
    scanned_name = ocr_result.get('name')
    
    # Compare with database Aadhaar number
    db_record = booking.aadhaar_record
    if not db_record:
        return jsonify({"success": False, "error": "No Aadhaar upload record associated with this booking."})
        
    aadhaar_match = (db_record.aadhaar_number.replace(" ", "") == scanned_number.replace(" ", ""))
    
    # Loose name matching (jaccard or subset matching to handle minor spelling errors)
    # Check if scanned name overlaps with booking user name
    db_user_name_parts = set(booking.user.name.lower().split())
    scanned_name_parts = set(scanned_name.lower().split())
    name_intersection = db_user_name_parts.intersection(scanned_name_parts)
    name_match_score = (len(name_intersection) / max(1, len(db_user_name_parts))) * 100
    
    return jsonify({
        "success": True,
        "scanned_aadhaar_number": scanned_number,
        "scanned_name": scanned_name,
        "db_aadhaar_number": db_record.aadhaar_number,
        "db_name": booking.user.name,
        "aadhaar_match": aadhaar_match,
        "name_match_score": round(name_match_score, 1),
        "confidence": ocr_result.get('confidence', 0.8) * 100
    })

@app.route('/admin/checkin-verify/face/<int:booking_id>', methods=['POST'])
@login_required
def admin_verify_face(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    
    # Capture webcam frame
    if 'live_frame' not in request.files:
        return jsonify({"success": False, "error": "No live camera frame uploaded"}), 400
        
    live_file = request.files['live_frame']
    if live_file.filename == '':
        return jsonify({"success": False, "error": "Empty file name"}), 400
        
    # Save live frame to temp folder
    filename = f"live_booking_{booking.id}.jpg"
    temp_path = os.path.join(app.config['TEMP_DIR'], filename)
    live_file.save(temp_path)
    
    # Get database uploaded face path
    db_record = booking.aadhaar_record
    if not db_record:
        return jsonify({"success": False, "error": "No customer face photo on record."})
        
    # Make absolute path to uploaded user face
    # db_record.face_image_path is like /static/uploads/faces/booking_1_face.jpg
    relative_path = db_record.face_image_path.lstrip('/')
    db_face_abs_path = os.path.join(os.path.abspath(os.path.dirname(__file__)), relative_path)
    
    # Process face verification
    simulate = app.config.get('SIMULATE_AI', False) or (request.args.get('simulate') == 'true')
    verify_result = verify_faces(db_face_abs_path, temp_path, simulate=simulate)
    
    return jsonify(verify_result)

@app.route('/admin/checkin-verify/finalize/<int:booking_id>', methods=['POST'])
@login_required
def admin_verify_finalize(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    
    payload = request.get_json()
    status = payload.get('status')  # VERIFIED or FAILED
    scanned_aadhaar = payload.get('scanned_aadhaar')
    scanned_name = payload.get('scanned_name')
    ocr_confidence = payload.get('ocr_confidence')
    face_score = payload.get('face_score')
    
    # Create Verification Log
    log = VerificationLog(
        booking_id=booking.id,
        scanned_aadhaar_number=scanned_aadhaar,
        scanned_name=scanned_name,
        confidence_score=ocr_confidence,
        face_match_score=face_score,
        status=status,
        verified_by=current_user.username
    )
    db.session.add(log)
    
    # Update Booking Statuses
    db_record = booking.aadhaar_record
    if status == 'VERIFIED':
        booking.status = 'Checked-in'
        # Update Room status to Occupied
        booking.room.status = 'Occupied'
        if db_record:
            db_record.verification_status = 'Verified'
    else:
        booking.status = 'Booked' # Reset or flag as verification failed
        if db_record:
            db_record.verification_status = 'Failed'
            
    db.session.commit()
    return jsonify({"success": True})


# ==========================================
# 8. ANALYTICS DATA (MODULE 9)
# ==========================================

@app.route('/admin/analytics/data')
@login_required
def admin_analytics_data():
    if not current_user.get_id().startswith('admin_'):
        return jsonify({"error": "Unauthorized"}), 403
        
    # 1. Monthly Revenue (Paid room bookings + food orders grouped by month for current year)
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    # Seed sample chart data if DB records are sparse, otherwise aggregate dynamically
    room_sales = [0.0] * 12
    food_sales = [0.0] * 12
    
    # Fetch from bookings
    bookings_paid = Booking.query.filter_by(payment_status='Paid').all()
    for b in bookings_paid:
        m_idx = b.created_at.month - 1
        room_sales[m_idx] += b.total_amount
        
    # Fetch from food orders
    food_paid = FoodOrder.query.filter_by(payment_status='Paid').all()
    for f in food_paid:
        m_idx = f.created_at.month - 1
        food_sales[m_idx] += f.total_amount
        
    # Inject nice starting data for demo curves if values are empty
    if sum(room_sales) == 0:
        room_sales = [45000, 52000, 48000, 62000, 71000, 85000, 0, 0, 0, 0, 0, 0]
    if sum(food_sales) == 0:
        food_sales = [12000, 15000, 14000, 19000, 21000, 24000, 0, 0, 0, 0, 0, 0]
        
    # 2. Room Occupancy by Category
    categories = ["Standard Room", "Deluxe Room", "Executive Room", "Family Room", "Suite Room"]
    occupancy_counts = []
    for cat in categories:
        cnt = Room.query.filter_by(category=cat, status='Occupied').count()
        occupancy_counts.append(cnt)
        
    # If all occupancy is zero, seed sample for presentation
    if sum(occupancy_counts) == 0:
        occupancy_counts = [5, 4, 3, 2, 1]
        
    # 3. Booking Trends (last 6 months booking count)
    booking_trends = [12, 18, 15, 24, 32, 45] # Mock default showing steady growth
    
    # 4. Food Sales by Item Category
    food_cats = ["Starters", "Main Course", "Desserts", "Beverages"]
    food_sales_by_cat = [1800, 4200, 1200, 950]
    
    # 5. Customer Growth (signup counts)
    customer_growth = [15, 22, 35, 48, 60, 85]
    
    return jsonify({
        "months": months[:datetime.now().month],
        "room_sales": room_sales[:datetime.now().month],
        "food_sales": food_sales[:datetime.now().month],
        "categories": categories,
        "occupancy": occupancy_counts,
        "trends_months": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"][:datetime.now().month],
        "booking_trends": booking_trends[:datetime.now().month],
        "food_categories": food_cats,
        "food_category_sales": food_sales_by_cat,
        "customer_growth": customer_growth[:datetime.now().month]
    })


if __name__ == '__main__':
    # Initialize and seed database
    seed_database()
    
    # Run server
    app.run(debug=True, port=5001)
