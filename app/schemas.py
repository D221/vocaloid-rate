import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class RatingBase(BaseModel):
    rating: float


class Rating(RatingBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    track_id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime


class Track(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    producer: str
    voicebank: str
    published_date: datetime.datetime
    link: str
    image_url: Optional[str] = None
    rank: Optional[int] = None
    ratings: List[Rating] = Field(default_factory=list)


class PlaylistBase(BaseModel):
    name: str
    description: Optional[str] = None


class PlaylistCreate(PlaylistBase):
    pass


class PlaylistSimple(PlaylistBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class PlaylistTrackDetail(Track):
    position: int


class Playlist(PlaylistBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime.datetime
    tracks: List[PlaylistTrackDetail] = Field(default_factory=list)


class UserBase(BaseModel):
    email: str


class UserCreate(UserBase):
    password: str


class User(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[str] = None
