import json
from datetime import datetime, timezone
from typing import Optional

from babel.support import Translations
from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app import models
from app.dependencies import templates


def serialize_tracks(tracks) -> str:
    return json.dumps([track.to_dict() for track in tracks])


def collect_producers_and_voicebanks(
    tracks, locale: str
) -> tuple[list[str], list[str]]:
    producers_flat: list[str] = []
    voicebanks_flat: list[str] = []

    for track in tracks:
        if locale == "ja" and track.producer_jp:
            producers_flat.extend(
                [producer.strip() for producer in track.producer_jp.split(",")]
            )
        else:
            producers_flat.extend(
                [producer.strip() for producer in track.producer.split(",")]
            )

        if locale == "ja" and track.voicebank_jp:
            voicebanks_flat.extend(
                [voicebank.strip() for voicebank in track.voicebank_jp.split(",")]
            )
        else:
            voicebanks_flat.extend(
                [voicebank.strip() for voicebank in track.voicebank.split(",")]
            )

    return sorted(set(producers_flat)), sorted(set(voicebanks_flat))


def get_user_filter_options(
    db: Session, user_id: int, locale: str
) -> tuple[list[str], list[str]]:
    # Query producers and voicebanks directly from their tables for efficiency
    p_name_col = models.Producer.name_jp if locale == "ja" else models.Producer.name
    v_name_col = models.Voicebank.name_jp if locale == "ja" else models.Voicebank.name

    producers = (
        db.query(p_name_col)
        .filter(p_name_col.isnot(None), p_name_col != "")
        .distinct()
        .order_by(p_name_col)
        .all()
    )
    voicebanks = (
        db.query(v_name_col)
        .filter(v_name_col.isnot(None), v_name_col != "")
        .distinct()
        .order_by(v_name_col)
        .all()
    )

    return [p[0] for p in producers], [v[0] for v in voicebanks]


def build_limit_offset(
    limit: str, total_tracks: int, page: int
) -> tuple[int, int, int]:
    limit_val = total_tracks if limit == "all" else int(limit)
    total_pages = (total_tracks + limit_val - 1) // limit_val if limit_val > 0 else 1
    skip = (page - 1) * limit_val
    return limit_val, total_pages, skip


def build_tracks_table_body(
    request: Request,
    translations: Translations,
    tracks,
    locale: str,
    current_user: Optional[models.User] = None,
) -> str:
    # Always ensure current_user is passed correctly
    return templates.get_template("partials/tracks_table_body.html").render(
        {
            "request": request,
            "_": translations.gettext,
            "tracks": tracks,
            "tracks_json": serialize_tracks(tracks),
            "locale": locale,
            "current_user": current_user,
        }
    )


def build_tracks_partial_response(
    request: Request,
    translations: Translations,
    tracks,
    locale: str,
    pagination: dict,
    current_user: Optional[models.User] = None,
) -> JSONResponse:
    return JSONResponse(
        content={
            "table_body_html": build_tracks_table_body(
                request=request,
                translations=translations,
                tracks=tracks,
                locale=locale,
                current_user=current_user,
            ),
            "pagination": pagination,
        }
    )


def time_ago_filter(date: datetime) -> str:
    now = datetime.now(timezone.utc)
    if date.tzinfo is None:
        date = date.replace(tzinfo=timezone.utc)

    diff = now - date
    days = diff.days

    if days == 0:
        return "Today"
    if days < 30:
        return f"{days} day{'s' if days != 1 else ''} ago"
    months = days // 30
    if months < 12:
        return f"{months} month{'s' if months != 1 else ''} ago"
    years = days // 365
    return f"{years} year{'s' if years != 1 else ''} ago"
