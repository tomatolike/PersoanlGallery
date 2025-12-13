# Personal Gallery

A web-based personal gallery application for viewing and managing photos and videos.

## Features

- **Authentication**: Secure login with username and password
- **Session Management**: Persistent sessions with cookies (30-day expiry)
- **Media Gallery**: Scrollable gallery with thumbnails, sorted by creation time (latest first)
- **Pagination**: Efficient handling of large media collections
- **Full Media Viewer**: Click any thumbnail to view full-size photos or videos
- **Batch Upload**: Upload up to 10 files at a time
- **Mobile Optimized**: Responsive design optimized for iPhone and mobile devices
- **Multiple Formats**: Supports various image (JPG, PNG, GIF, HEIC, WebP, etc.) and video formats (MP4, MOV, AVI, etc.)
- **Auto-Scanning**: Automatically scans media directory on startup and periodically (every 5 minutes)

## Installation

1. Install Python 3.8 or higher

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create configuration file:
```bash
cp config.example.json config.json
```

4. Edit `config.json` to configure admin credentials:
   - **Admin**: Set admin username and password
   - **Server Port**: Set the `server.port` value
   - **Storage Paths**: Configure `storage.media_path` and `storage.thumbnail_path` (use `{username}` placeholder)
   
   Example:
   ```json
   {
     "admin": {
       "username": "admin",
       "password": "your_secure_password"
     },
     "server": {
       "port": 5000
     },
     "storage": {
       "media_path": "./media/{username}",
       "thumbnail_path": "./thumbnails/{username}"
     }
   }
   ```

5. Run the application:
```bash
python app.py
```

The application will be available at `http://localhost:<port>` (default: 5000)

**Important**: 
- The `config.json` file contains passwords in plain text. Keep it secure and never commit it to version control.
- Use absolute paths for `media_path` and `thumbnail_path` if you want to store files in a different location.

## Usage

1. **Login**: Enter your username and password on the login page
2. **View Gallery**: Browse your photos and videos in the scrollable gallery
3. **View Full Media**: Click any thumbnail to view the full-size image or video
4. **Upload Media**: Click "Upload Media" button to select and upload files (max 10 at a time)
5. **Navigate**: Use pagination controls at the bottom to navigate through pages
6. **Mobile**: The interface is optimized for mobile devices and touch interactions

## Media Storage

- Media files are stored in the directory specified by `storage.media_path` in `config.json` (default: `./media`)
- Thumbnails are stored in the directory specified by `storage.thumbnail_path` in `config.json` (default: `./thumbnails`)
- The application automatically scans the media directory on startup and every 5 minutes
- You can manually place files in the media directory and they will be automatically detected
- Both relative and absolute paths are supported in the configuration file

## Database

The application uses SQLite database (`gallery.db`) to store:
- Normal user accounts (admin is configured in `config.json`)
- Media file metadata (filename, path, type, creation time, etc.)
- Gallery sharing relationships

**Note**: 
- Admin user credentials are stored in `config.json`
- Normal users are created through the admin panel and stored in the database
- User directories are automatically created when users are added

## Configuration

All configuration is done through the `config.json` file:

- **Admin**: Configure admin username and password in `config.json`
- **Server Port**: Change the `server.port` value in `config.json`
- **Storage Paths**: Configure `storage.media_path` and `storage.thumbnail_path` in `config.json` (use `{username}` placeholder for per-user directories)

**User Management**:
- Admin users log in to access the admin panel (`/admin`)
- Admin can create, view, and delete normal users through the admin panel
- Normal users are stored in the database and their directories are automatically created

Additional settings can be modified in `app.py`:
- `SCAN_INTERVAL`: How often to scan for new media files (default: 300 seconds)
- `MAX_CONTENT_LENGTH`: Maximum file size for uploads (default: 500MB)
- `PERMANENT_SESSION_LIFETIME`: Session duration (default: 30 days)

## Production Deployment

For production deployment on Linux:

1. Use a production WSGI server like Gunicorn:
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

2. Set up a reverse proxy (nginx) for better performance and HTTPS

3. Set `SESSION_COOKIE_SECURE = True` in `app.py` if using HTTPS

4. Change the default password and consider implementing password complexity requirements

5. Set appropriate file permissions for the `media/` and `thumbnails/` directories

## Supported Formats

**Images**: JPG, JPEG, PNG, GIF, BMP, WebP, HEIC, HEIF, TIFF, TIF

**Videos**: MP4, MOV, AVI, MKV, WebM, M4V, 3GP, FLV, WMV

## Browser Support

- Modern browsers (Chrome, Firefox, Safari, Edge)
- Mobile browsers (Safari on iOS, Chrome on Android)
- Optimized for iPhone/iPad

## Security Notes

- Passwords are hashed using Werkzeug's password hashing
- Sessions are managed securely with Flask-Session
- File uploads are validated for allowed extensions
- File names are sanitized to prevent directory traversal attacks

