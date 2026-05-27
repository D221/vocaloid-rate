from datetime import datetime, timedelta, timezone
from math import exp
from statistics import median
from typing import List, Optional

from sqlalchemy import and_, desc, distinct, func, nullslast, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, contains_eager, joinedload
from sqlalchemy.sql.expression import exists

from app import models, schemas
from app.auth import get_password_hash


def get_track_by_link(db: Session, link: str):
    return db.query(models.Track).filter(models.Track.link == link).first()


def _sync_track_relationships(db: Session, db_track: models.Track):
    """Syncs many-to-many relationships for a track based on its producer/voicebank strings."""
    # Sync Producers
    if db_track.producer:
        p_en = [p.strip() for p in db_track.producer.split(",")]
        p_jp = (
            [p.strip() for p in db_track.producer_jp.split(",")]
            if db_track.producer_jp
            else []
        )

        producers = []
        for i, name in enumerate(p_en):
            if not name:
                continue
            producer = (
                db.query(models.Producer).filter(models.Producer.name == name).first()
            )
            if not producer:
                name_jp = p_jp[i] if i < len(p_jp) else None
                producer = models.Producer(name=name, name_jp=name_jp)
                db.add(producer)
                db.flush()
            producers.append(producer)
        db_track.producers = producers

    # Sync Voicebanks
    if db_track.voicebank:
        v_en = [v.strip() for v in db_track.voicebank.split(",")]
        v_jp = (
            [v.strip() for v in db_track.voicebank_jp.split(",")]
            if db_track.voicebank_jp
            else []
        )

        voicebanks = []
        for i, name in enumerate(v_en):
            if not name:
                continue
            voicebank = (
                db.query(models.Voicebank).filter(models.Voicebank.name == name).first()
            )
            if not voicebank:
                name_jp = v_jp[i] if i < len(v_jp) else None
                voicebank = models.Voicebank(name=name, name_jp=name_jp)
                db.add(voicebank)
                db.flush()
            voicebanks.append(voicebank)
        db_track.voicebanks = voicebanks


def create_track(db: Session, track: dict):
    db_track = models.Track(**track)
    db.add(db_track)
    db.flush()
    _sync_track_relationships(db, db_track)
    db.commit()
    db.refresh(db_track)
    return db_track


def update_track(db: Session, db_track: models.Track, track: dict):
    for key, value in track.items():
        setattr(db_track, key, value)
    _sync_track_relationships(db, db_track)
    db.commit()
    db.refresh(db_track)
    return db_track


