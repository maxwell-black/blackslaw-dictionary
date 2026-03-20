// Black's Law Dictionary - Chunked Loading Application
// Loads letter-by-letter for instant first paint

let manifest = null;
let letterCache = {}; // { A: [...entries], B: [...], ... }
let currentLetter = 'A';
let currentMode = 'browse'; // 'browse' or 'search'
let isDarkMode = false;
let fontSize = 17;
let prefetchQueue = [];
let totalEntriesLoaded = 0;
let totalEntries = 0;

// Configuration
const FONT_SIZE_MIN = 14;
const FONT_SIZE_MAX = 28;

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
    loadSettings();
    setupEventListeners();
    
    // Load manifest
    await loadManifest();
    setupSidebar();
    
    // Hide loading, show welcome state
    document.getElementById('loadingState').style.display = 'none';
    document.getElementById('welcomeState').style.display = 'block';
    
    // Handle deep link if present (auto-load that letter)
    const hash = window.location.hash.slice(1);
    if (hash) {
        const firstChar = hash.charAt(0).toUpperCase();
        if (manifest[firstChar]) {
            await loadLetter(firstChar);
            hideWelcomeState();
            renderLetter(firstChar);
            highlightCurrentLetter(firstChar);
            setTimeout(() => scrollToEntry(hash), 100);
        }
    }
    
});

async function loadManifest() {
    try {
        const response = await fetch('data/manifest.json');
        if (!response.ok) throw new Error('Failed to load manifest');
        
        manifest = await response.json();
        
        // Calculate total entries
        totalEntries = Object.values(manifest).reduce((sum, m) => sum + m.count, 0);
        
        // Build prefetch queue (A first, then rest alphabetically)
        prefetchQueue = Object.keys(manifest).sort();
        
        console.log(`Manifest loaded: ${Object.keys(manifest).length} letters, ${totalEntries} total entries`);
        
        // Update search placeholder with actual count
        document.getElementById('search-box').placeholder = `Search ${totalEntries.toLocaleString()} entries…`;
    } catch (error) {
        console.error('Error loading manifest:', error);
        showError('Failed to load dictionary. Please refresh the page.');
    }
}

async function loadLetter(letter) {
    if (letterCache[letter]) {
        return letterCache[letter];
    }
    
    // Show loading for this letter if not in cache
    const entriesDiv = document.getElementById('entries');
    entriesDiv.innerHTML = '<div class="loading-inline">Loading...</div>';
    
    try {
        const response = await fetch(manifest[letter].file);
        if (!response.ok) throw new Error(`Failed to load ${letter}`);
        
        const entries = await response.json();
        letterCache[letter] = entries;
        totalEntriesLoaded += entries.length;
        
        console.log(`Loaded ${letter}: ${entries.length} entries`);
        return entries;
    } catch (error) {
        console.error(`Error loading letter ${letter}:`, error);
        entriesDiv.innerHTML = '<div class="error">Error loading entries. Please try again.</div>';
        return [];
    }
}

function renderLetter(letter) {
    const entries = letterCache[letter];
    if (!entries) return;
    
    const container = document.getElementById('entries');
    
    let html = `<div class="letter-group" id="letter-${letter}">`;
    html += `<h2 class="letter-heading">${letter}</h2>`;
    
    entries.forEach(entry => {
        html += renderEntry(entry);
    });
    
    html += '</div>';
    container.innerHTML = html;
}

function renderEntry(entry) {
    // Process body: collapse multiple newlines, single newlines to spaces
    let body = entry.body
        .replace(/\n\n\n+/g, '</p><p>')
        .replace(/\n/g, ' ');
    
    return `
        <div class="entry" id="entry-${entry.term.replace(/\s+/g, '-')}">
            <span class="term" onclick="updateHash('${entry.term}')">${escapeHtml(entry.term)}.</span>
            ${body}
        </div>
    `;
}

async function switchLetter(letter) {
    if (letter === currentLetter) return;
    
    currentLetter = letter;
    currentMode = 'browse';
    
    // Clear search
    document.getElementById('search-box').value = '';
    document.getElementById('resultCount').textContent = '';
    
    // Hide welcome state and show entries container
    hideWelcomeState();
    
    // Load letter if not cached
    if (!letterCache[letter]) {
        await loadLetter(letter);
    }
    
    // Render
    renderLetter(letter);
    highlightCurrentLetter(letter);
    
    // Scroll to top
    document.getElementById('main').scrollTop = 0;
}

function highlightCurrentLetter() {
    document.querySelectorAll('.letter-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.letter === currentLetter);
    });
}

