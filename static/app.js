const API_BASE = '';

let currentPage = 1;
let totalPages = 1;
let currentMediaList = [];
let currentViewerIndex = -1;
let currentFilters = {
    year: null,
    month: null,
    day: null
};
let availableFilterOptions = {
    years: [],
    months: [],
    days: []
};
let currentGalleryOwner = null; // Current user's username (their own gallery by default)
let accessibleGalleries = [];

// Check authentication on page load
async function checkAuth() {
    try {
        const response = await fetch('/api/check-auth');
        const data = await response.json();
        if (data.authenticated) {
            if (data.is_admin) {
                // Redirect admin to admin panel
                window.location.href = '/admin';
            } else {
                // Show gallery for normal users
                showGallery();
            }
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

async function showGallery() {
    document.getElementById('loginScreen').classList.add('hidden');
    document.getElementById('galleryScreen').classList.remove('hidden');
    await loadAccessibleGalleries();
    // Set current gallery owner to logged-in user initially
    const authResponse = await fetch('/api/check-auth', { credentials: 'include' });
    if (authResponse.ok) {
        const authData = await authResponse.json();
        currentGalleryOwner = authData.username;
        updateGallerySelector();
        
        // Enable upload section (viewing own gallery)
        const uploadSection = document.querySelector('.upload-section');
        uploadSection.classList.remove('disabled');
    }
    loadFilterOptions();
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
            if (data.is_admin) {
                // Redirect admin to admin panel
                window.location.href = '/admin';
            } else {
                // Show gallery for normal users
                showGallery();
            }
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

// Load accessible galleries
async function loadAccessibleGalleries() {
    try {
        const response = await fetch('/api/galleries', {
            credentials: 'include'
        });
        
        if (response.ok) {
            const data = await response.json();
            accessibleGalleries = data.galleries;
            updateGallerySelector();
        }
    } catch (error) {
        console.error('Error loading accessible galleries:', error);
    }
}

// Update gallery selector dropdown
function updateGallerySelector() {
    const selector = document.getElementById('gallerySelect');
    selector.innerHTML = '';
    
    accessibleGalleries.forEach(gallery => {
        const option = document.createElement('option');
        option.value = gallery.username;
        option.textContent = gallery.username + (gallery.type === 'own' ? ' (My Gallery)' : ' (Shared)');
        if (gallery.username === currentGalleryOwner) {
            option.selected = true;
        }
        selector.appendChild(option);
    });
}

// Load filter options from API
async function loadFilterOptions(year = null, month = null) {
    try {
        let url = `/api/filter-options?owner=${currentGalleryOwner}`;
        if (year !== null) {
            url += `&year=${year}`;
            if (month !== null) {
                url += `&month=${month}`;
            }
        }
        
        const response = await fetch(url, {
            credentials: 'include'
        });
        
        if (response.ok) {
            const data = await response.json();
            availableFilterOptions = data;
            populateFilterDropdowns();
        }
    } catch (error) {
        console.error('Error loading filter options:', error);
    }
}

// Populate filter dropdowns
function populateFilterDropdowns() {
    const yearSelect = document.getElementById('yearFilter');
    const monthSelect = document.getElementById('monthFilter');
    const daySelect = document.getElementById('dayFilter');
    
    // Populate years (keep current selection if valid)
    const selectedYear = yearSelect.value;
    yearSelect.innerHTML = '<option value="">Any Year</option>';
    availableFilterOptions.years.forEach(year => {
        const option = document.createElement('option');
        option.value = year;
        option.textContent = year;
        if (selectedYear === year) {
            option.selected = true;
        }
        yearSelect.appendChild(option);
    });
    
    // Populate months (only if year is selected)
    if (currentFilters.year !== null) {
        monthSelect.disabled = false;
        const selectedMonth = monthSelect.value;
        monthSelect.innerHTML = '<option value="">Any Month</option>';
        availableFilterOptions.months.forEach(month => {
            const option = document.createElement('option');
            option.value = month;
            option.textContent = new Date(2000, month - 1, 1).toLocaleString('default', { month: 'long' });
            if (selectedMonth === month.toString()) {
                option.selected = true;
            }
            monthSelect.appendChild(option);
        });
    } else {
        monthSelect.disabled = true;
        monthSelect.innerHTML = '<option value="">Any Month</option>';
        currentFilters.month = null;
    }
    
    // Populate days (only if year and month are selected)
    if (currentFilters.year !== null && currentFilters.month !== null) {
        daySelect.disabled = false;
        const selectedDay = daySelect.value;
        daySelect.innerHTML = '<option value="">Any Day</option>';
        availableFilterOptions.days.forEach(day => {
            const option = document.createElement('option');
            option.value = day;
            option.textContent = day;
            if (selectedDay === day.toString()) {
                option.selected = true;
            }
            daySelect.appendChild(option);
        });
    } else {
        daySelect.disabled = true;
        daySelect.innerHTML = '<option value="">Any Day</option>';
        currentFilters.day = null;
    }
}

// Load media from API
async function loadMedia(page = 1) {
    const gallery = document.getElementById('gallery');
    const loading = document.getElementById('loading');
    const pagination = document.getElementById('pagination');
    
    gallery.innerHTML = '';
    loading.classList.remove('hidden');
    pagination.innerHTML = '';
    
    try {
        // Build query string with filters and gallery owner
        let url = `/api/media?page=${page}&per_page=20&owner=${currentGalleryOwner}`;
        if (currentFilters.year !== null) {
            url += `&year=${currentFilters.year}`;
            if (currentFilters.month !== null) {
                url += `&month=${currentFilters.month}`;
                if (currentFilters.day !== null) {
                    url += `&day=${currentFilters.day}`;
                }
            }
        }
        
        const response = await fetch(url, {
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
        const hasFilters = currentFilters.year !== null || currentFilters.month !== null || currentFilters.day !== null;
        const message = hasFilters 
            ? 'No media found matching the selected filters. Try adjusting your filters or upload some photos or videos to get started!'
            : 'No media found. Upload some photos or videos to get started!';
        gallery.innerHTML = `<p style="text-align: center; padding: 2rem; grid-column: 1 / -1;">${message}</p>`;
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
            
            // Reload filter options and gallery (maintain current page if no filters, otherwise reset to page 1)
            setTimeout(async () => {
                await loadFilterOptions(currentFilters.year, currentFilters.month);
                const pageToLoad = (currentFilters.year !== null || currentFilters.month !== null || currentFilters.day !== null) ? 1 : currentPage;
                // Only reload if viewing own gallery (upload adds to own gallery)
                const authResponse = await fetch('/api/check-auth', { credentials: 'include' });
                if (authResponse.ok) {
                    const authData = await authResponse.json();
                    if (currentGalleryOwner === authData.username) {
                        loadMedia(pageToLoad);
                    }
                }
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

// Filter event handlers
document.getElementById('yearFilter').addEventListener('change', async (e) => {
    const year = e.target.value ? parseInt(e.target.value) : null;
    currentFilters.year = year;
    currentFilters.month = null;
    currentFilters.day = null;
    // Clear month and day selects
    document.getElementById('monthFilter').value = '';
    document.getElementById('dayFilter').value = '';
    currentPage = 1; // Reset to first page
    await loadFilterOptions(year, null);
    loadMedia(1);
    window.scrollTo(0, 0);
});

document.getElementById('monthFilter').addEventListener('change', async (e) => {
    if (!currentFilters.year) return;
    const month = e.target.value ? parseInt(e.target.value) : null;
    currentFilters.month = month;
    currentFilters.day = null;
    // Clear day select
    document.getElementById('dayFilter').value = '';
    currentPage = 1; // Reset to first page
    await loadFilterOptions(currentFilters.year, month);
    loadMedia(1);
    window.scrollTo(0, 0);
});

document.getElementById('dayFilter').addEventListener('change', (e) => {
    if (!currentFilters.year || !currentFilters.month) return;
    const day = e.target.value ? parseInt(e.target.value) : null;
    currentFilters.day = day;
    currentPage = 1; // Reset to first page
    loadMedia(1);
    window.scrollTo(0, 0);
});

document.getElementById('clearFilters').addEventListener('click', async () => {
    currentFilters.year = null;
    currentFilters.month = null;
    currentFilters.day = null;
    currentPage = 1;
    document.getElementById('yearFilter').value = '';
    document.getElementById('monthFilter').value = '';
    document.getElementById('dayFilter').value = '';
    await loadFilterOptions();
    loadMedia(1);
    window.scrollTo(0, 0);
});

// Gallery selector change handler
document.getElementById('gallerySelect').addEventListener('change', async (e) => {
    const newOwner = e.target.value;
    if (newOwner && newOwner !== currentGalleryOwner) {
        currentGalleryOwner = newOwner;
        currentFilters.year = null;
        currentFilters.month = null;
        currentFilters.day = null;
        document.getElementById('yearFilter').value = '';
        document.getElementById('monthFilter').value = '';
        document.getElementById('dayFilter').value = '';
        currentPage = 1;
        
        // Update upload section visibility based on whether viewing own gallery
        const authResponse = await fetch('/api/check-auth', { credentials: 'include' });
        if (authResponse.ok) {
            const authData = await authResponse.json();
            const uploadSection = document.querySelector('.upload-section');
            if (currentGalleryOwner === authData.username) {
                uploadSection.classList.remove('disabled');
            } else {
                uploadSection.classList.add('disabled');
            }
        }
        
        await loadFilterOptions();
        loadMedia(1);
        window.scrollTo(0, 0);
    }
});

// Share modal handlers
const shareModal = document.getElementById('shareModal');
const shareBtn = document.getElementById('shareBtn');
const closeShareModal = document.getElementById('closeShareModal');
const shareSubmitBtn = document.getElementById('shareSubmitBtn');
const shareUsernameInput = document.getElementById('shareUsername');
const shareMessage = document.getElementById('shareMessage');

shareBtn.addEventListener('click', () => {
    shareModal.classList.remove('hidden');
    shareUsernameInput.value = '';
    shareMessage.textContent = '';
    shareMessage.className = 'share-message';
});

closeShareModal.addEventListener('click', () => {
    shareModal.classList.add('hidden');
});

shareModal.addEventListener('click', (e) => {
    if (e.target === shareModal) {
        shareModal.classList.add('hidden');
    }
});

shareSubmitBtn.addEventListener('click', async () => {
    const username = shareUsernameInput.value.trim();
    if (!username) {
        shareMessage.textContent = 'Please enter a username';
        shareMessage.className = 'share-message error';
        return;
    }
    
    try {
        const response = await fetch('/api/share', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ username }),
            credentials: 'include'
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            shareMessage.textContent = data.message || 'Gallery shared successfully!';
            shareMessage.className = 'share-message success';
            shareUsernameInput.value = '';
            // Reload accessible galleries
            await loadAccessibleGalleries();
            setTimeout(() => {
                shareModal.classList.add('hidden');
            }, 2000);
        } else {
            shareMessage.textContent = data.error || 'Failed to share gallery';
            shareMessage.className = 'share-message error';
        }
    } catch (error) {
        console.error('Share error:', error);
        shareMessage.textContent = 'Network error. Please try again.';
        shareMessage.className = 'share-message error';
    }
});

shareUsernameInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        shareSubmitBtn.click();
    }
});

// Initialize
checkAuth();

