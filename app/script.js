// Configuration
const API_BASE_URL = window.location.origin;
const STRIPE_PUBLIC_KEY = 'YOUR_STRIPE_PUBLIC_KEY'; // Will be injected from backend
let stripe = null;
let elements = null;
let cardElement = null;

// State Management
let currentUser = null;
let selectedAmount = 3;

// Initialize on page load
document.addEventListener('DOMContentLoaded', async () => {
    // Get Stripe public key from backend
    await initializeStripe();
    
    // Check authentication
    const token = getAuthToken();
    if (token) {
        await loadUserData();
        showPaymentSection();
    } else {
        showAuthSection();
    }

    // Setup event listeners
    setupEventListeners();
});

// ===== Stripe Initialization =====
async function initializeStripe() {
    try {
        let pubKey = STRIPE_PUBLIC_KEY;
        
        // Try to fetch the public key from backend
        try {
            const response = await fetch(`${API_BASE_URL}/api/config/stripe-key`);
            if (response.ok) {
                const data = await response.json();
                pubKey = data.public_key;
            }
        } catch (error) {
            console.warn('Could not fetch Stripe key from backend:', error);
        }
        
        if (pubKey && pubKey !== 'YOUR_STRIPE_PUBLIC_KEY') {
            stripe = Stripe(pubKey);
            elements = stripe.elements();
            cardElement = elements.create('card');
            cardElement.mount('#card-element');

            // Handle card errors
            cardElement.addEventListener('change', (event) => {
                const displayError = document.getElementById('card-errors');
                if (event.error) {
                    displayError.textContent = event.error.message;
                } else {
                    displayError.textContent = '';
                }
            });
        } else {
            console.warn('Stripe public key not configured');
            showError('Payment system not configured. Please contact support.');
        }
    } catch (error) {
        console.error('Error initializing Stripe:', error);
    }
}

// ===== Authentication =====
function getAuthToken() {
    // Try to get token from localStorage, sessionStorage, or cookies
    return localStorage.getItem('access_token') || 
           sessionStorage.getItem('access_token') ||
           getCookie('access_token');
}

function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
}

function saveAuthToken(token) {
    localStorage.setItem('access_token', token);
}

function clearAuthToken() {
    localStorage.removeItem('access_token');
    sessionStorage.removeItem('access_token');
}

// ===== User Data =====
async function loadUserData() {
    try {
        const token = getAuthToken();
        const response = await fetch(`${API_BASE_URL}/api/payment/credits`, {
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            }
        });

        if (response.status === 401) {
            // Token invalid, need to re-authenticate
            clearAuthToken();
            showAuthSection();
            return;
        }

        if (!response.ok) throw new Error('Failed to load user data');

        const data = await response.json();
        currentUser = data;
        
        // Update balance display
        document.getElementById('current-balance').textContent = 
            `€${(data.available_balance / 100).toFixed(2)}`;
        document.getElementById('available-tokens').textContent = 
            formatTokens(data.available_tokens);
    } catch (error) {
        console.error('Error loading user data:', error);
    }
}

// ===== Payment Form =====
function setupEventListeners() {
    // Sign in button setup (in showAuthSection)
    
    // Amount selection buttons
    document.querySelectorAll('.amount-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const amount = parseFloat(btn.dataset.amount);
            setSelectedAmount(amount);
        });
    });

    // Custom amount input
    const customAmountInput = document.getElementById('amount');
    customAmountInput.addEventListener('change', (e) => {
        const amount = parseFloat(e.target.value);
        if (amount >= 3 && amount <= 20) {
            setSelectedAmount(amount);
        }
    });

    // Payment form submission
    const paymentForm = document.getElementById('payment-form');
    paymentForm.addEventListener('submit', handlePayment);

    // Sign out button
    document.getElementById('sign-out-btn').addEventListener('click', handleSignOut);

    // Success page buttons
    document.getElementById('back-to-extension').addEventListener('click', handleBackToExtension);
    document.getElementById('buy-more-btn').addEventListener('click', resetPaymentForm);

    // Retry button
    document.getElementById('retry-btn').addEventListener('click', () => {
        hideSection('error-section');
        showPaymentSection();
    });
}

function setSelectedAmount(amount) {
    selectedAmount = amount;
    
    // Update button states
    document.querySelectorAll('.amount-btn').forEach(btn => {
        const btnAmount = parseFloat(btn.dataset.amount);
        btn.classList.toggle('active', btnAmount === amount);
    });

    // Update custom input
    document.getElementById('amount').value = amount;

    // Update pay button
    document.getElementById('pay-amount').textContent = `€${amount.toFixed(2)}`;
    
    // Update expected tokens
    const tokensForUser = amount * 500000;
    const exchangeText = `You'll receive ${formatTokens(tokensForUser)}`;
    document.querySelector('.exchange-rate').textContent = exchangeText;
}