function setupEventListeners() {
    // Letter rail clicks
    document.getElementById('letter-rail').addEventListener('click', (e) => {
        if (e.target.classList.contains('letter-btn')) {
            const letter = e.target.dataset.letter;
            switchLetter(letter);
        }
    });
    
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
        if (e.key === '/' && document.activeElement.id !== 'search-box') {
            e.preventDefault();
            searchBox.focus();
        }
        
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

function setupSidebar() {
    if (!manifest) return;
    
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('overlay');
    const menuBtn = document.getElementById('menuBtn');
    const sidebarLetters = document.getElementById('sidebar-letters');
    
    // Build sidebar content
    sidebarLetters.innerHTML = Object.keys(manifest).map(letter => {
        const count = manifest[letter].count;
        return `<button class="sidebar-letter" data-letter="${letter}">
            <span>${letter}</span>
            <span class="count">${count.toLocaleString()}</span>
        </button>`;
    }).join('');
    
    menuBtn.addEventListener('click', () => {
        sidebar.classList.add('open');
        overlay.classList.add('show');
    });
    
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
            switchLetter(letter);
        }
    });
}

function hideWelcomeState() {
    document.getElementById('welcomeState').style.display = 'none';
    document.getElementById('entries-container').style.display = 'block';
}

async function ensureAllLoaded() {
    // Load all remaining letters for search
    const promises = Object.keys(manifest).map(async letter => {
        if (!letterCache[letter]) {
            const response = await fetch(manifest[letter].file);
            const entries = await response.json();
            letterCache[letter] = entries;
            totalEntriesLoaded += entries.length;
        }
    });
    await Promise.all(promises);
}

async function handleSearch() {
    const query = document.getElementById('search-box').value.trim().toLowerCase();
    
    if (!query) {
        currentMode = 'browse';
        // Return to last letter or welcome state
        if (currentLetter && letterCache[currentLetter]) {
            renderLetter(currentLetter);
            highlightCurrentLetter(currentLetter);
        } else {
            document.getElementById('entries').innerHTML = '';
            document.getElementById('welcomeState').style.display = 'block';
            document.getElementById('entries-container').style.display = 'none';
        }
        document.getElementById('resultCount').textContent = '';
        return;
    }
    
    currentMode = 'search';
    
    // On first search, ensure all letters are loaded
    if (totalEntriesLoaded < totalEntries) {
        document.getElementById('loadingState').style.display = 'block';
        document.getElementById('welcomeState').style.display = 'none';
        await ensureAllLoaded();
        document.getElementById('loadingState').style.display = 'none';
        document.getElementById('entries-container').style.display = 'block';
    }
    
    // Search across all letters
    const allEntries = [];
    for (const letter of Object.keys(letterCache).sort()) {
        allEntries.push(...letterCache[letter]);
    }
    
    const matches = allEntries.filter(e =>
        e.term.toLowerCase().includes(query) ||
        e.body.toLowerCase().includes(query)
    );
    
    document.getElementById('resultCount').textContent = `${matches.length} results`;
    
    // Deactivate letter buttons
    document.querySelectorAll('.letter-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Render results
    renderSearchResults(matches);
}

function renderSearchResults(matches) {
    const container = document.getElementById('entries');
    const emptyState = document.getElementById('emptyState');
    
    if (matches.length === 0) {
        container.innerHTML = '';
        emptyState.style.display = 'block';
        return;
    }
    
    emptyState.style.display = 'none';
    
    // Render all matches (search results are typically smaller)
    container.innerHTML = matches.map(entry => renderEntry(entry)).join('');
}

function scrollToEntry(termHash) {
    const element = document.getElementById(`entry-${termHash}`);
    if (element) {
        element.scrollIntoView({ behavior: 'smooth', block: 'center' });
        element.style.background = 'var(--hover)';
        setTimeout(() => {
            element.style.background = '';
        }, 2000);
    }
}

function updateHash(term) {
    const hash = term.replace(/\s+/g, '-');
    history.pushState(null, null, `#${hash}`);
}

function handleDeepLink() {
    const hash = window.location.hash.slice(1);
    if (!hash) return;
    
    scrollToEntry(hash);
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
    const savedSize = localStorage.getItem('blacks-font-size');
    if (savedSize) {
        fontSize = parseInt(savedSize, 10);
        document.documentElement.style.setProperty('--font-size', `${fontSize}px`);
    }
    
    const savedDark = localStorage.getItem('blacks-dark-mode');
    if (savedDark === 'true') {
        isDarkMode = true;
        document.body.classList.add('dark');
    }
}

function showError(message) {
    document.getElementById('loadingState').innerHTML = `
        <div class="error">${message}</div>
    `;
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