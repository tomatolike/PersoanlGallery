import os
import hashlib
import secrets
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, session, send_file, send_from_directory
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from PIL import Image
import sqlite3
import json
import threading
import time
from pathlib import Path

# Load configuration
CONFIG_FILE = 'config.json'

def load_config():
    """Load configuration from config.json file"""
    if not os.path.exists(CONFIG_FILE):
        raise FileNotFoundError(f"Configuration file '{CONFIG_FILE}' not found. Please create it.")
    
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # Validate required fields
    if 'users' not in config:
        raise ValueError("Configuration must contain 'users' field")
    if 'server' not in config or 'port' not in config['server']:
        raise ValueError("Configuration must contain 'server.port' field")
    if 'storage' not in config:
        raise ValueError("Configuration must contain 'storage' field")
    if 'media_path' not in config['storage'] or 'thumbnail_path' not in config['storage']:
        raise ValueError("Configuration must contain 'storage.media_path' and 'storage.thumbnail_path' fields")
    
    return config

# Load configuration
CONFIG = load_config()

# Build user dictionary for authentication
USERS = {}
for user in CONFIG['users']:
    if 'username' not in user or 'password' not in user:
        raise ValueError("Each user in configuration must have 'username' and 'password' fields")
    USERS[user['username']] = user['password']

app = Flask(__name__, static_folder='static', static_url_path='')
app.config['SECRET_KEY'] = secrets.token_hex(32)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

# Use paths from configuration (resolve relative paths)
media_path = CONFIG['storage']['media_path']
thumbnail_path = CONFIG['storage']['thumbnail_path']

# Convert relative paths to absolute paths
if not os.path.isabs(media_path):
    media_path = os.path.abspath(os.path.join(os.path.dirname(__file__), media_path))
if not os.path.isabs(thumbnail_path):
    thumbnail_path = os.path.abspath(os.path.join(os.path.dirname(__file__), thumbnail_path))

app.config['UPLOAD_FOLDER'] = media_path
app.config['THUMBNAIL_FOLDER'] = thumbnail_path
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max file size
app.config['SCAN_INTERVAL'] = 300  # 5 minutes

Session(app)

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['THUMBNAIL_FOLDER'], exist_ok=True)

# Database setup
def init_db():
    conn = sqlite3.connect('gallery.db')
    c = conn.cursor()
    # Users table removed - now using config file for authentication
    c.execute('''CREATE TABLE IF NOT EXISTS media
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  filename TEXT NOT NULL,
                  filepath TEXT NOT NULL UNIQUE,
                  file_type TEXT NOT NULL,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  size INTEGER,
                  thumbnail_path TEXT)''')
    conn.commit()
    conn.close()

# Allowed extensions
ALLOWED_EXTENSIONS = {
    'image': ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'heic', 'heif', 'tiff', 'tif'],
    'video': ['mp4', 'mov', 'avi', 'mkv', 'webm', 'm4v', '3gp', 'flv', 'wmv']
}

def allowed_file(filename, media_type='both'):
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    if media_type == 'image':
        return ext in ALLOWED_EXTENSIONS['image']
    elif media_type == 'video':
        return ext in ALLOWED_EXTENSIONS['video']
    else:
        return ext in ALLOWED_EXTENSIONS['image'] + ALLOWED_EXTENSIONS['video']

def get_media_type(filename):
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    if ext in ALLOWED_EXTENSIONS['image']:
        return 'image'
    elif ext in ALLOWED_EXTENSIONS['video']:
        return 'video'
    return None

def generate_thumbnail(filepath, media_type, output_path):
    try:
        if media_type == 'image':
            img = Image.open(filepath)
            img.thumbnail((400, 400), Image.Resampling.LANCZOS)
            # Convert RGBA to RGB if necessary
            if img.mode == 'RGBA':
                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                rgb_img.paste(img, mask=img.split()[3])
                img = rgb_img
            img.save(output_path, 'JPEG', quality=85)
            return True
        elif media_type == 'video':
            # For videos, we'll create a placeholder or use first frame
            # In production, use ffmpeg for video thumbnails
            img = Image.new('RGB', (400, 300), color=(100, 100, 100))
            img.save(output_path, 'JPEG')
            return True
    except Exception as e:
        print(f"Error generating thumbnail: {e}")
        return False

def scan_media_directory():
    """Scan the media directory for files and add them to database"""
    media_dir = Path(app.config['UPLOAD_FOLDER'])
    conn = sqlite3.connect('gallery.db')
    c = conn.cursor()
    
    added_count = 0
    for file_path in media_dir.rglob('*'):
        if file_path.is_file() and allowed_file(file_path.name):
            filepath_str = str(file_path)
            # Check if already in database
            c.execute('SELECT id FROM media WHERE filepath = ?', (filepath_str,))
            if c.fetchone() is None:
                media_type = get_media_type(file_path.name)
                if media_type:
                    # Get file stats
                    stat = file_path.stat()
                    size = stat.st_size
                    created_at = datetime.fromtimestamp(stat.st_mtime)
                    
                    # Generate thumbnail path
                    thumbnail_filename = f"{file_path.stem}_thumb.jpg"
                    thumbnail_path = os.path.join(app.config['THUMBNAIL_FOLDER'], thumbnail_filename)
                    
                    # Generate thumbnail if it doesn't exist
                    if not os.path.exists(thumbnail_path):
                        generate_thumbnail(filepath_str, media_type, thumbnail_path)
                    
                    # Add to database
                    c.execute('''INSERT INTO media (filename, filepath, file_type, created_at, size, thumbnail_path)
                                 VALUES (?, ?, ?, ?, ?, ?)''',
                             (file_path.name, filepath_str, media_type, created_at, size, thumbnail_path))
                    added_count += 1
    
    conn.commit()
    conn.close()
    print(f"Scan completed. Added {added_count} new media files.")

