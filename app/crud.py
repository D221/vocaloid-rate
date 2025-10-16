from collections import defaultdict
from statistics import median
from typing import Optional

from sqlalchemy import desc, distinct, func, nullslast, or_
from sqlalchemy.orm import Session

from app import models


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
    query = db.query(models.Track)

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

    return query.offset(skip).limit(limit).all()


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
