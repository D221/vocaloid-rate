from collections import defaultdict
from statistics import median
from typing import Optional

from sqlalchemy import desc, distinct, func, nullslast, or_
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.sql.expression import exists

from app import models, schemas


def get_track_by_link(db: Session, link: str):
    return db.query(models.Track).filter(models.Track.link == link).first()


def create_track(db: Session, track: dict):
    db_track = models.Track(**track)
    db.add(db_track)
    db.commit()
    db.refresh(db_track)
    return db_track


def update_track(db: Session, db_track: models.Track, track: dict):
    for key, value in track.items():
        setattr(db_track, key, value)
    db.commit()
    db.refresh(db_track)
    return db_track


def get_tracks(
    db: Session,
    skip: int = 0,
    limit: int = 300,
    rated_filter: Optional[str] = None,
    title_filter: Optional[str] = None,
    producer_filter: Optional[str] = None,
    voicebank_filter: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_dir: str = "asc",
    rank_filter: str = "ranked",
    exact_rating_filter: Optional[int] = None,
):
    query = db.query(
        models.Track,
        exists()
        .where(models.PlaylistTrack.track_id == models.Track.id)
        .label("is_in_playlist"),
    )

    if rank_filter == "ranked":
        query = query.filter(models.Track.rank.isnot(None))
    elif rank_filter == "unranked":
        query = query.filter(models.Track.rank.is_(None))

    if title_filter:
        search_term = f"%{title_filter}%"
        query = query.filter(
            or_(
                models.Track.title.ilike(search_term),
                models.Track.title_jp.ilike(search_term),
            )
        )

    rating_join_applied = False

    # This logic is now mutually exclusive (if/elif/else)
    if exact_rating_filter is not None:
        # If we have an exact filter, it takes priority.
        query = query.join(models.Rating).filter(
            models.Rating.rating == exact_rating_filter
        )
        rating_join_applied = True
    elif rated_filter == "rated":
        # This only runs if there's NO exact_rating_filter
        query = query.join(models.Rating)
        rating_join_applied = True
    elif rated_filter == "unrated":
        query = query.outerjoin(models.Rating).filter(models.Rating.id.is_(None))
        rating_join_applied = True

    if producer_filter:
        query = query.filter(models.Track.producer.ilike(f"%{producer_filter}%"))
    if voicebank_filter:
        query = query.filter(models.Track.voicebank.ilike(f"%{voicebank_filter}%"))

    if sort_by:
        sort_column = getattr(models.Track, sort_by, None)
        if sort_column:
            order_expression = (
                sort_column.desc() if sort_dir == "desc" else sort_column.asc()
            )
            query = query.order_by(order_expression)
        elif sort_by == "rating":
            if not rating_join_applied:
                query = query.outerjoin(models.Rating)
            rating_column = models.Rating.rating
            if sort_dir == "desc":
                query = query.order_by(nullslast(rating_column.desc()))
            else:
                query = query.order_by(nullslast(rating_column.asc()))
    else:
        # Default sort order for the main page
        if rank_filter == "unranked":
            # For unranked archive, sort by date makes more sense
            query = query.order_by(models.Track.published_date.desc())
        else:
            # Default to rank for on-chart view
            query = query.order_by(models.Track.rank.asc())

    # distinct() is important for any query that joins with ratings
    if rating_join_applied:
        query = query.distinct()

    results = query.offset(skip).limit(limit).all()

    tracks_with_flag = []
    for track, is_in_playlist in results:
        track.is_in_playlist = is_in_playlist
        tracks_with_flag.append(track)

    return tracks_with_flag


