const API_BASE = '';

let currentPage = 1;
let totalPages = 1;
let currentMediaList = [];
let currentViewerIndex = -1;

// Check authentication on page load
async function checkAuth() {
    try {
        const response = await fetch('/api/check-auth');
        const data = await response.json();
        if (data.authenticated) {
            showGallery();
        } else {
            showLogin();
        }
    } catch (error) {
        console.error('Auth check failed:', error);
        showLogin();
    }
}

function showLogin() {
    document.getElementById('loginScreen').classList.remove('hidden');
    document.getElementById('galleryScreen').classList.add('hidden');
    document.getElementById('mediaViewer').classList.add('hidden');
}

function showGallery() {
    document.getElementById('loginScreen').classList.add('hidden');
    document.getElementById('galleryScreen').classList.remove('hidden');
    loadMedia();
}

// Login form handler
document.getElementById('loginForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const errorDiv = document.getElementById('loginError');
    
    errorDiv.textContent = '';
    
    try {
        const response = await fetch('/api/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ username, password }),
            credentials: 'include'
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            showGallery();
        } else {
            errorDiv.textContent = data.error || 'Login failed';
        }
    } catch (error) {
        errorDiv.textContent = 'Network error. Please try again.';
        console.error('Login error:', error);
    }
});

// Logout handler
document.getElementById('logoutBtn').addEventListener('click', async () => {
    try {
        await fetch('/api/logout', {
            method: 'POST',
            credentials: 'include'
        });
        showLogin();
        document.getElementById('username').value = '';
        document.getElementById('password').value = '';
    } catch (error) {
        console.error('Logout error:', error);
    }
});

// Load media from API
async function loadMedia(page = 1) {
    const gallery = document.getElementById('gallery');
    const loading = document.getElementById('loading');
    const pagination = document.getElementById('pagination');
    
    gallery.innerHTML = '';
    loading.classList.remove('hidden');
    pagination.innerHTML = '';
    
    try {
        const response = await fetch(`/api/media?page=${page}&per_page=20`, {
            credentials: 'include'
        });
        
        if (response.status === 401) {
            showLogin();
            return;
        }
        
        const data = await response.json();
        currentMediaList = data.media;
        currentPage = data.page;
        totalPages = data.total_pages;
        
        renderGallery(data.media);
        renderPagination();
        
    } catch (error) {
        console.error('Error loading media:', error);
        gallery.innerHTML = '<p style="text-align: center; padding: 2rem;">Error loading media. Please refresh the page.</p>';
    } finally {
        loading.classList.add('hidden');
    }
}

// Render gallery grid
function renderGallery(mediaList) {
    const gallery = document.getElementById('gallery');
    gallery.innerHTML = '';
    
    if (mediaList.length === 0) {
        gallery.innerHTML = '<p style="text-align: center; padding: 2rem; grid-column: 1 / -1;">No media found. Upload some photos or videos to get started!</p>';
        return;
    }
    
    mediaList.forEach((item, index) => {
        const itemDiv = document.createElement('div');
        itemDiv.className = 'gallery-item';
        itemDiv.dataset.index = index;
        itemDiv.dataset.mediaId = item.id;
        
        const mediaElement = item.file_type === 'image' 
            ? document.createElement('img')
            : document.createElement('video');
        
        mediaElement.src = `/api/media/${item.id}/thumbnail`;
        mediaElement.loading = 'lazy';
        
        if (item.file_type === 'video') {
            mediaElement.muted = true;
        }
        
        const badge = document.createElement('div');
        badge.className = 'media-type-badge';
        badge.textContent = item.file_type === 'video' ? 'VIDEO' : 'IMG';
        
        itemDiv.appendChild(mediaElement);
        itemDiv.appendChild(badge);
        
        itemDiv.addEventListener('click', () => openViewer(index));
        
        gallery.appendChild(itemDiv);
    });
}

// Render pagination
function renderPagination() {
    const pagination = document.getElementById('pagination');
    pagination.innerHTML = '';
    
    if (totalPages <= 1) return;
    
    const prevBtn = document.createElement('button');
    prevBtn.textContent = 'Previous';
    prevBtn.disabled = currentPage === 1;
    prevBtn.addEventListener('click', () => {
        if (currentPage > 1) {
            loadMedia(currentPage - 1);
            window.scrollTo(0, 0);
        }
    });
    
    const nextBtn = document.createElement('button');
    nextBtn.textContent = 'Next';
    nextBtn.disabled = currentPage === totalPages;
    nextBtn.addEventListener('click', () => {
        if (currentPage < totalPages) {
            loadMedia(currentPage + 1);
            window.scrollTo(0, 0);
        }
    });
    
    pagination.appendChild(prevBtn);
    
    // Page numbers
    const maxVisiblePages = 5;
    let startPage = Math.max(1, currentPage - Math.floor(maxVisiblePages / 2));
    let endPage = Math.min(totalPages, startPage + maxVisiblePages - 1);
    
    if (endPage - startPage < maxVisiblePages - 1) {
        startPage = Math.max(1, endPage - maxVisiblePages + 1);
    }
    
    if (startPage > 1) {
        const firstBtn = document.createElement('button');
        firstBtn.textContent = '1';
        firstBtn.addEventListener('click', () => {
            loadMedia(1);
            window.scrollTo(0, 0);
        });
        pagination.appendChild(firstBtn);
        
        if (startPage > 2) {
            const dots = document.createElement('span');
            dots.textContent = '...';
            dots.style.padding = '0.5rem';
            pagination.appendChild(dots);
        }
    }
    
    for (let i = startPage; i <= endPage; i++) {
        const pageBtn = document.createElement('button');
        pageBtn.textContent = i;
        if (i === currentPage) {
            pageBtn.classList.add('active');
        }
        pageBtn.addEventListener('click', () => {
            loadMedia(i);
            window.scrollTo(0, 0);
        });
        pagination.appendChild(pageBtn);
    }
    
    if (endPage < totalPages) {
        if (endPage < totalPages - 1) {
            const dots = document.createElement('span');
            dots.textContent = '...';
            dots.style.padding = '0.5rem';
            pagination.appendChild(dots);
        }
        
        const lastBtn = document.createElement('button');
        lastBtn.textContent = totalPages;
        lastBtn.addEventListener('click', () => {
            loadMedia(totalPages);
            window.scrollTo(0, 0);
        });
        pagination.appendChild(lastBtn);
    }
    
    pagination.appendChild(nextBtn);
}

