/* global Sortable, playerState, loadAndPlayTrack */

document.addEventListener("DOMContentLoaded", () => {
  // --- ELEMENT SELECTORS ---
  const playlistContainer = document.querySelector("[data-playlist-id]");
  if (!playlistContainer) {
    // If this element isn't on the page, do nothing.
    // This prevents errors if the script is loaded on other pages.
    return;
  }

  const playlistId = playlistContainer.dataset.playlistId;
  const allTracksList = document.getElementById("all-tracks-list");
  const playlistTracksList = document.getElementById("playlist-tracks-list");
  const trackSearch = document.getElementById("track-search");

  // --- HELPER FUNCTIONS ---

  const showToast = (message, type = "success") => {
    const toast = document.createElement("div");
    const bgColor = type === "error" ? "bg-red-text" : "bg-green-text";

    toast.className = `fixed bottom-24 right-5 z-[2000] rounded-md px-4 py-3 font-semibold shadow-lg text-white ${bgColor}`;
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => {
      toast.style.transition = "opacity 0.5s ease";
      toast.style.opacity = "0";
      setTimeout(() => toast.remove(), 500);
    }, 2500);
  };

  const debounce = (func, delay) => {
    let timeout;
    return function (...args) {
      clearTimeout(timeout);
      timeout = setTimeout(() => func.apply(this, args), delay);
    };
  };

  // --- API FUNCTIONS ---

  const debouncedSaveOrder = debounce(async (trackIds) => {
    if (!trackIds) return;
    try {
      const response = await fetch(`/api/playlists/${playlistId}/reorder`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(trackIds),
      });
      if (!response.ok) throw new Error("Server error on save.");
      showToast("Playlist order saved!");
    } catch {
      showToast("Failed to save order.", "error");
    }
  }, 500);

  const addTrack = async (trackId) => {
    try {
      await fetch(`/api/playlists/${playlistId}/tracks/${trackId}`, {
        method: "POST",
      });
    } catch {
      showToast("Failed to add track.", "error");
    }
  };

  const removeTrack = async (trackId) => {
    try {
      await fetch(`/api/playlists/${playlistId}/tracks/${trackId}`, {
        method: "DELETE",
      });
    } catch {
      showToast("Failed to remove track.", "error");
    }
  };

  // --- INLINE EDITING FOR PLAYLIST DETAILS ---

  document.querySelectorAll("[data-edit-field]").forEach((button) => {
    button.addEventListener("click", (e) => {
      const fieldContainer = e.currentTarget.parentElement;
      const viewEl = fieldContainer.querySelector(".view-mode");
      const editEl = fieldContainer.querySelector(".edit-mode");

      viewEl.classList.add("hidden");
      editEl.classList.remove("hidden");
      editEl.focus();
      editEl.select();
    });
  });

  const saveDetailsChanges = async () => {
    const newName = document.querySelector("h1 .edit-mode").value.trim();
    const descriptionElement = document.querySelector("p .edit-mode");
    const newDescription = descriptionElement
      ? descriptionElement.value.trim()
      : "";

    if (!newName) {
      showToast("Playlist name cannot be empty.", "error");
      document.querySelector("h1 .edit-mode").value =
        document.querySelector("h1 .view-mode").textContent;
      return;
    }

    try {
      const response = await fetch(`/api/playlists/${playlistId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newName, description: newDescription }),
      });
      if (!response.ok) throw new Error("Failed to save details.");

      document.querySelector("h1 .view-mode").textContent = newName;
      if (document.querySelector("p .view-mode")) {
        document.querySelector("p .view-mode").textContent =
          newDescription || "No description.";
      }
      showToast("Playlist details saved!");
    } catch (error) {
      showToast(error.message, "error");
    } finally {
      document
        .querySelectorAll(".view-mode")
        .forEach((el) => el.classList.remove("hidden"));
      document
        .querySelectorAll(".edit-mode")
        .forEach((el) => el.classList.add("hidden"));
    }
  };

  document.querySelectorAll(".edit-mode").forEach((input) => {
    input.addEventListener("blur", saveDetailsChanges);
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        input.blur();
      } else if (e.key === "Escape") {
        // Optional: Revert changes on Escape key
        input.value =
          input.parentElement.querySelector(".view-mode").textContent;
        input.blur();
      }
    });
  });

  // --- SORTABLEJS INITIALIZATION ---

  new Sortable(allTracksList, {
    group: { name: "shared", pull: "clone", put: false },
    sort: false,
    animation: 150,
  });

  new Sortable(playlistTracksList, {
    group: "shared",
    animation: 150,
    // No 'handle' property means the whole item is draggable
    onAdd: function (evt) {
      const trackId = evt.item.dataset.trackId;
      const trackLink = evt.item.dataset.trackLink;
      addTrack(trackId);

      const trackContent = evt.item.innerHTML;
      evt.item.innerHTML = `
                <div class="flex items-center gap-3 overflow-hidden">
                    ${trackContent}
                </div>
                <button data-remove-track class="p-2 text-red-text hover:text-red-500">
                    <i class="fa-solid fa-trash pointer-events-none"></i>
                </button>
            `;
      evt.item.className =
        "track-item flex cursor-grab items-center justify-between gap-3 rounded bg-card-bg p-2 shadow";

      evt.item.dataset.trackLink = trackLink;
      evt.item.className = "...";

      const trackIds = Array.from(playlistTracksList.children).map(
        (item) => item.dataset.trackId,
      );
      debouncedSaveOrder(trackIds);
      updateInPlaylistIndicators();
    },
    onEnd: function () {
      const trackIds = Array.from(playlistTracksList.children).map(
        (item) => item.dataset.trackId,
      );
      debouncedSaveOrder(trackIds);
    },
  });

  // --- GENERAL EVENT LISTENERS ---

  trackSearch.addEventListener("input", () => {
    const searchTerm = trackSearch.value.toLowerCase();
    allTracksList.querySelectorAll(".track-item").forEach((item) => {
      const itemText = item.textContent.toLowerCase();
      item.style.display = itemText.includes(searchTerm) ? "flex" : "none";
    });
  });

  allTracksList.addEventListener("click", (e) => {
    const trackItem = e.target.closest(".track-item");
    if (!trackItem) return;
    const trackId = trackItem.dataset.trackId;

    if (trackItem && !trackItem.classList.contains("cursor-not-allowed")) {
      // Find the track data from the clicked item
      const trackId = trackItem.dataset.trackId;
      const trackLink = trackItem.dataset.trackLink;
      const imageSrc = trackItem.querySelector("img").src;
      const title = trackItem.querySelector(".font-semibold").textContent;
      const producer = trackItem.querySelector(".text-sm").textContent;

      // Add to the database
      addTrack(trackId);

      // Create a new element for the right-hand list
      const newPlaylistItem = document.createElement("div");
      newPlaylistItem.className =
        "track-item flex cursor-grab items-center justify-between gap-3 rounded bg-card-bg p-2 shadow";
      newPlaylistItem.dataset.trackId = trackId;
      newPlaylistItem.dataset.trackLink = trackLink;
      newPlaylistItem.innerHTML = `
            <div class="flex items-center gap-3 overflow-hidden">
                <button data-play-button data-track-id="${trackId}" class="p-2 text-gray-text hover:text-sky-text">
                    <i class="fa-solid fa-play"></i>
                </button>
                <a href="${trackLink}" target="_blank" class="flex items-center gap-3">
                    <img src="${imageSrc}" alt="${title}" class="h-10 w-10 rounded object-cover">
                    <div>
                        <div class="font-semibold">${title}</div>
                        <div class="text-sm text-gray-text">${producer}</div>
                    </div>
                </a>
            </div>
            <button data-remove-track class="p-2 text-red-text hover:text-red-500">
                <i class="fa-solid fa-trash pointer-events-none"></i>
            </button>
        `;

      // Add the new element to the DOM
      playlistTracksList.appendChild(newPlaylistItem);
    } else {
      const itemToRemove = playlistTracksList.querySelector(
        `.track-item[data-track-id="${trackId}"]`,
      );

      if (itemToRemove) {
        removeTrack(trackId);
        itemToRemove.remove();
        showToast("Track removed from playlist.");
      }
    }

    // Update the visual indicators
    updateInPlaylistIndicators();

    // Save the new order
    const trackIds = Array.from(playlistTracksList.children).map(
      (item) => item.dataset.trackId,
    );
    debouncedSaveOrder(trackIds);
  });

  playlistTracksList.addEventListener("click", (e) => {
    const removeButton = e.target.closest("[data-remove-track]");
    if (removeButton) {
      const trackItem = removeButton.closest(".track-item");
      const trackId = trackItem.dataset.trackId;

      removeTrack(trackId);
      trackItem.remove();

      const trackIds = Array.from(playlistTracksList.children).map(
        (item) => item.dataset.trackId,
      );
      debouncedSaveOrder(trackIds);
      updateInPlaylistIndicators();
      showToast("Track removed.");
    }
  });
  const editorContainer = document.querySelector(".grid.grid-cols-1");

  const buildPlaylistFromEditor = () => {
    const trackItems = document.querySelectorAll(".track-item");
    const newPlaylist = Array.from(trackItems)
      .map((item) => {
        const imageEl = item.querySelector("img");
        const titleEl = item.querySelector(".font-semibold");
        const producerEl = item.querySelector(".text-sm");

        return {
          id: item.dataset.trackId,
          title: titleEl ? titleEl.textContent : "Unknown Title",
          producer: producerEl ? producerEl.textContent : "Unknown Producer",
          imageUrl: imageEl ? imageEl.src : "",
          // We need the YouTube link. Let's assume we'll add it to the data attribute.
          link: item.dataset.trackLink || "",
        };
      })
      .filter((track) => track.id && track.link);

    // Update the global player state from main.js
    playerState.playlist = newPlaylist;
    console.log("Playlist built from editor:", playerState.playlist);
  };

  if (editorContainer) {
    editorContainer.addEventListener("click", (e) => {
      const playButton = e.target.closest("[data-play-button]");
      if (playButton) {
        e.stopPropagation(); // Prevent SortableJS from starting a drag

        const trackId = playButton.dataset.trackId;

        // On the first play click on this page, build the playlist
        if (
          playerState.playlist.length === 0 ||
          !playerState.playlist.some((t) => t.id === trackId)
        ) {
          buildPlaylistFromEditor();
        }

        // Now that the playlist exists, call the global function from main.js
        if (typeof loadAndPlayTrack === "function") {
          loadAndPlayTrack(trackId);
        } else {
          alert("Player function not found. Make sure main.js is loaded.");
        }
      }
    });
  }

  const updateInPlaylistIndicators = () => {
    // 1. Get a set of all track IDs currently in the playlist for fast lookups
    const playlistTrackIds = new Set();
    playlistTracksList.querySelectorAll("[data-track-id]").forEach((item) => {
      playlistTrackIds.add(item.dataset.trackId);
    });

    // 2. Loop through all available tracks on the left
    allTracksList.querySelectorAll(".track-item").forEach((item) => {
      const trackId = item.dataset.trackId;
      const addButton = item.querySelector("[data-add-indicator]"); // We will add this element

      if (playlistTrackIds.has(trackId)) {
        // If the track is already in the playlist:
        item.classList.add("opacity-50", "cursor-not-allowed"); // Gray it out
        if (addButton)
          addButton.innerHTML =
            '<i class="fa-solid fa-check text-green-text"></i>'; // Show a checkmark
      } else {
        // If the track is not in the playlist:
        item.classList.remove("opacity-50", "cursor-not-allowed"); // Restore normal style
        if (addButton) addButton.innerHTML = '<i class="fa-solid fa-plus"></i>'; // Show a plus icon
      }
    });
  };
  updateInPlaylistIndicators();
});
