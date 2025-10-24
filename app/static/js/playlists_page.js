document.addEventListener("DOMContentLoaded", () => {
  const createBtn = document.getElementById("create-new-playlist-btn");
  if (createBtn) {
    createBtn.addEventListener("click", () => {
      const name = prompt("Enter a name for your new playlist:");
      if (name && name.trim()) {
        fetch("/api/playlists", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: name.trim() }),
        }).then((res) => {
          if (res.ok) {
            window.location.reload();
          } else {
            alert("Failed to create playlist.");
          }
        });
      }
    });
  }

  // --- NEW: SINGLE IMPORT/EXPORT LOGIC ---
  const importSingleInput = document.getElementById(
    "import-single-playlist-input",
  );
  const importStatus = document.getElementById("import-status");
  const playlistsContainer = document.querySelector(".space-y-4");

  // Single Playlist Export
  if (playlistsContainer) {
    playlistsContainer.addEventListener("click", async (e) => {
      const exportButton = e.target.closest("[data-export-single-playlist]");
      if (exportButton) {
        console.log("Export button clicked!", exportButton);
        const playlistId = exportButton.dataset.exportSinglePlaylist;
        try {
          const response = await fetch(`/api/playlists/${playlistId}/export`);
          const data = await response.json();
          const blob = new Blob([JSON.stringify(data, null, 2)], {
            type: "application/json",
          });
          const url = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          // Sanitize the playlist name for the filename
          const safeName = data.name.replace(/[^a-z0-9]/gi, "_").toLowerCase();
          a.download = `playlist_${safeName}.json`;
          a.click();
          URL.revokeObjectURL(url);
        } catch (error) {
          alert("Failed to export playlist.");
          console.error(error);
        }
      }
    });
  }

  // Single Playlist Import
  if (importSingleInput) {
    importSingleInput.addEventListener("change", async () => {
      const file = importSingleInput.files[0];
      if (!file) return;

      importStatus.textContent = "Importing...";
      const formData = new FormData();
      formData.append("file", file);

      try {
        const response = await fetch("/api/playlists/import-single", {
          method: "POST",
          body: formData,
        });
        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || "Import failed");
        }
        const result = await response.json();
        importStatus.textContent = `Success! Playlist ${result.status}. Reloading...`;
        setTimeout(() => window.location.reload(), 2000);
      } catch (error) {
        importStatus.textContent = `Error: ${error.message}`;
      }
    });
  }
});
