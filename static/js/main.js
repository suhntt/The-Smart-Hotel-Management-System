/**
 * GrandStay Hotel – Main JavaScript
 */

document.addEventListener('DOMContentLoaded', function () {

    // ── Navbar scroll shadow ──────────────────────────────
    const navbar = document.getElementById('mainNavbar');
    if (navbar) {
        window.addEventListener('scroll', () => {
            navbar.classList.toggle('scrolled', window.scrollY > 50);
        });
    }

    // ── Bootstrap Tooltips ────────────────────────────────
    document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(el => {
        new bootstrap.Tooltip(el);
    });

    // ── Auto-dismiss flash alerts after 6 s ───────────────
    setTimeout(() => {
        document.querySelectorAll('.floating-alert.alert-dismissible').forEach(el => {
            try { new bootstrap.Alert(el).close(); } catch (_) {}
        });
    }, 6000);

    // ── Card hover elevation (extra sparkle on mobile) ────
    document.querySelectorAll('.hotel-card, .food-card').forEach(card => {
        card.addEventListener('touchstart', () => card.classList.add('touch-active'), { passive: true });
        card.addEventListener('touchend',   () => card.classList.remove('touch-active'), { passive: true });
    });
});

/**
 * Floating toast helper  (type: success | danger | warning | info)
 */
function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container') || document.body;
    const icons = {
        success: 'fa-check-circle text-success',
        danger:  'fa-times-circle text-danger',
        warning: 'fa-exclamation-triangle text-warning',
        info:    'fa-info-circle text-info'
    };
    const toast = document.createElement('div');
    toast.className = `floating-alert alert alert-${type} alert-dismissible fade show`;
    toast.role = 'alert';
    toast.innerHTML = `
        <div class="d-flex align-items-start gap-2">
            <i class="fas ${icons[type] || icons.info} mt-1"></i>
            <div>${message}</div>
        </div>
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>`;
    container.appendChild(toast);
    setTimeout(() => { try { new bootstrap.Alert(toast).close(); } catch (_) {} }, 5000);
}

// ── Theme Toggle (Light/Dark Mode) ────────────────────
document.addEventListener('DOMContentLoaded', () => {
    const themeToggles = document.querySelectorAll('#theme-toggle');
    const htmlElement = document.documentElement;
    
    // Check saved preference or system preference
    const savedTheme = localStorage.getItem('theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    
    let currentTheme = savedTheme ? savedTheme : (prefersDark ? 'dark' : 'light');
    
    // Apply initial theme
    htmlElement.setAttribute('data-bs-theme', currentTheme);
    updateToggleIcons(currentTheme);
    
    themeToggles.forEach(btn => {
        btn.addEventListener('click', () => {
            currentTheme = currentTheme === 'light' ? 'dark' : 'light';
            htmlElement.setAttribute('data-bs-theme', currentTheme);
            localStorage.setItem('theme', currentTheme);
            updateToggleIcons(currentTheme);
        });
    });
    
    function updateToggleIcons(theme) {
        themeToggles.forEach(btn => {
            const icon = btn.querySelector('i');
            if (icon) {
                if (theme === 'dark') {
                    icon.className = 'fas fa-sun text-warning';
                    btn.setAttribute('title', 'Switch to Light Mode');
                } else {
                    icon.className = 'fas fa-moon text-dark';
                    btn.setAttribute('title', 'Switch to Dark Mode');
                }
            }
        });
    }
});
