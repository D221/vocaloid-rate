---
sidebar_position: 6
---

# API Reference

This page documents the API endpoints available in the Vocaloid Rate application.

## Main Endpoints

- `GET /`: The main page of the application.
- `GET /rated_tracks`: Displays all the tracks that have been rated.
- `GET /playlists`: Displays all the playlists.
- `GET /playlist/{playlist_id}`: Displays a specific playlist.
- `GET /playlist/edit/{playlist_id}`: Displays the page to edit a specific playlist.
- `GET /options`: Displays the options page.

## Scraping

- `POST /scrape`: Starts the scraping process in the background.
- `GET /api/scrape-status`: Gets the current status of the scraping process.

## Ratings

- `POST /rate/{track_id}`: Adds or updates a rating for a specific track.
- `POST /rate/{track_id}/delete`: Deletes a rating for a specific track.

## Playlists

- `GET /api/playlists`: Gets a simple list of all playlists.
- `POST /api/playlists`: Creates a new, empty playlist.
- `POST /api/playlists/{playlist_id}/tracks/{track_id}`: Adds a single track to a playlist.
- `DELETE /api/playlists/{playlist_id}/tracks/{track_id}`: Removes a single track from a playlist.
- `POST /api/playlists/{playlist_id}/reorder`: Updates the order of all tracks in a playlist.
- `PUT /api/playlists/{playlist_id}`: Updates a playlist's name and description.
- `DELETE /api/playlists/{playlist_id}`: Deletes a playlist.

## Data Endpoints

- `GET /_/get_tracks`: Gets a partial list of tracks based on the provided filters.
- `GET /api/playlist/{playlist_id}/get_tracks`: Gets a partial list of tracks for a specific playlist based on the provided filters.
- `GET /api/tracks/{track_id}/playlist-status`: Gets the playlist status for a track.
- `GET /api/playlist-snapshot`: Gets a snapshot of the current playlist.
- `GET /api/playlist/{playlist_id}/playlist-snapshot`: Gets a snapshot of a specific playlist.

## VocaDB Integration

- `GET /api/vocadb_artist_search`: Searches for an artist on VocaDB.
- `GET /api/vocadb_search`: Searches for a song on VocaDB.
- `GET /api/vocadb_lyrics/{song_id}`: Gets the lyrics for a song from VocaDB.

## Backup & Restore

- `GET /api/backup/ratings`: Exports all ratings to a JSON file.
- `POST /api/restore/ratings`: Imports ratings from a JSON file.
- `GET /api/playlists/export`: Exports all playlists to a JSON file.
- `POST /api/playlists/import-single`: Imports a single playlist from a JSON file.
- `GET /api/playlists/{playlist_id}/export`: Exports a single playlist to a JSON file.
