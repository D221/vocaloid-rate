// --- HELPER FUNCTIONS ---
const timeAgo = (date) => {
    const seconds = Math.floor((new Date() - new Date(date)) / 1000);
    let interval = seconds / 31536000;
    if (interval > 1) return `${Math.floor(interval)} years ago`;
    interval = seconds / 2592000;
    if (interval > 1) return `${Math.floor(interval)} months ago`;
    interval = seconds / 86400;
    if (interval > 1) return `${Math.floor(interval)} days ago`;
    interval = seconds / 3600;
    if (interval > 1) return `${Math.floor(interval)} hours ago`;
    interval = seconds / 60;
    if (interval > 1) return `${Math.floor(interval)} minutes ago`;
    return `${Math.floor(seconds)} seconds ago`;
};

const getYouTubeVideoId = (url) => {
    const regex = /(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu\.be\/)([^"&?\/ ]{11})/;
    return url.match(regex)?.[1] || null;
};

// --- CORE LOGIC FUNCTIONS ---
const formatAllDates = () => {
    document.querySelectorAll('.published-date').forEach(td => {
        if (td.dataset.date) td.textContent = timeAgo(td.dataset.date);
    });
};

const updateSortIndicators = () => {
    const params = new URLSearchParams(window.location.search);
    const sortBy = params.get('sort_by');
    const sortDir = params.get('sort_dir');
    document.querySelectorAll('th a[data-sort]').forEach(a => {
        a.classList.remove('active');
        a.textContent = a.textContent.replace(/ [▲▼]/, '');
        if (a.dataset.sort === sortBy) {
            a.classList.add('active');
            a.textContent += sortDir === 'desc' ? ' ▼' : ' ▲';
        }
    });
};

const updateTracks = async () => {
    const tableBody = document.getElementById('tracks-table-body');
    const filterForm = document.getElementById('filter-form');
    const baseUrl = tableBody.dataset.updateUrl;
    
    if (!baseUrl) return;

    const params = new URLSearchParams(window.location.search);
    if (filterForm) {
        const formData = new FormData(filterForm);
        formData.forEach((value, key) => {
            if (value) {
                params.set(key, value);
            } else {
                params.delete(key);
            }
        });
    }

    const fetchUrl = `${baseUrl}?${params.toString()}`;
    const browserUrl = `${window.location.pathname}?${params.toString()}`;

    const response = await fetch(fetchUrl);
    const html = await response.text();
    
    tableBody.innerHTML = html;
    window.history.pushState({}, '', browserUrl);
    
    formatAllDates();
    updateSortIndicators();
};

const handleEmbed = (embedButton) => {
    const videoId = getYouTubeVideoId(embedButton.dataset.youtubeUrl);
    const videoContainer = embedButton.nextElementSibling;
    if (!videoId) {
        window.open(embedButton.dataset.youtubeUrl, '_blank');
        return;
    }
    const iframe = document.createElement('iframe');
    iframe.width = "560";
    iframe.height = "315";
    iframe.src = `https://www.youtube.com/embed/${videoId}?autoplay=1`;
    iframe.frameBorder = "0";
    iframe.allow = "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture";
    iframe.allowFullscreen = true;
    
    videoContainer.innerHTML = '';
    videoContainer.appendChild(iframe);
    videoContainer.style.display = 'block';

    const closeButton = document.createElement('button');
    closeButton.className = 'close-embed-button';
    closeButton.textContent = 'Close';
    embedButton.insertAdjacentElement('afterend', closeButton);

    embedButton.style.display = 'none';
};

const handleCloseEmbed = (closeButton) => {
    const parentCell = closeButton.closest('td');
    if (!parentCell) return;
    const embedButton = parentCell.querySelector('.embed-button');
    const videoContainer = parentCell.querySelector('.youtube-embed-container');

    if (videoContainer) {
        videoContainer.innerHTML = '';
        videoContainer.style.display = 'none';
    }
    if (embedButton) {
        embedButton.style.display = 'inline-block';
    }
    closeButton.remove();
};

const updateThemeUI = () => {
    const themeIcon = document.getElementById('theme-icon');
    const themeText = document.getElementById('theme-text');
    if (!themeIcon || !themeText) return;
    const currentTheme = document.documentElement.dataset.theme;

    if (currentTheme === 'dark') {
        themeIcon.innerHTML = '&#9728;'; // Sun icon
        themeText.textContent = 'Light Mode';
    } else {
        themeIcon.innerHTML = '&#127769;'; // Moon icon
        themeText.textContent = 'Dark Mode';
    }
};

const toggleClearButton = (input) => {
    const wrapper = input.parentElement;
    const clearBtn = wrapper.querySelector('.clear-input-btn');
    if (clearBtn) {
        clearBtn.classList.toggle('visible', input.value.length > 0);
    }
};

// --- INITIALIZATION ---
document.addEventListener('DOMContentLoaded', () => {
    formatAllDates();
    updateSortIndicators();
    updateThemeUI();

    document.getElementById('theme-switcher')?.addEventListener('click', () => {
        const doc = document.documentElement;
        const newTheme = doc.dataset.theme === 'dark' ? 'light' : 'dark';
        doc.dataset.theme = newTheme;
        localStorage.setItem('theme', newTheme);
        updateThemeUI();
    });

    const filterForm = document.getElementById('filter-form');
    if (filterForm) {
        filterForm.addEventListener('input', (e) => {
            // Toggle the 'x' button visibility when typing in text fields
            if (e.target.matches('input[type="text"]')) {
                toggleClearButton(e.target);
            }
            // Update the tracks list on any filter change
            updateTracks();
        });

        // Check initial state of text inputs on page load
        filterForm.querySelectorAll('input[type="text"]').forEach(input => {
            toggleClearButton(input);
        });
    }

    const scrapeButton = document.getElementById('scrape-button');
    if (scrapeButton) {
        scrapeButton.addEventListener('click', (e) => {
            e.preventDefault();
            const scrapeStatus = document.getElementById('scrape-status');
            scrapeButton.disabled = true;
            scrapeButton.textContent = 'Checking...'; // New initial text
            
            fetch('/scrape', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    scrapeStatus.textContent = data.message;
                    const interval = setInterval(() => {
                        fetch('/api/scrape-status').then(res => res.json()).then(statusData => {
                            
                            if (statusData.status === 'no_changes') {
                                clearInterval(interval);
                                scrapeStatus.textContent = 'Ranking is already up-to-date.';
                                scrapeButton.disabled = false;
                                scrapeButton.textContent = 'Update Tracks';
                                setTimeout(() => { scrapeStatus.textContent = ''; }, 4000);
                            } 
                            else if (statusData.status === 'completed') {
                                clearInterval(interval);
                                scrapeStatus.textContent = 'Completed! Reloading...';
                                window.location.reload();
                            } else if (statusData.status === 'error') {
                                clearInterval(interval);
                                scrapeStatus.textContent = 'An error occurred. Check server logs.';
                                scrapeButton.disabled = false;
                                scrapeButton.textContent = 'Update Tracks';
                            } else if (statusData.status === 'in_progress') {
                                scrapeButton.textContent = 'Scraping...';
                                scrapeStatus.textContent = 'Changes found, updating...';
                            }
                        });
                    }, 2000);
                });
        });
    }

    // --- 10-STAR RATING LOGIC ---
    const updateStarPreview = (container, event) => {
        const rect = container.getBoundingClientRect();
        const mouseX = event.clientX - rect.left;
        const rating = Math.round((mouseX / rect.width) * 10);
        const clampedRating = Math.max(1, Math.min(10, rating));
        const widthPercentage = (clampedRating / 10.0) * 100;
        container.style.setProperty('--rating-width', `${widthPercentage}%`);
        return clampedRating;
    };

    document.body.addEventListener('mousemove', (e) => {
        const ratingContainer = e.target.closest('.star-rating-container');
        if (ratingContainer) {
            updateStarPreview(ratingContainer, e);
        }
    });

    document.body.addEventListener('mouseleave', (e) => {
        const ratingContainer = e.target.closest('.star-rating-container');
        if (ratingContainer) {
            const actualRating = parseFloat(ratingContainer.dataset.rating) || 0;
            const widthPercentage = (actualRating / 10.0) * 100;
            ratingContainer.style.setProperty('--rating-width', `${widthPercentage}%`);
        }
    }, true);

    // --- MASTER CLICK HANDLER ---
    document.body.addEventListener('click', (e) => {
        // Clear Input Button Click
        const clearBtn = e.target.closest('.clear-input-btn');
        if (clearBtn) {
            const wrapper = clearBtn.parentElement;
            const input = wrapper.querySelector('input');
            if (input) {
                input.value = '';
                input.focus();
                input.dispatchEvent(new Event('input', { bubbles: true }));
            }
            return;
        }
        
        // Star Rating Click
        const ratingContainer = e.target.closest('.star-rating-container');
        if (ratingContainer) {
            const rating = updateStarPreview(ratingContainer, e);
            const form = ratingContainer.closest('form');
            const radioToSelect = form.querySelector(`input[value="${rating}"]`);
            if (radioToSelect) {
                radioToSelect.checked = true;
                const formData = new FormData(form);
                fetch(form.action, { method: 'POST', body: formData }).then(() => {
                    ratingContainer.dataset.rating = rating;
                    updateStarPreview(ratingContainer, e);
                    if (!form.nextElementSibling?.matches('.delete-rating-form')) {
                        const deleteFormHTML = `<form action="${form.action}/delete" method="post" class="delete-rating-form"><button type="submit" class="clear-rating-btn">X</button></form>`;
                        form.parentElement.insertAdjacentHTML('beforeend', deleteFormHTML);
                    }
                });
            }
            return;
        }

        // Sort links
        const sortLink = e.target.closest('th a[data-sort]');
        if (sortLink) {
            e.preventDefault();
            const params = new URLSearchParams(window.location.search);
            const newSort = sortLink.dataset.sort;
            const currentSort = params.get('sort_by');
            const currentDir = params.get('sort_dir');
            let newDir = ['rank', 'published_date', 'rating'].includes(newSort) ? 'desc' : 'asc';
            if (newSort === currentSort) {
                newDir = currentDir === 'asc' ? 'desc' : 'asc';
            }
            params.set('sort_by', newSort);
            params.set('sort_dir', newDir);
            window.history.pushState({}, '', `${window.location.pathname}?${params.toString()}`);
            updateTracks();
            return;
        }
        
        // Table Filter links
        const filterLink = e.target.closest('a.filter-link');
        if (filterLink) {
            e.preventDefault();
            const filterType = filterLink.dataset.filterType;
            const filterValue = filterLink.dataset.filterValue;
            const inputField = document.getElementById(filterType);
            if (inputField) {
                inputField.value = filterValue;
                inputField.dispatchEvent(new Event('input', { bubbles: true }));
            }
            return;
        }

        // Embed and Close buttons
        const embedButton = e.target.closest('.embed-button');
        if (embedButton) { e.preventDefault(); handleEmbed(embedButton); return; }
        
        const closeEmbedButton = e.target.closest('.close-embed-button');
        if (closeEmbedButton) { e.preventDefault(); handleCloseEmbed(closeEmbedButton); return; }
    });

    document.querySelectorAll('.chart-bar').forEach(bar => {
        const width = bar.dataset.width;
        bar.style.width = width + '%';
    });

    // --- MASTER SUBMIT HANDLER ---
    document.body.addEventListener('submit', (e) => {
        const deleteForm = e.target.closest('.delete-rating-form');
        if (deleteForm) {
            e.preventDefault();
            fetch(deleteForm.action, { method: 'POST' }).then(() => {
                const ratingForm = deleteForm.previousElementSibling;
                const ratingContainer = ratingForm.querySelector('.star-rating-container');
                ratingContainer.dataset.rating = "0";
                ratingContainer.style.setProperty('--rating-width', '0%');
                ratingForm.querySelectorAll('input[type="radio"]').forEach(r => r.checked = false);
                if (window.location.pathname.includes('rated_tracks')) {
                    deleteForm.closest('tr').remove();
                } else {
                    deleteForm.remove();
                }
            });
        }
    });
});