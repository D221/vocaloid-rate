from statistics import median
from typing import Optional

from sqlalchemy import desc, func, nullslast, or_
from sqlalchemy.orm import Session

from . import models


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
):
    query = db.query(models.Track)

    if rank_filter == "ranked":
        query = query.filter(models.Track.rank.isnot(None))
    elif rank_filter == "unranked":
        query = query.filter(models.Track.rank.is_(None))

    rating_join_applied = False  # Keep track of whether we've joined

    if rated_filter == "rated":
        query = query.join(models.Rating)
        rating_join_applied = True
    elif rated_filter == "unrated":
        # For unrated, we must use an outer join
        query = query.outerjoin(models.Rating).filter(models.Rating.id == None)
        rating_join_applied = True

    if title_filter:
        search_term = f"%{title_filter}%"
        query = query.filter(
            or_(
                models.Track.title.ilike(search_term),
                models.Track.title_jp.ilike(search_term),
            )
        )

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
            # Only apply the join if it hasn't been applied already
            if not rating_join_applied:
                query = query.outerjoin(models.Rating)

            rating_column = models.Rating.rating
            if sort_dir == "desc":
                query = query.order_by(nullslast(rating_column.desc()))
            else:
                query = query.order_by(nullslast(rating_column.asc()))
    else:
        query = query.order_by(models.Track.rank.asc())

    # We must use .distinct() when joining to avoid duplicate tracks in the results
    if rating_join_applied and rated_filter == "rated":
        query = query.distinct()

    return query.offset(skip).limit(limit).all()


def create_rating(db: Session, track_id: int, rating: float):
    db_rating = (
        db.query(models.Rating).filter(models.Rating.track_id == track_id).first()
    )
    if db_rating:
        db_rating.rating = rating
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
        return {
            "total_ratings": 0,
            "average_rating": 0,
            "median_rating": 0,
            "favorite_producer": {"name": "N/A", "avg_rating": 0},
            "favorite_voicebank": {"name": "N/A", "avg_rating": 0},
            "rating_distribution": {},
        }

    all_ratings = [r for (r,) in all_ratings_query]
    total_ratings = len(all_ratings)

    # C: The average rating across ALL tracks. This is our baseline.
    global_avg_rating = round(sum(all_ratings) / total_ratings, 2)

    # m: The minimum number of ratings needed to be considered a "favorite".
    # This prevents a producer with one 10/10 track from being #1.
    MINIMUM_RATINGS_FOR_FAVORITE = 3

    # --- Find Favorite Producer with Weighted Score ---

    # v: Number of ratings for the producer
    producer_v = func.count(models.Track.id)
    # R: Average rating for the producer
    producer_R = func.avg(models.Rating.rating)

    # The Bayesian average formula
    producer_weighted_score = (
        (producer_v * producer_R) + (MINIMUM_RATINGS_FOR_FAVORITE * global_avg_rating)
    ) / (producer_v + MINIMUM_RATINGS_FOR_FAVORITE)

    fav_producer_query = (
        db.query(
            models.Track.producer,
            func.avg(models.Rating.rating).label("avg_rating"),
            producer_weighted_score.label("weighted_score"),
        )
        .join(models.Rating)
        .group_by(models.Track.producer)
        .having(func.count(models.Track.id) >= MINIMUM_RATINGS_FOR_FAVORITE)
        .order_by(desc("weighted_score"))
        .first()
    )

    # --- Find Favorite Voicebank with Weighted Score (same logic) ---
    voicebank_v = func.count(models.Track.id)
    voicebank_R = func.avg(models.Rating.rating)
    voicebank_weighted_score = (
        (voicebank_v * voicebank_R) + (MINIMUM_RATINGS_FOR_FAVORITE * global_avg_rating)
    ) / (voicebank_v + MINIMUM_RATINGS_FOR_FAVORITE)

    fav_voicebank_query = (
        db.query(
            models.Track.voicebank,
            func.avg(models.Rating.rating).label("avg_rating"),
            voicebank_weighted_score.label("weighted_score"),
        )
        .join(models.Rating)
        .group_by(models.Track.voicebank)
        .having(func.count(models.Track.id) >= MINIMUM_RATINGS_FOR_FAVORITE)
        .order_by(desc("weighted_score"))
        .first()
    )

    median_rating = median(all_ratings)

    distribution_query = (
        db.query(models.Rating.rating, func.count(models.Rating.rating).label("count"))
        .group_by(models.Rating.rating)
        .order_by(desc(models.Rating.rating))
        .all()
    )

    rating_distribution = {rating: count for rating, count in distribution_query}

    return {
        "total_ratings": total_ratings,
        "average_rating": global_avg_rating,  # Use the already calculated global average
        "median_rating": median_rating,
        "favorite_producer": {
            "name": fav_producer_query[0] if fav_producer_query else "N/A",
            "avg_rating": round(fav_producer_query[1], 2) if fav_producer_query else 0,
        },
        "favorite_voicebank": {
            "name": fav_voicebank_query[0] if fav_voicebank_query else 0,
            "avg_rating": round(fav_voicebank_query[1], 2)
            if fav_voicebank_query
            else 0,
        },
        "rating_distribution": rating_distribution,
    }
