// Black's Law Dictionary - rebuilt renderer and search

let manifest = null;
let letterCache = Object.create(null);
let currentLetter = null;
let currentMode = 'browse';
let isDarkMode = false;
let fontSize = 17;
let totalEntriesLoaded = 0;
let totalEntries = 0;

const FONT_SIZE_MIN = 14;
const FONT_SIZE_MAX = 28;

window.addEventListener('hashchange', handleDeepLink);
document.addEventListener('DOMContentLoaded', init);

async function init() {
  loadSettings();
  setupEventListeners();
  await loadManifest();
  setupSidebar();
  document.getElementById('loadingState').style.display = 'none';
  document.getElementById('welcomeState').style.display = 'block';

  const hash = window.location.hash.slice(1);
  if (hash) {
    const firstChar = hash.charAt(0).toUpperCase();
    if (manifest[firstChar]) {
      await loadLetter(firstChar);
      hideWelcomeState();
      renderLetter(firstChar);
      highlightCurrentLetter();
      setTimeout(() => scrollToEntry(hash), 100);
    }
  }
}

async function loadManifest() {
  try {
    const response = await fetch('data/manifest.json');
    if (!response.ok) throw new Error('Failed to load manifest');
    manifest = await response.json();
    totalEntries = Object.values(manifest).reduce((sum, row) => sum + row.count, 0);
    document.getElementById('search-box').placeholder = 'Search ' + totalEntries.toLocaleString() + ' entries\u2026';
  } catch (error) {
    console.error(error);
    showError('Failed to load dictionary. Please refresh the page.');
  }
}

async function loadLetter(letter) {
  if (letterCache[letter]) return letterCache[letter];
  const entriesDiv = document.getElementById('entries');
  entriesDiv.innerHTML = '<p>Loading\u2026</p>';
  try {
    const response = await fetch(manifest[letter].file);
    if (!response.ok) throw new Error('Failed to load ' + letter);
    const entries = await response.json();
    letterCache[letter] = entries;
    totalEntriesLoaded += entries.length;
    return entries;
  } catch (error) {
    console.error(error);
    entriesDiv.innerHTML = '<p>Error loading entries. Please try again.</p>';
    return [];
  }
}

async function ensureAllLoaded() {
  await Promise.all(
    Object.keys(manifest).map(async (letter) => {
      if (!letterCache[letter]) {
        const response = await fetch(manifest[letter].file);
        const entries = await response.json();
        letterCache[letter] = entries;
        totalEntriesLoaded += entries.length;
      }
    })
  );
}

function renderLetter(letter) {
  const entries = letterCache[letter] || [];
  const container = document.getElementById('entries');
  const html = ['<h2 class="letter-heading">' + escapeHtml(letter) + '</h2>'];
  for (const entry of entries) html.push(renderEntry(entry));
  container.innerHTML = html.join('');
}

function renderSearchResults(entries) {
  const container = document.getElementById('entries');
  const emptyState = document.getElementById('emptyState');
  if (!entries.length) {
    container.innerHTML = '';
    emptyState.style.display = 'block';
    return;
  }
  emptyState.style.display = 'none';
  container.innerHTML = entries.map(renderEntry).join('');
}

function renderEntry(entry) {
  const id = slugify(entry.term);
  const bodyHtml = formatEntryBody(entry.term, entry.body || '');
  var pages = '';
  if (Array.isArray(entry.source_pages) && entry.source_pages.length) {
    var pageLinks = entry.source_pages.map(function(p) {
      var printed = parseInt(p, 10);
      if (isNaN(printed)) return escapeHtml(p);
      var leaf = printed + 11;
      return '<a href="https://archive.org/details/blacks-law-dictionary-2nd-edition-1910/page/n' +
        leaf + '/mode/1up" target="_blank" rel="noopener" title="View source page">' +
        escapeHtml(String(printed)) + '</a>';
    });
    pages = '<div class="entry-meta">Source p.' + pageLinks.join(', ') + '</div>';
  }
  return '<article class="entry" id="entry-' + id + '">' +
    '<h3 class="entry-term">' + escapeHtml(entry.term) + '</h3>' +
    pages +
    '<div class="entry-body">' + bodyHtml + '</div>' +
    '</article>';
}

function formatEntryBody(term, rawBody) {
  var text = stripDuplicateLeadingHeadword(term, String(rawBody || '').trim());
  var paragraphs = text.split(/\n{2,}/).map(function(part) { return part.trim(); }).filter(Boolean);
  if (!paragraphs.length) return '<p></p>';
  return paragraphs.map(function(part) {
    var html = escapeHtml(part).replace(/\n/g, ' ');
    html = linkCrossReferences(html);
    html = formatSubEntries(html);
    return '<p>' + html + '</p>';
  }).join('');
}