def get_tracks_count(
    db: Session,
    rated_filter: Optional[str] = None,
    title_filter: Optional[str] = None,
    producer_filter: Optional[str] = None,
    voicebank_filter: Optional[str] = None,
    rank_filter: str = "ranked",
    exact_rating_filter: Optional[int] = None,
):
    query = db.query(func.count(distinct(models.Track.id)))

    if rank_filter == "ranked":
        query = query.filter(models.Track.rank.isnot(None))
    elif rank_filter == "unranked":
        query = query.filter(models.Track.rank.is_(None))

    if title_filter:
        search_term = f"%{title_filter}%"
        query = query.filter(
            or_(
                models.Track.title.ilike(search_term),
                models.Track.title_jp.ilike(search_term),
            )
        )

    if exact_rating_filter is not None:
        query = query.join(models.Rating).filter(
            models.Rating.rating == exact_rating_filter
        )
    elif rated_filter == "rated":
        query = query.join(models.Rating)
    elif rated_filter == "unrated":
        query = query.outerjoin(models.Rating).filter(models.Rating.id.is_(None))

    if producer_filter:
        query = query.filter(models.Track.producer.ilike(f"%{producer_filter}%"))
    if voicebank_filter:
        query = query.filter(models.Track.voicebank.ilike(f"%{voicebank_filter}%"))

    return query.scalar()


def create_rating(
    db: Session, track_id: int, rating: float, notes: Optional[str] = None
):
    db_rating = (
        db.query(models.Rating).filter(models.Rating.track_id == track_id).first()
    )
    if db_rating:
        db_rating.rating = rating
        db_rating.notes = notes
    else:
        db_rating = models.Rating(track_id=track_id, rating=rating)
        db.add(db_rating)
    db.commit()
    db.refresh(db_rating)
    return db_rating


def delete_rating(db: Session, track_id: int):
    db_rating = (
        db.query(models.Rating).filter(models.Rating.track_id == track_id).first()
    )
    if db_rating:
        db.delete(db_rating)
        db.commit()


def get_rating_statistics(db: Session):
    all_ratings_query = db.query(models.Rating.rating).all()
    if not all_ratings_query:
        # Return default structure if no ratings exist
        return {
            "total_ratings": 0,
            "average_rating": 0,
            "median_rating": 0,
            "top_producers": [],
            "top_voicebanks": [],
            "rating_distribution": {},
        }

    all_ratings_values = [r for (r,) in all_ratings_query]
    total_ratings = len(all_ratings_values)
    global_avg_rating = round(sum(all_ratings_values) / total_ratings, 2)
    MINIMUM_RATINGS_FOR_FAVORITE = 3

    # --- NEW PYTHON-BASED AGGREGATION LOGIC ---

    # Fetch all rated tracks with their producer, voicebank, and rating
    rated_tracks_data = (
        db.query(models.Track.producer, models.Track.voicebank, models.Rating.rating)
        .join(models.Rating)
        .all()
    )

    producer_ratings = defaultdict(list)
    voicebank_ratings = defaultdict(list)

    # De-normalize the data: split comma-separated strings
    for producer_str, voicebank_str, rating in rated_tracks_data:
        producers = [p.strip() for p in producer_str.split(",")]
        voicebanks = [v.strip() for v in voicebank_str.split(",")]

        for p in producers:
            producer_ratings[p].append(rating)
        for v in voicebanks:
            voicebank_ratings[v].append(rating)

    # Now, calculate the weighted score for each individual producer/voicebank
    top_producers = []
    for name, ratings in producer_ratings.items():
        if len(ratings) >= MINIMUM_RATINGS_FOR_FAVORITE:
            v = len(ratings)
            R = sum(ratings) / v
            score = ((v * R) + (MINIMUM_RATINGS_FOR_FAVORITE * global_avg_rating)) / (
                v + MINIMUM_RATINGS_FOR_FAVORITE
            )
            top_producers.append(
                {"name": name, "avg_rating": round(R, 2), "score": score}
            )

    top_voicebanks = []
    for name, ratings in voicebank_ratings.items():
        if len(ratings) >= MINIMUM_RATINGS_FOR_FAVORITE:
            v = len(ratings)
            R = sum(ratings) / v
            score = ((v * R) + (MINIMUM_RATINGS_FOR_FAVORITE * global_avg_rating)) / (
                v + MINIMUM_RATINGS_FOR_FAVORITE
            )
            top_voicebanks.append(
                {"name": name, "avg_rating": round(R, 2), "score": score}
            )

    # Sort the lists by the weighted score and take the top 10
    top_producers = sorted(top_producers, key=lambda x: x["score"], reverse=True)[:10]
    top_voicebanks = sorted(top_voicebanks, key=lambda x: x["score"], reverse=True)[:10]

    # --- END OF NEW LOGIC ---

    median_rating = median(all_ratings_values)

    distribution_query = (
        db.query(models.Rating.rating, func.count(models.Rating.rating).label("count"))
        .group_by(models.Rating.rating)
        .order_by(desc(models.Rating.rating))
        .all()
    )
    rating_distribution = {rating: count for rating, count in distribution_query}

    return {
        "total_ratings": total_ratings,
        "average_rating": global_avg_rating,
        "median_rating": median_rating,
        "top_producers": top_producers,
        "top_voicebanks": top_voicebanks,
        "rating_distribution": rating_distribution,
    }


