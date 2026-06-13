// Food Menu Cart Manager

const CART_KEY = 'smarthotel_food_cart';

function getCart() {
    return JSON.parse(localStorage.getItem(CART_KEY)) || [];
}

function saveCart(cart) {
    localStorage.setItem(CART_KEY, JSON.stringify(cart));
}

function addToCart(id, name, price) {
    let cart = getCart();
    let existingItem = cart.find(item => item.id === id);
    
    if (existingItem) {
        existingItem.qty += 1;
    } else {
        cart.push({ id: id, name: name, price: price, qty: 1 });
    }
    
    saveCart(cart);
    updateCartCountBadge();
    renderCart();
    
    // Check if showToast exists in scope
    if (typeof showToast === 'function') {
        showToast(`Added ${name} to cart!`, 'success');
    }
}

function updateQty(id, change) {
    let cart = getCart();
    let item = cart.find(item => item.id === id);
    
    if (item) {
        item.qty += change;
        if (item.qty <= 0) {
            cart = cart.filter(i => i.id !== id);
        }
    }
    
    saveCart(cart);
    updateCartCountBadge();
    renderCart();
}

function clearCart() {
    localStorage.removeItem(CART_KEY);
    updateCartCountBadge();
    renderCart();
}

function updateCartCountBadge() {
    let cart = getCart();
    let totalItems = cart.reduce((sum, item) => sum + item.qty, 0);
    const badges = document.querySelectorAll('.cart-count-badge');
    badges.forEach(badge => {
        badge.textContent = totalItems;
        if (totalItems > 0) {
            badge.classList.remove('d-none');
        } else {
            badge.classList.add('d-none');
        }
    });
}

function renderCart() {
    const cartItemsList = document.getElementById('cart-items-list');
    if (!cartItemsList) return; // Not on food menu page
    
    let cart = getCart();
    
    if (cart.length === 0) {
        cartItemsList.innerHTML = `
            <div class="text-center py-4 text-muted">
                <i class="fas fa-shopping-basket fa-2x mb-2 d-block"></i>
                Your cart is empty
            </div>
        `;
        document.getElementById('cart-subtotal').textContent = '₹0.00';
        document.getElementById('cart-tax').textContent = '₹0.00';
        document.getElementById('cart-total').textContent = '₹0.00';
        document.getElementById('btn-checkout-food').disabled = true;
        return;
    }
    
    let subtotal = 0;
    let html = '';
    
    cart.forEach(item => {
        let itemTotal = item.price * item.qty;
        subtotal += itemTotal;
        html += `
            <div class="d-flex justify-content-between align-items-center mb-3 pb-3 border-bottom">
                <div style="max-width: 60%;">
                    <h6 class="mb-0 fw-semibold">${item.name}</h6>
                    <small class="text-muted">₹${item.price.toFixed(2)} each</small>
                </div>
                <div class="d-flex align-items-center">
                    <button class="btn btn-sm btn-outline-secondary py-0 px-2" onclick="updateQty(${item.id}, -1)">-</button>
                    <span class="mx-2 fw-bold" style="min-width: 15px; text-align: center;">${item.qty}</span>
                    <button class="btn btn-sm btn-outline-secondary py-0 px-2" onclick="updateQty(${item.id}, 1)">+</button>
                    <span class="ms-3 fw-semibold text-end" style="min-width: 70px;">₹${itemTotal.toFixed(2)}</span>
                </div>
            </div>
        `;
    });
    
    cartItemsList.innerHTML = html;
    
    let tax = subtotal * 0.05; // 5% Service tax / GST
    let total = subtotal + tax;
    
    document.getElementById('cart-subtotal').textContent = `₹${subtotal.toFixed(2)}`;
    document.getElementById('cart-tax').textContent = `₹${tax.toFixed(2)}`;
    document.getElementById('cart-total').textContent = `₹${total.toFixed(2)}`;
    
    const checkoutBtn = document.getElementById('btn-checkout-food');
    checkoutBtn.disabled = false;
    // Embed the total amount on the button for tracking
    checkoutBtn.dataset.total = total.toFixed(2);
}

function checkoutCart() {
    let cart = getCart();
    if (cart.length === 0) return;
    
    const checkoutBtn = document.getElementById('btn-checkout-food');
    const totalAmount = parseFloat(checkoutBtn.dataset.total);
    
    checkoutBtn.disabled = true;
    checkoutBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Processing...';
    
    fetch('/food-menu/order', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            cart: cart,
            total_amount: totalAmount
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Clear local cart before navigating
            localStorage.removeItem(CART_KEY);
            window.location.href = data.redirect_url;
        } else {
            alert('Failed to place food order: ' + data.error);
            checkoutBtn.disabled = false;
            checkoutBtn.innerHTML = 'Proceed to Checkout';
        }
    })
    .catch(err => {
        console.error('Error checking out food order:', err);
        alert('An unexpected network error occurred.');
        checkoutBtn.disabled = false;
        checkoutBtn.innerHTML = 'Proceed to Checkout';
    });
}

// Initial count updates on load
document.addEventListener('DOMContentLoaded', () => {
    updateCartCountBadge();
    renderCart();
});
