document.addEventListener("DOMContentLoaded", () => {
  const getIconSVG = (iconName, size = "h-full w-full") => {
    const icons = {
      plus: `<svg class="${size}" xmlns="http://www.w3.org/2000/svg" fill="currentColor" viewBox="0 0 640 640"><!--!Font Awesome Free v7.1.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc.--><path d="M352 128C352 110.3 337.7 96 320 96C302.3 96 288 110.3 288 128L288 288L128 288C110.3 288 96 302.3 96 320C96 337.7 110.3 352 128 352L288 352L288 512C288 529.7 302.3 544 320 544C337.7 544 352 529.7 352 512L352 352L512 352C529.7 352 544 337.7 544 320C544 302.3 529.7 288 512 288L352 288L352 128z"/></svg>`,
      play: `<svg class="${size}" xmlns="http://www.w3.org/2000/svg" fill="currentColor" viewBox="0 0 640 640"><!--!Font Awesome Free v7.1.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc.--><path d="M187.2 100.9C174.8 94.1 159.8 94.4 147.6 101.6C135.4 108.8 128 121.9 128 136L128 504C128 518.1 135.5 531.2 147.6 538.4C159.7 545.6 174.8 545.9 187.2 539.1L523.2 355.1C536 348.1 544 334.6 544 320C544 305.4 536 291.9 523.2 284.9L187.2 100.9z"/></svg>`,
      trash: `<svg class="${size}" xmlns="http://www.w3.org/2000/svg" fill="currentColor" viewBox="0 0 640 640"><!--!Font Awesome Free v7.1.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc.--><path d="M232.7 69.9L224 96L128 96C110.3 96 96 110.3 96 128C96 145.7 110.3 160 128 160L512 160C529.7 160 544 145.7 544 128C544 110.3 529.7 96 512 96L416 96L407.3 69.9C402.9 56.8 390.7 48 376.9 48L263.1 48C249.3 48 237.1 56.8 232.7 69.9zM512 208L128 208L149.1 531.1C150.7 556.4 171.7 576 197 576L443 576C468.3 576 489.3 556.4 490.9 531.1L512 208z"/></svg>`,
      check: `<svg class="${size}" xmlns="http://www.w3.org/2000/svg" fill="currentColor" viewBox="0 0 640 640"><!--!Font Awesome Free v7.1.0 by @fontawesome - https://fontawesome.com License - https://fontawesome.com/license/free Copyright 2025 Fonticons, Inc.--><path d="M530.8 134.1C545.1 144.5 548.3 164.5 537.9 178.8L281.9 530.8C276.4 538.4 267.9 543.1 258.5 543.9C249.1 544.7 240 541.2 233.4 534.6L105.4 406.6C92.9 394.1 92.9 373.8 105.4 361.3C117.9 348.8 138.2 348.8 150.7 361.3L252.2 462.8L486.2 141.1C496.6 126.8 516.6 123.6 530.9 134z"/></svg>`,
    };
    return icons[iconName] || "";
  };

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

  const createPlaylistItemElement = (sourceItem) => {
    // 1. Get all the necessary data from the source item's data attributes
    const trackData = sourceItem.dataset; // This gets all data-* attributes at once!

    // 2. Create the new element and set its properties
    const newPlaylistItem = document.createElement("div");
    newPlaylistItem.className =
      "track-item flex cursor-grab items-center justify-between gap-3 rounded bg-card-bg p-2 shadow";

    // Copy all data attributes from the source to the new item
    Object.keys(trackData).forEach((key) => {
      newPlaylistItem.dataset[key] = trackData[key];
    });

    // 3. Set the innerHTML using the data we gathered
    newPlaylistItem.innerHTML = `
        <div class="flex items-center gap-3 overflow-hidden">
            <button data-play-button data-track-id="${trackData.trackId}" class="p-2 text-gray-text hover:text-sky-text">
                <span class="inline-block h-6 w-6">${getIconSVG("play")}</span>
            </button>
            <a href="${trackData.trackLink}" target="_blank" class="flex items-center gap-3">
                <img src="${trackData.trackImageUrl}" alt="${trackData.trackTitle}" class="h-10 w-10 rounded object-cover">
                <div>
                    <div class="font-semibold truncate">${trackData.trackTitle}</div>
                    <div class="text-sm text-gray-text truncate">${trackData.trackProducer}</div>
                </div>
            </a>
        </div>
        <button data-remove-track class="p-2 text-red-text hover:text-red-500">
            <span class="inline-block h-6 w-6">${getIconSVG("trash")}</span>
        </button>
    `;

    return newPlaylistItem;
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
      addTrack(trackId); // API call

      // Create the new, correctly styled item using our helper
      const newPlaylistItem = createPlaylistItemElement(evt.item);

      // Replace the badly formatted item that SortableJS created with our perfect one
      evt.item.replaceWith(newPlaylistItem);

      updateInPlaylistIndicators(); // Update the left side

      const trackIds = Array.from(playlistTracksList.children).map(
        (item) => item.dataset.trackId,
      );
      debouncedSaveOrder(trackIds);
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
    // First, check if the click was on a button we should ignore.
    const playButton = e.target.closest("[data-play-button]");
    if (playButton) {
      // If the user clicked the play button, do nothing and let the other
      // event listener handle it.
      return;
    }

    // Now, continue with the original logic for adding/removing tracks.
    const trackItem = e.target.closest(".track-item");
    if (!trackItem) return;

    const trackId = trackItem.dataset.trackId;

    if (trackItem && !trackItem.classList.contains("cursor-not-allowed")) {
      addTrack(trackId); // API call
      const newPlaylistItem = createPlaylistItemElement(trackItem);
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

  if (editorContainer) {
    editorContainer.addEventListener("click", (e) => {
      const playButton = e.target.closest("[data-play-button]");
      if (playButton) {
        e.preventDefault();
        e.stopPropagation();

        const trackId = playButton.dataset.trackId;
        const clickedItem = playButton.closest(".track-item"); // Get the element that was clicked

        if (window.playerAPI) {
          let playlistItemsForPlayer;

          // Check if the clicked item is inside the "Available Tracks" list
          if (clickedItem.closest("#all-tracks-list")) {
            // It's a PREVIEW from the left. The playlist is just this one song.
            playlistItemsForPlayer = [clickedItem];
          } else {
            // It's from the playlist on the right. The playlist is the entire right-hand list.
            playlistItemsForPlayer =
              playlistTracksList.querySelectorAll(".track-item");
          }

          // Now, build the state using the correct context and play the track.
          // This works for both cases because the track will always be in the list we provide.
          window.playerAPI.buildPlaylistFromEditor(playlistItemsForPlayer);
          window.playerAPI.loadAndPlayTrack(trackId);
        } else {
          alert(
            "Player API not found. Make sure main.js is loaded before this script.",
          );
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
        if (addButton) {
          addButton.innerHTML = `<span class="inline-block h-6 w-6 text-green-text">${getIconSVG("check")}</span>`;
        }
      } else {
        // If the track is not in the playlist:
        item.classList.remove("opacity-50", "cursor-not-allowed"); // Restore normal style
        if (addButton) {
          addButton.innerHTML = `<span class="inline-block h-6 w-6">${getIconSVG("plus")}</span>`;
        }
      }
    });
  };
  updateInPlaylistIndicators();
});
