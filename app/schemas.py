import datetime
from typing import List, Optional

from pydantic import BaseModel


class RatingBase(BaseModel):
    rating: float


class Rating(RatingBase):
    id: int
    track_id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True


class Track(BaseModel):
    id: int
    title: str
    producer: str
    voicebank: str
    published_date: datetime.datetime
    link: str
    image_url: Optional[str] = None
    rank: Optional[int] = None
    ratings: List[Rating] = []

    class Config:
        from_attributes = True


class PlaylistBase(BaseModel):
    name: str
    description: Optional[str] = None


class PlaylistCreate(PlaylistBase):
    pass


class PlaylistSimple(PlaylistBase):
    id: int

    class Config:
        from_attributes = True


class PlaylistTrackDetail(Track):
    position: int


class Playlist(PlaylistBase):
    id: int
    created_at: datetime.datetime
    tracks: List[PlaylistTrackDetail] = []

    class Config:
        from_attributes = True
