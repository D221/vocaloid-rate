document.addEventListener("DOMContentLoaded", () => {
  function setDefaultPageSizeCookie(value) {
    const encoded = encodeURIComponent(value);
    document.cookie = `default_page_size=${encoded}; path=/; max-age=31536000; samesite=lax`;
  }

  function updateThemeSelectionUI() {
    // Get the current theme from storage, or fall back to the system theme
    const currentTheme = window.getStoredTheme() || window.getSystemTheme();

    // Find the radio button that matches the current theme
    const themeRadioButton = document.querySelector(
      `input[name="theme-select"][value="${currentTheme}"]`,
    );

    // If we find a matching radio button, check it
    if (themeRadioButton) {
      themeRadioButton.checked = true;
    }
  }

  updateThemeSelectionUI();

  const themeRadios = document.querySelectorAll('input[name="theme-select"]');
  themeRadios.forEach((radio) => {
    radio.addEventListener("change", (event) => {
      // When a radio button is selected, apply its value as the new theme
      window.applyTheme(event.target.value);
    });
  });

  // --- ELEMENT SELECTORS ---
  const backupButton = document.getElementById("backup-button");
  const restoreButton = document.getElementById("restore-button");
  const restoreFileInput = document.getElementById("restore-file-input");
  const restoreStatus = document.getElementById("restore-status");
  const restoreSpinner = document.getElementById("restore-spinner");
  const defaultPageSizeSelect = document.getElementById(
    "default-page-size-select",
  );
  // --- OPTIONS PAGE LOGIC ---

  // Load saved page size setting
  if (defaultPageSizeSelect) {
    const savedPageSize = localStorage.getItem("defaultPageSize") || "all";
    defaultPageSizeSelect.value = savedPageSize;
    setDefaultPageSizeCookie(savedPageSize);

    defaultPageSizeSelect.addEventListener("change", () => {
      const selectedPageSize = defaultPageSizeSelect.value;
      localStorage.setItem("defaultPageSize", selectedPageSize);
      setDefaultPageSizeCookie(selectedPageSize);
    });
  }

  // Enable restore button only when a file is selected
  if (restoreFileInput) {
    restoreFileInput.addEventListener("change", () => {
      restoreButton.disabled = !restoreFileInput.files.length;
    });
  }

  // Backup functionality
  if (backupButton) {
    backupButton.addEventListener("click", async () => {
      try {
        const response = await fetch("/api/backup/ratings");
        if (!response.ok) {
          throw new Error("Failed to fetch backup data.");
        }
        const data = await response.json();
        const blob = new Blob([JSON.stringify(data, null, 2)], {
          type: "application/json",
        });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `vocaloid_ratings_backup_${new Date().toISOString().slice(0, 10)}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      } catch (error) {
        console.error("Backup failed:", error);
        if (typeof window.showToast === "function") {
          window.showToast("Backup failed. See console for details.", "error");
        }
      }
    });
  }

  // Restore functionality
  if (restoreButton) {
    restoreButton.addEventListener("click", async () => {
      const file = restoreFileInput.files[0];
      if (!file) {
        restoreStatus.textContent = "Please select a file to restore.";
        return;
      }

      restoreButton.disabled = true;
      restoreStatus.textContent = "Restoring...";
      restoreSpinner.style.display = "inline-block";

      const formData = new FormData();
      formData.append("file", file);

      try {
        const response = await fetch("/api/restore/ratings", {
          method: "POST",
          body: formData,
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || "Restore failed.");
        }

        const result = await response.json();
        restoreStatus.textContent = `Restore successful! ${result.created} tracks created, ${result.updated} tracks updated.`;
      } catch (error) {
        console.error("Restore failed:", error);
        restoreStatus.textContent = `Error: ${error.message}`;
      } finally {
        restoreButton.disabled = false;
        restoreSpinner.style.display = "none";
      }
    });
  }

  const SLIM_MODE_KEY = "viewModeSlim";
  const slimModeToggle = document.getElementById("slim-mode-toggle");

  if (slimModeToggle) {
    // 1. Read the current setting from localStorage when the page loads.
    const isSlim = localStorage.getItem(SLIM_MODE_KEY) === "true";

    // 2. Set the checkbox's state to match the stored setting.
    slimModeToggle.checked = isSlim;

    // 3. Add the event listener to save changes and reload.
    slimModeToggle.addEventListener("change", () => {
      const isChecked = slimModeToggle.checked;
      localStorage.setItem(SLIM_MODE_KEY, isChecked);
      document.documentElement.classList.toggle("slim-mode-html", isChecked);
      if (typeof window.showToast === "function") {
        window.showToast(
          isChecked ? "Slim mode enabled." : "Slim mode disabled.",
          "success",
        );
      }
    });
  }

  // Profile settings functionality
  const profileForm = document.getElementById("profile-form");
  const profileStatus = document.getElementById("profile-status");
  const saveProfileButton = document.getElementById("save-profile-button");

  if (profileForm) {
    profileForm.addEventListener("submit", async (event) => {
      event.preventDefault();

      const usernameInput = document.getElementById("profile-username");
      const publicCheckbox = document.getElementById("profile-public");

      const username = usernameInput.value.trim();
      const is_profile_public = publicCheckbox.checked;

      saveProfileButton.disabled = true;
      profileStatus.textContent = "Saving...";
      profileStatus.className = "mt-2 font-bold text-gray-text";

      try {
        const response = await fetch("/api/users/me/profile", {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            username: username,
            is_profile_public: is_profile_public,
          }),
        });

        if (!response.ok) {
          const errData = await response.json();
          throw new Error(
            errData.detail || "Failed to update profile settings.",
          );
        }

        profileStatus.textContent =
          "Profile updated successfully! Reloading to apply...";
        profileStatus.className = "mt-2 font-bold text-green-600";
        if (typeof window.showToast === "function") {
          window.showToast("Profile settings saved.", "success");
        }

        setTimeout(() => {
          window.location.reload();
        }, 1000);
      } catch (error) {
        console.error("Profile update failed:", error);
        profileStatus.textContent = `Error: ${error.message}`;
        profileStatus.className = "mt-2 font-bold text-red-600";
        if (typeof window.showToast === "function") {
          window.showToast(error.message, "error");
        }
        saveProfileButton.disabled = false;
      }
    });
  }
});
