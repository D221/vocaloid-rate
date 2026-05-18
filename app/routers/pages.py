from datetime import datetime, timezone
from typing import Optional

from babel.support import Translations
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app import crud, models
from app.auth import get_optional_current_user
from app.constants import VALID_PAGE_LIMITS
from app.dependencies import (
    get_db,
    get_slim_mode,
    get_translations,
    locale_template_response,
)
from app.services.scraping import is_initial_scrape_in_progress
from app.utils.view_helpers import (
    build_limit_offset,
    collect_producers_and_voicebanks,
    get_user_filter_options,
    serialize_tracks,
)

router = APIRouter(tags=["Pages"])


def _main_module():
    from app import main

    return main


def _require_current_user(current_user: Optional[models.User]) -> models.User:
    if current_user is None:
        raise HTTPException(status_code=307, headers={"location": "/login"})
    return current_user


def _get_locale(translations: Translations) -> str:
    return translations.info()["language"]


async def _render_page(
    template_name: str,
    request: Request,
    translations: Translations,
    context: dict,
):
    return await locale_template_response(
        template_name,
        context,
        request=request,
        translations=translations,
    )


@router.get("/rated_tracks")
async def read_rated_tracks(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(get_optional_current_user),
    page: int = 1,
    limit: str = "all",
    title_filter: Optional[str] = None,
    producer_filter: Optional[str] = None,
    voicebank_filter: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_dir: str = "asc",
    exact_rating_filter: Optional[int] = None,
    translations: Translations = Depends(get_translations),
):
    if current_user is None:
        return RedirectResponse(url="/login")
    user = _require_current_user(current_user)

    locale = _get_locale(translations)
    if not sort_by:
        sort_by = "rating"
        sort_dir = "desc"

    filters = {
        "title_filter": title_filter,
        "producer_filter": producer_filter,
        "voicebank_filter": voicebank_filter,
        "exact_rating_filter": exact_rating_filter,
    }

    total_tracks = crud.get_tracks_count(
        db,
        user_id=user.id,
        rated_filter="rated",
        title_filter=title_filter,
        producer_filter=producer_filter,
        voicebank_filter=voicebank_filter,
        exact_rating_filter=exact_rating_filter,
        rank_filter="all",
        locale=locale,
    )

    limit_val, total_pages, skip = build_limit_offset(limit, total_tracks, page)

    tracks = crud.get_tracks(
        db,
        user_id=user.id,
        skip=skip,
        limit=limit_val,
        rated_filter="rated",
        title_filter=title_filter,
        producer_filter=producer_filter,
        voicebank_filter=voicebank_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        exact_rating_filter=exact_rating_filter,
        rank_filter="all",
        locale=locale,
    )

    all_producers, all_voicebanks = get_user_filter_options(db, user.id, locale)
    stats = crud.get_rating_statistics(db, user_id=user.id, locale=locale)

    context = {
        "request": request,
        "_": translations.gettext,
        "tracks": tracks,
        "tracks_json": serialize_tracks(tracks),
        "all_producers": all_producers,
        "all_voicebanks": all_voicebanks,
        "stats": stats,
        "filters": filters,
        "pagination": {
            "page": page,
            "limit": limit,
            "total_pages": total_pages,
            "total_tracks": total_tracks,
        },
    }

    return await _render_page("rated.html", request, translations, context)


@router.get("/robots.txt", response_class=Response)
async def get_robots_txt():
    content = (
        "User-agent: *\n"
        "Allow: /\n"
        "Sitemap: https://vocaloid-rate.vercel.app/sitemap.xml\n"
    )
    return Response(content=content, media_type="text/plain")


@router.get("/playlists")
async def view_playlists_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(get_optional_current_user),
    translations: Translations = Depends(get_translations),
):
    if current_user:
        playlists = crud.get_playlists(db, user_id=current_user.id)
    else:
        # Show all public playlists for guests
        playlists = db.query(models.Playlist).filter(models.Playlist.is_public).all()

    context = {
        "request": request,
        "current_user": current_user,
        "_": translations.gettext,
        "playlists": playlists,
    }
    return await _render_page("playlists.html", request, translations, context)