def periodic_scan():
    """Periodically scan the media directory"""
    while True:
        time.sleep(app.config['SCAN_INTERVAL'])
        scan_media_directory()

# Start periodic scanning in background thread
scan_thread = threading.Thread(target=periodic_scan, daemon=True)
scan_thread.start()

# Initial scan on startup
scan_media_directory()

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    # Authenticate against config file users
    if username in USERS and USERS[username] == password:
        session['user_id'] = username  # Use username as ID since we're not using DB for users
        session['username'] = username
        session.permanent = True
        return jsonify({'success': True, 'username': username})
    else:
        return jsonify({'error': 'Invalid username or password'}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True})

@app.route('/api/check-auth', methods=['GET'])
def check_auth():
    if 'user_id' in session:
        return jsonify({'authenticated': True, 'username': session.get('username')})
    return jsonify({'authenticated': False}), 401

@app.route('/api/media', methods=['GET'])
def get_media():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    conn = sqlite3.connect('gallery.db')
    c = conn.cursor()
    
    # Get total count
    c.execute('SELECT COUNT(*) FROM media')
    total = c.fetchone()[0]
    
    # Get paginated results
    offset = (page - 1) * per_page
    c.execute('''SELECT id, filename, filepath, file_type, created_at, uploaded_at, size, thumbnail_path
                 FROM media ORDER BY created_at DESC LIMIT ? OFFSET ?''',
              (per_page, offset))
    
    media_list = []
    for row in c.fetchall():
        media_list.append({
            'id': row[0],
            'filename': row[1],
            'filepath': row[2],
            'file_type': row[3],
            'created_at': row[4],
            'uploaded_at': row[5],
            'size': row[6],
            'thumbnail_path': row[7]
        })
    
    conn.close()
    
    return jsonify({
        'media': media_list,
        'total': total,
        'page': page,
        'per_page': per_page,
        'total_pages': (total + per_page - 1) // per_page
    })

@app.route('/api/media/<int:media_id>', methods=['GET'])
def get_media_file(media_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = sqlite3.connect('gallery.db')
    c = conn.cursor()
    c.execute('SELECT filepath, file_type FROM media WHERE id = ?', (media_id,))
    media = c.fetchone()
    conn.close()
    
    if not media:
        return jsonify({'error': 'Media not found'}), 404
    
    filepath, file_type = media
    return send_file(filepath)

@app.route('/api/media/<int:media_id>/thumbnail', methods=['GET'])
def get_thumbnail(media_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = sqlite3.connect('gallery.db')
    c = conn.cursor()
    c.execute('SELECT thumbnail_path FROM media WHERE id = ?', (media_id,))
    result = c.fetchone()
    conn.close()
    
    if not result or not result[0] or not os.path.exists(result[0]):
        return jsonify({'error': 'Thumbnail not found'}), 404
    
    return send_file(result[0])

@app.route('/api/upload', methods=['POST'])
def upload_files():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    if 'files' not in request.files:
        return jsonify({'error': 'No files provided'}), 400
    
    files = request.files.getlist('files')
    
    if len(files) > 10:
        return jsonify({'error': 'Maximum 10 files allowed per upload'}), 400
    
    uploaded_files = []
    conn = sqlite3.connect('gallery.db')
    c = conn.cursor()
    
    for file in files:
        if file.filename == '':
            continue
        
        if not allowed_file(file.filename):
            continue
        
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # Handle duplicate filenames
        counter = 1
        base_name, ext = os.path.splitext(filename)
        while os.path.exists(filepath):
            filename = f"{base_name}_{counter}{ext}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            counter += 1
        
        try:
            file.save(filepath)
            media_type = get_media_type(filename)
            stat = os.stat(filepath)
            size = stat.st_size
            created_at = datetime.fromtimestamp(stat.st_mtime)
            
            # Generate thumbnail
            thumbnail_filename = f"{os.path.splitext(filename)[0]}_thumb.jpg"
            thumbnail_path = os.path.join(app.config['THUMBNAIL_FOLDER'], thumbnail_filename)
            generate_thumbnail(filepath, media_type, thumbnail_path)
            
            # Add to database
            c.execute('''INSERT INTO media (filename, filepath, file_type, created_at, size, thumbnail_path)
                         VALUES (?, ?, ?, ?, ?, ?)''',
                     (filename, filepath, media_type, created_at, size, thumbnail_path))
            
            uploaded_files.append({
                'filename': filename,
                'file_type': media_type,
                'size': size
            })
        except Exception as e:
            print(f"Error uploading file {filename}: {e}")
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'uploaded': uploaded_files})

if __name__ == '__main__':
    init_db()
    
    # Print configuration info
    print(f"Configuration loaded from {CONFIG_FILE}")
    print(f"Media path: {app.config['UPLOAD_FOLDER']}")
    print(f"Thumbnail path: {app.config['THUMBNAIL_FOLDER']}")
    print(f"Server port: {CONFIG['server']['port']}")
    print(f"Configured users: {', '.join(USERS.keys())}")
    
    # Run app with configured port
    app.run(debug=True, host='0.0.0.0', port=CONFIG['server']['port'])

