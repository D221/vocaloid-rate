import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.auth import get_current_user
from app.dependencies import get_db
from app.utils.uploads import read_upload_with_size_limit

router = APIRouter(tags=["Playlists"])


class PlaylistUpdate(BaseModel):
    name: str
    description: Optional[str] = None
    is_public: bool = True


@router.get("/api/playlists", response_model=list[schemas.PlaylistSimple])
def get_user_playlists(
    db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    return crud.get_playlists(db, user_id=current_user.id)


@router.post("/api/playlists", response_model=schemas.PlaylistSimple)
def create_new_playlist(
    playlist: schemas.PlaylistCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return crud.create_playlist(db, user_id=current_user.id, playlist=playlist)


@router.post("/api/playlists/{playlist_id}/tracks/{track_id}")
def add_track_to_a_playlist(
    playlist_id: int,
    track_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    db_playlist = crud.add_track_to_playlist(
        db, playlist_id=playlist_id, track_id=track_id, user_id=current_user.id
    )
    if not db_playlist:
        raise HTTPException(
            status_code=404, detail="Playlist not found or not owned by user"
        )
    return Response(status_code=200, content="Track added successfully")


@router.delete("/api/playlists/{playlist_id}/tracks/{track_id}")
def remove_track_from_a_playlist(
    playlist_id: int,
    track_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    crud.remove_track_from_playlist(
        db, playlist_id=playlist_id, track_id=track_id, user_id=current_user.id
    )
    return Response(status_code=200, content="Track removed successfully")


@router.post("/api/playlists/{playlist_id}/reorder")
def reorder_a_playlist(
    playlist_id: int,
    track_ids: list[int],
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    crud.reorder_playlist(
        db, playlist_id=playlist_id, track_ids=track_ids, user_id=current_user.id
    )
    return Response(status_code=200, content="Playlist reordered successfully")


@router.put("/api/playlists/{playlist_id}", response_model=schemas.PlaylistSimple)
def update_playlist_details(
    playlist_id: int,
    playlist_update: PlaylistUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    db_playlist = crud.update_playlist(
        db,
        playlist_id=playlist_id,
        user_id=current_user.id,
        name=playlist_update.name,
        description=playlist_update.description,
        is_public=playlist_update.is_public,
    )
    if not db_playlist:
        raise HTTPException(
            status_code=404, detail="Playlist not found or not owned by user"
        )
    return db_playlist


@router.get("/api/playlists/export", tags=["Backup & Restore"])
def export_all_playlists(
    db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)
):
    return crud.export_playlists(db, user_id=current_user.id)


@router.post("/api/playlists/import", tags=["Backup & Restore"])
async def import_all_playlists(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not file.filename or not file.filename.lower().endswith(".json"):
        raise HTTPException(status_code=400, detail="Invalid file type. Must be .json")

    contents = await read_upload_with_size_limit(file)
    try:
        data = json.loads(contents)
        if not isinstance(data, list):
            raise HTTPException(
                status_code=400, detail="JSON is not a valid playlists export."
            )

        created, updated = crud.import_playlists(db, user_id=current_user.id, data=data)
        return {"created": created, "updated": updated}
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format.")
    except HTTPException:
        raise
    except Exception:
        logging.error("Playlists import failed", exc_info=True)
        raise HTTPException(
            status_code=500, detail="An internal error occurred while importing."
        )


@router.post("/api/playlists/import-single", tags=["Backup & Restore"])
async def import_single_playlist(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not file.filename or not file.filename.lower().endswith(".json"):
        raise HTTPException(status_code=400, detail="Invalid file type. Must be .json")

    contents = await read_upload_with_size_limit(file)
    try:
        data = json.loads(contents)
        if not isinstance(data, dict) or "name" not in data or "tracks" not in data:
            raise HTTPException(
                status_code=400, detail="JSON is not a valid single playlist export."
            )

        created, updated = crud.import_playlists(
            db, user_id=current_user.id, data=[data]
        )
        status = "created" if created > 0 else "updated"
        return {"status": status, "count": created + updated}

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format.")
    except HTTPException:
        raise
    except Exception:
        logging.error("Playlist import failed", exc_info=True)
        raise HTTPException(
            status_code=500, detail="An internal error occurred while importing."
        )


@router.get("/api/playlists/{playlist_id}/export", tags=["Backup & Restore"])
def export_single_playlist(
    playlist_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    playlist = crud.export_single_playlist(db, playlist_id, user_id=current_user.id)
    if not playlist:
        raise HTTPException(
            status_code=404, detail="Playlist not found or not owned by user"
        )
    return playlist


@router.delete("/api/playlists/{playlist_id}")
def delete_a_playlist(
    playlist_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    success = crud.delete_playlist(db, playlist_id=playlist_id, user_id=current_user.id)
    if not success:
        raise HTTPException(
            status_code=404, detail="Playlist not found or not owned by user"
        )
    return Response(status_code=200, content="Playlist deleted successfully")
