// Black's Law Dictionary - Main Application
// iA Writer/Monocle inspired design

let allEntries = [];
let letterIndex = {}; // { A: [0,1,2...], B: [...] }
let visibleEntries = [];
let currentMode = 'browse'; // 'browse' or 'search'
let currentLetter = 'A';
let fontSize = 17;
let isDarkMode = false;

// Configuration
const BATCH_SIZE = 100;
const INITIAL_BATCH = 200;
const FONT_SIZE_MIN = 14;
const FONT_SIZE_MAX = 28;

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
    loadSettings();
    setupEventListeners();
    setupLetterRail();
    setupSidebar();
    
    // Load entries
    await loadEntries();
    
    // Build letter index
    buildLetterIndex();
    
    // Setup intersection observer for lazy loading
    setupLazyLoader();
    
    // Setup scroll spy for letter highlighting
    setupScrollSpy();
    
    // Handle deep link if present
    handleDeepLink();
    
    // Initial render
    renderBrowseMode();
});

async function loadEntries() {
    try {
        const response = await fetch('blacks_entries.json');
        if (!response.ok) throw new Error('Failed to load entries');
        
        allEntries = await response.json();
        console.log(`Loaded ${allEntries.length} entries`);
    } catch (error) {
        console.error('Error loading entries:', error);
        document.getElementById('entries').innerHTML = `
            <div class="empty-state" style="display: block;">
                <p>Error loading dictionary. Please refresh the page.</p>
                <p style="font-size: 14px; margin-top: 8px;">${error.message}</p>
            </div>
        `;
    }
}

function buildLetterIndex() {
    letterIndex = {};
    const letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
    letters.split('').forEach(letter => {
        letterIndex[letter] = [];
    });
    
    allEntries.forEach((entry, index) => {
        const firstLetter = entry.term.charAt(0).toUpperCase();
        if (letterIndex[firstLetter]) {
            letterIndex[firstLetter].push(index);
        }
    });
}

function setupLetterRail() {
    const rail = document.getElementById('letter-rail');
    const letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('');
    
    rail.innerHTML = letters.map(letter => 
        `<button class="letter-btn" data-letter="${letter}">${letter}</button>`
    ).join('');
    
    rail.addEventListener('click', (e) => {
        if (e.target.classList.contains('letter-btn')) {
            const letter = e.target.dataset.letter;
            scrollToLetter(letter);
        }
    });
}

function setupSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('overlay');
    const menuBtn = document.getElementById('menuBtn');
    const sidebarLetters = document.getElementById('sidebar-letters');
    
    // Build sidebar content
    const letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('');
    sidebarLetters.innerHTML = letters.map(letter => {
        const count = letterIndex[letter] ? letterIndex[letter].length : 0;
        return `<button class="sidebar-letter" data-letter="${letter}">
            <span>${letter}</span>
            <span class="count">${count.toLocaleString()}</span>
        </button>`;
    }).join('');
    
    // Open sidebar
    menuBtn.addEventListener('click', () => {
        sidebar.classList.add('open');
        overlay.classList.add('show');
    });
    
    // Close sidebar
    const closeSidebar = () => {
        sidebar.classList.remove('open');
        overlay.classList.remove('show');
    };
    
    overlay.addEventListener('click', closeSidebar);
    
    sidebarLetters.addEventListener('click', (e) => {
        const btn = e.target.closest('.sidebar-letter');
        if (btn) {
            const letter = btn.dataset.letter;
            closeSidebar();
            scrollToLetter(letter);
        }
    });
}

function setupEventListeners() {
    // Search
    const searchBox = document.getElementById('search-box');
    searchBox.addEventListener('input', debounce(() => {
        handleSearch();
    }, 200));
    
    // Font size controls
    document.getElementById('fontDec').addEventListener('click', () => changeFontSize(-1));
    document.getElementById('fontInc').addEventListener('click', () => changeFontSize(1));
    
    // Theme toggle
    document.getElementById('themeBtn').addEventListener('click', toggleTheme);
    
    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        // / to focus search
        if (e.key === '/' && document.activeElement.id !== 'search-box') {
            e.preventDefault();
            searchBox.focus();
        }
        
        // Escape to clear search or close sidebar
        if (e.key === 'Escape') {
            const sidebar = document.getElementById('sidebar');
            if (sidebar.classList.contains('open')) {
                sidebar.classList.remove('open');
                document.getElementById('overlay').classList.remove('show');
            } else if (searchBox.value) {
                searchBox.value = '';
                handleSearch();
            }
        }
    });
}

function handleSearch() {
    const query = document.getElementById('search-box').value.trim().toLowerCase();
    
    if (!query) {
        currentMode = 'browse';
        renderBrowseMode();
        document.getElementById('resultCount').textContent = '';
        return;
    }
    
    currentMode = 'search';
    
    // Filter entries
    const results = allEntries.filter(entry => {
        const termMatch = entry.term.toLowerCase().includes(query);
        const bodyMatch = entry.body.toLowerCase().includes(query);
        return termMatch || bodyMatch;
    });
    
    // Update result count
    document.getElementById('resultCount').textContent = `${results.length.toLocaleString()} result${results.length !== 1 ? 's' : ''}`;
    
    // Deactivate all letter buttons
    document.querySelectorAll('.letter-btn, .sidebar-letter').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Render results
    renderSearchResults(results);
}

