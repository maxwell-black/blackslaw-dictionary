// Black's Law Dictionary - Main Application

let allEntries = [];
let filteredEntries = [];

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
    console.log('Loading Black's Law Dictionary...');
    
    // Load entries
    await loadEntries();
    
    // Setup search
    setupSearch();
    
    // Setup letter navigation
    setupLetterNav();
    
    // Initial display
    displayEntries(allEntries.slice(0, 50));
    updateStats(allEntries.length);
});

async function loadEntries() {
    const container = document.getElementById('entries');
    container.innerHTML = '<div class="loading">Loading dictionary entries...</div>';
    
    try {
        const response = await fetch('blacks_entries.json');
        if (!response.ok) throw new Error('Failed to load entries');
        
        allEntries = await response.json();
        console.log(`Loaded ${allEntries.length} entries`);
        
    } catch (error) {
        console.error('Error loading entries:', error);
        container.innerHTML = `
            <div class="empty">
                <p>Error loading dictionary. Please try again later.</p>
                <p><small>${error.message}</small></p>
            </div>
        `;
    }
}

function setupSearch() {
    const searchBox = document.getElementById('search-box');
    
    searchBox.addEventListener('input', debounce(() => {
        performSearch();
    }, 200));
}

function performSearch() {
    const query = document.getElementById('search-box').value.trim().toLowerCase();
    const exactMatch = document.getElementById('exact-match').checked;
    const searchDefinitions = document.getElementById('search-definitions').checked;
    
    if (!query) {
        displayEntries(allEntries.slice(0, 50));
        updateStats(allEntries.length, 50);
        return;
    }
    
    filteredEntries = allEntries.filter(entry => {
        const term = entry.term.toLowerCase();
        const body = entry.body.toLowerCase();
        
        if (exactMatch) {
            return term === query;
        }
        
        // Search term
        if (term.includes(query)) return true;
        
        // Search definitions if enabled
        if (searchDefinitions && body.includes(query)) return true;
        
        return false;
    });
    
    displayEntries(filteredEntries.slice(0, 100));
    updateStats(allEntries.length, filteredEntries.length);
}

function displayEntries(entries) {
    const container = document.getElementById('entries');
    
    if (entries.length === 0) {
        container.innerHTML = `
            <div class="empty">
                <p>No entries found.</p>
                <p>Try a different search term.</p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = entries.map(entry => `
        <div class="entry">
            <div class="term">${escapeHtml(entry.term)}</div>
            <div class="body">${escapeHtml(entry.body)}</div>
        </div>
    `).join('');
}

function setupLetterNav() {
    const letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('');
    const container = document.getElementById('letter-nav');
    
    container.innerHTML = letters.map(letter => `
        <button onclick="filterByLetter('${letter}')">${letter}</button>
    `).join('');
}

function filterByLetter(letter) {
    document.getElementById('search-box').value = '';
    
    filteredEntries = allEntries.filter(entry => 
        entry.term.toUpperCase().startsWith(letter)
    );
    
    displayEntries(filteredEntries);
    updateStats(allEntries.length, filteredEntries.length);
    
    // Scroll to results
    document.getElementById('entries').scrollIntoView({ behavior: 'smooth' });
}

function updateStats(total, showing = null) {
    const stats = document.getElementById('stats');
    
    if (showing === null || showing === total) {
        stats.textContent = `${total.toLocaleString()} entries total`;
    } else {
        stats.textContent = `Showing ${showing.toLocaleString()} of ${total.toLocaleString()} entries`;
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    // Press / to focus search
    if (e.key === '/' && document.activeElement.id !== 'search-box') {
        e.preventDefault();
        document.getElementById('search-box').focus();
    }
    
    // Press Escape to clear search
    if (e.key === 'Escape') {
        document.getElementById('search-box').value = '';
        performSearch();
    }
});