def create_update_log(db: Session):
    db_update_log = models.UpdateLog()
    db.add(db_update_log)
    db.commit()
    db.refresh(db_update_log)
    return db_update_log


def get_last_update_time(db: Session):
    return (
        db.query(models.UpdateLog).order_by(models.UpdateLog.updated_at.desc()).first()
    )


def get_playlist(db: Session, playlist_id: int) -> Optional[models.Playlist]:
    """Gets a single playlist by its ID, eagerly loading the tracks in their correct order."""
    return (
        db.query(models.Playlist)
        .filter(models.Playlist.id == playlist_id)
        .options(
            joinedload(models.Playlist.playlist_tracks).joinedload(
                models.PlaylistTrack.track
            )
        )
        .first()
    )


def get_playlists(db: Session) -> list[models.Playlist]:
    """Gets a list of all playlists."""
    return db.query(models.Playlist).order_by(models.Playlist.name).all()


def create_playlist(db: Session, playlist: schemas.PlaylistCreate) -> models.Playlist:
    """Creates a new playlist."""
    db_playlist = models.Playlist(name=playlist.name, description=playlist.description)
    db.add(db_playlist)
    db.commit()
    db.refresh(db_playlist)
    return db_playlist


def delete_playlist(db: Session, playlist_id: int) -> bool:
    """Deletes a playlist by its ID."""
    db_playlist = db.query(models.Playlist).filter_by(id=playlist_id).first()
    if db_playlist:
        db.delete(db_playlist)
        db.commit()
        return True
    return False


def update_playlist(
    db: Session, playlist_id: int, name: str, description: Optional[str]
) -> Optional[models.Playlist]:
    """Updates a playlist's name and description."""
    db_playlist = get_playlist(db, playlist_id)
    if db_playlist:
        db_playlist.name = name
        db_playlist.description = description
        db.commit()
        db.refresh(db_playlist)
    return db_playlist


def add_track_to_playlist(
    db: Session, playlist_id: int, track_id: int
) -> Optional[models.Playlist]:
    """Adds a track to the end of a playlist."""
    db_playlist = get_playlist(db, playlist_id)
    if not db_playlist:
        return None

    # Check if the track is already in the playlist
    for pt in db_playlist.playlist_tracks:
        if pt.track_id == track_id:
            return db_playlist  # Already exists, do nothing

    # Find the next position
    next_position = len(db_playlist.playlist_tracks)

    # Create the association
    playlist_track = models.PlaylistTrack(
        playlist_id=playlist_id, track_id=track_id, position=next_position
    )
    db.add(playlist_track)
    db.commit()
    db.refresh(db_playlist)
    return db_playlist


def remove_track_from_playlist(db: Session, playlist_id: int, track_id: int):
    """Removes a track from a playlist and re-orders the remaining tracks."""
    assoc_to_delete = (
        db.query(models.PlaylistTrack)
        .filter_by(playlist_id=playlist_id, track_id=track_id)
        .first()
    )

    if assoc_to_delete:
        deleted_position = assoc_to_delete.position
        db.delete(assoc_to_delete)

        # Update positions of subsequent tracks
        db.query(models.PlaylistTrack).filter(
            models.PlaylistTrack.playlist_id == playlist_id,
            models.PlaylistTrack.position > deleted_position,
        ).update({"position": models.PlaylistTrack.position - 1})

        db.commit()


