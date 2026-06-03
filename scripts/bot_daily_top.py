import argparse
import os
from datetime import datetime, timedelta, timezone

import httpx2
from atproto import Client, client_utils
from atproto import models as at_models
from dotenv import load_dotenv
from sqlalchemy import desc

from app import models as db_models
from app.database import SessionLocal

load_dotenv()

# PRIVACY: Use environment variables for sensitive URLs and credentials
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
BASE_URL = os.environ.get("BASE_URL", "https://vocaloid-rate.vercel.app")

# Bluesky Credentials
BSKY_HANDLE = os.environ.get("BSKY_HANDLE")
BSKY_PASSWORD = os.environ.get("BSKY_PASSWORD")


def get_rank_diff_icon(old_rank, new_rank):
    if old_rank is None:
        return "🆕"
    if new_rank < old_rank:
        return "📈"
    if new_rank > old_rank:
        return "📉"
    return "➖"


def get_relative_time(dt):
    """Returns a 'days ago' style string."""
    if not dt:
        return "unknown date"

    now = datetime.now(timezone.utc)

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    diff = now - dt
    days = diff.days

    if days == 0:
        return "today"
    if days == 1:
        return "yesterday"

    return f"{days} days ago"


def get_track_rich_data(track, old_rank):
    """Formats track data for rich webhook display, preferring English."""
    diff_icon = get_rank_diff_icon(old_rank, track.rank)

    rank_text = f"#{track.rank}"
    if old_rank is not None and old_rank != track.rank:
        diff = old_rank - track.rank
        rank_text += f" ({'+' if diff > 0 else ''}{diff})"

    title = track.title or track.title_jp
    producer = track.producer or track.producer_jp

    return {
        "id": track.id,
        "rank": track.rank,
        "rank_text": rank_text,
        "diff_icon": diff_icon,
        "title": title,
        "producer": producer,
        "app_link": f"{BASE_URL}/#track-{track.id}",
        "image_url": track.image_url,
        "voicebank": track.voicebank,
        "uploaded": get_relative_time(track.published_date),
    }


def send_to_discord(rich_top_10):
    """Sends a polished Top 10 report to Discord."""
    if WEBHOOK_URL is None:
        print("[DISCORD] DISCORD_WEBHOOK_URL missing. Skipping.")
        return

    embeds = []
    today_str = datetime.now().strftime("%Y-%m-%d")

    medals = ["🥇", "🥈", "🥉"]

    for i in range(min(3, len(rich_top_10))):
        track = rich_top_10[i]
        embeds.append(
            {
                "title": f"{medals[i]} {track['rank_text']}: {track['title']}",
                "description": (
                    f"👤 **Producer:** {track['producer']}\n"
                    f"🎤 **Voicebank:** {track['voicebank']}\n"
                    f"📅 **Uploaded:** {track['uploaded']}"
                ),
                "url": track["app_link"],
                "thumbnail": {"url": track["image_url"]},
                "color": 0x00D4FF if i == 0 else 0xCCCCCC,
            }
        )

    list_description = ""
    for i in range(3, min(10, len(rich_top_10))):
        track = rich_top_10[i]
        list_description += (
            f"{track['diff_icon']} **{track['rank_text']}** "
            f"[{track['title']}]({track['app_link']})\n"
        )
        list_description += f"└ *{track['producer']} • {track['uploaded']}*\n\n"

    if list_description:
        embeds.append(
            {
                "description": list_description,
                "color": 0x7289DA,
                "footer": {"text": f"Vocaloid Rate • {today_str}"},
            }
        )

    payload = {
        "content": f"📅 **Daily Chart Update: {today_str}**",
        "embeds": embeds,
        "username": "Vocaloid Rate Bot",
        "avatar_url": f"{BASE_URL}/static/android-chrome-512x512.png",
    }

    with httpx2.Client() as client:
        response = client.post(WEBHOOK_URL, json=payload)
        response.raise_for_status()


