import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# Junction tables for many-to-many relationships
track_producers = Table(
    "track_producers",
    Base.metadata,
    Column("track_id", ForeignKey("tracks.id"), primary_key=True),
    Column("producer_id", ForeignKey("producers.id"), primary_key=True),
)

track_voicebanks = Table(
    "track_voicebanks",
    Base.metadata,
    Column("track_id", ForeignKey("tracks.id"), primary_key=True),
    Column("voicebank_id", ForeignKey("voicebanks.id"), primary_key=True),
)


class Track(Base):
    __tablename__ = "tracks"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String, index=True)
    producer: Mapped[str] = mapped_column(String, index=True)
    voicebank: Mapped[str] = mapped_column(String, index=True)
    published_date: Mapped[datetime.datetime] = mapped_column(DateTime, index=True)
    link: Mapped[str] = mapped_column(String, unique=True)
    title_jp: Mapped[str | None] = mapped_column(String, nullable=True)
    producer_jp: Mapped[str | None] = mapped_column(String, nullable=True)
    voicebank_jp: Mapped[str | None] = mapped_column(String, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String, nullable=True)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)

    ratings: Mapped[list["Rating"]] = relationship("Rating", back_populates="track")
    lyrics: Mapped[list["Lyric"]] = relationship(
        "Lyric", back_populates="track", cascade="all, delete-orphan"
    )

    producers: Mapped[list["Producer"]] = relationship(
        "Producer", secondary=track_producers, back_populates="tracks"
    )
    voicebanks: Mapped[list["Voicebank"]] = relationship(
        "Voicebank", secondary=track_voicebanks, back_populates="tracks"
    )

    def to_dict(self) -> dict:
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
            "rank": self.rank,
            "rank_change": getattr(self, "rank_change", 0),
        }


class Rating(Base):
    __tablename__ = "ratings"
    __table_args__ = (
        UniqueConstraint("track_id", "user_id", name="uq_ratings_track_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)  # New
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
    user: Mapped["User"] = relationship("User")  # New


class UpdateLog(Base):
    __tablename__ = "update_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.now(datetime.timezone.utc)
    )


class RankHistory(Base):
    __tablename__ = "rank_history"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id"), index=True)
    rank: Mapped[int] = mapped_column(Integer, index=True)
    recorded_at: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        default=datetime.datetime.now(datetime.timezone.utc),
        index=True,
    )

    track: Mapped["Track"] = relationship("Track")


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
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)  # New
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(500))
    is_public: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.now(datetime.timezone.utc)
    )

    playlist_tracks: Mapped[list["PlaylistTrack"]] = relationship(
        order_by=PlaylistTrack.position, cascade="all, delete-orphan"
    )
    user: Mapped["User"] = relationship("User")  # New


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)  # New admin flag
    username: Mapped[str | None] = mapped_column(
        String, unique=True, index=True, nullable=True
    )
    is_profile_public: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )


class Lyric(Base):
    __tablename__ = "lyrics"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id"), index=True)
    language: Mapped[str] = mapped_column(String)  # e.g. "English", "Japanese"
    translation_type: Mapped[str] = mapped_column(
        String
    )  # e.g. "Original", "Translation"
    source: Mapped[str | None] = mapped_column(String, nullable=True)  # e.g. "VocaDB"
    url: Mapped[str | None] = mapped_column(String, nullable=True)
    content: Mapped[str] = mapped_column(String)  # The HTML or text content

    track: Mapped["Track"] = relationship("Track", back_populates="lyrics")


class Producer(Base):
    __tablename__ = "producers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, index=True, unique=True)
    name_jp: Mapped[str | None] = mapped_column(String, nullable=True)

    tracks: Mapped[list["Track"]] = relationship(
        "Track", secondary=track_producers, back_populates="producers"
    )


class Voicebank(Base):
    __tablename__ = "voicebanks"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, index=True, unique=True)
    name_jp: Mapped[str | None] = mapped_column(String, nullable=True)

    tracks: Mapped[list["Track"]] = relationship(
        "Track", secondary=track_voicebanks, back_populates="voicebanks"
    )
