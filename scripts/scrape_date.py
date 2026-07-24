#!/usr/bin/env python3
"""Manual historical scraper - scrape specific date and populate DB."""

import sys

sys.path.insert(0, ".")

from datetime import datetime
from app.scraper import _scrape_single_page
from app import crud, models
from app.database import SessionLocal

date = sys.argv[1] if len(sys.argv) > 1 else "2026-07-23"
print(f"Scraping {date} (all 6 pages)...")

db = SessionLocal()
all_tracks = []

for page in range(1, 7):
    print(f"  Page {page}...", end="")
    tracks = _scrape_single_page(page, date=date)
    if tracks:
        print(f" {len(tracks)} tracks")
        all_tracks.extend(tracks)
    else:
        print(" empty")
        break

print(f"\nTotal: {len(all_tracks)} tracks")

# Update database
for t in all_tracks:
    existing = crud.get_track_by_link(db, t["link"])
    if existing:
        crud.update_track(db, existing, t)
    else:
        crud.create_track(db, t)

# Save to rank history
hist_date = datetime.strptime(date, "%Y-%m-%d")
for t in all_tracks:
    track = crud.get_track_by_link(db, t["link"])
    if track:
        db.add(
            models.RankHistory(track_id=track.id, rank=t["rank"], recorded_at=hist_date)
        )

db.commit()
db.close()
print(f"✓ Database updated with {date} data")