@router.get("/playlist/{playlist_id}")
async def view_playlist_detail_page(
    playlist_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(get_optional_current_user),
    page: int = 1,
    limit: str = "all",
    title_filter: Optional[str] = None,
    producer_filter: Optional[str] = None,
    voicebank_filter: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_dir: str = "asc",
    translations: Translations = Depends(get_translations),
):
    locale = _get_locale(translations)
    db_playlist = crud.get_playlist(db, playlist_id)
    if not db_playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    # Access control: Owner OR Public
    is_owner = current_user and db_playlist.user_id == current_user.id
    if not db_playlist.is_public and not is_owner:
        raise HTTPException(
            status_code=403, detail="Not authorized to view this playlist"
        )

    filters = {
        "title_filter": title_filter,
        "producer_filter": producer_filter,
        "voicebank_filter": voicebank_filter,
    }

    total_tracks = crud.get_playlist_tracks_count(
        db,
        playlist_id=playlist_id,
        user_id=db_playlist.user_id,
        locale=locale,
        **filters,
    )
    limit_val, total_pages, skip = build_limit_offset(limit, total_tracks, page)

    tracks_in_playlist = crud.get_playlist_tracks_filtered(
        db,
        playlist_id=playlist_id,
        user_id=db_playlist.user_id,
        skip=skip,
        limit=limit_val,
        sort_by=sort_by,
        sort_dir=sort_dir,
        locale=locale,
        **filters,
    )

    all_playlist_tracks = [pt.track for pt in db_playlist.playlist_tracks if pt.track]
    all_producers, all_voicebanks = collect_producers_and_voicebanks(
        all_playlist_tracks, locale
    )

    context = {
        "request": request,
        "current_user": current_user,
        "_": translations.gettext,
        "playlist": db_playlist,
        "tracks": tracks_in_playlist,
        "tracks_json": serialize_tracks(tracks_in_playlist),
        "all_producers": all_producers,
        "all_voicebanks": all_voicebanks,
        "filters": filters,
        "pagination": {
            "page": page,
            "limit": limit,
            "total_pages": total_pages,
            "total_tracks": total_tracks,
        },
    }

    return await _render_page("playlist_view.html", request, translations, context)


@router.get("/playlist/edit/{playlist_id}")
async def edit_playlist_page(
    playlist_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(get_optional_current_user),
    translations: Translations = Depends(get_translations),
):
    user = _require_current_user(current_user)

    db_playlist = crud.get_playlist(db, playlist_id)
    if not db_playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    if db_playlist.user_id != user.id:
        raise HTTPException(
            status_code=403, detail="Not authorized to edit this playlist"
        )

    all_tracks = crud.get_tracks(db, limit=10000, sort_by="title", rank_filter="all")
    context = {
        "request": request,
        "current_user": user,
        "_": translations.gettext,
        "playlist": db_playlist,
        "all_tracks": all_tracks,
        "tracks_json": serialize_tracks(all_tracks),
    }

    return await _render_page("playlist_edit.html", request, translations, context)


@router.get("/options")
async def read_options(
    request: Request,
    current_user: Optional[models.User] = Depends(get_optional_current_user),
    translations: Translations = Depends(get_translations),
):
    context = {
        "request": request,
        "current_user": current_user,
        "_": translations.gettext,
    }
    return await _render_page("options.html", request, translations, context)


@router.get("/login")
async def login_page(
    request: Request,
    current_user: Optional[models.User] = Depends(get_optional_current_user),
    translations: Translations = Depends(get_translations),
):
    if _main_module().is_local_auth_mode() or current_user:
        return RedirectResponse(url="/")

    context = {
        "request": request,
        "current_user": None,
        "_": translations.gettext,
    }
    return await _render_page("login.html", request, translations, context)


@router.get("/register")
async def register_page(
    request: Request,
    current_user: Optional[models.User] = Depends(get_optional_current_user),
    translations: Translations = Depends(get_translations),
):
    if _main_module().is_local_auth_mode() or current_user:
        return RedirectResponse(url="/")

    context = {
        "request": request,
        "current_user": None,
        "_": translations.gettext,
    }
    return await _render_page("register.html", request, translations, context)