def post_to_bsky(rich_top_10):
    """Posts a threaded update to Bluesky with images and proper facets."""
    if not all([BSKY_HANDLE, BSKY_PASSWORD]):
        print("[BSKY] Credentials missing. Skipping.")
        return

    try:
        client = Client()
        client.login(BSKY_HANDLE, BSKY_PASSWORD)
        print("[BSKY] Login successful.")

        today_str = datetime.now().strftime("%Y-%m-%d")

        # --- 1. Prepare images for Top 3 ---
        images = []

        with httpx2.Client() as http:
            for i in range(min(3, len(rich_top_10))):
                track = rich_top_10[i]

                image_url = track.get("image_url")
                if not image_url:
                    print(f"[BSKY] No image URL for {track['title']}. Skipping image.")
                    continue

                try:
                    img_resp = http.get(image_url, follow_redirects=True)
                    img_resp.raise_for_status()

                    upload = client.upload_blob(img_resp.content)

                    images.append(
                        at_models.AppBskyEmbedImages.Image(
                            alt=(
                                f"Rank {track['rank']}: {track['title']} "
                                f"by {track['producer']} featuring {track['voicebank']}"
                            ),
                            image=upload.blob,
                        )
                    )

                    print(f"[BSKY] Uploaded image for {track['title']}.")

                except Exception as e:
                    print(f"[BSKY] Failed to process image for {track['title']}: {e}")

        # --- 2. Main post: compact Top 3 with details ---
        text_builder = client_utils.TextBuilder()
        text_builder.text(f"🏆 Vocaloid Rate Top 10 ({today_str})\n\n")

        medals = ["🥇", "🥈", "🥉"]

        for i in range(min(3, len(rich_top_10))):
            track = rich_top_10[i]

            text_builder.text(f"{medals[i]} #{track['rank']} ")
            text_builder.link(track["title"], track["app_link"])
            text_builder.text("\n")
            text_builder.text(
                f"└ {track['producer']} • {track['voicebank']} • {track['uploaded']}\n"
            )

        text_builder.text("\nFull charts: ")
        text_builder.link("vocaloid-rate.vercel.app", BASE_URL)

        embed = None
        if images:
            embed = at_models.AppBskyEmbedImages.Main(images=images)

        parent_post = client.send_post(text=text_builder, embed=embed)
        print(f"[BSKY] Main post sent: {parent_post.uri}")

        # --- 3. Threaded reply: positions 4-10 with details ---
        if len(rich_top_10) > 3:
            root_ref = at_models.create_strong_ref(parent_post)
            previous_ref = root_ref

            reply_groups = [
                (3, 6, "📋 Positions 4-6:\n\n"),
                (6, 10, "📋 Positions 7-10:\n\n"),
            ]

            for start, end, heading in reply_groups:
                if len(rich_top_10) <= start:
                    continue

                thread_builder = client_utils.TextBuilder()
                thread_builder.text(heading)

                for i in range(start, min(end, len(rich_top_10))):
                    track = rich_top_10[i]

                    thread_builder.text(f"{track['diff_icon']} #{track['rank']} ")
                    thread_builder.link(track["title"], track["app_link"])
                    thread_builder.text("\n")
                    thread_builder.text(
                        f"└ {track['producer']} • {track['voicebank']} • {track['uploaded']}\n"
                    )

                reply_post = client.send_post(
                    text=thread_builder,
                    reply_to=at_models.AppBskyFeedPost.ReplyRef(
                        root=root_ref,
                        parent=previous_ref,
                    ),
                )

                previous_ref = at_models.create_strong_ref(reply_post)
                print(
                    f"[BSKY] Threaded list sent: positions {start + 1}-{min(end, len(rich_top_10))}."
                )

    except Exception as e:
        print(f"[BSKY] ERROR: {e}")


def run_rank_analysis(args):
    db = SessionLocal()

    try:
        print(f"--- Analyzing Charts ({datetime.now().strftime('%Y-%m-%d %H:%M')}) ---")

        yesterday = datetime.now(timezone.utc) - timedelta(days=1)

        last_snapshot = (
            db.query(db_models.RankHistory.recorded_at)
            .filter(db_models.RankHistory.recorded_at <= yesterday)
            .order_by(desc(db_models.RankHistory.recorded_at))
            .first()
        )

        old_ranks = {}

        if last_snapshot:
            snapshot_time = last_snapshot[0]
            print(f"Comparing against snapshot from {snapshot_time}")

            old_ranks = {
                h.track_id: h.rank
                for h in db.query(db_models.RankHistory)
                .filter(db_models.RankHistory.recorded_at == snapshot_time)
                .all()
            }

        top_10_objs = (
            db.query(db_models.Track)
            .filter(db_models.Track.rank.isnot(None))
            .order_by(db_models.Track.rank)
            .limit(10)
            .all()
        )

        rich_top_10 = [get_track_rich_data(t, old_ranks.get(t.id)) for t in top_10_objs]

        if rich_top_10:
            # --- Discord ---
            if args.all or args.discord:
                print("Processing Discord update...")
                send_to_discord(rich_top_10)

            # --- Bluesky ---
            if (args.all or args.bsky) and BSKY_HANDLE:
                print("Processing Bluesky update...")
                post_to_bsky(rich_top_10)

            print("Done.")

    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Vocaloid Rate Daily Bot")

    parser.add_argument(
        "--all",
        action="store_true",
        help="Post to all configured platforms",
    )

    parser.add_argument(
        "--discord",
        action="store_true",
        help="Post to Discord",
    )

    parser.add_argument(
        "--bsky",
        action="store_true",
        help="Post to Bluesky",
    )

    args = parser.parse_args()

    if not any([args.discord, args.bsky]):
        args.all = True

    run_rank_analysis(args)


if __name__ == "__main__":
    main()
