from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import sqlite3
import os
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'doc', 'docx'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Create uploads folder if it doesn't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Initialize database
def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    # Create tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            college_code TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS colleges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            college_code TEXT UNIQUE
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS staff (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            college_id INTEGER,
            FOREIGN KEY (college_id) REFERENCES colleges(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            attachment TEXT,
            status TEXT DEFAULT 'Pending',
            student_id INTEGER,
            staff_id INTEGER,
            college_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (staff_id) REFERENCES staff(id),
            FOREIGN KEY (college_id) REFERENCES colleges(id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_type TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            is_read BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS password_resets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_type TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            token TEXT UNIQUE NOT NULL,
            expires_at TIMESTAMP NOT NULL
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# Migration helper for existing databases
def check_and_migrate_db():
    """Check if database needs migration and add missing columns"""
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    try:
        # Check if colleges table has college_code column
        cursor.execute('PRAGMA table_info(colleges)')
        college_cols = [row[1] for row in cursor.fetchall()]
        if 'college_code' not in college_cols:
            # Add non-UNIQUE column first
            cursor.execute('ALTER TABLE colleges ADD COLUMN college_code TEXT')
            conn.commit()
        
        # Check if students table has college_code column
        cursor.execute('PRAGMA table_info(students)')
        student_cols = [row[1] for row in cursor.fetchall()]
        if 'college_code' not in student_cols:
            cursor.execute('ALTER TABLE students ADD COLUMN college_code TEXT')
            conn.commit()
            
    except sqlite3.OperationalError as e:
        # Column might already exist, ignore
        pass
    finally:
        conn.close()

check_and_migrate_db()

def get_db():
    conn = sqlite3.connect('database.db', timeout=30.0)
    conn.row_factory = sqlite3.Row
    return conn

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def create_notification(user_type, user_id, message):
    db = get_db()
    cursor = db.cursor()
    cursor.execute('INSERT INTO notifications (user_type, user_id, message) VALUES (?, ?, ?)', 
                   (user_type, user_id, message))
    db.commit()
    db.close()

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/student/signup', methods=['GET', 'POST'])
def student_signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        college_code = request.form.get('college_code', '').upper()
        
        db = get_db()
        cursor = db.cursor()
        
        # Verify college_code exists
        if college_code:
            cursor.execute('SELECT id FROM colleges WHERE college_code = ?', (college_code,))
            college = cursor.fetchone()
            if not college:
                flash('Invalid college code! Please check and try again.', 'error')
                db.close()
                return render_template('student_signup.html')
        
        try:
            hashed_password = generate_password_hash(password)
            cursor.execute('INSERT INTO students (name, email, password, college_code) VALUES (?, ?, ?, ?)', 
                          (name, email, hashed_password, college_code))
            db.commit()
            flash('Account created successfully! Please login.', 'success')
            return redirect(url_for('student_login'))
        except sqlite3.IntegrityError:
            flash('Email already exists!', 'error')
        finally:
            db.close()
    
    return render_template('student_signup.html')

@app.route('/student/login', methods=['GET', 'POST'])
def student_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute('SELECT * FROM students WHERE email = ?', (email,))
        user = cursor.fetchone()
        db.close()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['user_type'] = 'student'
            session['user_email'] = user['email']
            session['college_code'] = user['college_code'] if 'college_code' in user.keys() else None
            return redirect(url_for('student_dashboard'))
        else:
            flash('Invalid email or password!', 'error')
    
    return render_template('student_login.html')

@app.route('/student/dashboard')
def student_dashboard():
    if 'user_id' not in session or session['user_type'] != 'student':
        return redirect(url_for('student_login'))
    
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM complaints WHERE student_id = ? ORDER BY created_at DESC', 
                   (session['user_id'],))
    complaints = cursor.fetchall()
    db.close()
    
    return render_template('student_dashboard.html', complaints=complaints)

@app.route('/college/signup', methods=['GET', 'POST'])
def college_signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        db = get_db()
        cursor = db.cursor()
        
        try:
            hashed_password = generate_password_hash(password)
            # Generate unique college code
            college_code = ''.join(secrets.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(6))
            
            # Ensure code is unique
            while True:
                cursor.execute('SELECT id FROM colleges WHERE college_code = ?', (college_code,))
                if cursor.fetchone() is None:
                    break
                college_code = ''.join(secrets.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(6))
            
            cursor.execute('INSERT INTO colleges (name, email, password, college_code) VALUES (?, ?, ?, ?)', 
                          (name, email, hashed_password, college_code))
            db.commit()
            flash(f'Account created successfully! Your College Code is: {college_code}. Please save this code!', 'success')
            flash(f'Share this code with your students and staff to connect them to your college.', 'info')
            return redirect(url_for('college_login'))
        except sqlite3.IntegrityError as e:
            flash('Email or college code already exists!', 'error')
        finally:
            db.close()
    
    return render_template('college_signup.html')

@app.route('/college/login', methods=['GET', 'POST'])
def college_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute('SELECT * FROM colleges WHERE email = ?', (email,))
        user = cursor.fetchone()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['user_type'] = 'college'
            session['user_email'] = user['email']
            
            cursor.execute('SELECT * FROM staff WHERE college_id = ?', (user['id'],))
            staff_members = cursor.fetchall()
            
            cursor.execute('SELECT * FROM complaints ORDER BY created_at DESC')
            complaints = cursor.fetchall()
            
            db.close()
            
            return redirect(url_for('college_dashboard'))
        else:
            flash('Invalid email or password!', 'error')
            db.close()
    
    return render_template('college_login.html')

@app.route('/college/dashboard')
def college_dashboard():
    if 'user_id' not in session or session['user_type'] != 'college':
        return redirect(url_for('college_login'))
    
    db = get_db()
    cursor = db.cursor()
    
    # Get college code
    cursor.execute('SELECT college_code FROM colleges WHERE id = ?', (session['user_id'],))
    college_data = cursor.fetchone()
    college_code = college_data['college_code'] if college_data else None
    
    # Get staff members for this college
    cursor.execute('SELECT * FROM staff WHERE college_id = ?', (session['user_id'],))
    staff_members = cursor.fetchall()
    
    # Get complaints from students of this college only
    if college_code:
        cursor.execute('''
            SELECT c.* FROM complaints c
            JOIN students s ON c.student_id = s.id
            WHERE s.college_code = ?
            ORDER BY c.created_at DESC
        ''', (college_code,))
    else:
        cursor.execute('SELECT * FROM complaints ORDER BY created_at DESC')
    
    complaints = cursor.fetchall()
    
    # Get student names for complaints
    complaints_list = []
    for complaint in complaints:
        complaint_dict = dict(complaint)
        if complaint['student_id']:
            cursor.execute('SELECT name FROM students WHERE id = ?', (complaint['student_id'],))
            student = cursor.fetchone()
            complaint_dict['student_name'] = student['name'] if student else 'Unknown'
        else:
            complaint_dict['student_name'] = 'Unknown'
        complaints_list.append(complaint_dict)
    
    db.close()
    
    return render_template('college_dashboard.html', complaints=complaints_list, staff_members=staff_members, college_code=college_code)

@app.route('/staff/signup', methods=['GET', 'POST'])
def staff_signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        college_code = request.form.get('college_code', '').upper()
        college_id = None
        
        db = get_db()
        cursor = db.cursor()
        
        # Verify college_code and get college_id
        if college_code:
            cursor.execute('SELECT id FROM colleges WHERE college_code = ?', (college_code,))
            college = cursor.fetchone()
            if not college:
                flash('Invalid college code! Please check and try again.', 'error')
                db.close()
                return render_template('staff_signup.html')
            college_id = college['id']
        
        try:
            hashed_password = generate_password_hash(password)
            cursor.execute('INSERT INTO staff (name, email, password, college_id) VALUES (?, ?, ?, ?)', 
                          (name, email, hashed_password, college_id))
            db.commit()
            flash('Account created successfully! Please login.', 'success')
            return redirect(url_for('staff_login'))
        except sqlite3.IntegrityError:
            flash('Email already exists!', 'error')
        finally:
            db.close()
    
    return render_template('staff_signup.html')

@app.route('/staff/login', methods=['GET', 'POST'])
def staff_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        db = get_db()
        cursor = db.cursor()
        
        cursor.execute('SELECT * FROM staff WHERE email = ?', (email,))
        user = cursor.fetchone()
        db.close()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['user_type'] = 'staff'
            session['user_email'] = user['email']
            session['college_id'] = user['college_id']
            return redirect(url_for('staff_dashboard'))
        else:
            flash('Invalid email or password!', 'error')
    
    return render_template('staff_login.html')

@app.route('/staff/dashboard')
def staff_dashboard():
    if 'user_id' not in session or session['user_type'] != 'staff':
        return redirect(url_for('staff_login'))
    
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM complaints WHERE staff_id = ? ORDER BY created_at DESC', 
                   (session['user_id'],))
    complaints = cursor.fetchall()
    db.close()
    
    return render_template('staff_dashboard.html', complaints=complaints)

@app.route('/complaint/new', methods=['GET', 'POST'])
def complaint_new():
    if 'user_id' not in session or session['user_type'] != 'student':
        return redirect(url_for('student_login'))
    
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        attachment = None
        
        if 'attachment' in request.files:
            file = request.files['attachment']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
                filename = timestamp + filename
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                attachment = filename
        
        db = get_db()
        cursor = db.cursor()
        
        # Get the college_id for the student (assuming first college for demo purposes)
        # In production, you'd link students to colleges properly
        cursor.execute('SELECT id FROM colleges LIMIT 1')
        college = cursor.fetchone()
        college_id = college['id'] if college else None
        
        cursor.execute('''INSERT INTO complaints (title, description, attachment, student_id, college_id) 
                         VALUES (?, ?, ?, ?, ?)''', 
                      (title, description, attachment, session['user_id'], college_id))
        db.commit()
        complaint_id = cursor.lastrowid
        
        # Notify college about new complaint
        if college_id:
            create_notification('college', college_id, f'New complaint submitted: {title}')
        
        db.close()
        
        flash('Complaint submitted successfully!', 'success')
        return redirect(url_for('student_dashboard'))
    
    return render_template('complaint_new.html')

@app.route('/complaint/<int:complaint_id>')
def view_complaint(complaint_id):
    if 'user_id' not in session:
        return redirect(url_for('index'))
    
    db = get_db()
    cursor = db.cursor()
    cursor.execute('SELECT * FROM complaints WHERE id = ?', (complaint_id,))
    complaint = cursor.fetchone()
    
    if not complaint:
        flash('Complaint not found!', 'error')
        return redirect(url_for('index'))
    
    # Get student name
    if complaint['student_id']:
        cursor.execute('SELECT name FROM students WHERE id = ?', (complaint['student_id'],))
        student = cursor.fetchone()
        complaint = dict(complaint)
        complaint['student_name'] = student['name'] if student else 'Unknown'
    
    db.close()
    
    return render_template('view_complaint.html', complaint=complaint)

@app.route('/college/add-staff', methods=['GET', 'POST'])
def add_staff():
    if 'user_id' not in session or session['user_type'] != 'college':
        return redirect(url_for('college_login'))
    
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        college_id = session['user_id']
        
        db = get_db()
        cursor = db.cursor()
        
        try:
            hashed_password = generate_password_hash(password)
            cursor.execute('INSERT INTO staff (name, email, password, college_id) VALUES (?, ?, ?, ?)', 
                          (name, email, hashed_password, college_id))
            db.commit()
            flash('Staff added successfully!', 'success')
        except sqlite3.IntegrityError:
            flash('Email already exists!', 'error')
        finally:
            db.close()
    
    return render_template('add_staff.html')

@app.route('/complaint/assign', methods=['POST'])
def assign_complaint():
    if 'user_id' not in session or session['user_type'] != 'college':
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    complaint_id = request.json.get('complaint_id')
    staff_id = request.json.get('staff_id')
    
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute('UPDATE complaints SET staff_id = ?, status = ? WHERE id = ?', 
                   (staff_id, 'In Progress', complaint_id))
    
    # Get complaint details for notification
    cursor.execute('SELECT title FROM complaints WHERE id = ?', (complaint_id,))
    complaint = cursor.fetchone()
    
    db.commit()
    db.close()
    
    # Notify staff about assignment (after closing main connection)
    create_notification('staff', staff_id, f'You have been assigned a complaint: {complaint["title"]}')
    
    return jsonify({'success': True})

@app.route('/complaint/update-status', methods=['POST'])
def update_status():
    if 'user_id' not in session or session['user_type'] != 'staff':
        return jsonify({'success': False, 'message': 'Unauthorized'})
    
    complaint_id = request.json.get('complaint_id')
    status = request.json.get('status')
    
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute('UPDATE complaints SET status = ? WHERE id = ?', (status, complaint_id))
    
    # Get complaint details for notification
    cursor.execute('SELECT title, student_id FROM complaints WHERE id = ?', (complaint_id,))
    complaint = cursor.fetchone()
    
    db.commit()
    db.close()
    
    # Notify student about status change (after closing main connection)
    if complaint['student_id']:
        create_notification('student', complaint['student_id'], 
                           f'Your complaint "{complaint["title"]}" status changed to {status}')
    
    return jsonify({'success': True})

@app.route('/forgot-password/<user_type>', methods=['GET', 'POST'])
def forgot_password(user_type):
    if request.method == 'POST':
        email = request.form['email']
        db = get_db()
        cursor = db.cursor()
        
        table = user_type + 's'
        cursor.execute(f'SELECT id FROM {table} WHERE email = ?', (email,))
        user = cursor.fetchone()
        
        if user:
            token = secrets.token_urlsafe(32)
            expires_at = datetime.now() + timedelta(hours=1)
            
            cursor.execute('INSERT INTO password_resets (user_type, user_id, token, expires_at) VALUES (?, ?, ?, ?)',
                          (user_type, user['id'], token, expires_at))
            db.commit()
            
            # In production, send email with reset link
            reset_link = url_for('reset_password', token=token, user_type=user_type, _external=True)
            flash(f'Reset link generated. In production, this would be emailed to you. Link: {reset_link}', 'info')
        else:
            flash('Email not found!', 'error')
        
        db.close()
    
    return render_template('forgot_password.html', user_type=user_type)

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute('SELECT user_type, user_id, expires_at FROM password_resets WHERE token = ?', (token,))
    reset_data = cursor.fetchone()
    
    if not reset_data or datetime.now() > datetime.fromisoformat(reset_data['expires_at']):
        flash('Invalid or expired reset token!', 'error')
        return redirect(url_for('index'))
    
    user_type = reset_data['user_type']
    user_id = reset_data['user_id']
    
    if request.method == 'POST':
        new_password = request.form['password']
        hashed_password = generate_password_hash(new_password)
        
        table = user_type + 's'
        cursor.execute(f'UPDATE {table} SET password = ? WHERE id = ?', (hashed_password, user_id))
        
        cursor.execute('DELETE FROM password_resets WHERE token = ?', (token,))
        db.commit()
        db.close()
        
        flash('Password reset successfully! Please login.', 'success')
        return redirect(url_for(f'{user_type}_login'))
    
    db.close()
    return render_template('reset_password.html', token=token)

@app.route('/notifications')
def get_notifications():
    if 'user_id' not in session or 'user_type' not in session:
        return jsonify([])
    
    db = get_db()
    cursor = db.cursor()
    cursor.execute('''SELECT * FROM notifications 
                      WHERE user_type = ? AND user_id = ? 
                      ORDER BY created_at DESC LIMIT 10''', 
                   (session['user_type'], session['user_id']))
    notifications = cursor.fetchall()
    
    notifications_list = []
    for notif in notifications:
        notifications_list.append({
            'id': notif['id'],
            'message': notif['message'],
            'is_read': bool(notif['is_read']),
            'created_at': notif['created_at']
        })
    
    db.close()
    return jsonify(notifications_list)

@app.route('/notifications/mark-read', methods=['POST'])
def mark_notifications_read():
    if 'user_id' not in session or 'user_type' not in session:
        return jsonify({'success': False})
    
    db = get_db()
    cursor = db.cursor()
    cursor.execute('''UPDATE notifications 
                      SET is_read = 1 
                      WHERE user_type = ? AND user_id = ?''', 
                   (session['user_type'], session['user_id']))
    db.commit()
    db.close()
    
    return jsonify({'success': True})

@app.route('/download/<filename>')
def download_file(filename):
    """Serve uploaded files"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully!', 'success')
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(host='0.0.0.0', port=port, debug=debug)