@router.get("/")
async def read_root(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(get_optional_current_user),
    page: int = 1,
    limit: Optional[str] = None,
    rated_filter: Optional[str] = None,
    title_filter: Optional[str] = None,
    producer_filter: Optional[str] = None,
    voicebank_filter: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_dir: str = "asc",
    rank_filter: str = "ranked",
    translations: Translations = Depends(get_translations),
    is_slim_mode: bool = Depends(get_slim_mode),
):
    user_id = current_user.id if current_user else None
    locale = _get_locale(translations)
    if is_initial_scrape_in_progress():
        return await _render_page(
            "scraping.html",
            request,
            translations,
            {
                "request": request,
                "current_user": current_user,
                "_": translations.gettext,
            },
        )

    filters = {
        "rated_filter": rated_filter,
        "title_filter": title_filter,
        "producer_filter": producer_filter,
        "voicebank_filter": voicebank_filter,
        "rank_filter": rank_filter,
    }

    cookie_limit = request.cookies.get("default_page_size")
    effective_limit = limit if limit is not None else cookie_limit
    if effective_limit not in VALID_PAGE_LIMITS:
        effective_limit = "all"

    total_tracks = crud.get_tracks_count(
        db,
        user_id=user_id,
        rated_filter=rated_filter,
        title_filter=title_filter,
        producer_filter=producer_filter,
        voicebank_filter=voicebank_filter,
        rank_filter=rank_filter,
        locale=locale,
    )

    limit_val = 10000
    if effective_limit.isdigit():
        limit_val = int(effective_limit)

    total_pages = 1
    if limit_val != 10000:
        total_pages = (total_tracks + limit_val - 1) // limit_val

    skip = (page - 1) * limit_val if limit_val != 10000 else 0

    tracks = crud.get_tracks(
        db,
        user_id=user_id,
        skip=skip,
        limit=limit_val,
        rated_filter=rated_filter,
        title_filter=title_filter,
        producer_filter=producer_filter,
        voicebank_filter=voicebank_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        rank_filter=rank_filter,
        locale=locale,
    )

    # Filter user ID 1 or current user for options
    filter_user_id = user_id if user_id else 1
    all_producers, all_voicebanks = get_user_filter_options(db, filter_user_id, locale)

    last_update = crud.get_last_update_time(db)
    update_age_days = None
    is_db_outdated = False
    if last_update:
        if last_update.updated_at.tzinfo is None:
            last_update.updated_at = last_update.updated_at.replace(tzinfo=timezone.utc)

        update_age = datetime.now(timezone.utc) - last_update.updated_at
        update_age_days = update_age.days
        if update_age.total_seconds() > 24 * 3600:
            is_db_outdated = True

    context = {
        "request": request,
        "current_user": current_user,
        "_": translations.gettext,
        "is_slim_mode": is_slim_mode,
        "tracks": tracks,
        "tracks_json": serialize_tracks(tracks),
        "all_producers": all_producers,
        "all_voicebanks": all_voicebanks,
        "last_update": last_update,
        "is_db_outdated": is_db_outdated,
        "update_age_days": update_age_days,
        "filters": filters,
        "pagination": {
            "page": page,
            "limit": effective_limit,
            "total_pages": total_pages,
            "total_tracks": total_tracks,
        },
    }

    return await _render_page("index.html", request, translations, context)


