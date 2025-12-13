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
    if 'admin' not in config:
        raise ValueError("Configuration must contain 'admin' field")
    if 'username' not in config['admin'] or 'password' not in config['admin']:
        raise ValueError("Admin configuration must have 'username' and 'password' fields")
    if 'server' not in config or 'port' not in config['server']:
        raise ValueError("Configuration must contain 'server.port' field")
    if 'storage' not in config:
        raise ValueError("Configuration must contain 'storage' field")
    if 'media_path' not in config['storage'] or 'thumbnail_path' not in config['storage']:
        raise ValueError("Configuration must contain 'storage.media_path' and 'storage.thumbnail_path' fields")
    
    return config

# Load configuration
CONFIG = load_config()

# Admin credentials from config
if 'admin' not in CONFIG:
    raise ValueError("Configuration must contain 'admin' field with username and password")
if 'username' not in CONFIG['admin'] or 'password' not in CONFIG['admin']:
    raise ValueError("Admin configuration must have 'username' and 'password' fields")

ADMIN_USERNAME = CONFIG['admin']['username']
ADMIN_PASSWORD = CONFIG['admin']['password']

app = Flask(__name__, static_folder='static', static_url_path='')
app.config['SECRET_KEY'] = secrets.token_hex(32)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)

# Helper function to get user-specific storage paths
def get_user_storage_paths(username, base_media_path, base_thumbnail_path):
    """Get storage paths for a specific user, replacing {username} placeholder"""
    media_path = base_media_path.replace('{username}', username)
    thumbnail_path = base_thumbnail_path.replace('{username}', username)
    
    # Convert relative paths to absolute paths
    if not os.path.isabs(media_path):
        media_path = os.path.abspath(os.path.join(os.path.dirname(__file__), media_path))
    if not os.path.isabs(thumbnail_path):
        thumbnail_path = os.path.abspath(os.path.join(os.path.dirname(__file__), thumbnail_path))
    
    return media_path, thumbnail_path

# Use paths from configuration (base paths with {username} placeholder)
base_media_path = CONFIG['storage']['media_path']
base_thumbnail_path = CONFIG['storage']['thumbnail_path']

app.config['BASE_MEDIA_PATH'] = base_media_path
app.config['BASE_THUMBNAIL_PATH'] = base_thumbnail_path
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max file size
app.config['SCAN_INTERVAL'] = 300  # 5 minutes

Session(app)

# Helper function to ensure user directories exist
def ensure_user_directories(username):
    """Create media and thumbnail directories for a user if they don't exist"""
    media_path, thumbnail_path = get_user_storage_paths(username, base_media_path, base_thumbnail_path)
    os.makedirs(media_path, exist_ok=True)
    os.makedirs(thumbnail_path, exist_ok=True)

# Ensure admin directories exist
ensure_user_directories(ADMIN_USERNAME)

