let currentPage = 1;
let isLoading = false;
let loadingQueue = [];
let isProcessingQueue = false;

// Function to process the loading queue
async function processLoadingQueue() {
    if (isProcessingQueue || loadingQueue.length === 0) return;
    
    isProcessingQueue = true;
    
    while (loadingQueue.length > 0) {
        const imgElement = loadingQueue.shift();
        if (imgElement && imgElement.dataset.src) {
            // Start loading the image
            imgElement.src = imgElement.dataset.src;
            imgElement.classList.add('loading');
            
            // Wait for image to load or fail
            await new Promise((resolve) => {
                imgElement.onload = () => {
                    imgElement.classList.remove('loading');
                    imgElement.classList.add('fade-in');
                    setTimeout(resolve, 200); // Add small delay between loads
                };
                imgElement.onerror = () => {
                    imgElement.src = 'https://via.placeholder.com/150';
                    imgElement.classList.remove('loading');
                    imgElement.classList.add('error-image');
                    setTimeout(resolve, 200);
                };
            });
        }
    }
    
    isProcessingQueue = false;
}

// Create IntersectionObserver for detecting visible images
const imageObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        const img = entry.target;
        if (entry.isIntersecting && img.dataset.src) {
            // Add to loading queue if visible
            if (!loadingQueue.includes(img)) {
                loadingQueue.push(img);
                processLoadingQueue();
            }
        }
    });
}, {
    rootMargin: '50px 0px',
    threshold: 0.1
});

function createFileCard(file, index) {
    const fileCard = document.createElement('div');
    fileCard.className = 'file-card';
    
    // Add delay based on index for progressive loading
    const delay = Math.min(index * 100, 1000);
    fileCard.style.animation = `fadeIn 0.5s ease ${delay}ms forwards`;
    fileCard.style.opacity = '0';

    fileCard.innerHTML = `
        <div class="thumbnail">
            <div class="thumbnail-placeholder"></div>
            <img 
                class="lazy-image" 
                data-src="${file.image_url}" 
                alt="${file.file_name}"
            >
        </div>
        <div class="file-info">
            <h3 class="file-title">${file.file_name || 'Unnamed File'}</h3>
            <p class="file-size">${file.file_size || 'Unknown size'}</p>
            <a href="${file.share_link}" class="ep-link-btn" target="_blank">EP Link</a>
        </div>
    `;

    return fileCard;
}

async function loadFiles(page) {
    if (isLoading) return;
    
    try {
        isLoading = true;
        document.body.style.cursor = 'wait';
        
        // Clear existing loading queue
        loadingQueue = [];
        isProcessingQueue = false;
        
        const response = await fetch(`/files?page=${page}`);
        const data = await response.json();
        
        const container = document.getElementById('files-container');
        container.innerHTML = '';
        
        if (!data.data || data.data.length === 0) {
            container.innerHTML = '<div class="no-files">No files found</div>';
            return;
        }

        // Create and append all cards first
        data.data.forEach((file, index) => {
            const fileCard = createFileCard(file, index);
            container.appendChild(fileCard);
        });

        // Start observing all lazy images
        container.querySelectorAll('.lazy-image').forEach(img => {
            imageObserver.observe(img);
        });

        // Update pagination controls
        document.getElementById('prev-page').disabled = page <= 1;
        document.getElementById('next-page').disabled = page >= data.total_pages;
        document.getElementById('page-info').textContent = `Page ${page} of ${data.total_pages}`;
        currentPage = page;
        
        // Update URL without refreshing
        const url = new URL(window.location);
        url.searchParams.set('page', page);
        window.history.pushState({}, '', url);
        
    } catch (error) {
        console.error('Error loading files:', error);
        const container = document.getElementById('files-container');
        container.innerHTML = '<div class="error">Error loading files. Please try again.</div>';
    } finally {
        isLoading = false;
        document.body.style.cursor = 'default';
    }
}

// Handle browser back/forward buttons
window.addEventListener('popstate', () => {
    const params = new URLSearchParams(window.location.search);
    const page = parseInt(params.get('page')) || 1;
    loadFiles(page);
});

document.addEventListener('DOMContentLoaded', () => {
    const prevButton = document.getElementById('prev-page');
    const nextButton = document.getElementById('next-page');

    prevButton.addEventListener('click', () => {
        if (!isLoading && currentPage > 1) {
            loadFiles(currentPage - 1);
        }
    });

    nextButton.addEventListener('click', () => {
        if (!isLoading) {
            loadFiles(currentPage + 1);
        }
    });

    // Load initial page
    const params = new URLSearchParams(window.location.search);
    const initialPage = parseInt(params.get('page')) || 1;
    loadFiles(initialPage);
});