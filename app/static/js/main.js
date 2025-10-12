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
    let sortBy = params.get('sort_by');
    let sortDir = params.get('sort_dir');
    if (!sortBy) { sortBy = 'rank'; sortDir = 'asc'; }
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

    let skeletonTimer;

    // --- SMART SKELETON LOGIC ---
    // Set a timer. If the fetch takes longer than 250ms, THEN show the skeleton.
    const showSkeleton = () => {
        const skeletonRowHTML = `
            <tr class="skeleton-row">
                <td><div class="skeleton-bar"></div></td>
                <td><div class="skeleton-bar"></div></td>
                <td><div class="skeleton-bar"></div></td>
                <td><div class="skeleton-bar"></div></td>
                <td><div class="skeleton-bar"></div></td>
                <td><div class="skeleton-bar"></div></td>
                <td><div class="skeleton-bar"></div></td>
            </tr>
        `;
        tableBody.innerHTML = skeletonRowHTML.repeat(10);
    };

    // Start a 250ms timer.
    skeletonTimer = setTimeout(showSkeleton, 250);

    const params = new URLSearchParams(window.location.search);
    if (filterForm) {
        const formData = new FormData(filterForm);
        formData.forEach((value, key) => {
            if (value) params.set(key, value);
            else params.delete(key);
        });
    }
    const fetchUrl = `${baseUrl}?${params.toString()}`;
    const browserUrl = `${window.location.pathname}?${params.toString()}`;

    try {
        const response = await fetch(fetchUrl);
        // When the fetch completes, clear the timer BEFORE updating the DOM.
        clearTimeout(skeletonTimer);
        const html = await response.text();
        tableBody.innerHTML = html;
    } catch (error) {
        clearTimeout(skeletonTimer); // Also clear on error
        console.error("Failed to update tracks:", error);
        tableBody.innerHTML = '<tr><td colspan="7">Error loading tracks. Please try again.</td></tr>';
    }

    window.history.pushState({}, '', browserUrl);
    formatAllDates();
    updateSortIndicators();
};

