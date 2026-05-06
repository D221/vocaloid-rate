import json
from datetime import datetime
from typing import Optional

from babel.support import Translations
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
)
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app import crud, models
from app.auth import get_current_user
from app.constants import get_resource_base_path
from app.dependencies import get_db, get_locale, get_translations
from app.utils.uploads import read_upload_with_size_limit
from app.utils.view_helpers import (
    build_limit_offset,
    build_tracks_partial_response,
)

router = APIRouter()


@router.get("/_/get_tracks", response_class=JSONResponse, tags=["Data"])
def get_tracks_partial(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    page: int = 1,
    limit: str = "all",
    rated_filter: Optional[str] = None,
    title_filter: Optional[str] = None,
    producer_filter: Optional[str] = None,
    voicebank_filter: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_dir: str = "asc",
    rank_filter: str = "ranked",
    exact_rating_filter: Optional[int] = None,
    translations: Translations = Depends(get_translations),
):
    locale = translations.info()["language"]
    if rated_filter == "rated":
        rank_filter = "all"
        if not sort_by:
            sort_by = "rating"
            sort_dir = "desc"

    total_tracks = crud.get_tracks_count(
        db,
        user_id=current_user.id,
        rated_filter=rated_filter,
        title_filter=title_filter,
        producer_filter=producer_filter,
        voicebank_filter=voicebank_filter,
        rank_filter=rank_filter,
        exact_rating_filter=exact_rating_filter,
        locale=locale,
    )

    limit_val, total_pages, skip = build_limit_offset(limit, total_tracks, page)

    tracks = crud.get_tracks(
        db,
        user_id=current_user.id,
        skip=skip,
        limit=limit_val,
        rated_filter=rated_filter,
        title_filter=title_filter,
        producer_filter=producer_filter,
        voicebank_filter=voicebank_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        rank_filter=rank_filter,
        exact_rating_filter=exact_rating_filter,
        locale=locale,
    )

    return build_tracks_partial_response(
        request=request,
        translations=translations,
        tracks=tracks,
        locale=locale,
        pagination={
            "page": page,
            "limit": limit,
            "total_pages": total_pages,
            "total_tracks": total_tracks,
        },
    )


@router.get(
    "/api/playlist/{playlist_id}/get_tracks", response_class=JSONResponse, tags=["Data"]
)
def get_playlist_tracks_partial(
    playlist_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    page: int = 1,
    limit: str = "all",
    title_filter: Optional[str] = None,
    producer_filter: Optional[str] = None,
    voicebank_filter: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_dir: str = "asc",
    translations: Translations = Depends(get_translations),
):
    db_playlist = crud.get_playlist(db, playlist_id)
    if not db_playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    if db_playlist.user_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="Not authorized to view this playlist"
        )

    locale = translations.info()["language"]
    total_tracks = crud.get_playlist_tracks_count(
        db,
        playlist_id=playlist_id,
        user_id=current_user.id,
        title_filter=title_filter,
        producer_filter=producer_filter,
        voicebank_filter=voicebank_filter,
        locale=locale,
    )

    limit_val, total_pages, skip = build_limit_offset(limit, total_tracks, page)

    tracks = crud.get_playlist_tracks_filtered(
        db,
        playlist_id=playlist_id,
        user_id=current_user.id,
        skip=skip,
        limit=limit_val,
        title_filter=title_filter,
        producer_filter=producer_filter,
        voicebank_filter=voicebank_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        locale=locale,
    )

    return build_tracks_partial_response(
        request=request,
        translations=translations,
        tracks=tracks,
        locale=locale,
        pagination={
            "page": page,
            "limit": limit,
            "total_pages": total_pages,
            "total_tracks": total_tracks,
        },
    )


@router.get(
    "/_/get_recently_added_tracks_partial", response_class=JSONResponse, tags=["Data"]
)
def get_recently_added_tracks_partial(
    request: Request,
    db: Session = Depends(get_db),
    title_filter: Optional[str] = None,
    producer_filter: Optional[str] = None,
    voicebank_filter: Optional[str] = None,
    translations: Translations = Depends(get_translations),
):
    locale = translations.info()["language"]
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

    return build_tracks_partial_response(
        request=request,
        translations=translations,
        tracks=tracks,
        locale=locale,
        pagination={
            "page": 1,
            "total_pages": 1,
            "total_tracks": total_tracks,
        },
    )


