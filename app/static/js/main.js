// --- HELPER FUNCTIONS ---
const debounce = (func, delay) => {
	let timeoutId;
	return (...args) => {
		clearTimeout(timeoutId);
		timeoutId = setTimeout(() => {
			func.apply(this, args);
		}, delay);
	};
};
const timeAgo = (date) => {
	const seconds = Math.floor((Date.now() - new Date(date)) / 1000);
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
	const regex =
		/(?:youtube\.com\/(?:[^/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu\.be\/)([^"&?/ ]{11})/;
	return url.match(regex)?.[1] || null;
};

const formatAllDates = () => {
	document.querySelectorAll(".published-date").forEach((td) => {
		if (td.dataset.date) td.textContent = timeAgo(td.dataset.date);
	});
};

const formatTime = (seconds) => {
	const minutes = Math.floor(seconds / 60);
	const secs = Math.floor(seconds % 60);
	return `${minutes}:${secs.toString().padStart(2, "0")}`;
};

const updateSortIndicators = () => {
	const params = new URLSearchParams(window.location.search);
	let sortBy = params.get("sort_by");
	let sortDir = params.get("sort_dir");
	if (!sortBy) {
		if (window.location.pathname.includes("rated_tracks")) {
			sortBy = "rating";
			sortDir = "desc";
		} else {
			sortBy = "rank";
			sortDir = "asc";
		}
	}
	document.querySelectorAll("th a[data-sort]").forEach((a) => {
		a.classList.remove("active");
		a.textContent = a.textContent.replace(/ [▲▼]/, "");
		if (a.dataset.sort === sortBy) {
			a.classList.add("active");
			a.textContent += sortDir === "desc" ? " ▼" : " ▲";
		}
	});
};
let currentPage = 1;
let currentLimit = localStorage.getItem("defaultPageSize") || "all";

const buildPlaylistFromDOM = () => {
	const tableBody = document.getElementById("tracks-table-body");
	if (!tableBody) return;

	const allRows = Array.from(tableBody.querySelectorAll("tr[data-track-id]"));
	playerState.playlist = allRows
		.map((row) => {
			const titleLink = row.querySelector("td:nth-child(3) a");
			const producerLink = row.querySelector("td:nth-child(4) a");
			const playButton = row.querySelector(".track-play-button");
			const imageUrl = row.querySelector("td:nth-child(1) img")?.src;
			if (!playButton || !imageUrl) return null; // Skip skeleton rows
			return {
				id: playButton.dataset.trackId,
				title: titleLink ? titleLink.textContent.trim() : "Unknown",
				producer: producerLink ? producerLink.textContent.trim() : "Unknown",
				link: titleLink ? titleLink.href : "",
				imageUrl: imageUrl,
			};
		})
		.filter((t) => t && t.id); // Filter out any nulls

	if (playerState.isShuffle) {
		generateShuffledPlaylist();
	}
};

let ytPlayer;
let progressUpdateInterval;
const playerState = {
	isPlaying: false,
	currentTrackId: null,
	playlist: [],
	shuffledPlaylist: [],
	volume: 100,
	isMuted: false,
	isEmbedded: false,
	isShuffle: false,
	isRepeat: false,
	embeddedPlayers: {}, // Track embedded players by track ID
};

const musicPlayerEl = document.getElementById("music-player");
const playPauseBtn = document.getElementById("player-play-pause-btn");
const nextBtn = document.getElementById("player-next-btn");
const prevBtn = document.getElementById("player-prev-btn");
const stopBtn = document.getElementById("player-stop-btn");
const volumeSlider = document.getElementById("player-volume-slider");
const muteBtn = document.getElementById("player-mute-btn");
const progressBar = document.getElementById("player-progress-bar");
const currentTimeEl = document.getElementById("player-current-time");
const durationEl = document.getElementById("player-duration");

function onPlayerError(event) {
	console.error("YouTube Player Error:", event.data);
	alert(
		`Could not play this video.\n\nThis might be because the uploader has disabled embedding, or the video is private/deleted.\n(Error code: ${event.data})`,
	);
	playNextTrack(); // Attempt to play the next track
}

function onPlayerStateChange(event) {
	if (event.data === YT.PlayerState.PLAYING) {
		playerState.isPlaying = true;
		startProgressUpdater();
		updatePlayerUI();
	} else if (event.data === YT.PlayerState.PAUSED) {
		playerState.isPlaying = false;
		stopProgressUpdater();
		updatePlayerUI();
	} else if (event.data === YT.PlayerState.ENDED) {
		if (playerState.isRepeat) {
			// If repeat is on, just seek to the beginning and play again
			const activePlayer =
				playerState.embeddedPlayers[playerState.currentTrackId] || ytPlayer;
			if (activePlayer) {
				activePlayer.seekTo(0, true);
				activePlayer.playVideo();
			}
		} else {
			// Otherwise, play the next track
			playNextTrack();
		}
	}
}

function startProgressUpdater() {
	stopProgressUpdater();
	progressUpdateInterval = setInterval(() => {
		let activePlayer;

		// Use embedded player if in embed mode
		if (
			playerState.isEmbedded &&
			playerState.embeddedPlayers[playerState.currentTrackId]
		) {
			activePlayer = playerState.embeddedPlayers[playerState.currentTrackId];
		} else {
			activePlayer = ytPlayer;
		}

		if (activePlayer && playerState.isPlaying) {
			const currentTime = activePlayer.getCurrentTime();
			const duration = activePlayer.getDuration();
			if (duration > 0) {
				progressBar.value = (currentTime / duration) * 100;
				currentTimeEl.textContent = formatTime(currentTime);
				durationEl.textContent = formatTime(duration);
			}
		}
	}, 250);
}

function stopProgressUpdater() {
	clearInterval(progressUpdateInterval);
}

function seekVideo() {
	let activePlayer;

	if (
		playerState.isEmbedded &&
		playerState.embeddedPlayers[playerState.currentTrackId]
	) {
		activePlayer = playerState.embeddedPlayers[playerState.currentTrackId];
	} else {
		activePlayer = ytPlayer;
	}

	if (activePlayer) {
		const duration = activePlayer.getDuration();
		if (duration > 0) {
			const seekToTime = (progressBar.value / 100) * duration;
			activePlayer.seekTo(seekToTime, true);
		}
	}
}

function loadAndPlayTrack(trackId) {
	const trackIndex = playerState.playlist.findIndex((t) => t.id === trackId);
	if (trackIndex === -1) return;

	// Always ensure we are in audio mode when this is called directly
	playerState.isEmbedded = false;
	playerState.currentTrackId = trackId;

	const track = playerState.playlist[trackIndex];
	const videoId = getYouTubeVideoId(track.link);

	if (!videoId) {
		alert("Could not find a valid YouTube video ID.");
		return;
	}

	// Show the player UI immediately
	musicPlayerEl.classList.remove("music-player-hidden");
	updatePlayerUI();

	// If player exists, just load the video.
	if (ytPlayer) {
		ytPlayer.loadVideoById(videoId);
	} else {
		// --- THIS IS THE FIX ---
		// If the main player doesn't exist yet, create it now.
		ytPlayer = new YT.Player("youtube-player-container", {
			height: "180",
			width: "320",
			videoId: videoId,
			playerVars: {
				playsinline: 1,
				autoplay: 1,
			},
			events: {
				onReady: (event) => {
					event.target.setVolume(playerState.volume);
					if (playerState.isMuted) event.target.mute();
				},
				onStateChange: onPlayerStateChange,
				onError: onPlayerError,
			},
		});
	}
}

function playNextTrack() {
	const activePlaylist = playerState.isShuffle
		? playerState.shuffledPlaylist
		: playerState.playlist;

	const wasInEmbedMode = playerState.isEmbedded;
	const previousTrackId = playerState.currentTrackId;

	const currentIndex = activePlaylist.findIndex(
		(t) => t.id === playerState.currentTrackId,
	);
	if (currentIndex === -1) return;

	const nextIndex = (currentIndex + 1) % activePlaylist.length;
	const nextTrack = activePlaylist[nextIndex];

	// Close previous embed if in embed mode
	if (wasInEmbedMode && previousTrackId) {
		const prevRow = document.querySelector(
			`tr[data-track-id="${previousTrackId}"]`,
		);
		if (prevRow) {
			const prevEmbedBtn = prevRow.querySelector(".embed-button.is-open");
			if (prevEmbedBtn) {
				// Manually close without triggering audio fallback
				if (playerState.embeddedPlayers[previousTrackId]) {
					playerState.embeddedPlayers[previousTrackId].destroy();
					delete playerState.embeddedPlayers[previousTrackId];
				}
				const container = prevRow.querySelector(".youtube-embed-container");
				if (container) {
					container.innerHTML = "";
					container.style.display = "none";
				}
				prevEmbedBtn.classList.remove("is-open");
				prevEmbedBtn.textContent = "Embed";
			}
		}
	}

	// Update current track
	playerState.currentTrackId = nextTrack.id;
	playerState.isEmbedded = false;

	// Update UI
	document.getElementById("player-thumbnail").src = nextTrack.imageUrl;
	document.getElementById("player-title").textContent = nextTrack.title;
	document.getElementById("player-producer").textContent = nextTrack.producer;
	updatePlayerUI();

	// If was in embed mode, open embed for new track
	if (wasInEmbedMode) {
		setTimeout(() => {
			const nextRow = document.querySelector(
				`tr[data-track-id="${nextTrack.id}"]`,
			);
			if (nextRow) {
				const nextEmbedBtn = nextRow.querySelector(".embed-button");
				if (nextEmbedBtn && !nextEmbedBtn.classList.contains("is-open")) {
					nextEmbedBtn.click();
				}
			}
		}, 300);
	} else {
		// Audio mode - load the track in hidden player
		const videoId = getYouTubeVideoId(nextTrack.link);
		if (ytPlayer && videoId) {
			ytPlayer.loadVideoById(videoId);
		} else if (videoId) {
			// Create player if it doesn't exist
			ytPlayer = new YT.Player("youtube-player-container", {
				height: "180",
				width: "320",
				videoId: videoId,
				playerVars: {
					playsinline: 1,
					autoplay: 1,
				},
				events: {
					onReady: (event) => {
						event.target.setVolume(playerState.volume);
						if (playerState.isMuted) event.target.mute();
					},
					onStateChange: onPlayerStateChange,
					onError: onPlayerError,
				},
			});
		}
	}
}

function playPrevTrack() {
	const activePlaylist = playerState.isShuffle
		? playerState.shuffledPlaylist
		: playerState.playlist;

	const wasInEmbedMode = playerState.isEmbedded;
	const previousTrackId = playerState.currentTrackId;

	const currentIndex = activePlaylist.findIndex(
		(t) => t.id === playerState.currentTrackId,
	);
	if (currentIndex === -1) return;

	const prevIndex =
		(currentIndex - 1 + activePlaylist.length) % activePlaylist.length;
	const prevTrack = activePlaylist[prevIndex];

	// Close previous embed if in embed mode
	if (wasInEmbedMode && previousTrackId) {
		const prevRow = document.querySelector(
			`tr[data-track-id="${previousTrackId}"]`,
		);
		if (prevRow) {
			const prevEmbedBtn = prevRow.querySelector(".embed-button.is-open");
			if (prevEmbedBtn) {
				// Manually close without triggering audio fallback
				if (playerState.embeddedPlayers[previousTrackId]) {
					playerState.embeddedPlayers[previousTrackId].destroy();
					delete playerState.embeddedPlayers[previousTrackId];
				}
				const container = prevRow.querySelector(".youtube-embed-container");
				if (container) {
					container.innerHTML = "";
					container.style.display = "none";
				}
				prevEmbedBtn.classList.remove("is-open");
				prevEmbedBtn.textContent = "Embed";
			}
		}
	}

	// Update current track
	playerState.currentTrackId = prevTrack.id;
	playerState.isEmbedded = false;

	// Update UI
	document.getElementById("player-thumbnail").src = prevTrack.imageUrl;
	document.getElementById("player-title").textContent = prevTrack.title;
	document.getElementById("player-producer").textContent = prevTrack.producer;
	updatePlayerUI();

	// If was in embed mode, open embed for new track
	if (wasInEmbedMode) {
		setTimeout(() => {
			const prevRow = document.querySelector(
				`tr[data-track-id="${prevTrack.id}"]`,
			);
			if (prevRow) {
				const prevEmbedBtn = prevRow.querySelector(".embed-button");
				if (prevEmbedBtn && !prevEmbedBtn.classList.contains("is-open")) {
					prevEmbedBtn.click();
				}
			}
		}, 300);
	} else {
		// Audio mode - load the track in hidden player
		const videoId = getYouTubeVideoId(prevTrack.link);
		if (ytPlayer && videoId) {
			ytPlayer.loadVideoById(videoId);
		} else if (videoId) {
			// Create player if it doesn't exist
			ytPlayer = new YT.Player("youtube-player-container", {
				height: "180",
				width: "320",
				videoId: videoId,
				playerVars: {
					playsinline: 1,
					autoplay: 1,
				},
				events: {
					onReady: (event) => {
						event.target.setVolume(playerState.volume);
						if (playerState.isMuted) event.target.mute();
					},
					onStateChange: onPlayerStateChange,
					onError: onPlayerError,
				},
			});
		}
	}
}

function togglePlayPause() {
	const currentTrackId = playerState.currentTrackId;

	// If there's an embedded player for the current track, control that
	if (playerState.isEmbedded && playerState.embeddedPlayers[currentTrackId]) {
		if (playerState.isPlaying) {
			playerState.embeddedPlayers[currentTrackId].pauseVideo();
		} else {
			playerState.embeddedPlayers[currentTrackId].playVideo();
		}
	} else if (ytPlayer) {
		// Control the hidden audio player
		if (playerState.isPlaying) {
			ytPlayer.pauseVideo();
		} else {
			ytPlayer.playVideo();
		}
	}
}

function stopPlayer() {
	if (ytPlayer) {
		ytPlayer.stopVideo();
	}

	// Close all embeds
	for (const trackId in playerState.embeddedPlayers) {
		if (playerState.embeddedPlayers[trackId]) {
			playerState.embeddedPlayers[trackId].destroy();
			delete playerState.embeddedPlayers[trackId];
		}
	}

	document.querySelectorAll(".embed-button.is-open").forEach((btn) => {
		btn.classList.remove("is-open");
		btn.textContent = "Embed";
		const container = btn
			.closest("td")
			.querySelector(".youtube-embed-container");
		if (container) {
			container.innerHTML = "";
			container.style.display = "none";
		}
	});

	playerState.isPlaying = false;
	playerState.currentTrackId = null;
	playerState.isEmbedded = false;
	stopProgressUpdater();
	musicPlayerEl.classList.add("music-player-hidden");
	progressBar.value = 0;
	currentTimeEl.textContent = "0:00";
	durationEl.textContent = "0:00";
	updatePlayerUI();
}

function generateShuffledPlaylist() {
	// Create a shuffled copy of the main playlist
	playerState.shuffledPlaylist = [...playerState.playlist];
	// Fisher-Yates shuffle algorithm
	for (let i = playerState.shuffledPlaylist.length - 1; i > 0; i--) {
		const j = Math.floor(Math.random() * (i + 1));
		[playerState.shuffledPlaylist[i], playerState.shuffledPlaylist[j]] = [
			playerState.shuffledPlaylist[j],
			playerState.shuffledPlaylist[i],
		];
	}
}

function updatePlayerUI() {
	playPauseBtn.innerHTML = playerState.isPlaying
		? "&#10074;&#10074;"
		: "&#9654;";

	// Clear previous highlights and icons
	document.querySelectorAll("tr.is-playing").forEach((row) => {
		row.classList.remove("is-playing");
	});
	document.querySelectorAll(".track-play-button.is-playing").forEach((btn) => {
		btn.innerHTML = "&#9654;"; // Reset to play icon
		btn.classList.remove("is-playing");
	});

	if (playerState.currentTrackId !== null) {
		const track = playerState.playlist.find(
			(t) => t.id === playerState.currentTrackId,
		);
		if (track) {
			// Update player info
			document.getElementById("player-thumbnail").src = track.imageUrl;
			document.getElementById("player-title").textContent = track.title;
			document.getElementById("player-producer").textContent = track.producer;

			// Find the corresponding row and play button in the table
			const trackRow = document.querySelector(
				`tr[data-track-id="${track.id}"]`,
			);
			if (trackRow) {
				// Highlight the row
				trackRow.classList.add("is-playing");

				// Update the play/pause icon in the table
				const playButtonInRow = trackRow.querySelector(".track-play-button");
				if (playButtonInRow) {
					playButtonInRow.innerHTML = playerState.isPlaying
						? "&#10074;&#10074;"
						: "&#9654;";
					playButtonInRow.classList.add("is-playing");
				}
			}
		}
	}

	volumeSlider.value = playerState.isMuted ? 0 : playerState.volume;
	muteBtn.innerHTML = playerState.isMuted ? "&#128263;" : "&#128266;";
}

const updatePaginationUI = (pagination) => {
	const pageLinks = document.getElementById("page-links");
	const prevButton = document.getElementById("prev-page-btn");
	const nextButton = document.getElementById("next-page-btn");
	const paginationContainer = document.getElementById("pagination-container");
	const limitFilter = document.getElementById("limit_filter");

	if (
		!pageLinks ||
		!prevButton ||
		!nextButton ||
		!limitFilter ||
		!paginationContainer
	)
		return;

	// Clear previous page links
	pageLinks.innerHTML = "";

	if (pagination.total_pages <= 1) {
		paginationContainer.style.display = "none";
		return;
	}

	paginationContainer.style.display = "flex";

	// Update prev/next buttons
	prevButton.disabled = pagination.page <= 1;
	nextButton.disabled = pagination.page >= pagination.total_pages;

	const createPageElement = (
		page,
		text = page,
		isCurrent = false,
		isDisabled = false,
	) => {
		if (isDisabled) {
			const ellipsis = document.createElement("span");
			ellipsis.className = "page-ellipsis";
			ellipsis.textContent = "...";
			return ellipsis;
		}
		const button = document.createElement("button");
		button.className = "page-btn";
		button.textContent = text;
		button.dataset.page = page;
		if (isCurrent) {
			button.classList.add("active");
		}
		return button;
	};

	const currentPage = pagination.page;
	const totalPages = pagination.total_pages;
	const pagesToShow = [];

	// --- FEATURE CHANGE: Logic to show all pages if total is 10 or less ---
	if (totalPages <= 10) {
		for (let i = 1; i <= totalPages; i++) {
			pagesToShow.push(i);
		}
	} else {
		// --- Use ellipsis logic for more than 10 pages ---
		const context = 2; // N pages before and after current page
		for (let i = 1; i <= totalPages; i++) {
			if (
				i === 1 ||
				i === totalPages ||
				(i >= currentPage - context && i <= currentPage + context)
			) {
				if (
					pagesToShow.length > 0 &&
					i > pagesToShow[pagesToShow.length - 1] + 1
				) {
					pagesToShow.push("...");
				}
				pagesToShow.push(i);
			}
		}
	}

	pagesToShow.forEach((p) => {
		if (p === "...") {
			pageLinks.appendChild(createPageElement(null, null, false, true));
		} else {
			pageLinks.appendChild(createPageElement(p, p, p === currentPage));
		}
	});

	limitFilter.value = pagination.limit;
};

const updateTracks = async () => {
	const tableBody = document.getElementById("tracks-table-body");
	const filterForm = document.getElementById("filter-form");
	const baseUrl = tableBody.dataset.updateUrl;
	if (!baseUrl) return;

	// Remember what was playing before we update the table.
	const currentTrackIdBeforeUpdate = playerState.currentTrackId;

	let skeletonTimer;
	const showSkeleton = () => {
		const skeletonRowHTML = `<tr class="skeleton-row"><td><div class="skeleton-bar"></div></td><td><div class="skeleton-bar"></div></td><td><div class="skeleton-bar"></div></td><td><div class="skeleton-bar"></div></td><td><div class="skeleton-bar"></div></td><td><div class="skeleton-bar"></div></td><td><div class="skeleton-bar"></div></td></tr>`;
		tableBody.innerHTML = skeletonRowHTML.repeat(10);
	};
	skeletonTimer = setTimeout(showSkeleton, 250);
	if (filterForm) {
		// 1. Start with all parameters currently in the URL's query string.
		//    This correctly preserves state from programmatic changes (like chart clicks).
		const newParams = new URLSearchParams(window.location.search);

		// 2. Let the current state of the form fields OVERRIDE the parameters.
		//    This ensures user input is always prioritized.
		const formData = new FormData(filterForm);
		formData.forEach((value, key) => {
			newParams.set(key, value);
		});

		// 3. Finally, set the pagination state from our JS variables.
		newParams.set("page", currentPage);
		newParams.set("limit", currentLimit);

		// --- END OF FIX ---
		const fetchUrl = `${baseUrl}?${newParams.toString()}`;
		const browserUrl = `${window.location.pathname}?${newParams.toString()}`;

		try {
			const response = await fetch(fetchUrl);
			clearTimeout(skeletonTimer);
			const data = await response.json();
			tableBody.innerHTML = data.table_body_html;

			// Immediately rebuild the playlist from the new DOM.
			buildPlaylistFromDOM();

			// Check if the previously playing track is still in the new list.
			if (currentTrackIdBeforeUpdate) {
				const isTrackStillVisible = playerState.playlist.some(
					(t) => t.id === currentTrackIdBeforeUpdate,
				);

				if (isTrackStillVisible) {
					// If it is, just update the UI to re-apply highlights.
					// The player's internal state (ID, isPlaying) is still valid.
					updatePlayerUI();
				} else {
					// If it was filtered out, stop the player completely.
					stopPlayer();
				}
			}

			updatePaginationUI(data.pagination);
		} catch (error) {
			clearTimeout(skeletonTimer);
			console.error("Failed to update tracks:", error);
			tableBody.innerHTML =
				'<tr><td colspan="7">Error loading tracks. Please try again.</td></tr>';
		}
		window.history.pushState({}, "", browserUrl);
		formatAllDates();
		updateSortIndicators();
		updateActiveFilterDisplay();
	}
};

const updateActiveFilterDisplay = () => {
	const container = document.getElementById(
		"rating-filter-indicator-container",
	);
	if (!container) return; // Only run on pages that have the container

	const params = new URLSearchParams(window.location.search);
	const ratingFilter = params.get("exact_rating_filter");

	if (ratingFilter) {
		container.innerHTML = `
            <div class="active-filter-indicator">
                <span>Filtering by rating: <strong>${ratingFilter} ★</strong></span>
                <button class="clear-rating-filter-btn" title="Clear rating filter">&times;</button>
            </div>
        `;
		container.style.display = "block";
	} else {
		container.innerHTML = "";
		container.style.display = "none";
	}
};

const updateThemeUI = () => {
	const themeIcon = document.getElementById("theme-icon");
	const themeText = document.getElementById("theme-text");
	if (!themeIcon || !themeText) return;
	const currentTheme = document.documentElement.dataset.theme;
	if (currentTheme === "dark") {
		themeIcon.innerHTML = "&#9728;";
		themeText.textContent = "Light Mode";
	} else {
		themeIcon.innerHTML = "&#127769;";
		themeText.textContent = "Dark Mode";
	}
};
const toggleClearButton = (input) => {
	const wrapper = input.parentElement;
	const clearBtn = wrapper.querySelector(".clear-input-btn");
	if (clearBtn) {
		clearBtn.classList.toggle("visible", input.value.length > 0);
	}
};

let ratingChart = null; // Variable to hold the chart instance

const renderRatingChart = () => {
	const chartCanvas = document.getElementById("ratingDistributionChart");
	if (!chartCanvas) return;
	if (ratingChart) {
		ratingChart.destroy();
	}
	try {
		const ratingsData = JSON.parse(chartCanvas.dataset.ratings);
		const labels = Object.keys(ratingsData).sort(
			(a, b) => parseFloat(a) - parseFloat(b),
		);
		const data = labels.map((label) => ratingsData[label]);
		const isDarkMode = document.documentElement.dataset.theme === "dark";
		const gridColor = isDarkMode
			? "rgba(255, 255, 255, 0.1)"
			: "rgba(0, 0, 0, 0.1)";
		const ticksColor = isDarkMode ? "#e0e0e0" : "#666";

		// --- THIS IS THE FIX ---
		// We wrap the handler in an anonymous function to pass the 'labels' array.
		const handleChartClick = (_event, elements) => {
			if (elements.length > 0) {
				const clickedElementIndex = elements[0].index;
				// It now correctly accesses the 'labels' array that was passed in.
				const ratingToFilter = labels[clickedElementIndex];

				const params = new URLSearchParams();
				params.set("sort_by", "rating");
				params.set("sort_dir", "desc");
				params.set("exact_rating_filter", ratingToFilter);
				window.history.pushState(
					{},
					"",
					`${window.location.pathname}?${params.toString()}`,
				);
				updateTracks();
			}
		};
		// --- END OF FIX ---

		ratingChart = new Chart(chartCanvas, {
			type: "bar",
			data: {
				labels: labels.map((l) => `${l} ★`),
				datasets: [
					{
						label: "# of Ratings",
						data: data,
						backgroundColor: isDarkMode
							? "rgba(144, 186, 255, 0.6)"
							: "rgba(0, 123, 255, 0.6)",
						borderColor: isDarkMode
							? "rgba(144, 186, 255, 1)"
							: "rgba(0, 123, 255, 1)",
						borderWidth: 1,
					},
				],
			},
			options: {
				// The onClick now calls our wrapper function
				onClick: handleChartClick,
				onHover: (event, chartElement) => {
					event.native.target.style.cursor = chartElement[0]
						? "pointer"
						: "default";
				},
				scales: {
					y: {
						beginAtZero: true,
						ticks: { stepSize: 1, color: ticksColor },
						grid: { color: gridColor },
					},
					x: { ticks: { color: ticksColor }, grid: { display: false } },
				},
				plugins: { legend: { display: false } },
			},
		});
	} catch (e) {
		console.error("Could not parse or render chart data:", e);
	}
};

// --- INITIALIZATION ---
document.addEventListener("DOMContentLoaded", () => {
	formatAllDates();
	updateSortIndicators();
	updateThemeUI();
	updateActiveFilterDisplay();

	const limitFilter = document.getElementById("limit_filter");
	if (limitFilter) {
		limitFilter.value = currentLimit;
		limitFilter.addEventListener("change", (e) => {
			currentLimit = e.target.value;
			currentPage = 1;
			updateTracks();
		});
	}

	const paginationContainer = document.getElementById("pagination-container");
	if (paginationContainer) {
		paginationContainer.addEventListener("click", (e) => {
			let pageChanged = false;
			// Handle previous button
			if (e.target.id === "prev-page-btn" && !e.target.disabled) {
				currentPage--;
				pageChanged = true;
			}
			// Handle next button
			if (e.target.id === "next-page-btn" && !e.target.disabled) {
				currentPage++;
				pageChanged = true;
			}
			// Handle specific page number buttons
			const pageButton = e.target.closest(".page-btn");
			if (pageButton && !pageButton.classList.contains("active")) {
				const page = parseInt(pageButton.dataset.page, 10);
				if (!Number.isNaN(page)) {
					currentPage = page;
					pageChanged = true;
				}
			}
			// If any page change happened, update the tracks
			if (pageChanged) {
				updateTracks();
			}
		});
	}

	renderRatingChart(); // Initial chart render

	const debouncedUpdateTracks = debounce(updateTracks, 300);
	const filterForm = document.getElementById("filter-form");
	if (filterForm) {
		filterForm.addEventListener("input", (e) => {
			currentPage = 1; // Reset page on filter change
			if (e.target.matches('input[type="text"], input[type="search"]')) {
				toggleClearButton(e.target);
				debouncedUpdateTracks();
			} else if (e.target.id !== "limit_filter") {
				// Any other form input (radios, selects) triggers an immediate update
				currentPage = 1; // Reset page on filter change
				updateTracks();
			}
		});
		filterForm
			.querySelectorAll('input[type="text"], input[type="search"]')
			.forEach((input) => {
				toggleClearButton(input);
			});
	}

	// --- Initial Page Load Logic ---
	// 1. Set state from URL or localStorage
	const urlParams = new URLSearchParams(window.location.search);
	currentPage = parseInt(urlParams.get("page"), 10) || 1;
	currentLimit =
		urlParams.get("limit") || localStorage.getItem("defaultPageSize") || "all";
	if (limitFilter) limitFilter.value = currentLimit;
	// 2. Fetch the initial view based on the resolved state
	updateTracks();

	document.getElementById("theme-switcher")?.addEventListener("click", () => {
		const doc = document.documentElement;
		const newTheme = doc.dataset.theme === "dark" ? "light" : "dark";
		doc.dataset.theme = newTheme;
		localStorage.setItem("theme", newTheme);
		updateThemeUI();
		renderRatingChart();
	});

	playPauseBtn.addEventListener("click", togglePlayPause);
	nextBtn.addEventListener("click", playNextTrack);
	prevBtn.addEventListener("click", playPrevTrack);
	stopBtn.addEventListener("click", stopPlayer);
	volumeSlider.addEventListener("input", (e) => {
		playerState.volume = e.target.value;
		playerState.isMuted = false;
		if (ytPlayer) {
			ytPlayer.setVolume(playerState.volume);
			ytPlayer.unMute();
		}
		updatePlayerUI();
	});
	muteBtn.addEventListener("click", () => {
		playerState.isMuted = !playerState.isMuted;
		if (ytPlayer) {
			if (playerState.isMuted) {
				ytPlayer.mute();
			} else {
				ytPlayer.unMute();
			}
		}
		updatePlayerUI();
	});

	const scrapeButton = document.getElementById("scrape-button");
	if (scrapeButton) {
		scrapeButton.addEventListener("click", (e) => {
			e.preventDefault();
			const scrapeStatus = document.getElementById("scrape-status");
			scrapeButton.disabled = true;
			scrapeButton.textContent = "Checking...";
			fetch("/scrape", { method: "POST" })
				.then((res) => res.json())
				.then((data) => {
					scrapeStatus.textContent = data.message;
					const interval = setInterval(() => {
						fetch("/api/scrape-status")
							.then((res) => res.json())
							.then((statusData) => {
								if (statusData.status === "no_changes") {
									clearInterval(interval);
									scrapeStatus.textContent = "Ranking is already up-to-date.";
									scrapeButton.disabled = false;
									scrapeButton.textContent = "Update Tracks";
									setTimeout(() => {
										scrapeStatus.textContent = "";
									}, 4000);
								} else if (statusData.status === "completed") {
									clearInterval(interval);
									scrapeStatus.textContent = "Completed! Reloading...";
									window.location.reload();
								} else if (statusData.status === "error") {
									clearInterval(interval);
									scrapeStatus.textContent =
										"An error occurred. Check server logs.";
									scrapeButton.disabled = false;
									scrapeButton.textContent = "Update Tracks";
								} else if (statusData.status === "in_progress") {
									scrapeButton.textContent = "Scraping...";
									scrapeStatus.textContent = "Changes found, updating...";
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
		container.style.setProperty("--rating-width", `${widthPercentage}%`);
		return clampedRating;
	};
	document.body.addEventListener("mousemove", (e) => {
		const ratingContainer = e.target.closest(".star-rating-container");
		if (ratingContainer) updateStarPreview(ratingContainer, e);
	});
	document.body.addEventListener(
		"mouseleave",
		(e) => {
			const ratingContainer = e.target.closest(".star-rating-container");
			if (ratingContainer) {
				const actualRating = parseFloat(ratingContainer.dataset.rating) || 0;
				const widthPercentage = (actualRating / 10.0) * 100;
				ratingContainer.style.setProperty(
					"--rating-width",
					`${widthPercentage}%`,
				);
			}
		},
		true,
	);

	document.body.addEventListener("click", (e) => {
		const clearRatingBtn = e.target.closest(".clear-rating-btn");
		if (clearRatingBtn) {
			e.preventDefault();
			const deleteForm = clearRatingBtn.closest("form");
			if (!deleteForm) return; // Safety check

			fetch(deleteForm.action, { method: "POST" }).then(() => {
				// Find the main rating form, which is the sibling before the delete form
				const ratingForm = deleteForm.previousElementSibling;
				if (ratingForm) {
					const ratingContainer = ratingForm.querySelector(
						".star-rating-container",
					);
					ratingContainer.dataset.rating = "0";
					ratingContainer.style.setProperty("--rating-width", "0%");
					ratingForm.querySelectorAll('input[type="radio"]').forEach((r) => {
						r.checked = false;
					});
				}

				// If we are on the rated_tracks page, remove the entire table row
				if (window.location.pathname.includes("rated_tracks")) {
					deleteForm.closest("tr").remove();
				} else {
					// Otherwise, just remove the delete form/button itself
					deleteForm.remove();
				}
			});
			return; // Stop processing other click handlers
		}

		const trackPlayBtn = e.target.closest(".track-play-button");
		if (trackPlayBtn) {
			e.preventDefault();
			const trackId = trackPlayBtn.dataset.trackId;

			// The playlist is now built/rebuilt by updateTracks,
			// so we just check if it's empty on the very first play action of a page load.
			if (playerState.playlist.length === 0) {
				buildPlaylistFromDOM();
			}

			// If the clicked track is the one already playing, just toggle play/pause
			if (trackId === playerState.currentTrackId) {
				togglePlayPause();
				return;
			}

			// Otherwise, play the new track
			loadAndPlayTrack(trackId);
			return;
		}

		const clearBtn = e.target.closest(".clear-input-btn");
		if (clearBtn) {
			const wrapper = clearBtn.parentElement;
			const input = wrapper.querySelector("input");
			if (input) {
				input.value = "";
				input.focus();
				input.dispatchEvent(new Event("input", { bubbles: true }));
			}
			return;
		}

		const ratingContainer = e.target.closest(".star-rating-container");
		if (ratingContainer) {
			const rating = updateStarPreview(ratingContainer, e);
			const form = ratingContainer.closest("form");
			const radioToSelect = form.querySelector(`input[value="${rating}"]`);
			if (radioToSelect) {
				radioToSelect.checked = true;
				const formData = new FormData(form);
				formData.set("rating", rating);
				fetch(form.action, { method: "POST", body: formData }).then(() => {
					ratingContainer.dataset.rating = rating;
					updateStarPreview(ratingContainer, e);
					if (!form.nextElementSibling?.matches(".delete-rating-form")) {
						const deleteFormHTML = `<form action="${form.action}/delete" method="post" class="delete-rating-form"><button type="submit" class="clear-rating-btn">X</button></form>`;
						form.parentElement.insertAdjacentHTML("beforeend", deleteFormHTML);
					}
				});
			}
			return;
		}

		const notesBtn = e.target.closest(".notes-toggle-btn");
		if (notesBtn) {
			e.preventDefault();
			const textarea = notesBtn.nextElementSibling;
			const isVisible = textarea.style.display !== "none";
			textarea.style.display = isVisible ? "none" : "block";
			notesBtn.textContent =
				textarea.value.trim().length > 0 ? "Edit Note" : "Add Note";

			if (!isVisible) {
				textarea.focus();
			}
			return;
		}

		const sortLink = e.target.closest("th a[data-sort]");
		if (sortLink) {
			e.preventDefault();
			const params = new URLSearchParams(window.location.search);
			const newSort = sortLink.dataset.sort;
			const currentSort = params.get("sort_by");
			const currentDir = params.get("sort_dir");
			let newDir = ["published_date", "rating"].includes(newSort)
				? "desc"
				: "asc";
			if (newSort === currentSort)
				newDir = currentDir === "asc" ? "desc" : "asc";
			params.set("sort_by", newSort);
			params.set("sort_dir", newDir);
			currentPage = 1; // Reset page on sort change
			window.history.pushState(
				{},
				"",
				`${window.location.pathname}?${params.toString()}`,
			);
			updateTracks();
			return;
		}

		const filterLink = e.target.closest("a.filter-link");
		if (filterLink) {
			e.preventDefault();
			const filterType = filterLink.dataset.filterType;
			const filterValue = filterLink.dataset.filterValue;
			const inputField = document.getElementById(filterType);
			if (inputField) {
				inputField.value = filterValue;
				inputField.dispatchEvent(new Event("input", { bubbles: true }));
			}
			return;
		}

		const clearRatingFilterBtn = e.target.closest(".clear-rating-filter-btn");
		if (clearRatingFilterBtn) {
			e.preventDefault();
			const params = new URLSearchParams(window.location.search);
			params.delete("exact_rating_filter");
			// When clearing, also remove sort to go back to default view
			params.delete("sort_by");
			params.delete("sort_dir");

			window.history.pushState(
				{},
				"",
				`${window.location.pathname}?${params.toString()}`,
			);
			updateTracks();
			return;
		}

		const vocadbBtn = e.target.closest(".vocadb-button");
		if (vocadbBtn) {
			e.preventDefault();
			const titleEn = encodeURIComponent(vocadbBtn.dataset.titleEn);
			const titleJp = vocadbBtn.dataset.titleJp
				? encodeURIComponent(vocadbBtn.dataset.titleJp)
				: "";
			const producer = encodeURIComponent(vocadbBtn.dataset.producer);
			vocadbBtn.disabled = true;
			vocadbBtn.textContent = "...";
			fetch(
				`/api/vocadb_search?title_en=${titleEn}&producer=${producer}&title_jp=${titleJp}`,
			)
				.then((res) => (res.ok ? res.json() : Promise.reject("Search failed")))
				.then((data) => {
					if (data.url) window.open(data.url, "_blank");
					else alert("Track not found on VocaDB.");
				})
				.catch(() => alert("Could not search VocaDB."))
				.finally(() => {
					vocadbBtn.disabled = false;
					vocadbBtn.textContent = "VocaDB";
				});
			return;
		}

		const vocadbProducerBtn = e.target.closest(".vocadb-producer-button");
		if (vocadbProducerBtn) {
			e.preventDefault();
			const producer = vocadbProducerBtn.dataset.producer;
			vocadbProducerBtn.disabled = true;
			vocadbProducerBtn.textContent = "...";
			fetch(
				`/api/vocadb_artist_search?producer=${encodeURIComponent(producer)}`,
			)
				.then((res) => (res.ok ? res.json() : Promise.reject("Search failed")))
				.then((data) => {
					if (data.url) {
						window.open(data.url, "_blank");
					} else {
						alert("Producer not found on VocaDB.");
					}
				})
				.catch(() => alert("Could not search VocaDB for this producer."))
				.finally(() => {
					vocadbProducerBtn.disabled = false;
					vocadbProducerBtn.textContent = "VDB";
				});
			return;
		}

		const embedButton = e.target.closest(".embed-button");
		if (embedButton) {
			e.preventDefault();
			const trackRow = embedButton.closest("tr");
			const trackId = trackRow.dataset.trackId;
			const parentCell = embedButton.closest("td");
			const videoContainer = parentCell.querySelector(
				".youtube-embed-container",
			);

			// Close any other open embeds (except the currently playing one)
			document.querySelectorAll(".embed-button.is-open").forEach((openBtn) => {
				const otherRow = openBtn.closest("tr");
				const otherTrackId = otherRow.dataset.trackId;
				if (
					openBtn !== embedButton &&
					otherTrackId !== playerState.currentTrackId
				) {
					openBtn.click();
				}
			});

			// Build playlist if needed
			const tableBody = trackRow.closest("tbody");
			if (!tableBody.dataset.playlistBuilt) {
				const allRows = Array.from(tableBody.querySelectorAll("tr"));
				playerState.playlist = allRows
					.map((row) => {
						const titleLink = row.querySelector("td:nth-child(3) a");
						const producerLink = row.querySelector("td:nth-child(4) a");
						const playButton = row.querySelector(".track-play-button");
						return {
							id: playButton ? playButton.dataset.trackId : null,
							title: titleLink ? titleLink.textContent.trim() : "Unknown",
							producer: producerLink
								? producerLink.textContent.trim()
								: "Unknown",
							link: titleLink ? titleLink.href : "",
							imageUrl: row.querySelector("td:nth-child(1) img").src,
						};
					})
					.filter((t) => t.id);
				tableBody.dataset.playlistBuilt = "true";
			}

			// Show the player menu
			musicPlayerEl.classList.remove("music-player-hidden");

			// If this track isn't loaded yet, set it as current
			if (playerState.currentTrackId !== trackId) {
				playerState.currentTrackId = trackId;
				const track = playerState.playlist.find((t) => t.id === trackId);
				if (track) {
					document.getElementById("player-thumbnail").src = track.imageUrl;
					document.getElementById("player-title").textContent = track.title;
					document.getElementById("player-producer").textContent =
						track.producer;
				}
			}

			if (embedButton.classList.toggle("is-open")) {
				const videoId = getYouTubeVideoId(embedButton.dataset.youtubeUrl);
				if (!videoId) {
					window.open(embedButton.dataset.youtubeUrl, "_blank");
					return;
				}

				// Create embedded player div
				const embedId = `embedded-player-${trackId}`;
				videoContainer.innerHTML = `<div id="${embedId}" style="width: 100%; aspect-ratio: 16/9;"></div>`;
				videoContainer.style.display = "block";
				embedButton.textContent = "Close";

				// Create YouTube player for this embed
				playerState.embeddedPlayers[trackId] = new YT.Player(embedId, {
					height: "100%",
					width: "100%",
					videoId: videoId,
					playerVars: {
						playsinline: 1,
						autoplay: 1,
					},
					events: {
						onReady: (event) => {
							// If this is the currently playing track, sync it
							if (trackId === playerState.currentTrackId && ytPlayer) {
								const currentTime = ytPlayer.getCurrentTime();
								const wasPlaying = playerState.isPlaying;

								ytPlayer.pauseVideo();
								event.target.seekTo(currentTime, true);
								if (wasPlaying) {
									event.target.playVideo();
								}
								playerState.isEmbedded = true;
							}
						},
						onStateChange: (event) => {
							if (event.data === YT.PlayerState.PLAYING) {
								// This embed started playing
								if (trackId !== playerState.currentTrackId) {
									// Switch to this track
									playerState.currentTrackId = trackId;
									const track = playerState.playlist.find(
										(t) => t.id === trackId,
									);
									if (track) {
										document.getElementById("player-thumbnail").src =
											track.imageUrl;
										document.getElementById("player-title").textContent =
											track.title;
										document.getElementById("player-producer").textContent =
											track.producer;
									}
								}

								// Pause the hidden player
								if (ytPlayer) ytPlayer.pauseVideo();

								// Pause other embeds
								for (const id in playerState.embeddedPlayers) {
									if (id !== trackId && playerState.embeddedPlayers[id]) {
										playerState.embeddedPlayers[id].pauseVideo();
									}
								}

								playerState.isPlaying = true;
								playerState.isEmbedded = true;
								startProgressUpdater();
								updatePlayerUI();
							} else if (event.data === YT.PlayerState.PAUSED) {
								if (trackId === playerState.currentTrackId) {
									playerState.isPlaying = false;
									stopProgressUpdater();
									updatePlayerUI();
								}
							} else if (event.data === YT.PlayerState.ENDED) {
								if (trackId === playerState.currentTrackId) {
									playNextTrack();
								}
							}
						},
						onError: onPlayerError,
					},
				});
			} else {
				// Closing embed
				const wasPlaying =
					playerState.isPlaying && trackId === playerState.currentTrackId;
				let currentTime = 0;

				if (playerState.embeddedPlayers[trackId]) {
					try {
						currentTime =
							playerState.embeddedPlayers[trackId].getCurrentTime() || 0;
					} catch {
						currentTime = 0;
					}
					playerState.embeddedPlayers[trackId].destroy();
					delete playerState.embeddedPlayers[trackId];
				}

				videoContainer.innerHTML = "";
				videoContainer.style.display = "none";
				embedButton.textContent = "Embed";

				// If this was the playing track, switch back to hidden audio player
				if (trackId === playerState.currentTrackId) {
					playerState.isEmbedded = false;

					// Always ensure the hidden player exists and continues playback
					if (!ytPlayer) {
						// Create the hidden player if it doesn't exist
						const track = playerState.playlist.find((t) => t.id === trackId);
						if (track) {
							const videoId = getYouTubeVideoId(track.link);
							ytPlayer = new YT.Player("youtube-player-container", {
								height: "180",
								width: "320",
								videoId: videoId,
								playerVars: {
									playsinline: 1,
									autoplay: wasPlaying ? 1 : 0,
								},
								events: {
									onReady: (event) => {
										event.target.setVolume(playerState.volume);
										if (playerState.isMuted) event.target.mute();
										if (currentTime > 0) {
											event.target.seekTo(currentTime, true);
										}
									},
									onStateChange: onPlayerStateChange,
									onError: onPlayerError,
								},
							});
						}
					} else {
						// Player exists, just seek and play/pause
						ytPlayer.seekTo(currentTime, true);
						if (wasPlaying) {
							ytPlayer.playVideo();
						} else {
							ytPlayer.pauseVideo();
						}
					}
				}
			}
			return;
		}

		const lyricsButton = e.target.closest(".lyrics-button");
		if (lyricsButton) {
			e.preventDefault();
			const parentCell = lyricsButton.closest("td");
			const lyricsContainer = parentCell.querySelector(".lyrics-container");
			const lyricsSelect = lyricsContainer.querySelector(".lyrics-select");
			const lyricsMetadata = lyricsContainer.querySelector(".lyrics-metadata");
			const lyricsContent = lyricsContainer.querySelector(".lyrics-content");
			if (lyricsButton.classList.toggle("is-open")) {
				lyricsButton.textContent = "Close";
				if (lyricsContainer.dataset.loaded === "true") {
					lyricsContainer.style.display = "block";
				} else {
					lyricsButton.disabled = true;
					lyricsButton.textContent = "...";
					const titleEn = encodeURIComponent(lyricsButton.dataset.titleEn);
					const titleJp = lyricsButton.dataset.titleJp
						? encodeURIComponent(lyricsButton.dataset.titleJp)
						: "";
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
					fetch(
						`/api/vocadb_search?title_en=${titleEn}&producer=${producer}&title_jp=${titleJp}`,
					)
						.then((res) =>
							res.ok ? res.json() : Promise.reject("Song not found"),
						)
						.then((searchData) =>
							searchData.song_id
								? fetch(`/api/vocadb_lyrics/${searchData.song_id}`)
								: Promise.reject("Song not found"),
						)
						.then((res) =>
							res.ok ? res.json() : Promise.reject("Lyrics not available"),
						)
						.then((data) => {
							allLyricsData = data.lyrics;
							if (allLyricsData.length === 0)
								return Promise.reject("No lyrics found");
							lyricsSelect.innerHTML = "";
							allLyricsData.forEach((lyric, index) => {
								const option = document.createElement("option");
								option.value = index;
								option.textContent = lyric.label;
								lyricsSelect.appendChild(option);
							});
							renderLyric(0);
							lyricsContainer.style.display = "block";
							lyricsContainer.dataset.loaded = "true";
							if (!lyricsSelect.dataset.listener) {
								lyricsSelect.addEventListener("change", (e) =>
									renderLyric(e.target.value),
								);
								lyricsSelect.dataset.listener = "true";
							}
						})
						.catch((errorMsg) => {
							lyricsMetadata.innerHTML = "";
							lyricsContent.innerHTML = `<em>${errorMsg}</em>`;
							lyricsContainer.style.display = "block";
							lyricsContainer.dataset.loaded = "false";
							setTimeout(() => {
								if (!lyricsButton.classList.contains("is-open")) {
									lyricsContainer.style.display = "none";
								}
							}, 4000);
						})
						.finally(() => {
							lyricsButton.disabled = false;
							if (lyricsButton.classList.contains("is-open")) {
								lyricsButton.textContent = "Close";
							} else {
								lyricsButton.textContent = "Lyrics";
							}
						});
				}
			} else {
				lyricsContainer.style.display = "none";
				lyricsButton.textContent = "Lyrics";
			}
			return;
		}
	});

	document.body.addEventListener(
		"blur",
		(e) => {
			const notesInput = e.target.closest(".notes-input");
			if (notesInput) {
				const form = notesInput.closest("form");
				const ratingContainer = form.querySelector(".star-rating-container");
				const currentRating = parseFloat(ratingContainer.dataset.rating) || 0;
				if (currentRating > 0) {
					const formData = new FormData(form);
					formData.set("rating", currentRating);
					fetch(form.action, { method: "POST", body: formData }).then(() => {
						const notesBtn = form.querySelector(".notes-toggle-btn");
						notesBtn.classList.toggle(
							"has-note",
							notesInput.value.trim().length > 0,
						);
						notesBtn.textContent = "Saved!";
						setTimeout(() => {
							notesBtn.textContent =
								notesInput.value.trim().length > 0 ? "Edit Note" : "Add Note";
						}, 2000);
					});
				}
			}
		},
		true,
	);

	document
		.getElementById("player-repeat-btn")
		.addEventListener("click", (e) => {
			playerState.isRepeat = !playerState.isRepeat;
			e.currentTarget.classList.toggle("active", playerState.isRepeat);
		});

	document
		.getElementById("player-shuffle-btn")
		.addEventListener("click", (e) => {
			playerState.isShuffle = !playerState.isShuffle;
			e.currentTarget.classList.toggle("active", playerState.isShuffle);

			if (playerState.isShuffle) {
				generateShuffledPlaylist();
			}
			// When shuffle is turned off, the next/prev buttons will just revert to the original playlist.
		});

	document
		.getElementById("player-jump-to-btn")
		.addEventListener("click", () => {
			if (playerState.currentTrackId) {
				const trackRow = document.querySelector(`tr.is-playing`);
				if (trackRow) {
					trackRow.scrollIntoView({
						behavior: "smooth",
						block: "center",
					});
				}
			}
		});

	progressBar.addEventListener("input", () => {
		stopProgressUpdater(); // Pause updates while user is scrubbing
	});
	progressBar.addEventListener("change", () => {
		seekVideo(); // Seek when user releases the slider
		startProgressUpdater(); // Resume updates
	});

	document.getElementById("player-embed-btn").addEventListener("click", () => {
		if (!playerState.currentTrackId) return;

		const trackRow = document.querySelector(
			`tr[data-track-id="${playerState.currentTrackId}"]`,
		);
		if (!trackRow) return;

		const embedBtn = trackRow.querySelector(".embed-button");
		if (!embedBtn) return;

		const isCurrentlyEmbedded = embedBtn.classList.contains("is-open");

		if (isCurrentlyEmbedded) {
			// Close the embed (switch to audio mode)
			embedBtn.click();
		} else {
			// Open the embed (switch to video mode)
			embedBtn.click();
			// Scroll to the track
			trackRow.scrollIntoView({ behavior: "smooth", block: "center" });
		}
	});
});
