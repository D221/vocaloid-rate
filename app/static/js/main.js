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

const getActivePlayer = () => {
  if (
    playerState.isEmbedded &&
    playerState.embeddedPlayers[playerState.currentTrackId]
  ) {
    return playerState.embeddedPlayers[playerState.currentTrackId];
  }
  return ytPlayer;
};

const formatAllDates = () => {
  document.querySelectorAll('td[data-label="Published"]').forEach((td) => {
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
    a.classList.remove("active", "font-bold", "text-cyan-text");
    a.textContent = a.textContent.replace(/ [▲▼]/, "");
    if (a.dataset.sort === sortBy) {
      a.classList.add("active", "font-bold", "text-cyan-text");
      a.textContent += sortDir === "desc" ? " ▼" : " ▲";
    }
  });
};

const closePlaylistModals = () => {
  document
    .querySelectorAll(".playlist-modal")
    .forEach((modal) => modal.remove());
};

const openPlaylistModal = async (trackId, buttonElement) => {
  closePlaylistModals();

  try {
    const response = await fetch(`/api/tracks/${trackId}/playlist-status`);
    if (!response.ok) throw new Error("Failed to fetch playlist status.");
    const { member_of, not_member_of } = await response.json();

    const modal = document.createElement("div");
    modal.className =
      "playlist-modal fixed z-20 mt-2 w-72 rounded-md border border-border bg-card-bg p-2 shadow-lg";
    modal.dataset.trackId = trackId;

    let memberHTML = "";
    if (member_of.length > 0) {
      memberHTML = `
                <div class="px-2 pt-2 text-sm font-bold text-header">In Playlists</div>
                <div class="space-y-1 p-1">
                    ${member_of
                      .map(
                        (p) => `
                        <div class="flex items-center justify-between rounded hover:bg-gray-hover">
                            <a href="/playlist/${p.id}" class="flex-grow p-2 text-left text-foreground">${p.name}</a>
                            <button data-remove-from-playlist="${p.id}" class="p-2 text-red-text hover:text-red-500">
                                <i class="fa-solid fa-minus pointer-events-none"></i>
                            </button>
                        </div>
                    `,
                      )
                      .join("")}
                </div>
            `;
    }

    // "Not Member Of" section
    let notMemberHTML = "";
    if (not_member_of.length > 0) {
      notMemberHTML = `
                <div class="px-2 pt-2 text-sm font-bold text-header">Add to...</div>
                <div class="space-y-1 p-1">
                     ${not_member_of
                       .map(
                         (p) => `
                        <div class="flex items-center justify-between rounded hover:bg-gray-hover">
                             <span class="flex-grow p-2 text-left text-foreground">${p.name}</span>
                             <button data-add-to-existing-playlist="${p.id}" class="p-2 text-green-text hover:text-green-500">
                                <i class="fa-solid fa-plus pointer-events-none"></i>
                            </button>
                        </div>
                    `,
                       )
                       .join("")}
                </div>
            `;
    }

    // Final Modal HTML
    modal.innerHTML = `
            <div class="max-h-80 overflow-y-auto">
                ${memberHTML}
                ${notMemberHTML}
            </div>
            <div class="mt-2 border-t border-border pt-2">
                <input type="text" data-new-playlist-name placeholder="Or create new..." class="w-full rounded border border-border bg-background p-2 text-foreground placeholder:text-gray-text">
                <button data-create-playlist class="mt-2 w-full rounded bg-cyan-text p-2 font-bold text-stone-950 hover:bg-cyan-hover disabled:opacity-50" disabled>Create & Add</button>
            </div>
        `;

    document.body.appendChild(modal);
    const btnRect = buttonElement.getBoundingClientRect();
    let top = window.scrollY + btnRect.bottom;
    let left = window.scrollX + btnRect.left;
    if (left + 288 > window.innerWidth) {
      left = window.innerWidth - 298;
    }
    modal.style.top = `${top}px`;
    modal.style.left = `${left}px`;
  } catch (error) {
    showToast(error.message, "error");
  }
};

let currentPage = 1;
let currentLimit = localStorage.getItem("defaultPageSize") || "all";

