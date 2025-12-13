// Load users on page load
async function loadUsers() {
    const usersList = document.getElementById('usersList');
    
    try {
        const response = await fetch('/api/admin/users', {
            credentials: 'include'
        });
        
        if (response.status === 401) {
            window.location.href = '/';
            return;
        }
        
        const data = await response.json();
        renderUsers(data.users);
    } catch (error) {
        console.error('Error loading users:', error);
        usersList.innerHTML = '<div class="empty-state">Error loading users. Please refresh the page.</div>';
    }
}

// Render users list
function renderUsers(users) {
    const usersList = document.getElementById('usersList');
    
    if (users.length === 0) {
        usersList.innerHTML = '<div class="empty-state">No users yet. Add a user to get started.</div>';
        return;
    }
    
    const ul = document.createElement('ul');
    ul.className = 'users-list';
    
    users.forEach(user => {
        const li = document.createElement('li');
        li.className = 'user-item';
        
        const userInfo = document.createElement('div');
        userInfo.className = 'user-info';
        
        const usernameDiv = document.createElement('div');
        usernameDiv.className = 'username';
        usernameDiv.textContent = user.username;
        
        const createdAtDiv = document.createElement('div');
        createdAtDiv.className = 'created-at';
        const date = new Date(user.created_at);
        createdAtDiv.textContent = `Created: ${date.toLocaleString()}`;
        
        userInfo.appendChild(usernameDiv);
        userInfo.appendChild(createdAtDiv);
        
        const deleteBtn = document.createElement('button');
        deleteBtn.className = 'delete-btn';
        deleteBtn.textContent = 'Delete';
        deleteBtn.addEventListener('click', () => deleteUser(user.username));
        
        li.appendChild(userInfo);
        li.appendChild(deleteBtn);
        ul.appendChild(li);
    });
    
    usersList.innerHTML = '';
    usersList.appendChild(ul);
}

// Show message
function showMessage(text, type = 'success') {
    const messageDiv = document.getElementById('message');
    messageDiv.textContent = text;
    messageDiv.className = `message ${type}`;
    messageDiv.classList.remove('hidden');
    
    setTimeout(() => {
        messageDiv.classList.add('hidden');
    }, 3000);
}

// Add user form handler
document.getElementById('addUserForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const username = document.getElementById('newUsername').value.trim();
    const password = document.getElementById('newPassword').value.trim();
    
    if (!username || !password) {
        showMessage('Username and password are required', 'error');
        return;
    }
    
    try {
        const response = await fetch('/api/admin/users', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ username, password }),
            credentials: 'include'
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            showMessage(data.message || 'User created successfully', 'success');
            document.getElementById('addUserForm').reset();
            loadUsers();
        } else {
            showMessage(data.error || 'Failed to create user', 'error');
        }
    } catch (error) {
        console.error('Error creating user:', error);
        showMessage('Network error. Please try again.', 'error');
    }
});

// Delete user
async function deleteUser(username) {
    if (!confirm(`Are you sure you want to delete user "${username}"? This will also delete their media records and sharing relationships.`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/admin/users/${username}`, {
            method: 'DELETE',
            credentials: 'include'
        });
        
        const data = await response.json();
        
        if (response.ok && data.success) {
            showMessage(data.message || 'User deleted successfully', 'success');
            loadUsers();
        } else {
            showMessage(data.error || 'Failed to delete user', 'error');
        }
    } catch (error) {
        console.error('Error deleting user:', error);
        showMessage('Network error. Please try again.', 'error');
    }
}

// Logout handler
document.getElementById('logoutBtn').addEventListener('click', async () => {
    try {
        await fetch('/api/logout', {
            method: 'POST',
            credentials: 'include'
        });
        window.location.href = '/';
    } catch (error) {
        console.error('Logout error:', error);
    }
});

// Check if user is admin on page load
async function checkAdmin() {
    try {
        const response = await fetch('/api/check-auth', {
            credentials: 'include'
        });
        const data = await response.json();
        
        if (!data.authenticated || !data.is_admin) {
            window.location.href = '/';
            return;
        }
        
        // User is admin, load users
        loadUsers();
    } catch (error) {
        console.error('Auth check failed:', error);
        window.location.href = '/';
    }
}

// Initialize
checkAdmin();