@router.get("/api/backup/ratings", tags=["Backup & Restore"])
def backup_ratings(
    db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    results = (
        db.query(models.Track, models.Rating)
        .join(models.Rating)
        .filter(models.Rating.user_id == current_user.id)
        .all()
    )
    backup_data = []
    for track, rating_obj in results:
        backup_data.append(
            {
                "link": track.link,
                "title": track.title,
                "producer": track.producer,
                "voicebank": track.voicebank,
                "published_date": track.published_date.isoformat(),
                "title_jp": track.title_jp,
                "producer_jp": track.producer_jp,
                "voicebank_jp": track.voicebank_jp,
                "image_url": track.image_url,
                "rating": rating_obj.rating,
                "notes": rating_obj.notes,
            }
        )
    return backup_data


@router.post("/api/restore/ratings", tags=["Backup & Restore"])
async def restore_ratings(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    filename = getattr(file, "filename", "") or ""
    if not filename.lower().endswith(".json"):
        raise HTTPException(
            status_code=400, detail="Invalid file type. Please upload a .json file."
        )

    contents = await read_upload_with_size_limit(file)
    try:
        backup_data = json.loads(contents)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON file.")

    created_count = 0
    updated_count = 0

    for item in backup_data:
        track = crud.get_track_by_link(db, item["link"])
        if not track:
            track_data = {
                "link": item["link"],
                "title": item["title"],
                "producer": item["producer"],
                "voicebank": item["voicebank"],
                "published_date": datetime.fromisoformat(item["published_date"]),
                "title_jp": item.get("title_jp"),
                "producer_jp": item.get("producer_jp"),
                "voicebank_jp": item.get("voicebank_jp"),
                "image_url": item.get("image_url"),
                "rank": None,
            }
            track = crud.create_track(db, track_data)
            created_count += 1
        else:
            updated_count += 1

        if item.get("rating") is not None:
            try:
                crud.create_rating(
                    db,
                    track.id,
                    user_id=current_user.id,
                    rating=item["rating"],
                    notes=item.get("notes"),
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc))

    return {"created": created_count, "updated": updated_count}


@router.get("/api/translations", tags=["Internal"])
def get_js_translations(locale: str = Depends(get_locale)):
    js_translations_path = get_resource_base_path() / "locales" / "js_translations.json"
    with open(js_translations_path, "r", encoding="utf-8") as file_handle:
        all_translations = json.load(file_handle)
    return JSONResponse(
        content=all_translations.get(locale, all_translations["en"]),
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.post("/rate/{track_id}/delete", tags=["Ratings"])
def delete_rating_endpoint(
    track_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    crud.delete_rating(db, track_id=track_id, user_id=current_user.id)
    return Response(status_code=204)


@router.post("/rate/{track_id}", tags=["Ratings"])
def rate_track(
    track_id: int,
    rating: int = Form(..., ge=1, le=10),
    notes: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    crud.create_rating(
        db, track_id=track_id, user_id=current_user.id, rating=rating, notes=notes
    )
    return Response(status_code=204)


@router.get("/api/tracks/{track_id}/playlist-status", tags=["Data"])
def get_track_playlist_status(
    track_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return crud.get_track_playlist_membership(
        db, track_id=track_id, user_id=current_user.id
    )


@router.get("/api/playlist-snapshot", response_class=JSONResponse, tags=["Data"])
def get_playlist_snapshot_endpoint(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    limit: str = "all",
    rated_filter: Optional[str] = None,
    title_filter: Optional[str] = None,
    producer_filter: Optional[str] = None,
    voicebank_filter: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_dir: str = "asc",
    rank_filter: str = "ranked",
    exact_rating_filter: Optional[int] = None,
    translations: Translations = Depends(get_translations),
):
    locale = translations.info()["language"]
    if rated_filter == "rated":
        rank_filter = "all"
        if not sort_by:
            sort_by = "rating"
            sort_dir = "desc"

    return crud.get_playlist_snapshot(
        db=db,
        user_id=current_user.id,
        limit=limit,
        rated_filter=rated_filter,
        title_filter=title_filter,
        producer_filter=producer_filter,
        voicebank_filter=voicebank_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        rank_filter=rank_filter,
        exact_rating_filter=exact_rating_filter,
        locale=locale,
    )


@router.get(
    "/api/playlist/{playlist_id}/playlist-snapshot",
    response_class=JSONResponse,
    tags=["Data"],
)
def get_playlist_snapshot_for_playlist_endpoint(
    playlist_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
    limit: str = "all",
    title_filter: Optional[str] = None,
    producer_filter: Optional[str] = None,
    voicebank_filter: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_dir: str = "asc",
    translations: Translations = Depends(get_translations),
):
    locale = translations.info()["language"]
    return crud.get_playlist_snapshot_for_playlist(
        db=db,
        playlist_id=playlist_id,
        user_id=current_user.id,
        limit=limit,
        title_filter=title_filter,
        producer_filter=producer_filter,
        voicebank_filter=voicebank_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
        locale=locale,
    )


@router.get("/api/recently-added-snapshot", response_class=JSONResponse, tags=["Data"])
def get_recently_added_snapshot_endpoint(
    db: Session = Depends(get_db),
    title_filter: Optional[str] = None,
    producer_filter: Optional[str] = None,
    voicebank_filter: Optional[str] = None,
    translations: Translations = Depends(get_translations),
):
    locale = translations.info()["language"]
    return crud.get_recently_added_snapshot(
        db=db,
        limit="10000",
        title_filter=title_filter,
        producer_filter=producer_filter,
        voicebank_filter=voicebank_filter,
        locale=locale,
    )