const updateThemeUI = () => {
    const themeIcon = document.getElementById('theme-icon');
    const themeText = document.getElementById('theme-text');
    if (!themeIcon || !themeText) return;
    const currentTheme = document.documentElement.dataset.theme;
    if (currentTheme === 'dark') {
        themeIcon.innerHTML = '&#9728;';
        themeText.textContent = 'Light Mode';
    } else {
        themeIcon.innerHTML = '&#127769;';
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

const debounce = (func, delay) => {
    let timeoutId;
    return (...args) => {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => {
            func.apply(this, args);
        }, delay);
    };
};

// --- INITIALIZATION ---
document.addEventListener('DOMContentLoaded', () => {
    formatAllDates();
    updateSortIndicators();
    updateThemeUI();

    const chartCanvas = document.getElementById('ratingDistributionChart');
    if (chartCanvas) {
        try {
            const ratingsData = JSON.parse(chartCanvas.dataset.ratings);
            const labels = Object.keys(ratingsData).sort((a, b) => parseFloat(a) - parseFloat(b));
            const data = labels.map(label => ratingsData[label]);
            const isDarkMode = document.documentElement.dataset.theme === 'dark';

            const gridColor = isDarkMode ? 'rgba(255, 255, 255, 0.1)' : 'rgba(0, 0, 0, 0.1)';
            const ticksColor = isDarkMode ? '#e0e0e0' : '#333';

            const handleChartClick = (event, elements, chart) => {
                if (elements.length > 0) {
                    const clickedElementIndex = elements[0].index;
                    const ratingToFilter = chart.data.labels[clickedElementIndex].replace(' ★', '');

                    // Clear existing filters and set the new exact rating filter
                    const params = new URLSearchParams();
                    params.set('sort_by', 'rating');
                    params.set('sort_dir', 'desc');
                    params.set('exact_rating_filter', ratingToFilter);

                    window.history.pushState({}, '', `${window.location.pathname}?${params.toString()}`);
                    updateTracks();
                }
            };

            new Chart(chartCanvas, {
                type: 'bar',
                data: {
                    labels: labels.map(l => `${l} ★`),
                    datasets: [{
                        label: '# of Ratings',
                        data: data,
                        backgroundColor: isDarkMode ? 'rgba(144, 186, 255, 0.6)' : 'rgba(0, 123, 255, 0.6)',
                        borderColor: isDarkMode ? 'rgba(144, 186, 255, 1)' : 'rgba(0, 123, 255, 1)',
                        borderWidth: 1
                    }]
                },
                options: {
                    // ADD THIS ONCLICK HANDLER
                    onClick: handleChartClick,

                    // Make it obvious the bars are clickable
                    onHover: (event, chartElement) => {
                        event.native.target.style.cursor = chartElement[0] ? 'pointer' : 'default';
                    },

                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: { stepSize: 1, color: ticksColor },
                            grid: { color: gridColor }
                        },
                        x: {
                            ticks: { color: ticksColor },
                            grid: { display: false }
                        }
                    },
                    plugins: {
                        legend: { display: false }
                    }
                }
            });
        } catch (e) {
            console.error("Could not parse or render chart data:", e);
        }
    }

    const debouncedUpdateTracks = debounce(updateTracks, 300);
    const filterForm = document.getElementById('filter-form');
    if (filterForm) {
        filterForm.addEventListener('input', (e) => {
            if (e.target.matches('input[type="text"], input[type="search"]')) {
                toggleClearButton(e.target);
                debouncedUpdateTracks();
            } else {
                updateTracks();
            }
        });
        filterForm.querySelectorAll('input[type="text"], input[type="search"]').forEach(input => {
            toggleClearButton(input);
        });
    }

    document.getElementById('theme-switcher')?.addEventListener('click', () => {
        const doc = document.documentElement;
        const newTheme = doc.dataset.theme === 'dark' ? 'light' : 'dark';
        doc.dataset.theme = newTheme;
        localStorage.setItem('theme', newTheme);
        updateThemeUI();
    });

    const scrapeButton = document.getElementById('scrape-button');
    if (scrapeButton) {
        scrapeButton.addEventListener('click', (e) => {
            e.preventDefault();
            const scrapeStatus = document.getElementById('scrape-status');
            scrapeButton.disabled = true;
            scrapeButton.textContent = 'Checking...';
            fetch('/scrape', { method: 'POST' }).then(res => res.json()).then(data => {
                scrapeStatus.textContent = data.message;
                const interval = setInterval(() => {
                    fetch('/api/scrape-status').then(res => res.json()).then(statusData => {
                        if (statusData.status === 'no_changes') {
                            clearInterval(interval);
                            scrapeStatus.textContent = 'Ranking is already up-to-date.';
                            scrapeButton.disabled = false;
                            scrapeButton.textContent = 'Update Tracks';
                            setTimeout(() => { scrapeStatus.textContent = ''; }, 4000);
                        } else if (statusData.status === 'completed') {
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
        if (ratingContainer) updateStarPreview(ratingContainer, e);
    });

    document.body.addEventListener('mouseleave', (e) => {
        const ratingContainer = e.target.closest('.star-rating-container');
        if (ratingContainer) {
            const actualRating = parseFloat(ratingContainer.dataset.rating) || 0;
            const widthPercentage = (actualRating / 10.0) * 100;
            ratingContainer.style.setProperty('--rating-width', `${widthPercentage}%`);
        }
    }, true);

    document.body.addEventListener('click', (e) => {
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

        const ratingContainer = e.target.closest('.star-rating-container');
        if (ratingContainer) {
            const rating = updateStarPreview(ratingContainer, e);
            const form = ratingContainer.closest('form');
            const radioToSelect = form.querySelector(`input[value="${rating}"]`);
            if (radioToSelect) {
                radioToSelect.checked = true;
                const formData = new FormData(form);
                formData.set('rating', rating);
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

        const notesBtn = e.target.closest('.notes-toggle-btn');
        if (notesBtn) {
            e.preventDefault();
            const textarea = notesBtn.nextElementSibling;
            const isVisible = textarea.style.display !== 'none';
            textarea.style.display = isVisible ? 'none' : 'block';
            notesBtn.textContent = textarea.value.trim().length > 0 ? 'Edit Note' : 'Add Note';

            if (!isVisible) {
                textarea.focus();
            }
            return;
        }

        const sortLink = e.target.closest('th a[data-sort]');
        if (sortLink) {
            e.preventDefault();
            const params = new URLSearchParams(window.location.search);
            const newSort = sortLink.dataset.sort;
            const currentSort = params.get('sort_by');
            const currentDir = params.get('sort_dir');
            let newDir = ['published_date', 'rating'].includes(newSort) ? 'desc' : 'asc';
            if (newSort === currentSort) newDir = currentDir === 'asc' ? 'desc' : 'asc';
            params.set('sort_by', newSort);
            params.set('sort_dir', newDir);
            window.history.pushState({}, '', `${window.location.pathname}?${params.toString()}`);
            updateTracks();
            return;
        }

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

        const vocadbBtn = e.target.closest('.vocadb-button');
        if (vocadbBtn) {
            e.preventDefault();
            const titleEn = encodeURIComponent(vocadbBtn.dataset.titleEn);
            const titleJp = vocadbBtn.dataset.titleJp ? encodeURIComponent(vocadbBtn.dataset.titleJp) : '';
            const producer = encodeURIComponent(vocadbBtn.dataset.producer);
            vocadbBtn.disabled = true;
            vocadbBtn.textContent = '...';
            fetch(`/api/vocadb_search?title_en=${titleEn}&producer=${producer}&title_jp=${titleJp}`)
                .then(response => response.ok ? response.json() : Promise.reject('Search failed'))
                .then(data => {
                    if (data.url) window.open(data.url, '_blank');
                    else alert('Track not found on VocaDB.');
                })
                .catch(() => alert('Could not search VocaDB.'))
                .finally(() => {
                    vocadbBtn.disabled = false;
                    vocadbBtn.textContent = 'VocaDB';
                });
            return;
        }

        const embedButton = e.target.closest('.embed-button');
        if (embedButton) {
            e.preventDefault();
            const parentCell = embedButton.closest('td');
            const videoContainer = parentCell.querySelector('.youtube-embed-container');
            if (embedButton.classList.toggle('is-open')) {
                const videoId = getYouTubeVideoId(embedButton.dataset.youtubeUrl);
                if (!videoId) { window.open(embedButton.dataset.youtubeUrl, '_blank'); return; }
                const iframe = document.createElement('iframe');
                iframe.width = "560"; iframe.height = "315";
                iframe.src = `https://www.youtube.com/embed/${videoId}?autoplay=1`;
                iframe.frameBorder = "0";
                iframe.allow = "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture";
                iframe.allowFullscreen = true;
                videoContainer.innerHTML = '';
                videoContainer.appendChild(iframe);
                videoContainer.style.display = 'block';
                embedButton.textContent = 'Close';
            } else {
                videoContainer.innerHTML = '';
                videoContainer.style.display = 'none';
                embedButton.textContent = 'Embed';
            }
            return;
        }

        const lyricsButton = e.target.closest('.lyrics-button');
        if (lyricsButton) {
            e.preventDefault();
            const parentCell = lyricsButton.closest('td');
            const lyricsContainer = parentCell.querySelector('.lyrics-container');
            const lyricsSelect = lyricsContainer.querySelector('.lyrics-select');
            const lyricsMetadata = lyricsContainer.querySelector('.lyrics-metadata');
            const lyricsContent = lyricsContainer.querySelector('.lyrics-content');

            if (lyricsButton.classList.toggle('is-open')) {
                lyricsButton.textContent = 'Close';
                if (lyricsContainer.dataset.loaded === 'true') {
                    lyricsContainer.style.display = 'block';
                } else {
                    lyricsButton.disabled = true;
                    lyricsButton.textContent = '...';
                    const titleEn = encodeURIComponent(lyricsButton.dataset.titleEn);
                    const titleJp = lyricsButton.dataset.titleJp ? encodeURIComponent(lyricsButton.dataset.titleJp) : '';
                    const producer = encodeURIComponent(lyricsButton.dataset.producer);
                    let allLyricsData = [];
                    const renderLyric = (index) => {
                        const selectedLyric = allLyricsData[index];
                        if (!selectedLyric) return;
                        let metadataHTML = `Type: <strong>${selectedLyric.translation_type}</strong>`;
                        if (selectedLyric.source) {
                            metadataHTML += ` | Source: `;
                            if (selectedLyric.url) {
                                metadataHTML += `<a href="${selectedLyric.url}" target="_blank">${selectedLyric.source}</a>`;
                            } else {
                                metadataHTML += selectedLyric.source;
                            }
                        }
                        lyricsMetadata.innerHTML = metadataHTML;
                        lyricsContent.innerHTML = selectedLyric.text;
                    };
                    fetch(`/api/vocadb_search?title_en=${titleEn}&producer=${producer}&title_jp=${titleJp}`)
                        .then(res => res.ok ? res.json() : Promise.reject('Song not found'))
                        .then(searchData => searchData.song_id ? fetch(`/api/vocadb_lyrics/${searchData.song_id}`) : Promise.reject('Song not found'))
                        .then(res => res.ok ? res.json() : Promise.reject('Lyrics not available'))
                        .then(data => {
                            allLyricsData = data.lyrics;
                            if (allLyricsData.length === 0) return Promise.reject('No lyrics found');
                            lyricsSelect.innerHTML = '';
                            allLyricsData.forEach((lyric, index) => {
                                const option = document.createElement('option');
                                option.value = index;
                                option.textContent = lyric.label;
                                lyricsSelect.appendChild(option);
                            });
                            renderLyric(0);
                            lyricsContainer.style.display = 'block';
                            lyricsContainer.dataset.loaded = 'true';
                            if (!lyricsSelect.dataset.listener) {
                                lyricsSelect.addEventListener('change', (e) => renderLyric(e.target.value));
                                lyricsSelect.dataset.listener = 'true';
                            }
                        })
                        .catch(errorMsg => {
                            lyricsMetadata.innerHTML = '';
                            lyricsContent.innerHTML = `<em>${errorMsg}</em>`;
                            lyricsContainer.style.display = 'block';
                            lyricsContainer.dataset.loaded = 'false';
                            setTimeout(() => { if (!lyricsButton.classList.contains('is-open')) { lyricsContainer.style.display = 'none'; } }, 4000);
                        })
                        .finally(() => {
                            lyricsButton.disabled = false;
                            if (lyricsButton.classList.contains('is-open')) {
                                lyricsButton.textContent = 'Close';
                            } else {
                                lyricsButton.textContent = 'Lyrics';
                            }
                        });
                }
            } else {
                lyricsContainer.style.display = 'none';
                lyricsButton.textContent = 'Lyrics';
            }
            return;
        }
    });

    document.body.addEventListener('blur', (e) => {
        const notesInput = e.target.closest('.notes-input');
        if (notesInput) {
            const form = notesInput.closest('form');
            const ratingContainer = form.querySelector('.star-rating-container');
            const currentRating = parseFloat(ratingContainer.dataset.rating) || 0;

            // Only save if there is already a rating for this track.
            if (currentRating > 0) {
                const formData = new FormData(form);

                // Ensure the rating value is included, as it's required by the backend.
                formData.set('rating', currentRating);

                fetch(form.action, { method: 'POST', body: formData }).then(() => {
                    // Optional: add a "Saved!" confirmation message
                    const notesBtn = form.querySelector('.notes-toggle-btn');

                    // Toggle the green class based on whether there's text
                    notesBtn.classList.toggle('has-note', notesInput.value.trim().length > 0);

                    const originalText = notesBtn.textContent;
                    notesBtn.textContent = 'Saved!';
                    setTimeout(() => { notesBtn.textContent = originalText; }, 2000);
                });
            }
        }
    }, true);


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
