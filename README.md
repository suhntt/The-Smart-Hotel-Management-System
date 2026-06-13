# Smart Hotel Booking & Verification System
**A Full-Stack B.Tech 6th-Semester Mini Project**

A comprehensive, production-ready hotel booking and property management system. This project features full online room reservations, simulated payment gateway integration (Razorpay), and a highly secure biometric reception check-in process.

## 🌟 Key Features
- **Online Room Booking**: Customers can browse premium rooms, filter by date and occupancy, and securely book.
- **Identity Verification**: Integrated OpenCV and EasyOCR to compare user selfies with physical Aadhaar cards at the reception desk.
- **Admin Dashboard**: A secure portal for hotel staff to manage check-ins, verify documents in real-time, process check-outs, and monitor occupancy.
- **Smart Checkout**: Automated synchronization that instantly frees up room availability upon checkout.
- **Dark/Light Mode**: Full responsive design with seamless dark mode support across all customer and admin interfaces.

## 🛠️ Technology Stack
- **Backend**: Python 3.10, Flask
- **Database**: SQLite with SQLAlchemy ORM
- **Computer Vision**: OpenCV (`cv2`), `face_recognition`, `easyocr`
- **Frontend**: HTML5, CSS3, JavaScript, Bootstrap 5
- **Payments**: Razorpay API Integration (Simulated)
- **Notifications**: Flask-Mail (SMTP)

## 🚀 How to Run Locally

1. **Clone the repository**
   ```bash
   git clone https://github.com/suhntt/scms.git
   cd scms
   ```

2. **Create and activate a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Initialize the Database and Setup Passwords**
   ```bash
   python create_db.py
   python update_pass.py
   ```

5. **Start the Flask Server**
   ```bash
   python app.py
   ```

## 👨‍💻 Admin Access
- The default admin dashboard can be accessed by navigating to `/login`.
- **Username**: `admin`
- **Password**: `3Q@1JJMy7lE7` (Configured via `update_pass.py`)

## 📄 License
This project was built for academic purposes as part of a B.Tech curriculum.
