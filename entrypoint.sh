#!/bin/sh
set -e

# Default user ID and group ID to use if the volume is root-owned.
# 1000 is a common default for the first non-root user on Linux.
DEFAULT_UID=1000
DEFAULT_GID=1000

# Get the UID and GID of the /app/data directory
DETECTED_UID=$(stat -c "%u" /app/data)
DETECTED_GID=$(stat -c "%g" /app/data)

# Check if the directory is owned by root. This happens when Docker auto-creates the volume.
if [ "$DETECTED_UID" -eq 0 ]; then
    echo "---"
    echo "INFO: Host directory is owned by root. Applying default owner (1000:1000)."
    echo "      This is a one-time setup."
    echo "---"

    # Set the user and group to our default
    FINAL_UID=$DEFAULT_UID
    FINAL_GID=$DEFAULT_GID

    # IMPORTANT: Change the ownership of the mounted directory.
    # This change will be reflected on the host, fixing the permissions problem permanently.
    chown "$FINAL_UID":"$FINAL_GID" /app/data
else
    echo "---"
    echo "INFO: Host directory is owned by a non-root user. Using detected owner."
    echo "---"
    # Use the detected UID and GID from the existing directory
    FINAL_UID=$DETECTED_UID
    FINAL_GID=$DETECTED_GID
fi

echo "---"
echo "Starting application with UID: $FINAL_UID, GID: $FINAL_GID"
echo "---"

# Create a group and user with the final UID/GID.
# The '2>/dev/null || true' part suppresses errors if the group already exists.
groupadd -g "$FINAL_GID" appgroup 2>/dev/null || true
useradd --shell /bin/bash -u "$FINAL_UID" -g "$FINAL_GID" -o -c "" -m appuser

# Give ownership of the rest of the app to this user for consistency,
# though the /app/data ownership is the most critical part.
chown -R appuser:appgroup /app

# Switch to the new user and execute the main command.
exec su appuser -c "$*"