const buildPlaylistFromDOM = () => {
  const tableBody = document.getElementById("tracks-table-body");
  if (!tableBody) return;

  const allRows = Array.from(tableBody.querySelectorAll("tr[data-track-id]"));
  playerState.playlist = allRows
    .map((row) => {
      // Image
      const imageEl = row.querySelector('td[data-label="Image"] img');
      const imageUrl = imageEl?.src;
      if (!imageUrl) return null;

      // Title link
      const titleLink = row.querySelector('td[data-label="Title"] a[href]');
      const title = titleLink ? titleLink.textContent.trim() : "Unknown";
      const link = titleLink ? titleLink.href : "";

      // Producer
      const producerLink = row.querySelector('td[data-label="Producer"] a');
      const producer = producerLink
        ? producerLink.textContent.trim()
        : "Unknown";

      // Play button (first button inside Title column)
      const playButton = row.querySelector('td[data-label="Title"] button');
      if (!playButton) return null;

      return {
        id: playButton.dataset.trackId,
        title,
        producer,
        link,
        imageUrl,
      };
    })
    .filter((t) => t?.id); // Filter out any nulls

  if (playerState.isShuffle) {
    generateShuffledPlaylist();
  }
};

const truncateTextByWords = (selector, maxLength) => {
  document.querySelectorAll(selector).forEach((el) => {
    // Store the original text if it's not already stored
    if (!el.dataset.originalText) {
      el.dataset.originalText = el.textContent.trim();
    }

    const originalText = el.dataset.originalText;

    if (originalText.length > maxLength) {
      // Hard cut, no word boundary check
      el.textContent = `${originalText.substring(0, maxLength)}...`;
    } else {
      // If it's shorter, ensure it's the full original text
      el.textContent = originalText;
    }
  });
};

const upgradeThumbnails = () => {
  document.querySelectorAll("img.track-thumbnail").forEach((img) => {
    // --- Desktop Logic (Corrected) ---
    if (window.innerWidth >= 768) {
      if (img.src.includes("i.ytimg.com")) {
        // This regex now correctly targets ALL possible endings and replaces them with mqdefault.jpg.
        // It's safe to run even if the src is already correct.
        const mqUrl = img.src.replace(
          /(\/)(maxresdefault|hqdefault|mqdefault|default)(\.jpg)/,
          "$1mqdefault$3",
        );

        if (img.src !== mqUrl) {
          img.src = mqUrl;
        }
      }
      img.classList.remove("object-cover", "aspect-video");
      return;
    }

    // --- Mobile Logic (Unchanged and Working) ---
    const currentSrc = img.src;

    if (currentSrc.includes("i.ytimg.com") && !img.dataset.processed) {
      img.dataset.processed = "true";

      const maxResUrl = currentSrc.replace(
        /(\/)(mqdefault|hqdefault|default)(\.jpg)/,
        "$1maxresdefault$3",
      );
      const hqUrl = currentSrc.replace(
        /(\/)(mqdefault|hqdefault|default)(\.jpg)/,
        "$1hqdefault$3",
      );

      fetch(maxResUrl, { method: "HEAD" })
        .then((response) => {
          if (
            response.ok &&
            parseInt(response.headers.get("Content-Length"), 10) > 1024
          ) {
            img.src = maxResUrl;
          } else {
            throw new Error("maxresdefault not available or is a placeholder");
          }
        })
        .catch(() => {
          img.src = hqUrl;
        })
        .finally(() => {
          img.classList.add("object-cover", "aspect-video");
        });
    }
  });
};

const showToast = (message, type = "success") => {
  const toast = document.createElement("div");
  const bgColor = type === "error" ? "bg-red-text" : "bg-green-text";
  const textColor = "text-white"; // Or a theme color for light text

  toast.className = `fixed bottom-24 right-5 z-[2000] rounded-md px-4 py-3 font-semibold shadow-lg ${bgColor} ${textColor}`;
  toast.textContent = message;

  document.body.appendChild(toast);

  setTimeout(() => {
    toast.style.transition = "opacity 0.5s ease";
    toast.style.opacity = "0";
    setTimeout(() => toast.remove(), 500);
  }, 2500); // Toast visible for 2.5 seconds
};

