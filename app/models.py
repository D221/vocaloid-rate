import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Track(Base):
    __tablename__ = "tracks"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String, index=True)
    producer: Mapped[str] = mapped_column(String, index=True)
    voicebank: Mapped[str] = mapped_column(String, index=True)
    published_date: Mapped[datetime.datetime] = mapped_column(DateTime)
    link: Mapped[str] = mapped_column(String, unique=True)
    title_jp: Mapped[str | None] = mapped_column(String, nullable=True)
    producer_jp: Mapped[str | None] = mapped_column(String, nullable=True)
    voicebank_jp: Mapped[str | None] = mapped_column(String, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String, nullable=True)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)

    ratings: Mapped[list["Rating"]] = relationship("Rating", back_populates="track")

    def to_dict(self):
        """Returns a dictionary representation of the track for JSON serialization."""
        return {
            "id": str(self.id),  # Ensure ID is a string for JS consistency
            "title": self.title,
            "producer": self.producer,
            "voicebank": self.voicebank,
            "link": self.link,
            "title_jp": self.title_jp,
            "producer_jp": self.producer_jp,
            "voicebank_jp": self.voicebank_jp,
            "imageUrl": self.image_url,
        }


class Rating(Base):
    __tablename__ = "ratings"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False) # New
    rating: Mapped[float] = mapped_column(Float, index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.now(datetime.timezone.utc)
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.now(datetime.timezone.utc),
        onupdate=datetime.datetime.now(datetime.timezone.utc),
    )
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    track: Mapped["Track"] = relationship("Track", back_populates="ratings")
    user: Mapped["User"] = relationship("User") # New


class UpdateLog(Base):
    __tablename__ = "update_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.now(datetime.timezone.utc)
    )


class PlaylistTrack(Base):
    __tablename__ = "playlist_track_association"

    playlist_id: Mapped[int] = mapped_column(
        ForeignKey("playlists.id"), primary_key=True
    )
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id"), primary_key=True)
    position: Mapped[int] = mapped_column(Integer)

    track: Mapped["Track"] = relationship()


class Playlist(Base):
    __tablename__ = "playlists"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False) # New
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(500))
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.now(datetime.timezone.utc)
    )

    playlist_tracks: Mapped[list["PlaylistTrack"]] = relationship(
        order_by=PlaylistTrack.position, cascade="all, delete-orphan"
    )
    user: Mapped["User"] = relationship("User") # New


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False) # New admin flag