function renderBrowseMode() {
    const container = document.getElementById('entries');
    const emptyState = document.getElementById('emptyState');
    
    emptyState.style.display = 'none';
    
    // Group entries by letter
    let html = '';
    const letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('');
    
    letters.forEach(letter => {
        const indices = letterIndex[letter];
        if (!indices || indices.length === 0) return;
        
        html += `<div class="letter-group" id="letter-${letter}">`;
        html += `<h2 class="letter-heading">${letter}</h2>`;
        
        indices.forEach(index => {
            const entry = allEntries[index];
            html += renderEntry(entry, index);
        });
        
        html += '</div>';
    });
    
    container.innerHTML = html;
    
    // Highlight current letter
    highlightCurrentLetter();
}

function renderSearchResults(results) {
    const container = document.getElementById('entries');
    const emptyState = document.getElementById('emptyState');
    
    if (results.length === 0) {
        container.innerHTML = '';
        emptyState.style.display = 'block';
        return;
    }
    
    emptyState.style.display = 'none';
    
    // Render first batch
    const toRender = results.slice(0, INITIAL_BATCH);
    container.innerHTML = toRender.map((entry, i) => renderEntry(entry, allEntries.indexOf(entry))).join('');
    
    // Store remaining for lazy loading
    visibleEntries = results.slice(INITIAL_BATCH);
}

function renderEntry(entry, index) {
    // Process body: collapse multiple newlines, single newlines to spaces
    let body = entry.body
        .replace(/\n\n\n+/g, '<br><br>')
        .replace(/\n/g, ' ')
        .replace(/<br><br>/g, '</p><p>');
    
    return `
        <div class="entry" id="entry-${entry.term.replace(/\s+/g, '-')}">
            <span class="term" onclick="updateHash('${entry.term}')">${escapeHtml(entry.term)}.</span>
            ${body}
        </div>
    `;
}

function scrollToLetter(letter) {
    currentLetter = letter;
    const element = document.getElementById(`letter-${letter}`);
    if (element) {
        element.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    highlightCurrentLetter();
}

function highlightCurrentLetter() {
    document.querySelectorAll('.letter-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.letter === currentLetter);
    });
}

function setupScrollSpy() {
    const observer = new IntersectionObserver((entries) => {
        if (currentMode !== 'browse') return;
        
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const letter = entry.target.id.replace('letter-', '');
                currentLetter = letter;
                highlightCurrentLetter();
            }
        });
    }, {
        root: document.getElementById('main'),
        rootMargin: '-20% 0px -60% 0px'
    });
    
    // Observe all letter headings
    document.querySelectorAll('.letter-heading').forEach(heading => {
        observer.observe(heading);
    });
}

function setupLazyLoader() {
    const sentinel = document.getElementById('sentinel');
    const main = document.getElementById('main');
    
    const observer = new IntersectionObserver((entries) => {
        if (entries[0].isIntersecting && currentMode === 'search' && visibleEntries.length > 0) {
            loadMoreEntries();
        }
    }, {
        root: main,
        rootMargin: '100px'
    });
    
    observer.observe(sentinel);
}

function loadMoreEntries() {
    if (visibleEntries.length === 0) return;
    
    const batch = visibleEntries.slice(0, BATCH_SIZE);
    visibleEntries = visibleEntries.slice(BATCH_SIZE);
    
    const container = document.getElementById('entries');
    const html = batch.map(entry => renderEntry(entry, allEntries.indexOf(entry))).join('');
    container.insertAdjacentHTML('beforeend', html);
}

function updateHash(term) {
    const hash = term.replace(/\s+/g, '-');
    history.pushState(null, null, `#${hash}`);
}

function handleDeepLink() {
    const hash = window.location.hash.slice(1);
    if (!hash) return;
    
    // Try to find entry by term
    const entry = allEntries.find(e => e.term.replace(/\s+/g, '-') === hash);
    if (entry) {
        const firstLetter = entry.term.charAt(0).toUpperCase();
        currentLetter = firstLetter;
        
        // Wait for render then scroll
        setTimeout(() => {
            const element = document.getElementById(`entry-${hash}`);
            if (element) {
                element.scrollIntoView({ behavior: 'smooth', block: 'center' });
                element.style.background = 'var(--hover)';
                setTimeout(() => {
                    element.style.background = '';
                }, 2000);
            }
        }, 100);
    }
}

function changeFontSize(delta) {
    fontSize = Math.max(FONT_SIZE_MIN, Math.min(FONT_SIZE_MAX, fontSize + delta));
    document.documentElement.style.setProperty('--font-size', `${fontSize}px`);
    localStorage.setItem('blacks-font-size', fontSize);
}

function toggleTheme() {
    isDarkMode = !isDarkMode;
    document.body.classList.toggle('dark', isDarkMode);
    localStorage.setItem('blacks-dark-mode', isDarkMode);
}

function loadSettings() {
    // Font size
    const savedSize = localStorage.getItem('blacks-font-size');
    if (savedSize) {
        fontSize = parseInt(savedSize, 10);
        document.documentElement.style.setProperty('--font-size', `${fontSize}px`);
    }
    
    // Dark mode
    const savedDark = localStorage.getItem('blacks-dark-mode');
    if (savedDark === 'true') {
        isDarkMode = true;
        document.body.classList.add('dark');
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

// Handle hash changes
window.addEventListener('hashchange', handleDeepLink);