document.addEventListener("DOMContentLoaded", () => {
  const createBtn = document.getElementById("create-new-playlist-btn");
  const createPanel = document.getElementById("create-playlist-panel");
  const createInput = document.getElementById("new-playlist-name-input");
  const createSaveBtn = document.getElementById("save-new-playlist-btn");
  const createStatus = document.getElementById("create-playlist-status");
  const playlistsContainer = document.getElementById("playlists-list");
  const importStatus = document.getElementById("import-status");
  const importSingleInput = document.getElementById(
    "import-single-playlist-input",
  );
  const importAllInput = document.getElementById("import-playlists-input");
  const importAllBtn = document.getElementById("import-playlists-btn");
  const exportAllBtn = document.getElementById("export-playlists-btn");

  const showMessage = (message, type = "success") => {
    if (typeof window.showToast === "function") {
      window.showToast(message, type);
    }
  };

  const escapeHtml = (value) =>
    String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");

  const playlistCardHtml = (playlist) => {
    const safeName = escapeHtml(playlist.name || "");
    const safeDescription = escapeHtml(
      playlist.description || window._("No description."),
    );
    return `
      <div class="flex items-center justify-between rounded border border-border bg-card-bg p-4 shadow-md"
        data-playlist-id="${playlist.id}"
        data-playlist-name="${safeName}"
        data-playlist-description="${safeDescription}">
        <div>
          <h2 class="text-xl font-bold text-header">${safeName}</h2>
          <p class="text-gray-text">${safeDescription}</p>
        </div>
        <div class="flex shrink-0 gap-2">
          <a href="/playlist/${playlist.id}" class="cursor-pointer rounded border border-gray-text p-2 font-bold text-gray-text shadow-md ease-in-out hover:bg-gray-hover hover:transition-colors hover:duration-200" title="${window._("View")}">${window._("View")}</a>
          <a href="/playlist/edit/${playlist.id}" class="cursor-pointer rounded border border-amber-text p-2 font-bold text-amber-text shadow-md ease-in-out hover:bg-amber-hover hover:transition-colors hover:duration-200" title="${window._("Edit")}">${window._("Edit")}</a>
          <button data-export-single-playlist="${playlist.id}" class="cursor-pointer rounded border border-sky-text p-2 font-bold text-sky-text shadow-md ease-in-out hover:bg-sky-hover hover:transition-colors hover:duration-200" title="${window._("Export")}">${window._("Export")}</button>
          <button data-delete-playlist="${playlist.id}" data-playlist-name="${safeName}" class="cursor-pointer rounded border border-red-text p-2 font-bold text-red-text shadow-md ease-in-out hover:bg-red-hover hover:transition-colors hover:duration-200" title="${window._("Delete")}">${window._("Delete")}</button>
        </div>
      </div>`;
  };

  const upsertPlaylistCard = (playlist) => {
    if (!playlistsContainer) return;

    const emptyState = document.getElementById("empty-playlists-state");
    if (emptyState) emptyState.remove();

    const existingCard = playlistsContainer.querySelector(
      `[data-playlist-id="${playlist.id}"]`,
    );
    if (existingCard) {
      existingCard.outerHTML = playlistCardHtml(playlist);
      return;
    }
    playlistsContainer.insertAdjacentHTML(
      "afterbegin",
      playlistCardHtml(playlist),
    );
  };

  const refreshPlaylistsFromServer = async () => {
    if (!playlistsContainer) return;
    const response = await fetch("/api/playlists");
    if (!response.ok) {
      throw new Error(window._("Failed to fetch playlists."));
    }
    const playlists = await response.json();
    if (!Array.isArray(playlists) || playlists.length === 0) {
      playlistsContainer.innerHTML = `<div id="empty-playlists-state" class="rounded border border-border bg-card-bg p-8 text-center text-gray-text shadow-md">${window._("You haven't created any playlists yet.")}</div>`;
      return;
    }
    playlistsContainer.innerHTML = playlists.map(playlistCardHtml).join("");
  };

  const setCreatePanelVisibility = (isVisible) => {
    if (!createPanel) return;
    createPanel.classList.toggle("hidden", !isVisible);
    if (isVisible && createInput) {
      createInput.focus();
      createInput.select();
    }
  };

  const createPlaylist = async () => {
    if (!createInput || !createSaveBtn || !createStatus) return;
    const name = createInput.value.trim();
    if (!name) {
      createStatus.textContent = window._("Please enter a playlist name.");
      return;
    }

    createSaveBtn.disabled = true;
    createStatus.textContent = window._("Creating...");
    try {
      const response = await fetch("/api/playlists", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
      if (!response.ok) {
        throw new Error(window._("Failed to create playlist."));
      }

      const playlist = await response.json();
      upsertPlaylistCard({
        id: playlist.id,
        name: playlist.name,
        description: playlist.description || "",
      });
      createInput.value = "";
      createStatus.textContent = window._("Playlist created.");
      showMessage(window._("Playlist created."));
      setCreatePanelVisibility(false);
    } catch (error) {
      createStatus.textContent = String(error.message || window._("Error."));
      showMessage(window._("Failed to create playlist."), "error");
    } finally {
      createSaveBtn.disabled = false;
    }
  };

  if (createBtn) {
    createBtn.addEventListener("click", () => {
      const isHidden = createPanel?.classList.contains("hidden");
      setCreatePanelVisibility(Boolean(isHidden));
    });
  }

  if (createSaveBtn) {
    createSaveBtn.addEventListener("click", createPlaylist);
  }

  if (createInput) {
    createInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        createPlaylist();
      }
    });
  }

  if (exportAllBtn) {
    exportAllBtn.addEventListener("click", async () => {
      try {
        const response = await fetch("/api/playlists/export");
        if (!response.ok) throw new Error();
        const data = await response.json();
        const blob = new Blob([JSON.stringify(data, null, 2)], {
          type: "application/json",
        });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `playlists_export_${new Date().toISOString().slice(0, 10)}.json`;
        a.click();
        URL.revokeObjectURL(url);
      } catch {
        showMessage(window._("Failed to export playlists."), "error");
      }
    });
  }

  if (importAllInput && importAllBtn) {
    importAllInput.addEventListener("change", () => {
      importAllBtn.disabled = !importAllInput.files.length;
    });

    importAllBtn.addEventListener("click", async () => {
      const file = importAllInput.files?.[0];
      if (!file) return;
      importAllBtn.disabled = true;
      if (importStatus) {
        importStatus.textContent = window._("Importing...");
      }
      try {
        const formData = new FormData();
        formData.append("file", file);
        const response = await fetch("/api/playlists/import", {
          method: "POST",
          body: formData,
        });
        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || window._("Import failed."));
        }
        const result = await response.json();
        if (importStatus) {
          importStatus.textContent = window._(
            "Import complete. %s created, %s updated.",
            String(result.created),
            String(result.updated),
          );
        }
        await refreshPlaylistsFromServer();
        showMessage(window._("Playlists imported."));
      } catch (error) {
        if (importStatus) {
          importStatus.textContent = `${window._("Error")}: ${error.message}`;
        }
        showMessage(window._("Failed to import playlists."), "error");
      } finally {
        importAllBtn.disabled = false;
      }
    });
  }

  if (playlistsContainer) {
    playlistsContainer.addEventListener("click", async (e) => {
      const exportButton = e.target.closest("[data-export-single-playlist]");
      const deleteButton = e.target.closest("[data-delete-playlist]");

      if (exportButton) {
        const playlistId = exportButton.dataset.exportSinglePlaylist;
        try {
          const response = await fetch(`/api/playlists/${playlistId}/export`);
          if (!response.ok) throw new Error();
          const data = await response.json();
          const blob = new Blob([JSON.stringify(data, null, 2)], {
            type: "application/json",
          });
          const url = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          const safeName = data.name.replace(/[^a-z0-9]/gi, "_").toLowerCase();
          a.download = `playlist_${safeName}.json`;
          a.click();
          URL.revokeObjectURL(url);
        } catch {
          showMessage(window._("Failed to export playlist."), "error");
        }
      }

      if (deleteButton) {
        const playlistId = deleteButton.dataset.deletePlaylist;
        const playlistName = deleteButton.dataset.playlistName;
        if (
          !confirm(
            `${window._("Are you sure you want to delete the playlist")} "${playlistName}"? ${window._("This cannot be undone.")}`,
          )
        ) {
          return;
        }

        try {
          const response = await fetch(`/api/playlists/${playlistId}`, {
            method: "DELETE",
          });
          if (!response.ok) throw new Error();

          const card = deleteButton.closest("[data-playlist-id]");
          card?.remove();
          showMessage(window._("Playlist deleted."));
          if (!playlistsContainer.querySelector("[data-playlist-id]")) {
            playlistsContainer.innerHTML = `<div id="empty-playlists-state" class="rounded border border-border bg-card-bg p-8 text-center text-gray-text shadow-md">${window._("You haven't created any playlists yet.")}</div>`;
          }
        } catch {
          showMessage(window._("Failed to delete playlist."), "error");
        }
      }
    });
  }

  if (importSingleInput) {
    importSingleInput.addEventListener("change", async () => {
      const file = importSingleInput.files[0];
      if (!file) return;

      if (importStatus) {
        importStatus.textContent = window._("Importing...");
      }
      const formData = new FormData();
      formData.append("file", file);

      try {
        const response = await fetch("/api/playlists/import-single", {
          method: "POST",
          body: formData,
        });
        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || window._("Import failed."));
        }
        const result = await response.json();
        if (importStatus) {
          importStatus.textContent = window._(
            "Success! Playlist %s.",
            String(result.status),
          );
        }
        await refreshPlaylistsFromServer();
        showMessage(window._("Playlist import completed."));
      } catch (error) {
        if (importStatus) {
          importStatus.textContent = `${window._("Error")}: ${error.message}`;
        }
        showMessage(window._("Failed to import playlist."), "error");
      }
    });
  }
});
