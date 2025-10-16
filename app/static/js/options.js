document.addEventListener('DOMContentLoaded', () => {
    const backupButton = document.getElementById('backup-button');
    const restoreButton = document.getElementById('restore-button');
    const restoreFileInput = document.getElementById('restore-file-input');
    const restoreStatus = document.getElementById('restore-status');
    const restoreSpinner = document.getElementById('restore-spinner');

    // Enable restore button only when a file is selected
    restoreFileInput.addEventListener('change', () => {
        restoreButton.disabled = !restoreFileInput.files.length;
    });

    // Backup functionality
    backupButton.addEventListener('click', async () => {
        try {
            const response = await fetch('/api/backup/ratings');
            if (!response.ok) {
                throw new Error('Failed to fetch backup data.');
            }
            const data = await response.json();
            const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `vocaloid_ratings_backup_${new Date().toISOString().slice(0, 10)}.json`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        } catch (error) {
            console.error('Backup failed:', error);
            alert('Backup failed. See console for details.');
        }
    });

    // Restore functionality
    restoreButton.addEventListener('click', async () => {
        const file = restoreFileInput.files[0];
        if (!file) {
            restoreStatus.textContent = 'Please select a file to restore.';
            return;
        }

        restoreButton.disabled = true;
        restoreStatus.textContent = 'Restoring...';
        restoreSpinner.style.display = 'inline-block';

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('/api/restore/ratings', {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Restore failed.');
            }

            const result = await response.json();
            restoreStatus.textContent = `Restore successful! ${result.created} tracks created, ${result.updated} tracks updated.`;
        } catch (error) {
            console.error('Restore failed:', error);
            restoreStatus.textContent = `Error: ${error.message}`;
        } finally {
            restoreButton.disabled = false;
            restoreSpinner.style.display = 'none';
        }
    });
});
