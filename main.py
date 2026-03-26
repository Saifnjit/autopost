"""
LinkedIn Auto-Poster Bot
Fetches trending AI/tech news → generates caption → viral check → finds image → posts to LinkedIn.
Runs automatically 3x per day.
"""

import os
import schedule
import time
import logging
from trending_fetcher import fetch_candidate_articles
from content_generator import generate_post
from image_fetcher import fetch_best_image
from linkedin_poster import post_to_linkedin
from viral_checker import check_viral_potential
from post_history import is_duplicate, record_post, load_history, clean_old_entries
from topic_filter import is_on_topic
from config import POST_TIMES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler(),
    ],
)

IMAGE_PATH = "post_image.jpg"
MAX_BATCHES = 15  # Hard cap — prevents infinite loops


def run_post_cycle():
    """Fetch → generate → viral check → image → post."""
    logging.info("Starting post cycle...")

    history = clean_old_entries(load_history())
    tried_titles = set()
    image_path = None
    article = None
    post_text = ""
    batch_num = 0
    found = False

    while batch_num < MAX_BATCHES:
        batch_num += 1
        logging.info(f"--- Batch {batch_num}/{MAX_BATCHES} (tried {len(tried_titles)} articles) ---")

        candidates = fetch_candidate_articles(batch_size=10, exclude_titles=tried_titles)
        if not candidates:
            logging.warning("No fresh articles found. Waiting 15s...")
            time.sleep(15)
            continue

        for i, candidate in enumerate(candidates):
            tried_titles.add(candidate["title"])
            logging.info(f"  [{i+1}/{len(candidates)}] {candidate['title'][:70]} ({candidate.get('upvotes', 0)} upvotes)")

            # Duplicate check
            if is_duplicate(candidate, history):
                logging.warning("    Already posted — skipping")
                continue

            # Topic relevance
            if not is_on_topic(candidate):
                logging.warning("    Off-topic — skipping")
                continue

            # Generate caption
            try:
                content = generate_post(candidate)
            except Exception as e:
                logging.warning(f"    Caption failed: {e}")
                continue

            post_text = content.get("caption", "").strip()
            if not post_text:
                logging.warning("    Empty caption — skipping")
                continue

            # LinkedIn hard limit is 3000 chars
            if len(post_text) > 3000:
                post_text = post_text[:2997] + "..."

            # Viral check
            try:
                viral = check_viral_potential(post_text)
            except Exception as e:
                logging.warning(f"    Viral check error: {e}")
                continue

            score = viral.get("score", 0)
            logging.info(f"    Viral: {score}/10 — {viral.get('reason', '')}")

            if not viral.get("passes"):
                logging.warning(f"    Score {score}/10 — below threshold")
                continue

            # Image search — required, skip article if no confident match found
            logging.info("    Passed viral check. Searching for matching image...")
            image_path = fetch_best_image(candidate, post_text, IMAGE_PATH)
            if not image_path:
                logging.warning("    No confident image found — skipping article")
                continue

            article = candidate
            found = True
            logging.info("    Image matched. Ready to post.")
            break

        if found:
            break

        logging.info("Batch exhausted — fetching new batch...")
        time.sleep(5)

    if not found or article is None:
        logging.error(f"Could not find a suitable post after {MAX_BATCHES} batches. Skipping this cycle.")
        if image_path and os.path.exists(image_path):
            os.remove(image_path)
        return

    # Post to LinkedIn
    success = post_to_linkedin(post_text, image_path=image_path)

    # Always clean up image
    if image_path and os.path.exists(image_path):
        try:
            os.remove(image_path)
        except Exception:
            pass

    if success:
        try:
            record_post(article, post_text)
        except Exception as e:
            logging.error(f"Failed to record post to history: {e}")
        logging.info("Post cycle complete.")
    else:
        logging.error("Post failed.")


def main():
    logging.info("LinkedIn Bot started.")
    logging.info(f"Scheduled post times: {POST_TIMES}")

    for t in POST_TIMES:
        schedule.every().day.at(t).do(run_post_cycle)
        logging.info(f"Scheduled post at {t}")

    logging.info("Running initial post now...")
    run_post_cycle()

    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()
