---
sidebar_position: 7
---

# Database Schema

This page documents the database schema used in the Vocaloid Rate application, as defined in `app/schemas.py`.

## Track

Represents a single song in the database.

- `id`: int (Primary Key)
- `title`: str
- `producer`: str
- `voicebank`: str
- `published_date`: datetime
- `link`: str (Unique)
- `image_url`: str (Optional)
- `rank`: int (Optional)

## Rating

Represents a rating for a single track.

- `id`: int (Primary Key)
- `track_id`: int (Foreign Key to Track)
- `rating`: float
- `notes`: str (Optional)
- `created_at`: datetime
- `updated_at`: datetime

## Playlist

Represents a user-created playlist.

- `id`: int (Primary Key)
- `name`: str
- `description`: str (Optional)
- `created_at`: datetime

## PlaylistTrack

Represents the association between a track and a playlist.

- `playlist_id`: int (Foreign Key to Playlist)
- `track_id`: int (Foreign Key to Track)
- `position`: int
