// ===================================================================
// GLOBAL STATE & CONFIGURATION
// ===================================================================

let ytPlayer;
let progressUpdateInterval;
let ratingChart = null;
let skeletonTimer;

let currentPage = 1;
let currentLimit = localStorage.getItem("defaultPageSize") || "all";

const playerState = {
  isPlaying: false,
  currentTrackId: null,
  playlist: [], // This will now hold ONLY the tracks visible on the current page
  shuffledPlaylist: [], // This can be removed or kept for page-only shuffle if desired
  masterPlaylist: [], // This will hold ALL track IDs for the current view
  shuffledMasterPlaylist: [], // For shuffle mode across all pages
  volume: localStorage.getItem("playerVolume") || 100,
  isMuted: localStorage.getItem("playerMuted") === "true",
  isEmbedded: false,
  isShuffle: false,
  isRepeat: false,
  embeddedPlayers: {}, // Track embedded players by track ID
};

// ===================================================================
// PURE HELPER FUNCTIONS
// ===================================================================

const debounce = (func, delay) => {
  let timeoutId;
  return (...args) => {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => {
      func.apply(this, args);
    }, delay);
  };
};
const getYouTubeVideoId = (url) => {
  const regex =
    /(?:youtube\.com\/(?:[^/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu\.be\/)([^"&?/ ]{11})/;
  return url.match(regex)?.[1] || null;
};

const formatTime = (seconds) => {
  const minutes = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${minutes}:${secs.toString().padStart(2, "0")}`;
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

const getIconSVG = (iconName, size = "h-full w-full") => {
  const icons = {
    sun: `<svg class="${size}" xmlns="http://www.w3.org/2000/svg" fill="currentColor" viewBox="0 0 640 640"><!--!Font Awesome Free v7.1.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc.--><path d="M210.2 53.9C217.6 50.8 226 51.7 232.7 56.1L320.5 114.3L408.3 56.1C415 51.7 423.4 50.9 430.8 53.9C438.2 56.9 443.4 63.5 445 71.3L465.9 174.5L569.1 195.4C576.9 197 583.5 202.4 586.5 209.7C589.5 217 588.7 225.5 584.3 232.2L526.1 320L584.3 407.8C588.7 414.5 589.5 422.9 586.5 430.3C583.5 437.7 576.9 443.1 569.1 444.6L465.8 465.4L445 568.7C443.4 576.5 438 583.1 430.7 586.1C423.4 589.1 414.9 588.3 408.2 583.9L320.4 525.7L232.6 583.9C225.9 588.3 217.5 589.1 210.1 586.1C202.7 583.1 197.3 576.5 195.8 568.7L175 465.4L71.7 444.5C63.9 442.9 57.3 437.5 54.3 430.2C51.3 422.9 52.1 414.4 56.5 407.7L114.7 320L56.5 232.2C52.1 225.5 51.3 217.1 54.3 209.7C57.3 202.3 63.9 196.9 71.7 195.4L175 174.6L195.9 71.3C197.5 63.5 202.9 56.9 210.2 53.9zM239.6 320C239.6 275.6 275.6 239.6 320 239.6C364.4 239.6 400.4 275.6 400.4 320C400.4 364.4 364.4 400.4 320 400.4C275.6 400.4 239.6 364.4 239.6 320zM448.4 320C448.4 249.1 390.9 191.6 320 191.6C249.1 191.6 191.6 249.1 191.6 320C191.6 390.9 249.1 448.4 320 448.4C390.9 448.4 448.4 390.9 448.4 320z"/></svg>`,
    moon: `<svg class="${size}" xmlns="http://www.w3.org/2000/svg" fill="currentColor" viewBox="0 0 640 640"><!--!Font Awesome Free v7.1.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc.--><path d="M320 64C178.6 64 64 178.6 64 320C64 461.4 178.6 576 320 576C388.8 576 451.3 548.8 497.3 504.6C504.6 497.6 506.7 486.7 502.6 477.5C498.5 468.3 488.9 462.6 478.8 463.4C473.9 463.8 469 464 464 464C362.4 464 280 381.6 280 280C280 207.9 321.5 145.4 382.1 115.2C391.2 110.7 396.4 100.9 395.2 90.8C394 80.7 386.6 72.5 376.7 70.3C358.4 66.2 339.4 64 320 64z"/></svg>`,
    plus: `<svg class="${size}" xmlns="http://www.w3.org/2000/svg" fill="currentColor" viewBox="0 0 640 640"><!--!Font Awesome Free v7.1.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc.--><path d="M352 128C352 110.3 337.7 96 320 96C302.3 96 288 110.3 288 128L288 288L128 288C110.3 288 96 302.3 96 320C96 337.7 110.3 352 128 352L288 352L288 512C288 529.7 302.3 544 320 544C337.7 544 352 529.7 352 512L352 352L512 352C529.7 352 544 337.7 544 320C544 302.3 529.7 288 512 288L352 288L352 128z"/></svg>`,
    minus: `<svg class="${size}" xmlns="http://www.w3.org/2000/svg" fill="currentColor" viewBox="0 0 640 640"><!--!Font Awesome Free v7.1.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc.--><path d="M96 320C96 302.3 110.3 288 128 288L512 288C529.7 288 544 302.3 544 320C544 337.7 529.7 352 512 352L128 352C110.3 352 96 337.7 96 320z"/></svg>`,
    play: `<svg class="${size}" xmlns="http://www.w3.org/2000/svg" fill="currentColor" viewBox="0 0 640 640"><!--!Font Awesome Free v7.1.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc.--><path d="M187.2 100.9C174.8 94.1 159.8 94.4 147.6 101.6C135.4 108.8 128 121.9 128 136L128 504C128 518.1 135.5 531.2 147.6 538.4C159.7 545.6 174.8 545.9 187.2 539.1L523.2 355.1C536 348.1 544 334.6 544 320C544 305.4 536 291.9 523.2 284.9L187.2 100.9z"/></svg>`,
    pause: `<svg class="${size}" xmlns="http://www.w3.org/2000/svg" fill="currentColor" viewBox="0 0 640 640"><!--!Font Awesome Free v7.1.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc.--><path d="M176 96C149.5 96 128 117.5 128 144L128 496C128 522.5 149.5 544 176 544L240 544C266.5 544 288 522.5 288 496L288 144C288 117.5 266.5 96 240 96L176 96zM400 96C373.5 96 352 117.5 352 144L352 496C352 522.5 373.5 544 400 544L464 544C490.5 544 512 522.5 512 496L512 144C512 117.5 490.5 96 464 96L400 96z"/></svg>`,
    volume_xmark: `<svg class="${size}" xmlns="http://www.w3.org/2000/svg" fill="currentColor" viewBox="0 0 640 640"><!--!Font Awesome Free v7.1.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc.--><path d="M80 416L128 416L262.1 535.2C268.5 540.9 276.7 544 285.2 544C304.4 544 320 528.4 320 509.2L320 130.8C320 111.6 304.4 96 285.2 96C276.7 96 268.5 99.1 262.1 104.8L128 224L80 224C53.5 224 32 245.5 32 272L32 368C32 394.5 53.5 416 80 416zM399 239C389.6 248.4 389.6 263.6 399 272.9L446 319.9L399 366.9C389.6 376.3 389.6 391.5 399 400.8C408.4 410.1 423.6 410.2 432.9 400.8L479.9 353.8L526.9 400.8C536.3 410.2 551.5 410.2 560.8 400.8C570.1 391.4 570.2 376.2 560.8 366.9L513.8 319.9L560.8 272.9C570.2 263.5 570.2 248.3 560.8 239C551.4 229.7 536.2 229.6 526.9 239L479.9 286L432.9 239C423.5 229.6 408.3 229.6 399 239z"/></svg>`,
    volume_high: `<svg class="${size}" xmlns="http://www.w3.org/2000/svg" fill="currentColor" viewBox="0 0 640 640"><!--!Font Awesome Free v7.1.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc.--><path d="M533.6 96.5C523.3 88.1 508.2 89.7 499.8 100C491.4 110.3 493 125.4 503.3 133.8C557.5 177.8 592 244.8 592 320C592 395.2 557.5 462.2 503.3 506.3C493 514.7 491.5 529.8 499.8 540.1C508.1 550.4 523.3 551.9 533.6 543.6C598.5 490.7 640 410.2 640 320C640 229.8 598.5 149.2 533.6 96.5zM473.1 171C462.8 162.6 447.7 164.2 439.3 174.5C430.9 184.8 432.5 199.9 442.8 208.3C475.3 234.7 496 274.9 496 320C496 365.1 475.3 405.3 442.8 431.8C432.5 440.2 431 455.3 439.3 465.6C447.6 475.9 462.8 477.4 473.1 469.1C516.3 433.9 544 380.2 544 320.1C544 260 516.3 206.3 473.1 171.1zM412.6 245.5C402.3 237.1 387.2 238.7 378.8 249C370.4 259.3 372 274.4 382.3 282.8C393.1 291.6 400 305 400 320C400 335 393.1 348.4 382.3 357.3C372 365.7 370.5 380.8 378.8 391.1C387.1 401.4 402.3 402.9 412.6 394.6C434.1 376.9 448 350.1 448 320C448 289.9 434.1 263.1 412.6 245.5zM80 416L128 416L262.1 535.2C268.5 540.9 276.7 544 285.2 544C304.4 544 320 528.4 320 509.2L320 130.8C320 111.6 304.4 96 285.2 96C276.7 96 268.5 99.1 262.1 104.8L128 224L80 224C53.5 224 32 245.5 32 272L32 368C32 394.5 53.5 416 80 416z"/></svg>`,
    xmark: `<svg class="${size}" xmlns="http://www.w3.org/2000/svg" fill="currentColor" viewBox="0 0 640 640"><!--!Font Awesome Free v7.1.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc.--><path d="M183.1 137.4C170.6 124.9 150.3 124.9 137.8 137.4C125.3 149.9 125.3 170.2 137.8 182.7L275.2 320L137.9 457.4C125.4 469.9 125.4 490.2 137.9 502.7C150.4 515.2 170.7 515.2 183.2 502.7L320.5 365.3L457.9 502.6C470.4 515.1 490.7 515.1 503.2 502.6C515.7 490.1 515.7 469.8 503.2 457.3L365.8 320L503.1 182.6C515.6 170.1 515.6 149.8 503.1 137.3C490.6 124.8 470.3 124.8 457.8 137.3L320.5 274.7L183.1 137.4z"/></svg>`,
  };
  return icons[iconName] || "";
};

// ===================================================================
// CORE APPLICATION LOGIC & STATE MANAGEMENT
// ===================================================================

// --- Playlist Management ---
const loadPlaylistFromTemplate = () => {
  const playlistDataTemplate = document.getElementById("playlist-data");
  if (playlistDataTemplate) {
    try {
      const data = JSON.parse(playlistDataTemplate.innerHTML);
      if (Array.isArray(data)) {
        playerState.playlist = data;
      }
    } catch (e) {
      console.error("Failed to parse playlist data from <template> tag:", e);
    }
  }
};

function generateShuffledPlaylist() {
  // Create a shuffled copy of the MASTER playlist
  playerState.shuffledMasterPlaylist = [...playerState.masterPlaylist];
  // Fisher-Yates shuffle algorithm
  for (let i = playerState.shuffledMasterPlaylist.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [
      playerState.shuffledMasterPlaylist[i],
      playerState.shuffledMasterPlaylist[j],
    ] = [
      playerState.shuffledMasterPlaylist[j],
      playerState.shuffledMasterPlaylist[i],
    ];
  }
}

// --- Player Controls ---
const getActivePlayer = () => {
  if (
    playerState.isEmbedded &&
    playerState.embeddedPlayers[playerState.currentTrackId]
  ) {
    return playerState.embeddedPlayers[playerState.currentTrackId];
  }
  return ytPlayer;
};

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

// --- Player Events & Updaters ---
function stopProgressUpdater() {
  clearInterval(progressUpdateInterval);
}

function cleanupPreviousEmbed(trackId) {
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

// ===================================================================
// UI & DOM MANIPULATION FUNCTIONS
// ===================================================================

const showSkeleton = () => {
  const tableBody = document.getElementById("tracks-table-body");
  if (tableBody) {
    clearTimeout(skeletonTimer);

    skeletonTimer = setTimeout(() => {
      const skeletonRowHTML = `<tr class="skeleton-row"><td><div class="skeleton-bar"></div></td><td><div class="skeleton-bar"></div></td><td><div class="skeleton-bar"></div></td><td><div class="skeleton-bar"></div></td><td><div class="skeleton-bar"></div></td><td><div class="skeleton-bar"></div></td><td><div class="skeleton-bar"></div></td></tr>`;
      tableBody.innerHTML = skeletonRowHTML.repeat(10);
    }, 200);
  }
};

const hideSkeleton = () => {
  clearTimeout(skeletonTimer);
};

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
      "shadow-md py-2 px-4 rounded border border-sky-text text-sky-text font-bold cursor-pointer ease-in-out  hover:transition-colors hover:duration-200 enabled:hover:bg-sky-hover";
    button.textContent = text;
    button.dataset.page = page;
    if (isCurrent) {
      button.classList.add("bg-sky-text", "text-stone-950", "border-sky-text");
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
    a.classList.remove("active", "font-bold", "text-sky-text");
    a.textContent = a.textContent.replace(/ [▲▼]/, "");
    if (a.dataset.sort === sortBy) {
      a.classList.add("active", "font-bold", "text-sky-text");
      a.textContent += sortDir === "desc" ? " ▼" : " ▲";
    }
  });
};

const updateThemeUI = () => {
  const themeIcon = document.getElementById("theme-icon");
  if (!themeIcon) return;
  const currentTheme = document.documentElement.dataset.theme;
  if (currentTheme === "dark") {
    themeIcon.innerHTML = getIconSVG("sun");
  } else {
    themeIcon.innerHTML = getIconSVG("moon");
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
      <div data-active-rating-filter class="inline-flex items-center justify-between gap-3 rounded-3xl border border-gray-text bg-card-bg px-3 py-2 shadow-sm">
          <span>Filtering by rating: <strong>${ratingFilter} ★</strong></span>
          <button type="button" data-clear-rating-filter
              class="text-xl text-gray-text hover:text-red-text leading-none"
              title="Clear rating filter">&times;</button>
      </div>
		`;
    container.style.display = "block";
  } else {
    container.innerHTML = "";
    container.style.display = "none";
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

// --- Playlist Modal UI ---
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
                            <a href="/playlist/${p.id}" class="grow p-2 text-left text-foreground">${p.name}</a>
                            <button data-remove-from-playlist="${p.id}" class="p-2 text-red-text hover:text-red-500">
                                <span class="inline-block h-4 w-4">${getIconSVG("minus")}</span>
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
                             <span class="grow p-2 text-left text-foreground">${p.name}</span>
                             <button data-add-to-existing-playlist="${p.id}" class="p-2 text-green-text hover:text-green-500">
                                <span class="inline-block h-4 w-4 text-green-text">${getIconSVG("plus")}</span>
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
                <button data-create-playlist class="mt-2 w-full cursor-pointer rounded border border-cyan-text px-2 py-1 text-cyan-text ease-in-out  hover:transition-colors hover:duration-200 hover:bg-cyan-hover disabled:opacity-50" disabled>Create & Add</button>
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

// ===================================================================
// INITIALIZATION & EVENT LISTENERS (The "Entry Point")
// ===================================================================
document.addEventListener("DOMContentLoaded", () => {
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
  const limitFilter = document.getElementById("limit_filter");
  const paginationContainer = document.getElementById("pagination-container");
  const filterForm = document.getElementById("filter-form");
  const scrapeButton = document.getElementById("scrape-button");

  function loadAndPlayTrack(trackId) {
    const trackIndex = playerState.playlist.findIndex((t) => t.id === trackId);
    if (trackIndex === -1) {
      // This can happen if the track is on another page, but the page hasn't loaded yet.
      // The playNext/Prev logic already handles this, but this is a safety net.
      console.warn(
        `Track ${trackId} not found in current page's playlist. A page transition might be in progress.`,
      );
      return;
    }

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

    // If shuffle mode is active, always scroll to the newly playing track.
    if (playerState.isShuffle) {
      scrollToPlayingTrack();
    }

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

  async function playNextTrack() {
    const activeMasterPlaylist = playerState.isShuffle
      ? playerState.shuffledMasterPlaylist
      : playerState.masterPlaylist;

    if (activeMasterPlaylist.length === 0) return;

    const currentIndex = activeMasterPlaylist.findIndex(
      (t) => t.id === playerState.currentTrackId,
    );

    // If the current track isn't found, we can't determine the next one.
    if (currentIndex === -1) return;

    const nextIndex = (currentIndex + 1) % activeMasterPlaylist.length;
    const nextTrack = activeMasterPlaylist[nextIndex];

    if (String(nextTrack.page) !== String(currentPage)) {
      cleanupPreviousEmbed(playerState.currentTrackId);
      currentPage = nextTrack.page;
      showSkeleton();
      await updateTracks(); // Wait for the new page and its data to load
      scrollToPlayingTrack();
    }

    // Now that the correct page is loaded, find the track data and play it
    loadAndPlayTrack(nextTrack.id);
  }

  async function playPrevTrack() {
    const activePlayer = getActivePlayer();
    if (
      activePlayer &&
      typeof activePlayer.getCurrentTime === "function" &&
      activePlayer.getCurrentTime() > 5
    ) {
      activePlayer.seekTo(0, true);
      activePlayer.playVideo();
      return;
    }

    const activeMasterPlaylist = playerState.isShuffle
      ? playerState.shuffledMasterPlaylist
      : playerState.masterPlaylist;

    if (activeMasterPlaylist.length === 0) return;

    const currentIndex = activeMasterPlaylist.findIndex(
      (t) => t.id === playerState.currentTrackId,
    );

    if (currentIndex === -1) return;

    const prevIndex =
      (currentIndex - 1 + activeMasterPlaylist.length) %
      activeMasterPlaylist.length;
    const prevTrack = activeMasterPlaylist[prevIndex];

    if (String(prevTrack.page) !== String(currentPage)) {
      cleanupPreviousEmbed(playerState.currentTrackId);
      currentPage = prevTrack.page;
      showSkeleton();
      await updateTracks();
      scrollToPlayingTrack();
    }

    loadAndPlayTrack(prevTrack.id);
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

  const updateTracks = async () => {
    const tableBody = document.getElementById("tracks-table-body");
    const filterForm = document.getElementById("filter-form");
    const baseUrl = tableBody.dataset.updateUrl;
    if (!baseUrl) return;

    const currentTrackIdBeforeUpdate = playerState.currentTrackId;

    if (filterForm) {
      // Start with the current URL's params to preserve sorting state.
      const paramsForFetch = new URLSearchParams(window.location.search);

      const formData = new FormData(filterForm);

      formData.forEach((value, key) => {
        if (value) {
          paramsForFetch.set(key, value);
        } else {
          paramsForFetch.delete(key);
        }
      });
      paramsForFetch.set("page", currentPage);
      if (!paramsForFetch.has("limit")) {
        paramsForFetch.set("limit", currentLimit);
      }

      // Check for static filters embedded in the table body tag
      const staticFilterKey = tableBody.dataset.staticFilterKey;
      const staticFilterValue = tableBody.dataset.staticFilterValue;
      if (staticFilterKey && staticFilterValue) {
        paramsForFetch.set(staticFilterKey, staticFilterValue);
      }

      // Logic for browser URL (no changes here)
      const paramsForBrowser = new URLSearchParams(paramsForFetch.toString());
      if (paramsForBrowser.get("rank_filter") === "ranked")
        paramsForBrowser.delete("rank_filter");
      if (paramsForBrowser.get("rated_filter") === "all")
        paramsForBrowser.delete("rated_filter");
      const defaultPageSize = localStorage.getItem("defaultPageSize") || "all";
      if (paramsForBrowser.get("limit") === defaultPageSize)
        paramsForBrowser.delete("limit");
      if (paramsForBrowser.get("page") === "1") paramsForBrowser.delete("page");
      const browserQueryString = paramsForBrowser.toString();
      const browserUrl = browserQueryString
        ? `${window.location.pathname}?${browserQueryString}`
        : window.location.pathname;
      window.history.pushState({}, "", browserUrl);

      const snapshotUrl =
        tableBody.dataset.snapshotUrl || "/api/playlist-snapshot";

      const pageContentUrl = `${baseUrl}?${paramsForFetch.toString()}`;
      const masterPlaylistUrl = `${snapshotUrl}?${paramsForFetch.toString()}`;
      try {
        const [pageResponse, masterPlaylistResponse] = await Promise.all([
          fetch(pageContentUrl),
          fetch(masterPlaylistUrl),
        ]);

        hideSkeleton();

        if (!pageResponse.ok || !masterPlaylistResponse.ok) {
          throw new Error("Failed to fetch page data or playlist snapshot.");
        }

        const pageData = await pageResponse.json();
        const masterPlaylistData = await masterPlaylistResponse.json();

        // Update the master playlist in the global state
        playerState.masterPlaylist = masterPlaylistData;
        if (playerState.isShuffle) {
          generateShuffledPlaylist(); // Re-shuffle with the new master list
        }

        // Update the UI with the paginated content
        tableBody.innerHTML = pageData.table_body_html;
        loadPlaylistFromTemplate(); // This still loads the *current page* tracks into playerState.playlist for UI interaction

        if (currentTrackIdBeforeUpdate) {
          // Check against master list to see if track is still in the filtered set
          const isTrackStillInSet = playerState.masterPlaylist.some(
            (t) => t.id === currentTrackIdBeforeUpdate,
          );
          if (isTrackStillInSet) {
            updatePlayerUI();
          } else {
            stopPlayer();
          }
        }

        updatePaginationUI(pageData.pagination);
        upgradeThumbnails();
      } catch (error) {
        hideSkeleton();
        console.error("Failed to update tracks:", error);
        tableBody.innerHTML =
          '<tr><td colspan="7">Error loading tracks. Please try again.</td></tr>';
      }
      updateSortIndicators();
      updateActiveFilterDisplay();
    }
  };

  function updatePlayerUI() {
    playPauseBtn.innerHTML = playerState.isPlaying
      ? getIconSVG("pause", "h-8 w-8")
      : getIconSVG("play", "h-8 w-8");

    // Clear previous highlights and icons
    document.querySelectorAll("tr.is-playing").forEach((row) => {
      row.classList.remove("is-playing");
    });
    document
      .querySelectorAll("button[data-play-button].is-playing")
      .forEach((btn) => {
        btn.innerHTML = getIconSVG("play", "h-4 w-4");
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
              ? getIconSVG("pause", "h-4 w-4")
              : getIconSVG("play", "h-4 w-4");
            playButtonInRow.classList.add("is-playing");
          }
        }
      }
    }

    volumeSlider.value = playerState.isMuted ? 0 : playerState.volume;
    muteBtn.innerHTML = playerState.isMuted
      ? getIconSVG("volume_xmark", "h-8 w-8")
      : getIconSVG("volume_high", "h-8 w-8");
  }

  function onPlayerError(event) {
    console.error("YouTube Player Error:", event.data);
    showToast(
      `Could not play this video.\n\nThis might be because the uploader has disabled embedding, or the video is private/deleted.\n(Error code: ${event.data})`,
      "error",
    );
    playNextTrack(); // Attempt to play the next track
  }

  const debouncedUpdateTracks = debounce(updateTracks, 300);

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

  function scrollToPlayingTrack() {
    // A short delay ensures the DOM has updated and the .is-playing class is set
    setTimeout(() => {
      const trackRow = document.querySelector(`tr.is-playing`);
      if (trackRow) {
        trackRow.scrollIntoView({
          behavior: "smooth",
          block: "center",
        });
      }
    }, 100);
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
          showSkeleton();
          updateTracks();
        }
      };

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

  updateSortIndicators();
  updateThemeUI();
  updateActiveFilterDisplay();
  upgradeThumbnails();
  renderRatingChart();

  loadPlaylistFromTemplate();

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

      if (playerState.playlist.length === 0) {
        loadPlaylistFromTemplate();
        if (playerState.playlist.length === 0) {
          showToast("Could not find playlist data to play track.", "error");
          return;
        }
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
      showSkeleton();
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
									class="shadow-md p-1 rounded border border-red-text text-red-text font-bold cursor-pointer ease-in-out  hover:transition-colors hover:duration-200 hover:bg-red-hover">
									<span class="inline-block h-6 w-6">${getIconSVG("xmark")}</span>
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
      showSkeleton();
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
      showSkeleton();
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
              // Sync volume and mute state from the global player state
              event.target.setVolume(playerState.volume);
              if (playerState.isMuted) {
                event.target.mute();
              } else {
                event.target.unMute();
              }

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
        // --- Closing the embed and switching to audio-only mode ---
        const wasPlaying =
          playerState.isPlaying && trackId === playerState.currentTrackId;
        let currentTime = 0;

        // Safely get current time before destroying the player
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

        // Clean up DOM
        videoContainer.innerHTML = "";
        videoContainer.style.display = "none";

        // Only proceed if we are closing the currently active track
        if (trackId === playerState.currentTrackId) {
          playerState.isEmbedded = false;

          const track = playerState.playlist.find((t) => t.id === trackId);
          if (!track) return; // Safety check

          const videoId = getYouTubeVideoId(track.link);
          if (!videoId) return; // Safety check

          // Always ensure the hidden player exists and continues playback
          if (!ytPlayer) {
            // If the hidden player doesn't exist, create it.
            ytPlayer = new YT.Player("youtube-player-container", {
              height: "180",
              width: "320",
              videoId: videoId,
              playerVars: {
                playsinline: 1,
                autoplay: wasPlaying ? 1 : 0,
                start: Math.floor(currentTime), // Use startSeconds for efficiency
              },
              events: {
                onReady: (event) => {
                  event.target.setVolume(playerState.volume);
                  if (playerState.isMuted) event.target.mute();
                  else event.target.unMute();
                },
                onStateChange: onPlayerStateChange,
                onError: onPlayerError,
              },
            });
          } else {
            // Player exists, ensure it's synced before use.
            const currentHiddenPlayerVideoId = getYouTubeVideoId(
              ytPlayer.getVideoUrl(),
            );

            // Always sync volume and mute state from our global state back to the hidden player.
            ytPlayer.setVolume(playerState.volume);
            if (playerState.isMuted) {
              ytPlayer.mute();
            } else {
              ytPlayer.unMute();
            }

            if (currentHiddenPlayerVideoId !== videoId) {
              // The hidden player is on the WRONG video. Load the correct one.
              if (wasPlaying) {
                ytPlayer.loadVideoById({
                  videoId: videoId,
                  startSeconds: currentTime,
                });
              } else {
                ytPlayer.cueVideoById({
                  videoId: videoId,
                  startSeconds: currentTime,
                });
              }
            } else {
              // The hidden player is on the correct video. Just seek and update state.
              ytPlayer.seekTo(currentTime, true);
              if (wasPlaying) {
                ytPlayer.playVideo();
              } else {
                ytPlayer.pauseVideo();
              }
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
                metadataHTML += `<a class="hover:underline hover:text-sky-text font-semibold" href="${selectedLyric.url}" target="_blank">${selectedLyric.source}</a>`;
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
            showSkeleton();
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
            showSkeleton();
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
              showSkeleton();
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

  document.body.addEventListener("input", (e) => {
    const newPlaylistInput = e.target.closest("[data-new-playlist-name]");
    if (newPlaylistInput) {
      const modal = newPlaylistInput.closest(".playlist-modal");
      if (modal) {
        const createBtn = modal.querySelector("[data-create-playlist]");
        if (createBtn) {
          createBtn.disabled = newPlaylistInput.value.trim().length === 0;
        }
      }
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

  document.getElementById("theme-switcher")?.addEventListener("click", () => {
    const doc = document.documentElement;
    const newTheme = doc.dataset.theme === "dark" ? "light" : "dark";
    doc.dataset.theme = newTheme;
    localStorage.setItem("theme", newTheme);
    updateThemeUI();
    renderRatingChart();
  });

  const menuToggle = document.getElementById("menu-toggle");
  const navLinks = document.getElementById("nav-links");

  if (menuToggle && navLinks) {
    menuToggle.addEventListener("click", (e) => {
      // Prevent this click from instantly closing the menu via the body listener
      e.stopPropagation();
      navLinks.classList.toggle("hidden");
    });

    // Add a listener to the body to close the menu when clicking elsewhere
    document.body.addEventListener("click", () => {
      if (!navLinks.classList.contains("hidden")) {
        navLinks.classList.add("hidden");
      }
    });
  }

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
    .addEventListener("click", scrollToPlayingTrack);

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
  progressBar.addEventListener("input", () => {
    stopProgressUpdater(); // Pause updates while user is scrubbing
  });
  progressBar.addEventListener("change", () => {
    seekVideo(); // Seek when user releases the slider
    startProgressUpdater(); // Resume updates
  });

  if (limitFilter) {
    limitFilter.value = currentLimit;
    limitFilter.addEventListener("change", (e) => {
      currentLimit = e.target.value;
      currentPage = 1;
      showSkeleton();
      updateTracks();
    });
  }

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
        showSkeleton();
        updateTracks();
      }
    });
  }

  if (filterForm) {
    filterForm.addEventListener("input", (e) => {
      currentPage = 1; // Reset page on filter change
      if (e.target.matches('input[type="text"], input[type="search"]')) {
        toggleClearButton(e.target);
        showSkeleton();
        debouncedUpdateTracks();
      } else if (e.target.id !== "limit_filter") {
        // Any other form input (radios, selects) triggers an immediate update
        currentPage = 1; // Reset page on filter change
        showSkeleton();
        updateTracks();
      }
    });
    filterForm
      .querySelectorAll('input[type="text"], input[type="search"]')
      .forEach(toggleClearButton);
  }

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

  // --- Initial Page Load Logic ---
  if (document.getElementById("tracks-table-body")) {
    const urlParams = new URLSearchParams(window.location.search);
    currentPage = parseInt(urlParams.get("page"), 10) || 1;
    currentLimit =
      urlParams.get("limit") ||
      localStorage.getItem("defaultPageSize") ||
      "all";
    if (limitFilter) limitFilter.value = currentLimit;

    // Fetch the initial view based on the resolved state
    showSkeleton();
    updateTracks();
  }

  window.playerAPI = {
    loadAndPlayTrack: loadAndPlayTrack,
    playerState: playerState,
    buildPlaylistFromEditor: (items) => {
      // A new helper for the editor
      const newPlaylist = Array.from(items)
        .map((item) => {
          const imageEl = item.querySelector("img");
          const titleEl = item.querySelector(".font-semibold");
          const producerEl = item.querySelector(".text-sm");
          return {
            id: item.dataset.trackId,
            title: titleEl ? titleEl.textContent : "Unknown",
            producer: producerEl ? producerEl.textContent : "Unknown",
            imageUrl: imageEl ? imageEl.src : "",
            link: item.dataset.trackLink || "",
          };
        })
        .filter((track) => track.id && track.link);
      playerState.playlist = newPlaylist;
    },
  };
});