# Database setup
def init_db():
    conn = sqlite3.connect('gallery.db')
    c = conn.cursor()
    
    # Users table for normal users (admin is in config)
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE NOT NULL,
                  password_hash TEXT NOT NULL,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Media table with owner
    c.execute('''CREATE TABLE IF NOT EXISTS media
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  filename TEXT NOT NULL,
                  filepath TEXT NOT NULL UNIQUE,
                  file_type TEXT NOT NULL,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  size INTEGER,
                  thumbnail_path TEXT,
                  owner_username TEXT NOT NULL)''')
    
    # Add owner_username column if it doesn't exist (for migration)
    try:
        c.execute('ALTER TABLE media ADD COLUMN owner_username TEXT')
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists
    
    # Shares table to track gallery sharing
    c.execute('''CREATE TABLE IF NOT EXISTS shares
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  owner_username TEXT NOT NULL,
                  shared_with_username TEXT NOT NULL,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  UNIQUE(owner_username, shared_with_username))''')
    
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
    """Scan all user media directories for files and add them to database"""
    conn = sqlite3.connect('gallery.db')
    c = conn.cursor()
    
    # Get all usernames (admin + database users)
    usernames = [ADMIN_USERNAME]
    c.execute('SELECT username FROM users')
    for row in c.fetchall():
        usernames.append(row[0])
    
    total_added = 0
    # Scan each user's directory
    for username in usernames:
        media_path, thumbnail_path = get_user_storage_paths(
            username, 
            app.config['BASE_MEDIA_PATH'], 
            app.config['BASE_THUMBNAIL_PATH']
        )
        
        media_dir = Path(media_path)
        if not media_dir.exists():
            continue
            
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
                        user_thumbnail_path = os.path.join(thumbnail_path, thumbnail_filename)
                        
                        # Ensure thumbnail directory exists
                        os.makedirs(thumbnail_path, exist_ok=True)
                        
                        # Generate thumbnail if it doesn't exist
                        if not os.path.exists(user_thumbnail_path):
                            generate_thumbnail(filepath_str, media_type, user_thumbnail_path)
                        
                        # Add to database with owner
                        c.execute('''INSERT INTO media (filename, filepath, file_type, created_at, size, thumbnail_path, owner_username)
                                     VALUES (?, ?, ?, ?, ?, ?, ?)''',
                                 (file_path.name, filepath_str, media_type, created_at, size, user_thumbnail_path, username))
                        added_count += 1
        total_added += added_count
        if added_count > 0:
            print(f"Scan completed for {username}. Added {added_count} new media files.")
    
    conn.commit()
    conn.close()
    if total_added > 0:
        print(f"Total scan completed. Added {total_added} new media files.")

def periodic_scan():
    """Periodically scan the media directory"""
    while True:
        time.sleep(app.config['SCAN_INTERVAL'])
        scan_media_directory()

# Note: Scan initialization moved to if __name__ == '__main__' block
# after database initialization

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
    
    # Check if admin
    if username == ADMIN_USERNAME:
        if password == ADMIN_PASSWORD:
            session['user_id'] = username
            session['username'] = username
            session['is_admin'] = True
            session.permanent = True
            return jsonify({'success': True, 'username': username, 'is_admin': True})
        else:
            return jsonify({'error': 'Invalid username or password'}), 401
    
    # Check normal users in database
    conn = sqlite3.connect('gallery.db')
    c = conn.cursor()
    c.execute('SELECT password_hash FROM users WHERE username = ?', (username,))
    user = c.fetchone()
    conn.close()
    
    if user and check_password_hash(user[0], password):
        session['user_id'] = username
        session['username'] = username
        session['is_admin'] = False
        session.permanent = True
        return jsonify({'success': True, 'username': username, 'is_admin': False})
    else:
        return jsonify({'error': 'Invalid username or password'}), 401

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True})

@app.route('/api/check-auth', methods=['GET'])
def check_auth():
    if 'user_id' in session:
        return jsonify({
            'authenticated': True, 
            'username': session.get('username'),
            'is_admin': session.get('is_admin', False)
        })
    return jsonify({'authenticated': False}), 401

@app.route('/api/filter-options', methods=['GET'])
def get_filter_options():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int)
    
    conn = sqlite3.connect('gallery.db')
    c = conn.cursor()
    
    # Get available years
    c.execute("SELECT DISTINCT strftime('%Y', created_at) as year FROM media ORDER BY year DESC")
    years = [row[0] for row in c.fetchall()]
    
    months = []
    days = []
    
    # Get available months for selected year
    if year is not None:
        c.execute("SELECT DISTINCT strftime('%m', created_at) as month FROM media WHERE strftime('%Y', created_at) = ? ORDER BY month DESC", (str(year),))
        months = [int(row[0]) for row in c.fetchall()]
        
        # Get available days for selected year and month
        if month is not None:
            c.execute("SELECT DISTINCT strftime('%d', created_at) as day FROM media WHERE strftime('%Y', created_at) = ? AND strftime('%m', created_at) = ? ORDER BY day DESC", (str(year), f"{month:02d}"))
            days = [int(row[0]) for row in c.fetchall()]
    
    conn.close()
    
    return jsonify({
        'years': years,
        'months': months,
        'days': days
    })