// Open media viewer
function openViewer(index) {
    currentViewerIndex = index;
    const item = currentMediaList[index];
    
    const viewer = document.getElementById('mediaViewer');
    const viewerImage = document.getElementById('viewerImage');
    const viewerVideo = document.getElementById('viewerVideo');
    
    if (item.file_type === 'image') {
        viewerImage.src = `/api/media/${item.id}`;
        viewerImage.classList.remove('hidden');
        viewerVideo.classList.add('hidden');
        viewerVideo.pause();
        viewerVideo.src = '';
    } else {
        viewerVideo.src = `/api/media/${item.id}`;
        viewerVideo.classList.remove('hidden');
        viewerImage.classList.add('hidden');
    }
    
    viewer.classList.remove('hidden');
    updateNavButtons();
    document.body.style.overflow = 'hidden';
}

// Close media viewer
function closeViewer() {
    const viewer = document.getElementById('mediaViewer');
    const viewerVideo = document.getElementById('viewerVideo');
    
    viewer.classList.add('hidden');
    viewerVideo.pause();
    viewerVideo.src = '';
    document.body.style.overflow = '';
    currentViewerIndex = -1;
}

document.getElementById('closeViewer').addEventListener('click', closeViewer);

// Navigation in viewer
function updateNavButtons() {
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');
    
    prevBtn.disabled = currentViewerIndex <= 0;
    nextBtn.disabled = currentViewerIndex >= currentMediaList.length - 1;
}

document.getElementById('prevBtn').addEventListener('click', () => {
    if (currentViewerIndex > 0) {
        openViewer(currentViewerIndex - 1);
    }
});

document.getElementById('nextBtn').addEventListener('click', () => {
    if (currentViewerIndex < currentMediaList.length - 1) {
        openViewer(currentViewerIndex + 1);
    }
});

// Keyboard navigation
document.addEventListener('keydown', (e) => {
    const viewer = document.getElementById('mediaViewer');
    if (viewer.classList.contains('hidden')) return;
    
    if (e.key === 'Escape') {
        closeViewer();
    } else if (e.key === 'ArrowLeft' && currentViewerIndex > 0) {
        openViewer(currentViewerIndex - 1);
    } else if (e.key === 'ArrowRight' && currentViewerIndex < currentMediaList.length - 1) {
        openViewer(currentViewerIndex + 1);
    }
});

// Upload functionality
const fileInput = document.getElementById('fileInput');
const uploadBtn = document.getElementById('uploadBtn');
const uploadProgress = document.getElementById('uploadProgress');

uploadBtn.addEventListener('click', () => {
    fileInput.click();
});

fileInput.addEventListener('change', async (e) => {
    const files = Array.from(e.target.files);
    
    if (files.length === 0) return;
    
    if (files.length > 10) {
        alert('Maximum 10 files allowed per upload');
        fileInput.value = '';
        return;
    }
    
    uploadBtn.disabled = true;
    uploadProgress.classList.remove('hidden');
    uploadProgress.textContent = `Uploading ${files.length} file(s)...`;
    
    const formData = new FormData();
    files.forEach(file => {
        formData.append('files', file);
    });
    
    try {
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData,
            credentials: 'include'
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            uploadProgress.textContent = `Successfully uploaded ${data.uploaded.length} file(s)!`;
            uploadProgress.style.color = 'var(--success-color)';
            
            // Reload gallery
            setTimeout(() => {
                loadMedia(currentPage);
                uploadProgress.classList.add('hidden');
                uploadProgress.style.color = '';
            }, 1500);
        } else {
            uploadProgress.textContent = data.error || 'Upload failed';
            uploadProgress.style.color = 'var(--error-color)';
            setTimeout(() => {
                uploadProgress.classList.add('hidden');
                uploadProgress.style.color = '';
            }, 3000);
        }
    } catch (error) {
        console.error('Upload error:', error);
        uploadProgress.textContent = 'Network error during upload';
        uploadProgress.style.color = 'var(--error-color)';
        setTimeout(() => {
            uploadProgress.classList.add('hidden');
            uploadProgress.style.color = '';
        }, 3000);
    } finally {
        uploadBtn.disabled = false;
        fileInput.value = '';
    }
});

// Initialize
checkAuth();

