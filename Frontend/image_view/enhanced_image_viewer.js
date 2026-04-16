// enhanced_image_viewer.js
import { getCookie, getToken } from "../shared/utils.js";

const csrftoken = getCookie('csrftoken');
const token = getToken();
const BACKEND_BASE_URL = 'http://127.0.0.1:8000';

// Application state
let currentPage = 1;
let hasNextPage = true;
let isLoading = false;
let imageData = [];
let filteredData = [];
let currentFilters = {
    sensor: '',
    process_id: '',
    search: '',
    type: 'all',
    sort: 'sensor',
    order: 'asc'
};

// Debounce utility
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

// Initialize application
document.addEventListener('DOMContentLoaded', async () => {
    await initializeApp();
    setupEventListeners();
});

async function initializeApp() {
    showLoading(true);
    
    try {
        // Load initial data and sensor summary
        await Promise.all([
            fetchImages(1, true),
            fetchSensorSummary()
        ]);
        
        populateSensorTabs();
        
        // Auto-select first sensor if available
        const sensorIds = getSensorIds();
        if (sensorIds.length > 0) {
            selectSensor(sensorIds[0]);
        }
        
    } catch (error) {
        console.error('Failed to initialize app:', error);
        showError('Failed to load images. Please try again.');
    } finally {
        showLoading(false);
    }
}

function setupEventListeners() {
    // Search functionality with debouncing
    const searchBar = document.getElementById('searchBar');
    const debouncedSearch = debounce(handleSearch, 300);
    
    searchBar.addEventListener('input', debouncedSearch);
    searchBar.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
            handleSearch(e);
        }
    });
    
    // Clear search
    document.getElementById('clearSearch').addEventListener('click', clearSearchInput);
    
    // Filter pills
    document.querySelectorAll('.filter-pill').forEach(pill => {
        pill.addEventListener('click', handleFilterPill);
    });
    
    // Load more button
    document.getElementById('loadMoreBtn').addEventListener('click', loadMoreImages);
    
    // View toggle
    document.querySelectorAll('.view-btn').forEach(btn => {
        btn.addEventListener('click', handleViewToggle);
    });
    
    // Keyboard shortcuts
    document.addEventListener('keydown', handleKeyboardShortcuts);
    
    // Setup search suggestions
    setupSearchSuggestions();
}