@app.route('/api/media', methods=['GET'])
def get_media():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    current_user = session['username']
    owner_username = request.args.get('owner', current_user)  # Default to current user's gallery
    
    # Check if user has access to this gallery (owner or shared with)
    if owner_username != current_user:
        conn = sqlite3.connect('gallery.db')
        c = conn.cursor()
        c.execute('SELECT id FROM shares WHERE owner_username = ? AND shared_with_username = ?', 
                  (owner_username, current_user))
        if c.fetchone() is None:
            conn.close()
            return jsonify({'error': 'Access denied'}), 403
        conn.close()
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int)
    day = request.args.get('day', type=int)
    
    conn = sqlite3.connect('gallery.db')
    c = conn.cursor()
    
    # Build WHERE clause for owner and date filtering
    where_clauses = ["owner_username = ?"]
    params = [owner_username]
    
    if year is not None:
        where_clauses.append("strftime('%Y', created_at) = ?")
        params.append(str(year))
        if month is not None:
            where_clauses.append("strftime('%m', created_at) = ?")
            params.append(f"{month:02d}")
            if day is not None:
                where_clauses.append("strftime('%d', created_at) = ?")
                params.append(f"{day:02d}")
    
    where_clause = "WHERE " + " AND ".join(where_clauses)
    
    # Get total count
    c.execute(f'SELECT COUNT(*) FROM media {where_clause}', params)
    total = c.fetchone()[0]
    
    # Get paginated results
    offset = (page - 1) * per_page
    query_params = params + [per_page, offset]
    c.execute(f'''SELECT id, filename, filepath, file_type, created_at, uploaded_at, size, thumbnail_path, owner_username
                 FROM media {where_clause} ORDER BY created_at DESC LIMIT ? OFFSET ?''',
              query_params)
    
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
            'thumbnail_path': row[7],
            'owner_username': row[8]
        })
    
    conn.close()
    
    return jsonify({
        'media': media_list,
        'total': total,
        'page': page,
        'per_page': per_page,
        'total_pages': (total + per_page - 1) // per_page,
        'owner_username': owner_username
    })