def get_tracks(
    db: Session,
    user_id: Optional[int] = None,
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
    locale: str = "en",
) -> List[models.Track]:
    # Optimized subquery for checking if track is in ANY of the current user's playlists
    playlist_exists = (
        exists()
        .where(models.PlaylistTrack.track_id == models.Track.id)
        .where(models.Playlist.id == models.PlaylistTrack.playlist_id)
        .where(models.Playlist.user_id == user_id)
    )

    query = db.query(
        models.Track,
        playlist_exists.label("is_in_playlist"),
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

    # Always outerjoin the current user's rating so we can display it and sort by it
    # without redundant queries (N+1 problem) or incorrect cross-user results.
    query = query.outerjoin(
        models.Rating,
        and_(
            models.Rating.track_id == models.Track.id, models.Rating.user_id == user_id
        ),
    ).options(contains_eager(models.Track.ratings))

    if exact_rating_filter is not None:
        query = query.filter(models.Rating.rating == exact_rating_filter)
    elif rated_filter == "rated":
        query = query.filter(models.Rating.id.isnot(None))
    elif rated_filter == "unrated":
        query = query.filter(models.Rating.id.is_(None))

    if producer_filter:
        search_term = f"%{producer_filter}%"
        if locale == "ja":
            query = query.filter(
                or_(
                    models.Track.producer.ilike(search_term),
                    models.Track.producer_jp.ilike(search_term),
                )
            )
        else:
            query = query.filter(models.Track.producer.ilike(search_term))
    if voicebank_filter:
        search_term = f"%{voicebank_filter}%"
        if locale == "ja":
            query = query.filter(
                or_(
                    models.Track.voicebank.ilike(search_term),
                    models.Track.voicebank_jp.ilike(search_term),
                )
            )
        else:
            query = query.filter(models.Track.voicebank.ilike(search_term))

    if sort_by:
        sort_column = getattr(models.Track, sort_by, None)
        if sort_column:
            order_expression = (
                sort_column.desc() if sort_dir == "desc" else sort_column.asc()
            )
            query = query.order_by(order_expression)
        elif sort_by == "rating":
            rating_column = models.Rating.rating
            if sort_dir == "desc":
                query = query.order_by(nullslast(rating_column.desc()))
            else:
                query = query.order_by(nullslast(rating_column.asc()))
    else:
        if rank_filter == "unranked":
            query = query.order_by(models.Track.published_date.desc())
        else:
            query = query.order_by(models.Track.rank.asc())

    results = query.offset(skip).limit(limit).all()

    tracks_with_flag = []
    for track, is_in_playlist in results:
        track.is_in_playlist = is_in_playlist
        tracks_with_flag.append(track)

    return tracks_with_flag


def get_tracks_count(
    db: Session,
    user_id: Optional[int] = None,
    rated_filter: Optional[str] = None,
    title_filter: Optional[str] = None,
    producer_filter: Optional[str] = None,
    voicebank_filter: Optional[str] = None,
    rank_filter: str = "ranked",
    exact_rating_filter: Optional[int] = None,
    locale: str = "en",
) -> int:
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

    # Apply the same rating filters as get_tracks for consistent counting
    if exact_rating_filter is not None or rated_filter in ["rated", "unrated"]:
        query = query.outerjoin(
            models.Rating,
            and_(
                models.Rating.track_id == models.Track.id,
                models.Rating.user_id == user_id,
            ),
        )

        if exact_rating_filter is not None:
            query = query.filter(models.Rating.rating == exact_rating_filter)
        elif rated_filter == "rated":
            query = query.filter(models.Rating.id.isnot(None))
        elif rated_filter == "unrated":
            query = query.filter(models.Rating.id.is_(None))

    if producer_filter:
        search_term = f"%{producer_filter}%"
        if locale == "ja":
            query = query.filter(
                or_(
                    models.Track.producer.ilike(search_term),
                    models.Track.producer_jp.ilike(search_term),
                )
            )
        else:
            query = query.filter(models.Track.producer.ilike(search_term))
    if voicebank_filter:
        search_term = f"%{voicebank_filter}%"
        if locale == "ja":
            query = query.filter(
                or_(
                    models.Track.voicebank.ilike(search_term),
                    models.Track.voicebank_jp.ilike(search_term),
                )
            )
        else:
            query = query.filter(models.Track.voicebank.ilike(search_term))

    result = query.scalar()
    return int(result or 0)


def get_recently_added_tracks(
    db: Session,
    skip: int = 0,
    limit: int = 300,
    title_filter: Optional[str] = None,
    producer_filter: Optional[str] = None,
    voicebank_filter: Optional[str] = None,
    locale: str = "en",
):
    query = db.query(models.Track)

    # Filter for tracks published within the last month
    one_month_ago = datetime.now() - timedelta(days=30)
    query = query.filter(models.Track.published_date >= one_month_ago)

    if title_filter:
        search_term = f"%{title_filter}%"
        query = query.filter(
            or_(
                models.Track.title.ilike(search_term),
                models.Track.title_jp.ilike(search_term),
            )
        )
    if producer_filter:
        search_term = f"%{producer_filter}%"
        if locale == "ja":
            query = query.filter(
                or_(
                    models.Track.producer.ilike(search_term),
                    models.Track.producer_jp.ilike(search_term),
                )
            )
        else:
            query = query.filter(models.Track.producer.ilike(search_term))
    if voicebank_filter:
        search_term = f"%{voicebank_filter}%"
        if locale == "ja":
            query = query.filter(
                or_(
                    models.Track.voicebank.ilike(search_term),
                    models.Track.voicebank_jp.ilike(search_term),
                )
            )
        else:
            query = query.filter(models.Track.voicebank.ilike(search_term))

    query = query.order_by(models.Track.published_date.desc())

    return query.offset(skip).limit(limit).all()


def create_rating(
    db: Session, track_id: int, user_id: int, rating: float, notes: Optional[str] = None
):
    if rating < 1 or rating > 10:
        raise ValueError("Rating must be between 1 and 10.")

    db_rating = (
        db.query(models.Rating)
        .filter(
            models.Rating.track_id == track_id, models.Rating.user_id == user_id
        )  # Filter by user_id
        .first()
    )
    if db_rating:
        db_rating.rating = rating
        db_rating.notes = notes
    else:
        db_rating = models.Rating(
            track_id=track_id, user_id=user_id, rating=rating
        )  # Store user_id
        db.add(db_rating)
    try:
        db.commit()
    except IntegrityError:
        # Handle rare race condition where duplicate row is created concurrently.
        db.rollback()
        db_rating = (
            db.query(models.Rating)
            .filter(
                models.Rating.track_id == track_id, models.Rating.user_id == user_id
            )
            .first()
        )
        if db_rating:
            db_rating.rating = rating
            db_rating.notes = notes
            db.commit()
    db.refresh(db_rating)
    return db_rating


def delete_rating(db: Session, track_id: int, user_id: int):
    db_rating = (
        db.query(models.Rating)
        .filter(
            models.Rating.track_id == track_id, models.Rating.user_id == user_id
        )  # Filter by user_id
        .first()
    )
    if db_rating:
        db.delete(db_rating)
        db.commit()


def get_rating_statistics(db: Session, user_id: int, locale: str = "en"):
    all_ratings_query = (
        db.query(models.Rating.rating).filter(models.Rating.user_id == user_id).all()
    )
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
    global_avg_rating = sum(all_ratings_values) / total_ratings
    MINIMUM_RATINGS_FOR_FAVORITE = 3

    def get_top_entities(
        model_class, junction_table, entity_id_col, name_attr, name_jp_attr
    ):
        name_col = getattr(model_class, name_jp_attr if locale == "ja" else name_attr)

        query = (
            db.query(
                name_col.label("name"),
                func.avg(models.Rating.rating).label("avg_rating"),
                func.count(models.Rating.rating).label("count"),
            )
            .join(junction_table, entity_id_col == model_class.id)
            .join(models.Rating, models.Rating.track_id == junction_table.c.track_id)
            .filter(models.Rating.user_id == user_id)
            .group_by(model_class.id, name_col)
            .having(func.count(models.Rating.rating) >= MINIMUM_RATINGS_FOR_FAVORITE)
        )

        results = query.all()
        scored = []
        for row in results:
            v = row.count
            R = row.avg_rating
            score = ((v * R) + (MINIMUM_RATINGS_FOR_FAVORITE * global_avg_rating)) / (
                v + MINIMUM_RATINGS_FOR_FAVORITE
            )
            scored.append(
                {
                    "name": row.name,
                    "avg_rating": round(float(R), 2),
                    "score": float(score),
                }
            )
        return sorted(scored, key=lambda x: x["score"], reverse=True)[:10]

    top_producers = get_top_entities(
        models.Producer,
        models.track_producers,
        models.track_producers.c.producer_id,
        "name",
        "name_jp",
    )
    top_voicebanks = get_top_entities(
        models.Voicebank,
        models.track_voicebanks,
        models.track_voicebanks.c.voicebank_id,
        "name",
        "name_jp",
    )

    median_rating = median(all_ratings_values)

    distribution_query = (
        db.query(models.Rating.rating, func.count(models.Rating.rating).label("count"))
        .filter(models.Rating.user_id == user_id)
        .group_by(models.Rating.rating)
        .order_by(desc(models.Rating.rating))
        .all()
    )
    rating_distribution = {rating: count for rating, count in distribution_query}

    return {
        "total_ratings": total_ratings,
        "average_rating": round(global_avg_rating, 2),
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


def get_playlists(db: Session, user_id: int) -> list[models.Playlist]:
    """Gets a list of all playlists for a specific user."""
    return (
        db.query(models.Playlist)
        .filter(models.Playlist.user_id == user_id)
        .order_by(models.Playlist.name)
        .all()
    )


def create_playlist(
    db: Session, user_id: int, playlist: schemas.PlaylistCreate
) -> models.Playlist:
    """Creates a new playlist."""
    db_playlist = models.Playlist(
        user_id=user_id,
        name=playlist.name,
        description=playlist.description,
        is_public=playlist.is_public,
    )
    db.add(db_playlist)
    db.commit()
    db.refresh(db_playlist)
    return db_playlist


def delete_playlist(db: Session, playlist_id: int, user_id: int) -> bool:
    """Deletes a playlist by its ID."""
    db_playlist = (
        db.query(models.Playlist).filter_by(id=playlist_id, user_id=user_id).first()
    )
    if db_playlist:
        db.delete(db_playlist)
        db.commit()
        return True
    return False


def update_playlist(
    db: Session,
    playlist_id: int,
    user_id: int,
    name: str,
    description: Optional[str],
    is_public: bool = True,
) -> Optional[models.Playlist]:
    """Updates a playlist's name and description."""
    db_playlist = (
        db.query(models.Playlist).filter_by(id=playlist_id, user_id=user_id).first()
    )
    if db_playlist:
        db_playlist.name = name
        db_playlist.description = description
        db_playlist.is_public = is_public
        db.commit()
        db.refresh(db_playlist)
    return db_playlist


def add_track_to_playlist(
    db: Session, playlist_id: int, track_id: int, user_id: int
) -> Optional[models.Playlist]:
    """Adds a track to the end of a playlist."""
    db_playlist = (
        db.query(models.Playlist).filter_by(id=playlist_id, user_id=user_id).first()
    )
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


def remove_track_from_playlist(
    db: Session, playlist_id: int, track_id: int, user_id: int
):
    """Removes a track from a playlist and re-orders the remaining tracks."""
    # First, get the playlist to ensure it belongs to the user
    db_playlist = (
        db.query(models.Playlist).filter_by(id=playlist_id, user_id=user_id).first()
    )
    if not db_playlist:
        return  # Playlist not found or not owned by user

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


def reorder_playlist(db: Session, playlist_id: int, track_ids: list[int], user_id: int):
    """Re-orders an entire playlist based on a new list of track IDs."""
    # First, get the playlist to ensure it belongs to the user
    db_playlist = (
        db.query(models.Playlist).filter_by(id=playlist_id, user_id=user_id).first()
    )
    if not db_playlist:
        return  # Playlist not found or not owned by user

    # This is an efficient way to update all positions at once
    for index, track_id in enumerate(track_ids):
        db.query(models.PlaylistTrack).filter_by(
            playlist_id=playlist_id, track_id=track_id
        ).update({"position": index})
    db.commit()


def export_playlists(db: Session, user_id: int) -> list[dict]:
    """Fetches all playlists for a specific user and formats them for JSON export."""
    playlists_to_export = []
    all_playlists = (
        db.query(models.Playlist)
        .filter(models.Playlist.user_id == user_id)  # Filter by user_id
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
                "is_public": playlist.is_public,
                "tracks": track_links,
            }
        )
    return playlists_to_export


def export_single_playlist(
    db: Session, playlist_id: int, user_id: int
) -> Optional[dict]:
    """Fetches a single playlist for a specific user and formats it for JSON export."""
    playlist = (
        db.query(models.Playlist)
        .filter_by(id=playlist_id, user_id=user_id)  # Filter by user_id
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
        "is_public": playlist.is_public,
        "tracks": track_links,
    }


def import_playlists(db: Session, user_id: int, data: list[dict]) -> tuple[int, int]:
    """Imports playlists for a specific user from a list of dictionaries, merging with existing data."""
    created_count = 0
    updated_count = 0

    for playlist_data in data:
        playlist_name = playlist_data.get("name")
        if not playlist_name:
            continue

        # Find existing playlist by name and user_id or create a new one
        db_playlist = (
            db.query(models.Playlist)
            .filter_by(name=playlist_name, user_id=user_id)
            .first()
        )
        if not db_playlist:
            db_playlist = models.Playlist(
                user_id=user_id,  # Store user_id
                name=playlist_name,
                description=playlist_data.get("description"),
                is_public=playlist_data.get("is_public", True),
            )
            db.add(db_playlist)
            created_count += 1
        else:
            db_playlist.description = playlist_data.get("description")
            db_playlist.is_public = playlist_data.get(
                "is_public", db_playlist.is_public
            )
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


def get_track_playlist_membership(db: Session, track_id: int, user_id: int) -> dict:
    """Checks which playlists a track belongs to for a specific user."""

    # 1. Get IDs of playlists the track is in for the current user.
    member_playlist_ids_query = (
        db.query(models.PlaylistTrack.playlist_id)
        .join(models.Playlist)
        .filter(
            models.PlaylistTrack.track_id == track_id,
            models.Playlist.user_id == user_id,
        )
    )
    member_playlist_ids = {id for (id,) in member_playlist_ids_query}

    # 2. Get all playlists for the current user.
    all_playlists = (
        db.query(models.Playlist).filter(models.Playlist.user_id == user_id).all()
    )

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


def _calculate_snapshot(all_track_ids: List[int], limit: str) -> List[dict]:
    """Helper to calculate page numbers for a list of track IDs."""
    limit_val = len(all_track_ids)
    if limit.isdigit() and int(limit) > 0:
        limit_val = int(limit)

    snapshot = []
    if limit_val > 0:
        for i, track_id in enumerate(all_track_ids):
            page_num = (i // limit_val) + 1
            snapshot.append({"id": str(track_id), "page": page_num})
    return snapshot


def get_playlist_snapshot(
    db: Session,
    user_id: Optional[int] = None,
    limit: str = "all",
    rated_filter: Optional[str] = None,
    title_filter: Optional[str] = None,
    producer_filter: Optional[str] = None,
    voicebank_filter: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_dir: str = "asc",
    rank_filter: str = "ranked",
    exact_rating_filter: Optional[int] = None,
    locale: str = "en",
) -> list[dict]:
    """
    Gets a sorted list of all track IDs matching the filters,
    annotated with the page number they would appear on.
    """
    # --- 1. Build the exact same query as get_tracks, but only select the ID ---
    query = db.query(models.Track.id)

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
    if exact_rating_filter is not None:
        query = query.join(models.Rating).filter(
            models.Rating.rating == exact_rating_filter,
            models.Rating.user_id == user_id,
        )
        rating_join_applied = True
    elif rated_filter == "rated":
        query = query.join(models.Rating).filter(models.Rating.user_id == user_id)
        rating_join_applied = True
    elif rated_filter == "unrated":
        user_ratings = select(models.Rating.track_id).where(
            models.Rating.user_id == user_id
        )
        query = query.filter(models.Track.id.notin_(user_ratings))
        rating_join_applied = False

    if producer_filter:
        search_term = f"%{producer_filter}%"
        if locale == "ja":
            query = query.filter(
                or_(
                    models.Track.producer.ilike(search_term),
                    models.Track.producer_jp.ilike(search_term),
                )
            )
        else:
            query = query.filter(models.Track.producer.ilike(search_term))
    if voicebank_filter:
        search_term = f"%{voicebank_filter}%"
        if locale == "ja":
            query = query.filter(
                or_(
                    models.Track.voicebank.ilike(search_term),
                    models.Track.voicebank_jp.ilike(search_term),
                )
            )
        else:
            query = query.filter(models.Track.voicebank.ilike(search_term))

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
        if rank_filter == "unranked":
            query = query.order_by(models.Track.published_date.desc())
        else:
            query = query.order_by(models.Track.rank.asc())

    # --- 2. Execute the query to get ALL matching track IDs in order ---
    all_track_ids_tuples = query.all()
    all_track_ids = [id_tuple[0] for id_tuple in all_track_ids_tuples]

    return _calculate_snapshot(all_track_ids, limit)


def get_playlist_tracks_filtered(
    db: Session,
    playlist_id: int,
    user_id: int,
    skip: int = 0,
    limit: int = 1000,
    title_filter: Optional[str] = None,
    producer_filter: Optional[str] = None,
    voicebank_filter: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_dir: str = "asc",
    locale: str = "en",
):
    query = (
        db.query(models.Track)
        .join(models.PlaylistTrack)
        .join(models.Playlist)
        .filter(models.PlaylistTrack.playlist_id == playlist_id)
        .filter(models.Playlist.user_id == user_id)
        .outerjoin(
            models.Rating,
            and_(
                models.Rating.track_id == models.Track.id,
                models.Rating.user_id == user_id,
            ),
        )
        .options(contains_eager(models.Track.ratings))
    )

    if title_filter:
        search_term = f"%{title_filter}%"
        query = query.filter(
            or_(
                models.Track.title.ilike(search_term),
                models.Track.title_jp.ilike(search_term),
            )
        )
    if producer_filter:
        search_term = f"%{producer_filter}%"
        if locale == "ja":
            query = query.filter(
                or_(
                    models.Track.producer.ilike(search_term),
                    models.Track.producer_jp.ilike(search_term),
                )
            )
        else:
            query = query.filter(models.Track.producer.ilike(search_term))
    if voicebank_filter:
        search_term = f"%{voicebank_filter}%"
        if locale == "ja":
            query = query.filter(
                or_(
                    models.Track.voicebank.ilike(search_term),
                    models.Track.voicebank_jp.ilike(search_term),
                )
            )
        else:
            query = query.filter(models.Track.voicebank.ilike(search_term))

    if sort_by:
        sort_column = getattr(models.Track, sort_by, None)
        if sort_column:
            order_expression = (
                sort_column.desc() if sort_dir == "desc" else sort_column.asc()
            )
            query = query.order_by(order_expression)
    else:
        # Default sort for playlists is their manually set position
        query = query.order_by(models.PlaylistTrack.position.asc())

    tracks = query.offset(skip).limit(limit).all()
    for track in tracks:
        track.is_in_playlist = True
    return tracks


def get_playlist_tracks_count(
    db: Session,
    playlist_id: int,
    user_id: int,
    title_filter: Optional[str] = None,
    producer_filter: Optional[str] = None,
    voicebank_filter: Optional[str] = None,
    locale: str = "en",
):
    query = (
        db.query(func.count(distinct(models.Track.id)))
        .join(models.PlaylistTrack)
        .join(models.Playlist)
        .filter(models.PlaylistTrack.playlist_id == playlist_id)
        .filter(models.Playlist.user_id == user_id)
    )

    if title_filter:
        search_term = f"%{title_filter}%"
        query = query.filter(
            or_(
                models.Track.title.ilike(search_term),
                models.Track.title_jp.ilike(search_term),
            )
        )
    if producer_filter:
        search_term = f"%{producer_filter}%"
        if locale == "ja":
            query = query.filter(
                or_(
                    models.Track.producer.ilike(search_term),
                    models.Track.producer_jp.ilike(search_term),
                )
            )
        else:
            query = query.filter(models.Track.producer.ilike(search_term))
    if voicebank_filter:
        search_term = f"%{voicebank_filter}%"
        if locale == "ja":
            query = query.filter(
                or_(
                    models.Track.voicebank.ilike(search_term),
                    models.Track.voicebank_jp.ilike(search_term),
                )
            )
        else:
            query = query.filter(models.Track.voicebank.ilike(search_term))

    return query.scalar()


def get_playlist_snapshot_for_playlist(
    db: Session,
    playlist_id: int,
    user_id: int,
    limit: str = "all",
    title_filter: Optional[str] = None,
    producer_filter: Optional[str] = None,
    voicebank_filter: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_dir: str = "asc",
    locale: str = "en",
) -> list[dict]:
    """
    Gets a sorted list of all track IDs for a specific playlist,
    annotated with the page number they would appear on.
    """
    # --- 1. Build the query, starting with the playlist join ---
    query = (
        db.query(models.Track.id)
        .join(models.PlaylistTrack)
        .join(models.Playlist)
        .filter(
            models.PlaylistTrack.playlist_id == playlist_id,
            models.Playlist.user_id == user_id,
        )
    )
    # --- 2. Apply filters ---
    if title_filter:
        search_term = f"%{title_filter}%"
        query = query.filter(
            or_(
                models.Track.title.ilike(search_term),
                models.Track.title_jp.ilike(search_term),
            )
        )
    if producer_filter:
        search_term = f"%{producer_filter}%"
        if locale == "ja":
            query = query.filter(
                or_(
                    models.Track.producer.ilike(search_term),
                    models.Track.producer_jp.ilike(search_term),
                )
            )
        else:
            query = query.filter(models.Track.producer.ilike(search_term))
    if voicebank_filter:
        search_term = f"%{voicebank_filter}%"
        if locale == "ja":
            query = query.filter(
                or_(
                    models.Track.voicebank.ilike(search_term),
                    models.Track.voicebank_jp.ilike(search_term),
                )
            )
        else:
            query = query.filter(models.Track.voicebank.ilike(search_term))

    # --- 3. Apply sorting ---
    if sort_by:
        sort_column = getattr(models.Track, sort_by, None)
        if sort_column:
            order_expression = (
                sort_column.desc() if sort_dir == "desc" else sort_column.asc()
            )
            query = query.order_by(order_expression)
    else:
        # Default sort for playlists is their manually set position
        query = query.order_by(models.PlaylistTrack.position.asc())

    all_track_ids_tuples = query.all()
    all_track_ids = [id_tuple[0] for id_tuple in all_track_ids_tuples]

    return _calculate_snapshot(all_track_ids, limit)


def get_recently_added_snapshot(
    db: Session,
    limit: str = "all",
    title_filter: Optional[str] = None,
    producer_filter: Optional[str] = None,
    voicebank_filter: Optional[str] = None,
    locale: str = "en",
) -> list[dict]:
    """
    Gets a sorted list of all track IDs for recently added tracks,
    annotated with the page number they would appear on.
    """
    query = db.query(models.Track.id)

    # Filter for tracks published within the last month
    one_month_ago = datetime.now() - timedelta(days=30)
    query = query.filter(models.Track.published_date >= one_month_ago)

    if title_filter:
        search_term = f"%{title_filter}%"
        query = query.filter(
            or_(
                models.Track.title.ilike(search_term),
                models.Track.title_jp.ilike(search_term),
            )
        )
    if producer_filter:
        search_term = f"%{producer_filter}%"
        if locale == "ja":
            query = query.filter(
                or_(
                    models.Track.producer.ilike(search_term),
                    models.Track.producer_jp.ilike(search_term),
                )
            )
        else:
            query = query.filter(models.Track.producer.ilike(search_term))
    if voicebank_filter:
        search_term = f"%{voicebank_filter}%"
        if locale == "ja":
            query = query.filter(
                or_(
                    models.Track.voicebank.ilike(search_term),
                    models.Track.voicebank_jp.ilike(search_term),
                )
            )
        else:
            query = query.filter(models.Track.voicebank.ilike(search_term))

    # Always sort by published_date descending for recently added
    query = query.order_by(models.Track.published_date.desc())

    all_track_ids_tuples = query.all()
    all_track_ids = [id_tuple[0] for id_tuple in all_track_ids_tuples]

    return _calculate_snapshot(all_track_ids, limit)


def get_recommended_tracks(
    db: Session,
    user_id: int,
    locale: str = "en",
    limit: int = 25,
    recent_bias: str = "off",
) -> List[models.Track]:
    """
    Generates track recommendations based on user's rated producers and voicebanks.
    Producers have 3x the weight of voicebanks.
    """

    MINIMUM_SCORE_THRESHOLD = 0.3
    bias_weights = {"off": 0.0, "light": 0.35, "strong": 0.75}
    recency_weight = bias_weights.get(recent_bias, 0.0)
    now_utc = datetime.now(timezone.utc)

    # 1. Get average ratings for producers and voicebanks from the normalized tables
    def get_avg_ratings(model_class, junction_table, entity_id_col):
        results = (
            db.query(model_class.id, func.avg(models.Rating.rating).label("avg_rating"))
            .join(junction_table, entity_id_col == model_class.id)
            .join(models.Rating, models.Rating.track_id == junction_table.c.track_id)
            .filter(models.Rating.user_id == user_id)
            .group_by(model_class.id)
            .all()
        )
        return {row.id: float(row.avg_rating) for row in results}

    producer_avg_ratings = get_avg_ratings(
        models.Producer, models.track_producers, models.track_producers.c.producer_id
    )
    voicebank_avg_ratings = get_avg_ratings(
        models.Voicebank,
        models.track_voicebanks,
        models.track_voicebanks.c.voicebank_id,
    )

    all_ratings_query = (
        db.query(models.Rating.rating).filter(models.Rating.user_id == user_id).all()
    )
    if not all_ratings_query:
        return []

    all_ratings_values = [r for (r,) in all_ratings_query]
    global_avg_rating = sum(all_ratings_values) / len(all_ratings_values)

    # 2. Get unrated tracks with their producers and voicebanks
    unrated_tracks = (
        db.query(models.Track)
        .options(
            joinedload(models.Track.producers), joinedload(models.Track.voicebanks)
        )
        .filter(
            ~exists().where(
                and_(
                    models.Rating.track_id == models.Track.id,
                    models.Rating.user_id == user_id,
                )
            )
        )
        .all()
    )

    # 3. Calculate recommendation score for each unrated track
    track_scores = []
    producer_weight = 3
    voicebank_weight = 1

    for track in unrated_tracks:
        score = 0.0

        # Score from producers
        p_scores = [
            producer_avg_ratings[p.id] - global_avg_rating
            for p in track.producers
            if p.id in producer_avg_ratings
        ]
        if p_scores:
            score += producer_weight * (sum(p_scores) / len(p_scores))

        # Score from voicebanks
        v_scores = [
            voicebank_avg_ratings[v.id] - global_avg_rating
            for v in track.voicebanks
            if v.id in voicebank_avg_ratings
        ]
        if v_scores:
            score += voicebank_weight * (sum(v_scores) / len(v_scores))

        if recency_weight > 0 and track.published_date:
            published_dt = track.published_date
            if published_dt.tzinfo is None:
                published_dt = published_dt.replace(tzinfo=timezone.utc)
            age_days = max((now_utc - published_dt).days, 0)
            recency_score = exp(-age_days / 730)
            score += recency_weight * recency_score

        if score > MINIMUM_SCORE_THRESHOLD:
            track_scores.append((track, score))

    track_scores.sort(key=lambda x: x[1], reverse=True)
    return [track for track, _ in track_scores[:limit]]


# User CRUD operations
def get_user(db: Session, user_id: int) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.id == user_id).first()


def get_user_by_email(db: Session, email: str) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.email == email).first()


def create_user(db: Session, user: schemas.UserCreate) -> models.User:
    hashed_password = get_password_hash(user.password)
    db_user = models.User(email=user.email, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def get_users(db: Session) -> list[models.User]:
    """Gets a list of all users."""
    return db.query(models.User).all()


def delete_user(db: Session, user_id: int) -> bool:
    """Deletes a user by ID."""
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if db_user:
        db.delete(db_user)
        db.commit()
        return True
    return False


def update_user_admin_status(
    db: Session, user_id: int, is_admin: bool
) -> Optional[models.User]:
    """Sets the admin status of a user."""
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if db_user:
        db_user.is_admin = is_admin
        db.commit()
        db.refresh(db_user)
    return db_user