function formatSubEntries(html) {
  // Bold sub-entry headwords: text from em-dash to first period
  // Matches: —Sub-entry name. or \u2014Sub-entry name.
  return html.replace(
    /(\u2014|&mdash;)([\w\s,'-]+\.)/g,
    function(match, dash, headword) {
      return '<span class="sub-entry">' + dash + '<strong>' + headword + '</strong></span>';
    }
  );
}

function linkCrossReferences(html) {
  // Match "See TERM", "See also TERM", "Vide TERM", "(q. v.)", "(q.v.)"
  // TERM is one or more uppercase words, possibly with hyphens/spaces
  html = html.replace(
    /\b(See also|See|Vide)\s+([A-Z][A-Z\s,\-]{1,40}[A-Z])\b/g,
    function(match, prefix, term) {
      var cleanTerm = term.replace(/,\s*$/, '').trim();
      var slug = slugify(cleanTerm);
      return prefix + ' <a href="#' + slug + '" class="xref" onclick="jumpToEntry(\'' +
        escapeHtml(slug) + '\');return false;">' + cleanTerm + '</a>';
    }
  );
  return html;
}

async function jumpToEntry(slug) {
  // Try to find the entry's letter and navigate there
  var parts = slug.split('-');
  if (!parts.length) return;
  var firstChar = parts[0].charAt(0).toUpperCase();
  if (manifest && manifest[firstChar]) {
    if (!letterCache[firstChar]) await loadLetter(firstChar);
    var el = document.getElementById('entry-' + slug);
    if (!el) {
      // Switch to that letter first
      await switchLetter(firstChar);
      el = document.getElementById('entry-' + slug);
    }
    if (el) {
      window.location.hash = slug;
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      el.style.background = 'var(--hover)';
      setTimeout(function() { el.style.background = ''; }, 1200);
    }
  }
}

function stripDuplicateLeadingHeadword(term, body) {
  if (!body) return body;
  var escaped = escapeRegex(term).replace(/\s+/g, '\\s+');
  var senseRe = new RegExp('^' + escaped + '\\s*,\\s*((?:v|n|adj|adv|vb|prep|part|pl|pp)\\.)\\s*', 'i');
  var senseMatch = body.match(senseRe);
  if (senseMatch) {
    return senseMatch[1] + ' ' + body.slice(senseMatch[0].length).trimStart();
  }
  var plainRe = new RegExp('^' + escaped + '\\s*[.,;:]\\s*', 'i');
  if (plainRe.test(body)) {
    return body.replace(plainRe, '');
  }
  return body;
}

function normalizeForSearch(text) {
  return String(text || '')
    .toLowerCase()
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/['']/g, "'")
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();
}

function scoreEntry(entry, query) {
  var term = normalizeForSearch(entry.term);
  var body = normalizeForSearch(entry.body || '');
  if (!term || !query) return -1;
  if (term === query) return 100;
  if (term.startsWith(query + ' ') || term.startsWith(query)) return 80;
  if (term.includes(query)) return 60;
  if (body.includes(query)) return 20;
  return -1;
}

async function handleSearch() {
  var raw = document.getElementById('search-box').value.trim();
  var query = normalizeForSearch(raw);
  if (!query) {
    currentMode = 'browse';
    document.getElementById('resultCount').textContent = '';
    if (currentLetter && letterCache[currentLetter]) {
      renderLetter(currentLetter);
      highlightCurrentLetter();
    } else {
      document.getElementById('entries').innerHTML = '';
      document.getElementById('welcomeState').style.display = 'block';
      document.getElementById('entries-container').style.display = 'none';
    }
    return;
  }

  currentMode = 'search';
  if (totalEntriesLoaded < totalEntries) {
    document.getElementById('loadingState').style.display = 'block';
    document.getElementById('welcomeState').style.display = 'none';
    await ensureAllLoaded();
    document.getElementById('loadingState').style.display = 'none';
    document.getElementById('entries-container').style.display = 'block';
  }

  var allEntries = Object.keys(letterCache).sort().flatMap(function(letter) { return letterCache[letter]; });
  var ranked = allEntries
    .map(function(entry) { return { entry: entry, score: scoreEntry(entry, query) }; })
    .filter(function(row) { return row.score >= 0; })
    .sort(function(a, b) { return b.score - a.score || a.entry.term.localeCompare(b.entry.term); })
    .map(function(row) { return row.entry; });

  document.getElementById('resultCount').textContent = ranked.length + ' results';
  document.querySelectorAll('.letter-btn').forEach(function(btn) { btn.classList.remove('active'); });
  hideWelcomeState();
  renderSearchResults(ranked);
}

async function switchLetter(letter) {
  if (letter === currentLetter && currentMode === 'browse') return;
  currentLetter = letter;
  currentMode = 'browse';
  document.getElementById('search-box').value = '';
  document.getElementById('resultCount').textContent = '';
  hideWelcomeState();
  if (!letterCache[letter]) await loadLetter(letter);
  renderLetter(letter);
  highlightCurrentLetter();
  document.getElementById('main').scrollTop = 0;
}

function highlightCurrentLetter() {
  document.querySelectorAll('.letter-btn').forEach(function(btn) {
    btn.classList.toggle('active', btn.dataset.letter === currentLetter);
  });
}

function setupEventListeners() {
  document.getElementById('letter-rail').addEventListener('click', function(event) {
    if (event.target.classList.contains('letter-btn')) {
      switchLetter(event.target.dataset.letter);
    }
  });

  var searchBox = document.getElementById('search-box');
  searchBox.addEventListener('input', debounce(handleSearch, 200));

  document.getElementById('fontDec').addEventListener('click', function() { changeFontSize(-1); });
  document.getElementById('fontInc').addEventListener('click', function() { changeFontSize(1); });
  document.getElementById('themeBtn').addEventListener('click', toggleTheme);

  document.addEventListener('keydown', function(event) {
    if (event.key === '/' && document.activeElement.id !== 'search-box') {
      event.preventDefault();
      searchBox.focus();
    }
    if (event.key === 'Escape') {
      var sidebar = document.getElementById('sidebar');
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
  var sidebar = document.getElementById('sidebar');
  var overlay = document.getElementById('overlay');
  var menuBtn = document.getElementById('menuBtn');
  var sidebarLetters = document.getElementById('sidebar-letters');

  sidebarLetters.innerHTML = Object.keys(manifest).map(function(letter) {
    var count = manifest[letter].count;
    return '<button class="sidebar-letter" data-letter="' + letter + '">' + letter + ' <span>' + count.toLocaleString() + '</span></button>';
  }).join('');

  menuBtn.addEventListener('click', function() {
    sidebar.classList.add('open');
    overlay.classList.add('show');
  });

  var closeSidebar = function() {
    sidebar.classList.remove('open');
    overlay.classList.remove('show');
  };

  overlay.addEventListener('click', closeSidebar);
  sidebarLetters.addEventListener('click', function(event) {
    var btn = event.target.closest('.sidebar-letter');
    if (!btn) return;
    closeSidebar();
    switchLetter(btn.dataset.letter);
  });
}

function hideWelcomeState() {
  document.getElementById('welcomeState').style.display = 'none';
  document.getElementById('entries-container').style.display = 'block';
}

function handleDeepLink() {
  var hash = window.location.hash.slice(1);
  if (hash) scrollToEntry(hash);
}

function scrollToEntry(termHash) {
  var element = document.getElementById('entry-' + termHash);
  if (!element) return;
  element.scrollIntoView({ behavior: 'smooth', block: 'center' });
  element.style.background = 'var(--hover)';
  setTimeout(function() {
    element.style.background = '';
  }, 1200);
}

function changeFontSize(delta) {
  fontSize = Math.max(FONT_SIZE_MIN, Math.min(FONT_SIZE_MAX, fontSize + delta));
  document.documentElement.style.setProperty('--font-size', fontSize + 'px');
  localStorage.setItem('blacks-font-size', String(fontSize));
}

function toggleTheme() {
  isDarkMode = !isDarkMode;
  document.body.classList.toggle('dark', isDarkMode);
  localStorage.setItem('blacks-dark-mode', isDarkMode ? 'true' : 'false');
}

function loadSettings() {
  var savedSize = localStorage.getItem('blacks-font-size');
  if (savedSize) {
    fontSize = parseInt(savedSize, 10);
    document.documentElement.style.setProperty('--font-size', fontSize + 'px');
  }
  var savedDark = localStorage.getItem('blacks-dark-mode');
  if (savedDark === 'true') {
    isDarkMode = true;
    document.body.classList.add('dark');
  }
}

function showError(message) {
  document.getElementById('loadingState').innerHTML = '<p>' + escapeHtml(message) + '</p>';
}

function slugify(term) {
  return String(term || '')
    .trim()
    .toLowerCase()
    .normalize('NFKD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

function escapeHtml(text) {
  var div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function escapeRegex(text) {
  return String(text).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function debounce(fn, wait) {
  var timeout = null;
  return function() {
    var args = arguments;
    clearTimeout(timeout);
    timeout = setTimeout(function() { fn.apply(null, args); }, wait);
  };
}