async function handlePayment(e) {
    e.preventDefault();

    if (!selectedAmount || selectedAmount < 3 || selectedAmount > 20) {
        showError('Please select a valid amount (€3-€20)');
        return;
    }

    if (!stripe || !cardElement) {
        showError('Payment system not initialized. Please refresh the page.');
        return;
    }

    showLoadingSection();

    try {
        const token = getAuthToken();

        // Step 1: Create Payment Intent
        const intentResponse = await fetch(`${API_BASE_URL}/api/payment/create-intent`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ amount_eur: selectedAmount })
        });

        if (!intentResponse.ok) {
            const error = await intentResponse.json();
            throw new Error(error.detail || 'Failed to create payment intent');
        }

        const intentData = await intentResponse.json();

        // Step 2: Confirm Payment with Stripe
        const { error, paymentIntent } = await stripe.confirmCardPayment(
            intentData.client_secret,
            {
                payment_method: {
                    card: cardElement
                }
            }
        );

        if (error) {
            throw new Error(error.message);
        }

        if (paymentIntent.status !== 'succeeded') {
            throw new Error('Payment not completed');
        }

        // Step 3: Confirm with Backend
        const confirmResponse = await fetch(`${API_BASE_URL}/api/payment/confirm`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ payment_intent_id: paymentIntent.id })
        });

        if (!confirmResponse.ok) {
            const error = await confirmResponse.json();
            throw new Error(error.detail || 'Failed to confirm payment');
        }

        const confirmData = await confirmResponse.json();

        // Step 4: Show success
        showSuccessSection(selectedAmount, intentData.tokens_available);

    } catch (error) {
        console.error('Payment error:', error);
        showError(error.message || 'Payment failed. Please try again.');
    }
}

function handleSignOut() {
    if (confirm('Are you sure you want to sign out?')) {
        clearAuthToken();
        currentUser = null;
        resetPaymentForm();
        showAuthSection();
    }
}

function handleBackToExtension() {
    // Check if there's a redirect URL in the query params
    const params = new URLSearchParams(window.location.search);
    const redirect = params.get('redirect_uri');
    
    if (redirect) {
        // Redirect to extension or specified URL
        window.location.href = redirect;
    } else {
        // Default: suggest user return to extension
        alert('Payment successful! You can now use your credits in the Chrome extension.');
        resetPaymentForm();
    }
}

function resetPaymentForm() {
    document.getElementById('payment-form').reset();
    setSelectedAmount(3);
    cardElement?.clear();
    loadUserData();
    showPaymentSection();
}

// ===== UI Management =====
function showAuthSection() {
    hideAllSections();
    
    // Set up the sign-in button with OAuth flow
    const signInBtn = document.getElementById('sign-in-btn');
    if (signInBtn) {
        const redirectUri = `${window.location.origin}/api/auth/google/callback`;
        signInBtn.href = `/api/auth/google?redirect_uri=${encodeURIComponent(redirectUri)}`;
    }
    
    document.getElementById('auth-section').classList.remove('hidden');
}

function showPaymentSection() {
    hideAllSections();
    document.getElementById('payment-section').classList.remove('hidden');
    loadUserData();
}

function showLoadingSection() {
    hideAllSections();
    document.getElementById('loading-section').classList.remove('hidden');
}

function showSuccessSection(amount, tokens) {
    hideAllSections();
    document.getElementById('success-amount').textContent = `€${amount.toFixed(2)}`;
    document.getElementById('success-tokens').textContent = formatTokens(tokens);
    document.getElementById('success-section').classList.remove('hidden');
}

function showError(message) {
    hideAllSections();
    document.getElementById('error-text').textContent = message;
    document.getElementById('error-section').classList.remove('hidden');
}

function hideSection(sectionId) {
    document.getElementById(sectionId).classList.add('hidden');
}

function hideAllSections() {
    document.querySelectorAll('.section').forEach(section => {
        section.classList.add('hidden');
    });
}

// ===== Utility Functions =====
function formatTokens(tokens) {
    if (tokens >= 1000000) {
        return `${(tokens / 1000000).toFixed(1)}M`;
    } else if (tokens >= 1000) {
        return `${(tokens / 1000).toFixed(1)}K`;
    }
    return tokens.toString();
}

// ===== Google OAuth Redirect Handler =====
// If the page loads with auth_token in URL (from OAuth callback)
window.addEventListener('load', () => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get('auth_token');
    const error = params.get('error');
    
    if (token) {
        saveAuthToken(token);
        // Remove token from URL for security
        window.history.replaceState({}, document.title, window.location.pathname);
        
        // Reload page to show payment section
        location.reload();
    }
    
    if (error) {
        showError(`Authentication failed: ${error}`);
        // Remove error from URL
        window.history.replaceState({}, document.title, window.location.pathname);
    }
});