let ytPlayer;
let progressUpdateInterval;
const playerState = {
  isPlaying: false,
  currentTrackId: null,
  playlist: [],
  shuffledPlaylist: [],
  volume: localStorage.getItem("playerVolume") || 100,
  isMuted: localStorage.getItem("playerMuted") === "true",
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
  showToast(
    `Could not play this video.\n\nThis might be because the uploader has disabled embedding, or the video is private/deleted.\n(Error code: ${event.data})`,
    "error",
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
    showToast("Could not find a valid YouTube video ID.", "error");
    return;
  }

  // Immediately reset the progress bar and timers to zero
  progressBar.value = 0;
  currentTimeEl.textContent = "0:00";
  durationEl.textContent = "0:00";

  // Show the player UI immediately
  musicPlayerEl.classList.replace("hidden", "grid");
  updatePlayerUI();

  // If player exists, just load the video.
  if (ytPlayer) {
    ytPlayer.loadVideoById(videoId);
  } else {
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
          if (playerState.isMuted) {
            event.target.mute();
          } else {
            event.target.unMute();
          }
        },
        onStateChange: onPlayerStateChange,
        onError: onPlayerError,
      },
    });
  }
}

function _cleanupPreviousEmbed(trackId) {
  if (!trackId) return;
  const prevRow = document.querySelector(`tr[data-track-id="${trackId}"]`);
  if (!prevRow) return;

  const prevEmbedBtn = prevRow.querySelector(
    "button[data-embed-button].is-open",
  );
  if (prevEmbedBtn) {
    if (playerState.embeddedPlayers[trackId]) {
      playerState.embeddedPlayers[trackId].destroy();
      delete playerState.embeddedPlayers[trackId];
    }
    const container = prevRow.querySelector("div[data-embed-container]");
    if (container) {
      container.innerHTML = "";
      container.style.display = "none";
    }
    prevEmbedBtn.classList.remove("is-open");
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
  if (wasInEmbedMode) {
    _cleanupPreviousEmbed(previousTrackId);
  }

  // Update current track
  playerState.currentTrackId = nextTrack.id;
  playerState.isEmbedded = false;

  // Immediately reset the progress bar and timers to zero
  progressBar.value = 0;
  currentTimeEl.textContent = "0:00";
  durationEl.textContent = "0:00";

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
        const nextEmbedBtn = nextRow.querySelector("button[data-embed-button]");
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
            if (playerState.isMuted) {
              event.target.mute();
            } else {
              event.target.unMute();
            }
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
  if (wasInEmbedMode) {
    _cleanupPreviousEmbed(previousTrackId);
  }

  // Update current track
  playerState.currentTrackId = prevTrack.id;
  playerState.isEmbedded = false;

  // Immediately reset the progress bar and timers to zero
  progressBar.value = 0;
  currentTimeEl.textContent = "0:00";
  durationEl.textContent = "0:00";

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
        const prevEmbedBtn = prevRow.querySelector("button[data-embed-button]");
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
            if (playerState.isMuted) {
              event.target.mute();
            } else {
              event.target.unMute();
            }
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

  document
    .querySelectorAll("button[data-embed-button].is-open")
    .forEach((btn) => {
      btn.classList.remove("is-open");
      const container = btn
        .closest("td")
        .querySelector("div[data-embed-container]");
      if (container) {
        container.innerHTML = "";
        container.style.display = "none";
      }
    });

  playerState.isPlaying = false;
  playerState.currentTrackId = null;
  playerState.isEmbedded = false;
  stopProgressUpdater();
  musicPlayerEl.classList.replace("grid", "hidden");
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
    ? '<i class="fa-solid fa-pause"></i>'
    : '<i class="fa-solid fa-play"></i>';

  // Clear previous highlights and icons
  document.querySelectorAll("tr.is-playing").forEach((row) => {
    row.classList.remove("is-playing");
  });
  document
    .querySelectorAll("button[data-play-button].is-playing")
    .forEach((btn) => {
      btn.innerHTML = '<i class="fa-solid fa-play"></i>'; // Reset to play icon
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
        const playButtonInRow = trackRow.querySelector(
          "button[data-play-button]",
        );
        if (playButtonInRow) {
          playButtonInRow.innerHTML = playerState.isPlaying
            ? '<i class="fa-solid fa-pause"></i>'
            : '<i class="fa-solid fa-play"></i>';
          playButtonInRow.classList.add("is-playing");
        }
      }
    }
  }

  volumeSlider.value = playerState.isMuted ? 0 : playerState.volume;
  muteBtn.innerHTML = playerState.isMuted
    ? '<i class="fa-solid fa-volume-xmark"></i>'
    : '<i class="fa-solid fa-volume-high"></i>';
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
      ellipsis.className = "p-2";
      ellipsis.textContent = "...";
      return ellipsis;
    }
    const button = document.createElement("button");
    button.className =
      "shadow-md py-2 px-4 rounded border border-cyan-text text-cyan-text font-bold cursor-pointer transition-colors duration-200 ease-in-out enabled:hover:bg-cyan-hover";
    button.textContent = text;
    button.dataset.page = page;
    if (isCurrent) {
      button.classList.add(
        "bg-cyan-text",
        "text-stone-950",
        "border-cyan-text",
      );
      button.disabled = true;
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

  const currentTrackIdBeforeUpdate = playerState.currentTrackId;

  let skeletonTimer;
  const showSkeleton = () => {
    const skeletonRowHTML = `<tr class="skeleton-row"><td><div class="skeleton-bar"></div></td><td><div class="skeleton-bar"></div></td><td><div class="skeleton-bar"></div></td><td><div class="skeleton-bar"></div></td><td><div class="skeleton-bar"></div></td><td><div class="skeleton-bar"></div></td><td><div class="skeleton-bar"></div></td></tr>`;
    tableBody.innerHTML = skeletonRowHTML.repeat(10);
  };
  skeletonTimer = setTimeout(showSkeleton, 250);

  if (filterForm) {
    // Start with the current URL's params to preserve sorting state.
    const paramsForFetch = new URLSearchParams(window.location.search);

    const formData = new FormData(filterForm);

    // Step 1: Update the fetch parameters with the latest form data.
    // .set() will overwrite existing keys, which is what we want.
    formData.forEach((value, key) => {
      if (value) {
        paramsForFetch.set(key, value);
      } else {
        // If a form field is cleared, remove it from the params.
        paramsForFetch.delete(key);
      }
    });
    paramsForFetch.set("page", currentPage);
    if (!paramsForFetch.has("limit")) {
      paramsForFetch.set("limit", currentLimit);
    }

    // Step 2: Create a separate parameter list for the browser URL bar, removing defaults.
    const paramsForBrowser = new URLSearchParams(paramsForFetch.toString());

    // Remove default filters
    if (paramsForBrowser.get("rank_filter") === "ranked")
      paramsForBrowser.delete("rank_filter");
    if (paramsForBrowser.get("rated_filter") === "all")
      paramsForBrowser.delete("rated_filter");

    // Remove default pagination, correctly checking against localStorage
    const defaultPageSize = localStorage.getItem("defaultPageSize") || "all";
    if (paramsForBrowser.get("limit") === defaultPageSize)
      paramsForBrowser.delete("limit");
    if (paramsForBrowser.get("page") === "1") paramsForBrowser.delete("page");

    // Step 3: Construct the final URLs
    const fetchUrl = `${baseUrl}?${paramsForFetch.toString()}`;
    const browserQueryString = paramsForBrowser.toString();
    const browserUrl = browserQueryString
      ? `${window.location.pathname}?${browserQueryString}`
      : window.location.pathname;

    try {
      const response = await fetch(fetchUrl);
      clearTimeout(skeletonTimer);
      const data = await response.json();
      tableBody.innerHTML = data.table_body_html;

      buildPlaylistFromDOM();

      if (currentTrackIdBeforeUpdate) {
        const isTrackStillVisible = playerState.playlist.some(
          (t) => t.id === currentTrackIdBeforeUpdate,
        );

        if (isTrackStillVisible) {
          updatePlayerUI();
        } else {
          stopPlayer();
        }
      }

      updatePaginationUI(data.pagination);
      truncateTextByWords("[data-js-truncate]", 25);
      upgradeThumbnails();
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
  if (!container) return;

  const params = new URLSearchParams(window.location.search);
  const ratingFilter = params.get("exact_rating_filter");

  if (ratingFilter) {
    container.innerHTML = `
			<div data-active-rating-filter class="flex items-center justify-between gap-3 bg-gray-100 border border-border rounded px-3 py-2 shadow-sm w-1/6">
				<span>Filtering by rating: <strong>${ratingFilter} ★</strong></span>
				<button type="button" data-clear-rating-filter
					class="text-xl text-gray-500 hover:text-gray-700 leading-none"
					title="Clear rating filter">&times;</button>
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
  if (!themeIcon) return;
  const currentTheme = document.documentElement.dataset.theme;
  if (currentTheme === "dark") {
    themeIcon.innerHTML = '<i class="fa-solid fa-sun"></i>';
  } else {
    themeIcon.innerHTML = '<i class="fa-solid fa-moon"></i>';
  }
};

const toggleClearButton = (input) => {
  const wrapper = input.closest(".relative"); // safer than parentElement
  if (!wrapper) return;

  const btn = wrapper.querySelector("[data-clear]");
  if (!btn) return;

  const visible = input.value.length > 0;
  btn.classList.toggle("opacity-100", visible);
  btn.classList.toggle("opacity-0", !visible);
  btn.classList.toggle("visible", visible);
  btn.classList.toggle("invisible", !visible);
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
  truncateTextByWords("[data-js-truncate]", 25);
  upgradeThumbnails();

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
      const pageButton = e.target.closest("button[data-page]");
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
      .forEach(toggleClearButton);
  }

  // --- Initial Page Load Logic ---
  // This should only run on the main index page, not the rated tracks page.
  if (document.getElementById("scrape-button")) {
    const urlParams = new URLSearchParams(window.location.search);
    currentPage = parseInt(urlParams.get("page"), 10) || 1;
    currentLimit =
      urlParams.get("limit") ||
      localStorage.getItem("defaultPageSize") ||
      "all";
    if (limitFilter) limitFilter.value = currentLimit;
    // 2. Fetch the initial view based on the resolved state
    updateTracks();
  }

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
    const newVolume = e.target.value;
    playerState.volume = newVolume;
    playerState.isMuted = newVolume == 0;

    localStorage.setItem("playerVolume", newVolume);

    const activePlayer = getActivePlayer();
    if (activePlayer) {
      activePlayer.setVolume(newVolume);
      if (playerState.isMuted) {
        activePlayer.mute();
      } else {
        activePlayer.unMute();
      }
    }
    updatePlayerUI();
  });
  muteBtn.addEventListener("click", () => {
    playerState.isMuted = !playerState.isMuted;

    localStorage.setItem("playerMuted", playerState.isMuted);

    const activePlayer = getActivePlayer();
    if (activePlayer) {
      if (playerState.isMuted) {
        activePlayer.mute();
      } else {
        activePlayer.unMute();
        if (playerState.volume == 0) {
          playerState.volume = 50;
          activePlayer.setVolume(playerState.volume);
        }
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
                } else if (statusData.status.startsWith("in_progress")) {
                  scrapeButton.textContent = "Scraping...";
                  const progress = statusData.status.split(":")[1];
                  if (progress) {
                    scrapeStatus.textContent = `Scraping page ${progress}...`;
                  } else {
                    scrapeStatus.textContent = "Changes found, updating...";
                  }
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
    const ratingContainer = e.target.closest("[data-star-rating]");
    if (ratingContainer) updateStarPreview(ratingContainer, e);
  });

  document.body.addEventListener(
    "mouseleave",
    (e) => {
      const ratingContainer = e.target.closest("[data-star-rating]");
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
    const clearRatingBtn = e.target.closest("[data-clear-rating]");
    if (clearRatingBtn) {
      e.preventDefault();
      const ratingForm = clearRatingBtn.closest("form[data-rating-form]");
      const deleteEndpoint = clearRatingBtn.dataset.deleteEndpoint;
      if (!ratingForm || !deleteEndpoint) return;

      // Special case for the "My Rated Tracks" page: remove the whole row
      if (window.location.pathname.includes("rated_tracks")) {
        fetch(deleteEndpoint, { method: "POST" }).then(() => {
          ratingForm.closest("tr")?.remove();
        });
        return;
      }

      // Logic for the main tracks page
      fetch(deleteEndpoint, { method: "POST" }).then(() => {
        // 1. Reset the star UI
        const ratingContainer = ratingForm.querySelector("[data-star-rating]");
        if (ratingContainer) {
          ratingContainer.dataset.rating = "0";
          ratingContainer.style.setProperty("--rating-width", "0%");
        }

        // 2. Clear radio buttons
        ratingForm
          .querySelectorAll('input[type="radio"]')
          .forEach((r) => (r.checked = false));

        // 3. Clear and reset notes
        const notesInput = ratingForm.querySelector(
          "textarea[data-notes-input]",
        );
        const notesButton = ratingForm.querySelector(
          "button[data-notes-toggle]",
        );
        if (notesInput) notesInput.value = "";
        if (notesButton) {
          notesButton.classList.add("text-foreground", "text-foreground");
          notesButton.textContent = "Add Note";
        }

        // 4. Remove the clear button itself
        clearRatingBtn.remove();
      });
      return; // Stop processing other click handlers
    }

    const trackPlayBtn = e.target.closest("button[data-play-button]");
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

    const btn = e.target.closest("[data-clear]");
    if (btn) {
      const input = btn.parentElement.querySelector("input");
      if (input) {
        input.value = "";
        input.focus();
        input.dispatchEvent(new Event("input", { bubbles: true }));
      }
    }

    const clearAllBtn = e.target.closest("#clear-filters-btn");
    if (clearAllBtn) {
      e.preventDefault();

      // 1. Manually and explicitly clear the form to its default state
      const filterForm = document.getElementById("filter-form");
      if (filterForm) {
        // Set text/search inputs to empty
        filterForm
          .querySelectorAll('input[type="text"], input[type="search"]')
          .forEach((input) => {
            input.value = "";
            toggleClearButton(input);
          });

        // Set radio buttons to the default ('ranked') if they exist
        const rankRanked = filterForm.querySelector("#rank_ranked");
        if (rankRanked) rankRanked.checked = true;

        // Set select dropdowns to the default ('all') if they exist
        const ratedFilter = filterForm.querySelector("#rated_filter");
        if (ratedFilter) ratedFilter.value = "all";
      }

      // 2. Clear the URL parameters
      const cleanPath = window.location.pathname; // This gets "/" or "/rated_tracks"
      window.history.pushState({}, "", cleanPath);

      // 3. Reset pagination and fetch the default track list without a page reload
      currentPage = 1;
      updateTracks(); // This re-uses your existing logic and preserves player state
      return; // Stop processing other click handlers
    }

    const ratingContainer = e.target.closest("div[data-star-rating]");
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
          if (!form.querySelector("[data-clear-rating]")) {
            // Correctly create just the button with the necessary data attribute
            const deleteButtonHTML = `
								<button data-clear-rating type="button" data-delete-endpoint="${form.action}/delete"
									class="shadow-md p-1 rounded border border-red-text text-red-text font-bold cursor-pointer transition-colors duration-200 ease-in-out hover:bg-red-hover">
									<i class="fa-solid fa-xmark"></i>
								</button>`;

            // Find the container where the notes button lives
            const buttonContainer = form.querySelector(
              "button[data-notes-toggle]",
            )?.parentElement;
            if (buttonContainer) {
              // Insert the new button right into that container
              buttonContainer.insertAdjacentHTML("beforeend", deleteButtonHTML);
            }
          }
        });
      }
      return;
    }
    const notesBtn = e.target.closest("button[data-notes-toggle]");
    if (notesBtn) {
      e.preventDefault();
      const trackRow = notesBtn.closest("tr[data-track-id]");
      if (!trackRow) return;

      const notesContainer = trackRow.querySelector(
        "div[data-notes-container]",
      );
      if (!notesContainer) return;

      // Toggle the 'hidden' class directly. This is the correct way.
      notesContainer.classList.toggle("hidden");

      // If the container is NO LONGER hidden, focus the textarea.
      if (!notesContainer.classList.contains("hidden")) {
        const textarea = notesContainer.querySelector(
          "textarea[data-notes-input]",
        );
        if (textarea) {
          textarea.focus();
        }
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
      let newDir = ["published_date", "rating", "rank"].includes(newSort)
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

    const clearBtn = e.target.closest("[data-clear-rating-filter]");
    if (clearBtn) {
      e.preventDefault();

      const params = new URLSearchParams(window.location.search);
      params.delete("exact_rating_filter");
      params.delete("sort_by");
      params.delete("sort_dir");

      window.history.pushState(
        {},
        "",
        `${window.location.pathname}?${params.toString()}`,
      );
      updateTracks();
    }

    const vocadbBtn = e.target.closest("button[data-vocadb-track-button]");
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
          else showToast("Track not found on VocaDB.", "error");
        })
        .catch(() => showToast("Could not search VocaDB.", "error"))
        .finally(() => {
          vocadbBtn.disabled = false;
          vocadbBtn.textContent = "VocaDB";
        });
      return;
    }

    const vocadbProducerBtn = e.target.closest(
      "button[data-vocadb-artist-button]",
    );
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
            showToast("Producer not found on VocaDB.", "error");
          }
        })
        .catch(() =>
          showToast("Could not search VocaDB for this producer.", "error"),
        )
        .finally(() => {
          vocadbProducerBtn.disabled = false;
          vocadbProducerBtn.textContent = "VocaDB";
        });
      return;
    }

    const embedButton = e.target.closest("button[data-embed-button]");
    if (embedButton) {
      e.preventDefault();
      const trackRow = embedButton.closest("tr");
      const trackId = trackRow.dataset.trackId;
      const parentCell = embedButton.closest("td");
      const videoContainer = parentCell.querySelector(
        "div[data-embed-container]",
      );

      // Close any other open embeds (except the currently playing one)
      document
        .querySelectorAll("button[data-embed-button].is-open")
        .forEach((openBtn) => {
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
            const titleLink = row.querySelector('td[data-label="Title"] a');
            const producerLink = row.querySelector(
              'td[data-label="Producer"] a',
            );
            const playButton = row.querySelector("button[data-play-button]");
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
      musicPlayerEl.classList.replace("hidden", "grid");

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
              // Get the video ID of the hidden player, if it exists and has a video
              const hiddenPlayerVideoId = ytPlayer
                ? getYouTubeVideoId(ytPlayer.getVideoUrl())
                : null;

              // Only sync time if this new embed is for the EXACT same video
              // that is currently paused in the hidden audio player.
              if (videoId === hiddenPlayerVideoId) {
                const currentTime = ytPlayer.getCurrentTime();
                ytPlayer.pauseVideo(); // Pause the hidden player
                event.target.seekTo(currentTime, true);
                // Only play if the original was playing.
                if (playerState.isPlaying) {
                  event.target.playVideo();
                }
              }

              // If it's not the same video (like in playNext), this block is skipped,
              // and the new video correctly starts from 0 because of autoplay:1.
              playerState.isEmbedded = true;
            },
            onStateChange: onPlayerStateChange,
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
                    if (playerState.isMuted) {
                      event.target.mute();
                    } else {
                      event.target.unMute();
                    }
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

    const lyricsButton = e.target.closest("button[data-lyrics-button]");
    if (lyricsButton) {
      e.preventDefault();
      const parentCell = lyricsButton.closest("td");
      const lyricsContainer = parentCell.querySelector(
        "div[data-lyrics-container]",
      );
      const lyricsSelect = lyricsContainer.querySelector(
        "select[data-lyrics-select]",
      );
      const lyricsMetadata = lyricsContainer.querySelector(
        "div[data-lyrics-metadata]",
      );
      const lyricsContent = lyricsContainer.querySelector(
        "div[data-lyrics-content]",
      );
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
                metadataHTML += `<a class="hover:underline hover:text-cyan-text font-semibold" href="${selectedLyric.url}" target="_blank">${selectedLyric.source}</a>`;
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

    const addToPlaylistBtn = e.target.closest("[data-add-to-playlist-button]");
    const playlistModal = e.target.closest(".playlist-modal");

    // 1. Handle opening the modal
    if (addToPlaylistBtn) {
      e.preventDefault();
      const trackId = addToPlaylistBtn.dataset.trackId;
      openPlaylistModal(trackId, addToPlaylistBtn);
      return;
    }

    // 2. Handle clicks INSIDE the modal
    if (playlistModal) {
      const trackId = playlistModal.dataset.trackId;

      // A. Handle ADDING to an existing playlist
      const addBtn = e.target.closest("[data-add-to-existing-playlist]");
      if (addBtn) {
        const playlistId = addBtn.dataset.addToExistingPlaylist;
        fetch(`/api/playlists/${playlistId}/tracks/${trackId}`, {
          method: "POST",
        })
          .then((res) => {
            if (!res.ok) throw new Error("Failed to add track.");
            showToast("Track added!");
            closePlaylistModals();
            updateTracks(); // This will handle the button color change
          })
          .catch((err) => showToast(err.message, "error"));
      }

      // B. Handle REMOVING from a playlist
      const removeBtn = e.target.closest("[data-remove-from-playlist]");
      if (removeBtn) {
        const playlistId = removeBtn.dataset.removeFromPlaylist;
        fetch(`/api/playlists/${playlistId}/tracks/${trackId}`, {
          method: "DELETE",
        })
          .then((res) => {
            if (!res.ok) throw new Error("Failed to remove track.");
            showToast("Track removed.");
            closePlaylistModals();
            updateTracks(); // This will handle the button color change
          })
          .catch((err) => showToast(err.message, "error"));
      }

      // C. Handle CREATING a new playlist
      const createPlaylistBtn = e.target.closest("[data-create-playlist]");
      if (createPlaylistBtn && !createPlaylistBtn.disabled) {
        const input = playlistModal.querySelector("[data-new-playlist-name]");
        const playlistName = input.value.trim();
        if (playlistName) {
          fetch("/api/playlists", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ name: playlistName }),
          })
            .then((res) => res.json())
            .then((newPlaylist) =>
              fetch(`/api/playlists/${newPlaylist.id}/tracks/${trackId}`, {
                method: "POST",
              }),
            )
            .then((res) => {
              if (!res.ok)
                throw new Error("Failed to add track to new playlist.");
              showToast(`Track added to new playlist: ${playlistName}!`);
              closePlaylistModals();
              updateTracks(); // This will handle the button color change
            })
            .catch((err) => showToast(err.message, "error"));
        }
      }

      return; // IMPORTANT: Stop processing other clicks if inside a modal
    }

    // 3. Handle closing the modal by clicking outside
    if (!playlistModal && !addToPlaylistBtn) {
      closePlaylistModals();
    }
  });

  document.body.addEventListener(
    "blur",
    (e) => {
      const notesInput = e.target.closest("textarea[data-notes-input]");
      if (notesInput) {
        const trackRow = notesInput.closest("tr[data-track-id]");
        if (!trackRow) return;

        const ratingForm = trackRow.querySelector("form[data-rating-form]");
        const ratingContainer = trackRow.querySelector("div[data-star-rating]");
        if (!ratingForm || !ratingContainer) return;

        const currentRating = parseFloat(ratingContainer.dataset.rating) || 0;

        // Only save notes if the track has been rated.
        if (currentRating > 0) {
          const formData = new FormData();
          formData.set("rating", currentRating);
          formData.set("notes", notesInput.value);

          fetch(ratingForm.action, { method: "POST", body: formData }).then(
            () => {
              const notesBtn = ratingForm.querySelector(
                "button[data-notes-toggle]",
              );
              if (notesBtn) {
                const hasNote = notesInput.value.trim().length > 0;
                notesBtn.textContent = "Saved!";

                // Update button style based on whether there's a note
                notesBtn.classList.toggle("border-green-text", hasNote);
                notesBtn.classList.toggle("text-green-text", hasNote);
                notesBtn.classList.toggle("border-gray-text", !hasNote);
                notesBtn.classList.toggle("text-gray-text", !hasNote);

                setTimeout(() => {
                  notesBtn.textContent = hasNote ? "Edit Note" : "Add Note";
                }, 2000);
              }
            },
          );
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

    const embedBtn = trackRow.querySelector("button[data-embed-button]");
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
