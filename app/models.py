import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Track(Base):
    __tablename__ = "tracks"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String, index=True)
    producer: Mapped[str] = mapped_column(String, index=True)
    voicebank: Mapped[str] = mapped_column(String, index=True)
    published_date: Mapped[datetime.datetime] = mapped_column(DateTime)
    link: Mapped[str] = mapped_column(String, unique=True)
    title_jp: Mapped[str | None] = mapped_column(String, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String, nullable=True)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)

    ratings: Mapped[list["Rating"]] = relationship("Rating", back_populates="track")


class Rating(Base):
    __tablename__ = "ratings"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    track_id: Mapped[int] = mapped_column(ForeignKey("tracks.id"))
    rating: Mapped[float] = mapped_column(Float, index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.now(datetime.timezone.utc)
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        default=datetime.datetime.now(datetime.timezone.utc),
        onupdate=datetime.datetime.now(datetime.timezone.utc),
    )

    track: Mapped["Track"] = relationship("Track", back_populates="ratings")