@app.route('/api/media/<int:media_id>', methods=['GET'])
def get_media_file(media_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    current_user = session['username']
    conn = sqlite3.connect('gallery.db')
    c = conn.cursor()
    c.execute('SELECT filepath, file_type, owner_username FROM media WHERE id = ?', (media_id,))
    media = c.fetchone()
    
    if not media:
        conn.close()
        return jsonify({'error': 'Media not found'}), 404
    
    filepath, file_type, owner_username = media
    
    # Check access
    if owner_username != current_user:
        c.execute('SELECT id FROM shares WHERE owner_username = ? AND shared_with_username = ?', 
                  (owner_username, current_user))
        if c.fetchone() is None:
            conn.close()
            return jsonify({'error': 'Access denied'}), 403
    
    conn.close()
    return send_file(filepath)

@app.route('/api/media/<int:media_id>/thumbnail', methods=['GET'])
def get_thumbnail(media_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    current_user = session['username']
    conn = sqlite3.connect('gallery.db')
    c = conn.cursor()
    c.execute('SELECT thumbnail_path, owner_username FROM media WHERE id = ?', (media_id,))
    result = c.fetchone()
    
    if not result:
        conn.close()
        return jsonify({'error': 'Thumbnail not found'}), 404
    
    thumbnail_path, owner_username = result
    
    # Check access
    if owner_username != current_user:
        c.execute('SELECT id FROM shares WHERE owner_username = ? AND shared_with_username = ?', 
                  (owner_username, current_user))
        if c.fetchone() is None:
            conn.close()
            return jsonify({'error': 'Access denied'}), 403
    
    conn.close()
    
    if not thumbnail_path or not os.path.exists(thumbnail_path):
        return jsonify({'error': 'Thumbnail not found'}), 404
    
    return send_file(thumbnail_path)

@app.route('/api/upload', methods=['POST'])
def upload_files():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Users can only upload to their own gallery
    current_user = session['username']
    
    if 'files' not in request.files:
        return jsonify({'error': 'No files provided'}), 400
    
    files = request.files.getlist('files')
    
    if len(files) > 10:
        return jsonify({'error': 'Maximum 10 files allowed per upload'}), 400
    
    # Get user-specific storage paths
    media_path, thumbnail_path = get_user_storage_paths(
        current_user,
        app.config['BASE_MEDIA_PATH'],
        app.config['BASE_THUMBNAIL_PATH']
    )
    
    # Ensure directories exist
    os.makedirs(media_path, exist_ok=True)
    os.makedirs(thumbnail_path, exist_ok=True)
    
    uploaded_files = []
    conn = sqlite3.connect('gallery.db')
    c = conn.cursor()
    
    for file in files:
        if file.filename == '':
            continue
        
        if not allowed_file(file.filename):
            continue
        
        filename = secure_filename(file.filename)
        filepath = os.path.join(media_path, filename)
        
        # Handle duplicate filenames
        counter = 1
        base_name, ext = os.path.splitext(filename)
        while os.path.exists(filepath):
            filename = f"{base_name}_{counter}{ext}"
            filepath = os.path.join(media_path, filename)
            counter += 1
        
        try:
            file.save(filepath)
            media_type = get_media_type(filename)
            stat = os.stat(filepath)
            size = stat.st_size
            created_at = datetime.fromtimestamp(stat.st_mtime)
            
            # Generate thumbnail
            thumbnail_filename = f"{os.path.splitext(filename)[0]}_thumb.jpg"
            user_thumbnail_path = os.path.join(thumbnail_path, thumbnail_filename)
            generate_thumbnail(filepath, media_type, user_thumbnail_path)
            
            # Add to database with owner
            c.execute('''INSERT INTO media (filename, filepath, file_type, created_at, size, thumbnail_path, owner_username)
                         VALUES (?, ?, ?, ?, ?, ?, ?)''',
                     (filename, filepath, media_type, created_at, size, user_thumbnail_path, current_user))
            
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

@app.route('/api/galleries', methods=['GET'])
def get_accessible_galleries():
    """Get list of galleries the current user has access to (own + shared)"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    current_user = session['username']
    conn = sqlite3.connect('gallery.db')
    c = conn.cursor()
    
    galleries = [{'username': current_user, 'type': 'own'}]
    
    # Get galleries shared with current user
    c.execute('SELECT owner_username FROM shares WHERE shared_with_username = ?', (current_user,))
    for row in c.fetchall():
        galleries.append({'username': row[0], 'type': 'shared'})
    
    conn.close()
    
    return jsonify({'galleries': galleries})

@app.route('/api/share', methods=['POST'])
def share_gallery():
    """Share current user's gallery with another user"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    current_user = session['username']
    data = request.json
    share_with = data.get('username', '').strip()
    
    if not share_with:
        return jsonify({'error': 'Username required'}), 400
    
    if share_with == current_user:
        return jsonify({'error': 'Cannot share with yourself'}), 400
    
    # Check if user exists (admin or in database)
    user_exists = False
    if share_with == ADMIN_USERNAME:
        user_exists = True
    else:
        conn_check = sqlite3.connect('gallery.db')
        c_check = conn_check.cursor()
        c_check.execute('SELECT id FROM users WHERE username = ?', (share_with,))
        user_exists = c_check.fetchone() is not None
        conn_check.close()
    
    if not user_exists:
        return jsonify({'error': 'User not found'}), 404
    
    conn = sqlite3.connect('gallery.db')
    c = conn.cursor()
    
    # Check if already shared
    c.execute('SELECT id FROM shares WHERE owner_username = ? AND shared_with_username = ?', 
              (current_user, share_with))
    if c.fetchone():
        conn.close()
        return jsonify({'error': 'Gallery already shared with this user'}), 400
    
    # Add share
    c.execute('INSERT INTO shares (owner_username, shared_with_username) VALUES (?, ?)', 
              (current_user, share_with))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': f'Gallery shared with {share_with}'})

@app.route('/api/unshare', methods=['POST'])
def unshare_gallery():
    """Unshare current user's gallery with another user"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    current_user = session['username']
    data = request.json
    unshare_with = data.get('username', '').strip()
    
    if not unshare_with:
        return jsonify({'error': 'Username required'}), 400
    
    conn = sqlite3.connect('gallery.db')
    c = conn.cursor()
    
    c.execute('DELETE FROM shares WHERE owner_username = ? AND shared_with_username = ?', 
              (current_user, unshare_with))
    
    if c.rowcount == 0:
        conn.close()
        return jsonify({'error': 'Share not found'}), 404
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': f'Gallery unshared with {unshare_with}'})

@app.route('/admin')
def admin_page():
    """Admin page route"""
    return send_from_directory('static', 'admin.html')

@app.route('/api/admin/users', methods=['GET'])
def get_all_users():
    """Get all users (admin only)"""
    if 'user_id' not in session or not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = sqlite3.connect('gallery.db')
    c = conn.cursor()
    c.execute('SELECT id, username, created_at FROM users ORDER BY created_at DESC')
    users = []
    for row in c.fetchall():
        users.append({
            'id': row[0],
            'username': row[1],
            'created_at': row[2]
        })
    conn.close()
    
    return jsonify({'users': users})

@app.route('/api/admin/users', methods=['POST'])
def create_user():
    """Create a new user (admin only)"""
    if 'user_id' not in session or not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    # Validate username
    if username == ADMIN_USERNAME:
        return jsonify({'error': 'Username conflicts with admin username'}), 400
    
    if len(username) < 3:
        return jsonify({'error': 'Username must be at least 3 characters'}), 400
    
    if len(password) < 4:
        return jsonify({'error': 'Password must be at least 4 characters'}), 400
    
    conn = sqlite3.connect('gallery.db')
    c = conn.cursor()
    
    # Check if username already exists
    c.execute('SELECT id FROM users WHERE username = ?', (username,))
    if c.fetchone():
        conn.close()
        return jsonify({'error': 'Username already exists'}), 400
    
    # Create user
    password_hash = generate_password_hash(password)
    c.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)', (username, password_hash))
    conn.commit()
    conn.close()
    
    # Create user directories
    ensure_user_directories(username)
    
    return jsonify({'success': True, 'message': f'User {username} created successfully'})

@app.route('/api/admin/users/<username>', methods=['DELETE'])
def delete_user(username):
    """Delete a user (admin only)"""
    if 'user_id' not in session or not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    if username == ADMIN_USERNAME:
        return jsonify({'error': 'Cannot delete admin user'}), 400
    
    conn = sqlite3.connect('gallery.db')
    c = conn.cursor()
    
    # Check if user exists
    c.execute('SELECT id FROM users WHERE username = ?', (username,))
    if not c.fetchone():
        conn.close()
        return jsonify({'error': 'User not found'}), 404
    
    # Delete user's shares
    c.execute('DELETE FROM shares WHERE owner_username = ? OR shared_with_username = ?', (username, username))
    
    # Delete user's media records (files remain on disk)
    c.execute('DELETE FROM media WHERE owner_username = ?', (username,))
    
    # Delete user
    c.execute('DELETE FROM users WHERE username = ?', (username,))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': f'User {username} deleted successfully'})

if __name__ == '__main__':
    init_db()
    
    # Ensure directories exist for all existing users in database
    conn = sqlite3.connect('gallery.db')
    c = conn.cursor()
    try:
        c.execute('SELECT username FROM users')
        for row in c.fetchall():
            ensure_user_directories(row[0])
    except sqlite3.OperationalError:
        pass  # Table might not exist yet, but init_db() should have created it
    conn.close()
    
    # Start periodic scanning in background thread (after DB is initialized)
    scan_thread = threading.Thread(target=periodic_scan, daemon=True)
    scan_thread.start()
    
    # Initial scan on startup
    scan_media_directory()
    
    # Print configuration info
    print(f"Configuration loaded from {CONFIG_FILE}")
    print(f"Base media path: {app.config['BASE_MEDIA_PATH']}")
    print(f"Base thumbnail path: {app.config['BASE_THUMBNAIL_PATH']}")
    print(f"Server port: {CONFIG['server']['port']}")
    print(f"Admin username: {ADMIN_USERNAME}")
    
    # Run app with configured port
    app.run(debug=True, host='0.0.0.0', port=CONFIG['server']['port'])