// API Functions
async function fetchImages(page = 1, reset = false) {
    if (reset) {
        currentPage = 1;
        imageData = [];
    }
    
    const params = new URLSearchParams({
        page: page,
        page_size: 150,
        ...currentFilters
    });
    
    try {
        const response = await fetch(`${BACKEND_BASE_URL}/test/images/?${params}`, {
            headers: {
                'Authorization': `Bearer ${token}`,
                'X-CSRFToken': csrftoken,
                'Content-Type': 'application/json'
            }
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        if (reset) {
            imageData = data.results;
        } else {
            imageData = [...imageData, ...data.results];
        }
        
        hasNextPage = !!data.next;
        filteredData = [...imageData];
        
        // Update UI metadata
        updateMetadata(data.metadata);
        
        return data;
        
    } catch (error) {
        console.error('Error fetching images:', error);
        throw error;
    }
}

async function fetchSensorSummary() {
    try {
        const response = await fetch(`${BACKEND_BASE_URL}/test/sensors/summary/`, {
            headers: {
                'Authorization': `Bearer ${token}`,
                'X-CSRFToken': csrftoken
            }
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        return data;
        
    } catch (error) {
        console.error('Error fetching sensor summary:', error);
        return null;
    }
}

async function fetchSearchSuggestions(query) {
    if (query.length < 2) return [];
    
    try {
        const response = await fetch(`${BACKEND_BASE_URL}/api/search/suggestions/?q=${encodeURIComponent(query)}`, {
            headers: {
                'Authorization': `Bearer ${token}`,
                'X-CSRFToken': csrftoken
            }
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        return data.suggestions || [];
        
    } catch (error) {
        console.error('Error fetching suggestions:', error);
        return [];
    }
}

// Search Functions
async function handleSearch(e) {
    const searchTerm = e.target.value.trim();
    const clearBtn = document.getElementById('clearSearch');
    
    clearBtn.style.display = searchTerm ? 'block' : 'none';
    currentFilters.search = searchTerm;
    
    if (searchTerm) {
        await performSearch(searchTerm);
    } else {
        await clearSearch();
    }
}

async function performSearch(searchTerm) {
    showLoading(true);
    
    try {
        await fetchImages(1, true);
        
        if (currentFilters.sensor) {
            renderSensorContent(currentFilters.sensor);
        } else {
            populateSensorTabs();
        }
        
        showSearchResults(searchTerm, imageData.length);
        
    } catch (error) {
        console.error('Search failed:', error);
        showError('Search failed. Please try again.');
    } finally {
        showLoading(false);
    }
}

function showSearchResults(searchTerm, count) {
    const resultsInfo = document.getElementById('searchResults');
    resultsInfo.innerHTML = `Found ${count} image${count !== 1 ? 's' : ''} matching "${searchTerm}"`;
    resultsInfo.style.display = 'block';
    
    setTimeout(() => {
        resultsInfo.style.display = 'none';
    }, 3000);
}

async function clearSearch() {
    currentFilters.search = '';
    await fetchImages(1, true);
    
    if (currentFilters.sensor) {
        renderSensorContent(currentFilters.sensor);
    } else {
        populateSensorTabs();
    }
}

function clearSearchInput() {
    const searchBar = document.getElementById('searchBar');
    const clearBtn = document.getElementById('clearSearch');
    const resultsInfo = document.getElementById('searchResults');
    
    searchBar.value = '';
    clearBtn.style.display = 'none';
    resultsInfo.style.display = 'none';
    
    clearSearch();
}

// Search Suggestions
function setupSearchSuggestions() {
    const searchBar = document.getElementById('searchBar');
    const suggestionsContainer = createSuggestionsContainer();
    
    const debouncedSuggestions = debounce(async (query) => {
        if (query.length >= 2) {
            const suggestions = await fetchSearchSuggestions(query);
            showSuggestions(suggestions, suggestionsContainer);
        } else {
            hideSuggestions(suggestionsContainer);
        }
    }, 200);
    
    searchBar.addEventListener('input', (e) => {
        debouncedSuggestions(e.target.value);
    });
    
    // Hide suggestions when clicking outside
    document.addEventListener('click', (e) => {
        if (!searchBar.contains(e.target) && !suggestionsContainer.contains(e.target)) {
            hideSuggestions(suggestionsContainer);
        }
    });
}

function createSuggestionsContainer() {
    const container = document.createElement('div');
    container.className = 'search-suggestions';
    container.style.cssText = `
        position: absolute;
        top: 100%;
        left: 0;
        right: 0;
        background: white;
        border: 1px solid #ddd;
        border-radius: 0 0 15px 15px;
        box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        z-index: 1000;
        max-height: 200px;
        overflow-y: auto;
        display: none;
    `;
    
    document.querySelector('.search-container').appendChild(container);
    return container;
}

function showSuggestions(suggestions, container) {
    if (suggestions.length === 0) {
        hideSuggestions(container);
        return;
    }
    
    container.innerHTML = '';
    
    suggestions.forEach(suggestion => {
        const item = document.createElement('div');
        item.className = 'suggestion-item';
        item.style.cssText = `
            padding: 12px 20px;
            cursor: pointer;
            border-bottom: 1px solid #f0f0f0;
            transition: background-color 0.2s ease;
        `;
        
        const icon = getSuggestionIcon(suggestion.type);
        item.innerHTML = `${icon} ${suggestion.label}`;
        
        item.addEventListener('click', () => {
            document.getElementById('searchBar').value = suggestion.value;
            currentFilters.search = suggestion.value;
            performSearch(suggestion.value);
            hideSuggestions(container);
        });
        
        item.addEventListener('mouseenter', () => {
            item.style.backgroundColor = '#f8f9fa';
        });
        
        item.addEventListener('mouseleave', () => {
            item.style.backgroundColor = 'transparent';
        });
        
        container.appendChild(item);
    });
    
    container.style.display = 'block';
}

function hideSuggestions(container) {
    container.style.display = 'none';
}

function getSuggestionIcon(type) {
    const icons = {
        sensor: '📱',
        process: '🔬',
        filename: '📄'
    };
    return icons[type] || '🔍';
}

// Filter Functions
async function handleFilterPill(e) {
    document.querySelectorAll('.filter-pill').forEach(p => p.classList.remove('active'));
    e.target.classList.add('active');
    
    currentFilters.type = e.target.dataset.filter;
    
    showLoading(true);
    try {
        await fetchImages(1, true);
        
        if (currentFilters.sensor) {
            renderSensorContent(currentFilters.sensor);
        } else {
            populateSensorTabs();
        }
    } finally {
        showLoading(false);
    }
}

// Sensor Management
function getSensorIds() {
    return [...new Set(imageData.map(item => item.sensor))].sort();
}

function populateSensorTabs() {
    const tabsContainer = document.getElementById('sensorTabs');
    const sensorIds = getSensorIds();
    
    document.getElementById('sensorCount').textContent = `${sensorIds.length} sensor${sensorIds.length !== 1 ? 's' : ''}`;
    
    tabsContainer.innerHTML = '';
    
    if (sensorIds.length === 0) {
        tabsContainer.innerHTML = `
            <div style="padding: 20px; text-align: center; color: #6c757d;">
                <div style="font-size: 48px; margin-bottom: 15px;">📱</div>
                <div>No sensors found</div>
            </div>
        `;
        return;
    }
    
    sensorIds.forEach((sensorId, index) => {
        const sensorImages = imageData.filter(item => item.sensor === sensorId);
        const processCount = new Set(sensorImages.map(item => item.process_id)).size;
        
        const tab = document.createElement('button');
        tab.className = `sensor-tab ${index === 0 ? 'active' : ''}`;
        tab.dataset.sensor = sensorId;
        tab.innerHTML = `
            <div class="sensor-name">📱 Sensor ${sensorId}</div>
            <div class="sensor-info">
                <span>${sensorImages.length} images</span>
                <span>${processCount} processes</span>
            </div>
        `;
        
        tab.addEventListener('click', () => selectSensor(sensorId));
        tabsContainer.appendChild(tab);
    });
}

async function selectSensor(sensorId) {
    // Update active tab
    document.querySelectorAll('.sensor-tab').forEach(tab => tab.classList.remove('active'));
    const targetTab = document.querySelector(`[data-sensor="${sensorId}"]`);
    if (targetTab) {
        targetTab.classList.add('active');
    }
    
    currentFilters.sensor = sensorId;
    
    // If we need to fetch new data for this sensor
    if (!imageData.some(img => img.sensor === sensorId)) {
        showLoading(true);
        try {
            await fetchImages(1, true);
        } finally {
            showLoading(false);
        }
    }
    
    renderSensorContent(sensorId);
}

function renderSensorContent(sensorId) {
    const contentArea = document.getElementById('processContent');
    const contentTitle = document.getElementById('contentTitle');
    const totalImages = document.getElementById('totalImages');
    
    const sensorData = imageData.filter(item => item.sensor === sensorId);
    const groupedByProcess = groupByProcess(sensorData);
    
    contentTitle.textContent = `Sensor ${sensorId}`;
    totalImages.textContent = `${sensorData.length} image${sensorData.length !== 1 ? 's' : ''}`;
    
    if (sensorData.length === 0) {
        contentArea.innerHTML = `
            <div class="no-results">
                <div class="no-results-icon">🔍</div>
                <h3>No images found</h3>
                <p>Try adjusting your filters or search terms.</p>
            </div>
        `;
        return;
    }
    
    contentArea.innerHTML = '';
    
    Object.entries(groupedByProcess).forEach(([processId, images]) => {
        const section = createProcessSection(processId, images);
        contentArea.appendChild(section);
    });
    
    // Update load more button visibility
    updateLoadMoreButton();
}

function groupByProcess(data) {
    return data.reduce((acc, item) => {
        const process = item.process_id || 'Unspecified';
        if (!acc[process]) acc[process] = [];
        acc[process].push(item);
        return acc;
    }, {});
}

function createProcessSection(processId, images) {
    const section = document.createElement('div');
    section.className = 'process-section';
    
    const header = document.createElement('div');
    header.className = 'process-header';
    header.innerHTML = `
        <div class="process-title">🔬 ${processId}</div>
        <div class="process-meta">
            <span class="image-count">${images.length} images</span>
            <span class="toggle-icon">▼</span>
        </div>
    `;
    
    const imagesContainer = document.createElement('div');
    imagesContainer.className = 'process-images';
    
    const grid = document.createElement('div');
    grid.className = 'image-grid';
    
    images.forEach((image, index) => {
        const imageItem = createImageItem(image, images, index);
        grid.appendChild(imageItem);
    });
    
    imagesContainer.appendChild(grid);
    section.appendChild(header);
    section.appendChild(imagesContainer);
    
    // Toggle functionality
    header.addEventListener('click', () => {
        const isVisible = imagesContainer.style.display !== 'none';
        imagesContainer.style.display = isVisible ? 'none' : 'block';
        header.classList.toggle('collapsed', isVisible);
    });
    
    return section;
}

function createImageItem(image, imageList, index) {
    const item = document.createElement('div');
    item.className = 'image-item';
    item.innerHTML = `
        <div class="image-container">
            <img src="${image.image}" alt="${image.file_name}" loading="lazy" onerror="handleImageError(this)">
            <div class="image-overlay">
                👁️ View Image
            </div>
        </div>
        <div class="image-info">
            <div class="image-filename">${image.file_name}</div>
            <div class="image-meta">
                <span class="image-type">${getImageTypeLabel(image.suffix)}</span>
                <span>${formatFileSize(image.file_size)}</span>
            </div>
        </div>
    `;
    
    item.addEventListener('click', () => openImageModal(image, imageList, index));
    return item;
}

function getImageTypeLabel(suffix) {
    const typeMap = {
        't': 'Thermal',
        'h': 'Humidity',
        'p': 'Pressure',
        'v': 'Vibration',
        'w': 'Wideband'
    };
    return typeMap[suffix] || (suffix ? suffix.toUpperCase() : 'Unknown');
}

function formatFileSize(bytes) {
    if (!bytes) return 'Unknown';
    
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i];
}

// Modal Functions (integrate with your existing modal)
function openImageModal(image, imageList, index) {
    // This should integrate with your existing modal system
    // For now, we'll log the action
    console.log('Opening image modal:', {
        image: image.file_name,
        index: index,
        total: imageList.length
    });
    
    // Your existing modal code should go here
    // Example integration:
    /*
    currentImageList = imageList;
    currentImageIndex = index;
    const modal = document.getElementById('imageModal');
    const modalImg = document.getElementById('modalImage');
    const modalFilename = document.getElementById('modalFilename');
    
    modalImg.src = image.image;
    modalFilename.textContent = image.file_name;
    modal.style.display = 'flex';
    */
}

// Load More Functions
async function loadMoreImages() {
    if (isLoading || !hasNextPage) return;
    
    isLoading = true;
    const loadBtn = document.getElementById('loadMoreBtn');
    loadBtn.innerHTML = '<span class="loading-spinner"></span>Loading more images...';
    loadBtn.disabled = true;
    
    try {
        currentPage++;
        await fetchImages(currentPage, false);
        
        // Re-render current view
        if (currentFilters.sensor) {
            renderSensorContent(currentFilters.sensor);
        } else {
            populateSensorTabs();
        }
        
    } catch (error) {
        console.error('Failed to load more images:', error);
        showError('Failed to load more images. Please try again.');
        currentPage--; // Revert page increment on failure
    } finally {
        isLoading = false;
        updateLoadMoreButton();
    }
}

function updateLoadMoreButton() {
    const loadBtn = document.getElementById('loadMoreBtn');
    
    if (hasNextPage && !isLoading) {
        loadBtn.innerHTML = 'Load More Images';
        loadBtn.disabled = false;
        loadBtn.style.display = 'block';
    } else if (!hasNextPage) {
        loadBtn.innerHTML = '✓ All images loaded';
        loadBtn.disabled = true;
        loadBtn.style.display = 'block';
    } else {
        loadBtn.style.display = 'none';
    }
}

// Utility Functions
function showLoading(show) {
    const overlay = document.getElementById('loadingOverlay');
    overlay.style.display = show ? 'flex' : 'none';
}

function showError(message) {
    // You can integrate with your existing error handling system
    console.error(message);
    
    // Simple error display
    const errorDiv = document.createElement('div');
    errorDiv.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: #dc3545;
        color: white;
        padding: 15px 20px;
        border-radius: 8px;
        z-index: 9999;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    `;
    errorDiv.textContent = message;
    
    document.body.appendChild(errorDiv);
    
    setTimeout(() => {
        document.body.removeChild(errorDiv);
    }, 5000);
}

function updateMetadata(metadata) {
    if (!metadata) return;
    
    // Update any metadata displays in your UI
    console.log('Metadata:', metadata);
}

function handleImageError(img) {
    img.src = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjE1MCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMTAwJSIgaGVpZ2h0PSIxMDAlIiBmaWxsPSIjZjhmOWZhIi8+PHRleHQgeD0iNTAlIiB5PSI1MCUiIGZvbnQtZmFtaWx5PSJBcmlhbCwgc2Fucy1zZXJpZiIgZm9udC1zaXplPSIxNCIgZmlsbD0iIzZjNzU3ZCIgdGV4dC1hbmNob3I9Im1pZGRsZSIgZHk9Ii4zZW0iPkltYWdlIG5vdCBmb3VuZDwvdGV4dD48L3N2Zz4=';
    img.alt = 'Image not found';
}

// Event Handlers
function handleViewToggle(e) {
    document.querySelectorAll('.view-btn').forEach(b => b.classList.remove('active'));
    e.target.classList.add('active');
    
    const viewType = e.target.dataset.view;
    // Implement view change logic here (grid vs list)
    console.log('Switching to view:', viewType);
}

function handleKeyboardShortcuts(e) {
    // Ctrl+F to focus search
    if (e.ctrlKey && e.key === 'f') {
        e.preventDefault();
        document.getElementById('searchBar').focus();
    }
    
    // Escape to clear search
    if (e.key === 'Escape') {
        const searchBar = document.getElementById('searchBar');
        if (document.activeElement === searchBar) {
            clearSearchInput();
        }
    }
    
    // Arrow keys for sensor navigation
    if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
        const sensorIds = getSensorIds();
        const currentIndex = sensorIds.indexOf(currentFilters.sensor);
        
        if (currentIndex !== -1) {
            let newIndex;
            if (e.key === 'ArrowLeft') {
                newIndex = currentIndex > 0 ? currentIndex - 1 : sensorIds.length - 1;
            } else {
                newIndex = currentIndex < sensorIds.length - 1 ? currentIndex + 1 : 0;
            }
            
            selectSensor(sensorIds[newIndex]);
        }
    }
}

// Infinite Scroll (optional)
function setupInfiniteScroll() {
    const processContent = document.getElementById('processContent');
    let scrollTimeout;
    
    processContent.addEventListener('scroll', (e) => {
        clearTimeout(scrollTimeout);
        scrollTimeout = setTimeout(() => {
            const { scrollTop, scrollHeight, clientHeight } = e.target;
            if (scrollHeight - scrollTop <= clientHeight + 100) {
                if (hasNextPage && !isLoading) {
                    loadMoreImages();
                }
            }
        }, 100);
    });
}

// Optional: Enable infinite scroll
// setupInfiniteScroll();

export {
    initializeApp,
    fetchImages,
    selectSensor,
    handleSearch,
    loadMoreImages
};