@router.get("/recently_added")
async def read_recently_added(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(get_optional_current_user),
    title_filter: Optional[str] = None,
    producer_filter: Optional[str] = None,
    voicebank_filter: Optional[str] = None,
    translations: Translations = Depends(get_translations),
):
    user_id = current_user.id if current_user else None
    locale = _get_locale(translations)
    filters = {
        "title_filter": title_filter,
        "producer_filter": producer_filter,
        "voicebank_filter": voicebank_filter,
    }

    tracks = crud.get_recently_added_tracks(
        db,
        skip=0,
        limit=10000,
        title_filter=title_filter,
        producer_filter=producer_filter,
        voicebank_filter=voicebank_filter,
        locale=locale,
    )
    total_tracks = len(tracks)

    filter_user_id = user_id if user_id else 1
    all_producers, all_voicebanks = get_user_filter_options(db, filter_user_id, locale)

    context = {
        "request": request,
        "current_user": current_user,
        "_": translations.gettext,
        "tracks": tracks,
        "tracks_json": serialize_tracks(tracks),
        "all_producers": all_producers,
        "all_voicebanks": all_voicebanks,
        "filters": filters,
        "pagination": {
            "page": 1,
            "total_pages": 1,
            "total_tracks": total_tracks,
        },
        "is_recently_added_page": True,
    }

    return await _render_page("recently_added.html", request, translations, context)


@router.get("/recommendations")
async def read_recommendations(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(get_optional_current_user),
    recent_bias: str = "off",
    translations: Translations = Depends(get_translations),
):
    if current_user is None:
        return RedirectResponse(url="/login")
    user = _require_current_user(current_user)

    recent_bias = recent_bias.lower()
    if recent_bias not in {"off", "light", "strong"}:
        recent_bias = "off"

    locale = _get_locale(translations)
    stats = crud.get_rating_statistics(db, user_id=user.id, locale=locale)
    recommended_tracks = crud.get_recommended_tracks(
        db,
        user_id=user.id,
        locale=locale,
        recent_bias=recent_bias,
    )

    context = {
        "request": request,
        "current_user": user,
        "_": translations.gettext,
        "stats": stats,
        "recommended_tracks": recommended_tracks,
        "tracks_json": serialize_tracks(recommended_tracks),
        "recent_bias": recent_bias,
    }

    return await _render_page("recommendations.html", request, translations, context)


@router.get("/explore")
async def view_explore_page(
    request: Request,
    current_user: Optional[models.User] = Depends(get_optional_current_user),
    translations: Translations = Depends(get_translations),
):
    context = {
        "request": request,
        "current_user": current_user,
        "_": translations.gettext,
    }
    return await _render_page("explore.html", request, translations, context)
async def view_producers_index(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(get_optional_current_user),
    translations: Translations = Depends(get_translations),
):
    producers = db.query(models.Producer).order_by(models.Producer.name).all()
    context = {
        "request": request,
        "current_user": current_user,
        "_": translations.gettext,
        "entities": producers,
        "type": "producer",
    }
    return await _render_page("entity_index.html", request, translations, context)


@router.get("/producer/{producer_name}")
async def view_producer_page(
    producer_name: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(get_optional_current_user),
    translations: Translations = Depends(get_translations),
):
    # Use ilike for case-insensitive lookup
    producer = (
        db.query(models.Producer).filter(models.Producer.name.ilike(producer_name)).first()
    )
    if not producer:
        raise HTTPException(status_code=404, detail="Producer not found")

    context = {
        "request": request,
        "current_user": current_user,
        "_": translations.gettext,
        "entity": producer,
        "type": "producer",
    }
    return await _render_page("entity_view.html", request, translations, context)



@router.get("/voicebanks")
async def view_voicebanks_index(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(get_optional_current_user),
    translations: Translations = Depends(get_translations),
):
    voicebanks = db.query(models.Voicebank).order_by(models.Voicebank.name).all()
    context = {
        "request": request,
        "current_user": current_user,
        "_": translations.gettext,
        "entities": voicebanks,
        "type": "voicebank",
    }
    return await _render_page("entity_index.html", request, translations, context)


@router.get("/voicebank/{name}")
async def view_voicebank_page(
    name: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(get_optional_current_user),
    translations: Translations = Depends(get_translations),
):
    voicebank = (
        db.query(models.Voicebank).filter(models.Voicebank.name.ilike(name)).first()
    )
    if not voicebank:
        raise HTTPException(status_code=404, detail="Voicebank not found")

    context = {
        "request": request,
        "current_user": current_user,
        "_": translations.gettext,
        "entity": voicebank,
        "type": "voicebank",
    }
    return await _render_page("entity_view.html", request, translations, context)
