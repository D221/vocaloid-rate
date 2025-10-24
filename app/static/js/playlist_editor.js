/* global Sortable */

document.addEventListener("DOMContentLoaded", () => {
  const allTracksList = document.getElementById("all-tracks-list");
  const playlistTracksList = document.getElementById("playlist-tracks-list");
  const trackSearch = document.getElementById("track-search");
  const playlistId =
    document.querySelector("[data-playlist-id]").dataset.playlistId;

  // --- API HELPER FUNCTIONS ---
  const saveOrder = async (trackIds) => {
    try {
      await fetch(`/api/playlists/${playlistId}/reorder`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(trackIds),
      });
      // You can add a "Saved!" notification here
    } catch (error) {
      console.error("Failed to save order:", error);
      alert("Failed to save order.");
    }
  };

  const addTrack = async (trackId) => {
    try {
      await fetch(`/api/playlists/${playlistId}/tracks/${trackId}`, {
        method: "POST",
      });
    } catch (error) {
      console.error("Failed to add track:", error);
      alert("Failed to add track.");
    }
  };

  const removeTrack = async (trackId) => {
    try {
      await fetch(`/api/playlists/${playlistId}/tracks/${trackId}`, {
        method: "DELETE",
      });
    } catch (error) {
      console.error("Failed to remove track:", error);
      alert("Failed to remove track.");
    }
  };

  // --- SORTABLEJS INITIALIZATION ---

  // Initialize the "All Tracks" list (the source)
  new Sortable(allTracksList, {
    group: {
      name: "shared",
      pull: "clone", // Clone items instead of moving them
      put: false, // Don't allow items to be dropped here
    },
    sort: false, // Don't let the user reorder the master list
    animation: 150,
  });

  // Initialize the "Playlist Tracks" list (the destination)
  new Sortable(playlistTracksList, {
    group: "shared", // Items can be dropped here
    animation: 150,
    handle: ".fa-grip-vertical", // Use a handle for reordering
    onAdd: function (evt) {
      // A new track was dropped from the left list
      const trackId = evt.item.dataset.trackId;
      addTrack(trackId);
      // We need to rebuild the item to match the playlist style
      const clonedItem = evt.item.cloneNode(true);
      const originalItemHTML = `
                <div class="flex items-center gap-3 overflow-hidden">
                    <i class="fa-solid fa-grip-vertical text-gray-text"></i>
                    ${clonedItem.innerHTML}
                </div>
                <button data-remove-track class="text-red-text hover:text-red-500 p-2"><i class="fa-solid fa-trash"></i></button>
            `;
      evt.item.innerHTML = originalItemHTML;
      evt.item.classList.add("justify-between", "bg-card-bg", "shadow");
    },
    onEnd: function () {
      // Reordering finished, save the new order
      const trackIds = Array.from(playlistTracksList.children).map(
        (item) => item.dataset.trackId,
      );
      saveOrder(trackIds);
    },
  });

  // --- EVENT LISTENERS ---

  // Search/Filter for the "All Tracks" list
  trackSearch.addEventListener("input", () => {
    const searchTerm = trackSearch.value.toLowerCase();
    allTracksList.querySelectorAll(".track-item").forEach((item) => {
      const itemText = item.textContent.toLowerCase();
      item.style.display = itemText.includes(searchTerm) ? "flex" : "none";
    });
  });

  // Handle clicks on the "Remove" trash icon
  playlistTracksList.addEventListener("click", (e) => {
    const removeButton = e.target.closest("[data-remove-track]");
    if (removeButton) {
      const trackItem = removeButton.closest(".track-item");
      const trackId = trackItem.dataset.trackId;
      removeTrack(trackId);
      trackItem.remove();
    }
  });
});
