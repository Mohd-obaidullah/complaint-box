// Notification functionality
document.addEventListener('DOMContentLoaded', function() {
    const notificationBtn = document.getElementById('notificationBtn');
    const notificationDropdown = document.getElementById('notificationDropdown');
    const notificationCount = document.getElementById('notificationCount');
    const notificationList = document.getElementById('notificationList');

    // Load notifications on page load
    loadNotifications();

    // Toggle notification dropdown
    if (notificationBtn) {
        notificationBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            if (notificationDropdown) {
                notificationDropdown.classList.toggle('hidden');
                if (!notificationDropdown.classList.contains('hidden')) {
                    markNotificationsRead();
                }
            }
        });
    }

    // Close dropdown when clicking outside
    document.addEventListener('click', function(e) {
        if (notificationDropdown && !notificationDropdown.contains(e.target) && !notificationBtn.contains(e.target)) {
            notificationDropdown.classList.add('hidden');
        }
    });

    function loadNotifications() {
        fetch('/notifications')
            .then(response => response.json())
            .then(data => {
                displayNotifications(data);
                updateNotificationCount(data);
            })
            .catch(error => console.error('Error loading notifications:', error));
    }

    function displayNotifications(notifications) {
        if (!notificationList) return;

        if (notifications.length === 0) {
            notificationList.innerHTML = '<p class="text-gray-500 text-center py-4">No notifications</p>';
            return;
        }

        notificationList.innerHTML = notifications.map(notif => `
            <div class="p-3 border-b border-gray-100 hover:bg-gray-50 transition-colors">
                <p class="text-sm text-gray-800 ${!notif.is_read ? 'font-semibold' : ''}">${notif.message}</p>
                <p class="text-xs text-gray-500 mt-1">${formatDate(notif.created_at)}</p>
            </div>
        `).join('');
    }

    function updateNotificationCount(notifications) {
        if (!notificationCount) return;
        
        const unreadCount = notifications.filter(n => !n.is_read).length;
        if (unreadCount > 0) {
            notificationCount.textContent = unreadCount;
            notificationCount.classList.remove('hidden');
        } else {
            notificationCount.classList.add('hidden');
        }
    }

    function markNotificationsRead() {
        fetch('/notifications/mark-read', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        })
        .then(() => {
            // Reload notifications to update count
            loadNotifications();
        })
        .catch(error => console.error('Error marking notifications as read:', error));
    }

    function formatDate(dateString) {
        const date = new Date(dateString);
        const now = new Date();
        const diffInSeconds = Math.floor((now - date) / 1000);

        if (diffInSeconds < 60) {
            return 'Just now';
        } else if (diffInSeconds < 3600) {
            const minutes = Math.floor(diffInSeconds / 60);
            return `${minutes} minute${minutes > 1 ? 's' : ''} ago`;
        } else if (diffInSeconds < 86400) {
            const hours = Math.floor(diffInSeconds / 3600);
            return `${hours} hour${hours > 1 ? 's' : ''} ago`;
        } else if (diffInSeconds < 604800) {
            const days = Math.floor(diffInSeconds / 86400);
            return `${days} day${days > 1 ? 's' : ''} ago`;
        } else {
            return date.toLocaleDateString();
        }
    }

    // Auto-refresh notifications every 30 seconds
    setInterval(loadNotifications, 30000);

    // File upload preview
    const fileInput = document.getElementById('attachment');
    if (fileInput) {
        fileInput.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (file) {
                const fileName = file.name;
                const fileSize = (file.size / 1024 / 1024).toFixed(2); // Convert to MB

                // Update the file input area to show selected file
                const label = fileInput.closest('label');
                if (label) {
                    const icon = label.querySelector('svg');
                    const text = label.querySelector('p');
                    
                    if (text) {
                        text.innerHTML = `<span class="font-semibold">${fileName}</span><br><span class="text-xs">${fileSize} MB</span>`;
                    }

                    if (icon) {
                        icon.classList.add('hidden');
                    }
                }
            }
        });
    }

    // Form validation feedback
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            const requiredFields = form.querySelectorAll('[required]');
            let isValid = true;

            requiredFields.forEach(field => {
                if (!field.value.trim()) {
                    isValid = false;
                    field.classList.add('border-red-500');
                } else {
                    field.classList.remove('border-red-500');
                }
            });

            if (!isValid) {
                e.preventDefault();
            }
        });
    });

    // Auto-hide flash messages after 5 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.transition = 'opacity 0.5s ease-out';
            alert.style.opacity = '0';
            setTimeout(() => {
                alert.remove();
            }, 500);
        }, 5000);
    });

    // Mobile menu toggle
    const mobileMenuBtn = document.getElementById('mobileMenuBtn');
    const mobileMenu = document.getElementById('mobileMenu');
    
    if (mobileMenuBtn && mobileMenu) {
        mobileMenuBtn.addEventListener('click', function() {
            mobileMenu.classList.toggle('hidden');
        });

        // Close mobile menu when clicking outside
        document.addEventListener('click', function(e) {
            if (!mobileMenu.contains(e.target) && !mobileMenuBtn.contains(e.target)) {
                mobileMenu.classList.add('hidden');
            }
        });

        // Close mobile menu when a link is clicked
        const mobileLinks = mobileMenu.querySelectorAll('a');
        mobileLinks.forEach(link => {
            link.addEventListener('click', function() {
                mobileMenu.classList.add('hidden');
            });
        });
    }

    // Handle mobile notification button
    const notificationBtnMobile = document.getElementById('notificationBtnMobile');
    if (notificationBtnMobile) {
        notificationBtnMobile.addEventListener('click', function(e) {
            e.stopPropagation();
            const notificationDropdown = document.querySelector('.notification-dropdown #notificationDropdown');
            if (notificationDropdown) {
                notificationDropdown.classList.toggle('hidden');
                if (!notificationDropdown.classList.contains('hidden')) {
                    markNotificationsRead();
                }
            }
        });

        // Update mobile notification count
        function updateMobileNotificationCount(notifications) {
            const notificationCountMobile = document.getElementById('notificationCountMobile');
            if (!notificationCountMobile) return;
            
            const unreadCount = notifications.filter(n => !n.is_read).length;
            if (unreadCount > 0) {
                notificationCountMobile.textContent = unreadCount;
                notificationCountMobile.classList.remove('hidden');
            } else {
                notificationCountMobile.classList.add('hidden');
            }
        }

        // Update original function to also update mobile count
        const originalLoadNotifications = loadNotifications;
        loadNotifications = function() {
            fetch('/notifications')
                .then(response => response.json())
                .then(data => {
                    displayNotifications(data);
                    updateNotificationCount(data);
                    updateMobileNotificationCount(data);
                })
                .catch(error => console.error('Error loading notifications:', error));
        };
    }
});