def reorder_playlist(db: Session, playlist_id: int, track_ids: list[int]):
    """Re-orders an entire playlist based on a new list of track IDs."""
    # This is an efficient way to update all positions at once
    for index, track_id in enumerate(track_ids):
        db.query(models.PlaylistTrack).filter_by(
            playlist_id=playlist_id, track_id=track_id
        ).update({"position": index})
    db.commit()


def export_playlists(db: Session) -> list[dict]:
    """Fetches all playlists and formats them for JSON export."""
    playlists_to_export = []
    all_playlists = (
        db.query(models.Playlist)
        .options(
            joinedload(models.Playlist.playlist_tracks).joinedload(
                models.PlaylistTrack.track
            )
        )
        .all()
    )

    for playlist in all_playlists:
        track_links = [pt.track.link for pt in playlist.playlist_tracks if pt.track]
        playlists_to_export.append(
            {
                "name": playlist.name,
                "description": playlist.description,
                "tracks": track_links,
            }
        )
    return playlists_to_export


def export_single_playlist(db: Session, playlist_id: int) -> Optional[dict]:
    """Fetches a single playlist and formats it for JSON export."""
    playlist = (
        db.query(models.Playlist)
        .filter_by(id=playlist_id)
        .options(
            joinedload(models.Playlist.playlist_tracks).joinedload(
                models.PlaylistTrack.track
            )
        )
        .first()
    )

    if not playlist:
        return None

    track_links = [pt.track.link for pt in playlist.playlist_tracks if pt.track]
    return {
        "name": playlist.name,
        "description": playlist.description,
        "tracks": track_links,
    }


def import_playlists(db: Session, data: list[dict]) -> tuple[int, int]:
    """Imports playlists from a list of dictionaries, merging with existing data."""
    created_count = 0
    updated_count = 0

    for playlist_data in data:
        playlist_name = playlist_data.get("name")
        if not playlist_name:
            continue

        # Find existing playlist by name or create a new one
        db_playlist = db.query(models.Playlist).filter_by(name=playlist_name).first()
        if not db_playlist:
            db_playlist = models.Playlist(
                name=playlist_name, description=playlist_data.get("description")
            )
            db.add(db_playlist)
            created_count += 1
        else:
            updated_count += 1

        # We need to flush to get the playlist ID if it's new
        db.flush()

        # Clear existing tracks to ensure order is correct from the import
        db.query(models.PlaylistTrack).filter_by(playlist_id=db_playlist.id).delete()

        # Add tracks from the import file
        track_links = playlist_data.get("tracks", [])
        for index, link in enumerate(track_links):
            # Find the track in the DB by its unique link
            track = db.query(models.Track).filter_by(link=link).first()
            if track:
                assoc = models.PlaylistTrack(
                    playlist_id=db_playlist.id, track_id=track.id, position=index
                )
                db.add(assoc)

    db.commit()
    return created_count, updated_count


def get_track_playlist_membership(db: Session, track_id: int) -> dict:
    """Checks which playlists a track belongs to."""

    # 1. Get IDs of playlists the track is in.
    member_playlist_ids_query = db.query(models.PlaylistTrack.playlist_id).filter_by(
        track_id=track_id
    )
    member_playlist_ids = {id for (id,) in member_playlist_ids_query}

    # 2. Get all playlists.
    all_playlists = db.query(models.Playlist).all()

    # 3. Separate them into two lists.
    member_of = []
    not_member_of = []
    for p in all_playlists:
        playlist_info = {"id": p.id, "name": p.name}
        if p.id in member_playlist_ids:
            member_of.append(playlist_info)
        else:
            not_member_of.append(playlist_info)

    return {"member_of": member_of, "not_member_of": not_member_of}
