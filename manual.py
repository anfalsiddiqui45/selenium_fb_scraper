"""
Facebook Post Collector — Serenity AI
======================================
Collects post text (not comments) from a Facebook group/page/feed,
with automatic crash recovery.

KEY DESIGN DECISION:
Long Selenium sessions scrolling Facebook WILL eventually crash the
Chrome tab — this is a known limitation of infinite-scroll single
page apps, not a bug you can fully code around. Instead of fighting
it, this script:
  1. Saves progress + a resume "cursor" to disk after every post.
  2. Detects a crash immediately.
  3. Automatically relaunches a brand new Chrome process and
     re-navigates to the same URL, then keeps collecting.
  4. Repeats this until TARGET_POSTS is hit or you stop it.

You never lose more than the last unsaved post, and you never have
to manually restart the script — it restarts itself.
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import (
    WebDriverException,
    InvalidSessionIdException,
)
from webdriver_manager.chrome import ChromeDriverManager
import time
import csv
import random
import json
import os
import sys

# ═══════════════════════════════════════════
#  SETTINGS
# ═══════════════════════════════════════════
TARGET_POSTS    = 10000
SCROLL_STEP     = 600
SAVE_FILE_TXT   = "posts_dataset.txt"
SAVE_FILE_CSV   = "posts_dataset.csv"
PROGRESS_FILE   = "progress.json"   # cursor + collected posts

PAUSE_SCROLL_MIN  = 1.6
PAUSE_SCROLL_MAX  = 10.0
PAUSE_BETWEEN_MIN = 1.6
PAUSE_BETWEEN_MAX = 10.0
PAUSE_SEE_MORE    = 0.7

MAX_AUTO_RESTARTS = 200   # safety ceiling so it can't restart forever
# ═══════════════════════════════════════════


def rp(lo, hi):
    t = random.uniform(lo, hi)
    time.sleep(t)
    return t


# ───────────────────────────────────────────
# PROGRESS / CURSOR PERSISTENCE
# ───────────────────────────────────────────
def load_progress():
    """
    Load previous run's data: collected posts + the resume cursor.
    Cursor = fingerprint of the last successfully saved post, used
    only for your own reference (shown on screen). Actual dedup is
    handled by content matching, which is far more reliable on
    Facebook than DOM IDs or scroll position (Facebook's feed order
    can shift between sessions).
    """
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            posts = data.get("collected", [])
            cursor = data.get("last_post_fingerprint", "")
            target_url = data.get("target_url", "")
            print(f"  ↻ Resuming: {len(posts)} posts already collected.")
            if cursor:
                print(f"  ↻ Last saved post started with: \"{cursor[:60]}...\"")
            return posts, target_url
        except Exception as e:
            print(f"  ⚠ Could not read progress file ({e}). Starting fresh.")
    return [], ""


def save_progress(posts, target_url):
    try:
        fingerprint = posts[-1][:80] if posts else ""
        with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "collected": posts,
                    "last_post_fingerprint": fingerprint,
                    "target_url": target_url,
                },
                f, ensure_ascii=False, indent=1
            )
    except Exception:
        pass


def save_posts(posts, target_url):
    with open(SAVE_FILE_TXT, "w", encoding="utf-8") as f:
        for i, p in enumerate(posts, 1):
            f.write(f"--- Post {i} ---\n{p}\n\n")
    with open(SAVE_FILE_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "post_text"])
        for i, p in enumerate(posts, 1):
            w.writerow([i, p])
    save_progress(posts, target_url)


# ───────────────────────────────────────────
# BROWSER LAUNCH / RELAUNCH
# ───────────────────────────────────────────
def launch_browser():
    options = Options()
    # Use an external browser profile directory to avoid saving
    # personal login credentials inside the repository.
    USER_DATA_DIR = os.environ.get("USER_DATA_DIR", "selenium_profile")
    options.add_argument(f"--user-data-dir={USER_DATA_DIR}")
    options.add_argument("--disable-notifications")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--js-flags=--max-old-space-size=4096")
    drv = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )
    return drv


def browser_alive(drv):
    try:
        _ = drv.current_url
        return True
    except Exception:
        return False


# ───────────────────────────────────────────
# SCRAPING HELPERS  (operate on a given driver)
# ───────────────────────────────────────────
def find_post_containers(drv):
    elements = drv.find_elements(By.XPATH, "//*[@data-ad-preview='message']")
    def get_y(el):
        try:
            return el.location['y']
        except Exception:
            return 999999
    elements.sort(key=get_y)
    return elements


def expand_post(drv, container):
    for label in ["See more", "See More", "مزید دیکھیں"]:
        btns = container.find_elements(
            By.XPATH, f".//*[normalize-space(text())='{label}']"
        )
        for btn in btns:
            try:
                drv.execute_script(
                    "arguments[0].scrollIntoView({block:'center'});", btn
                )
                time.sleep(random.uniform(0.2, 0.5))
                drv.execute_script("arguments[0].click();", btn)
                time.sleep(PAUSE_SEE_MORE)
            except Exception:
                pass


def read_text(container):
    try:
        text = container.text.strip()
        return text if len(text) >= 40 else None
    except Exception:
        return None


# ───────────────────────────────────────────
# MAIN
# ───────────────────────────────────────────
collected, saved_url = load_progress()
seen_texts = set(collected)

print("\n========================================")
print("  Facebook Post Collector - Serenity AI")
print("========================================")
print(f"  Target          : {TARGET_POSTS} posts")
print(f"  Auto-restart     : ON (relaunches browser if it crashes)")
print(f"  Resume file       : {PROGRESS_FILE}")
print("========================================")

driver = launch_browser()

if saved_url:
    print(f"\n  Reopening your previous page automatically:\n  {saved_url}")
    try:
        driver.get(saved_url)
    except Exception:
        driver.get("https://www.facebook.com")
    target_url = saved_url
else:
    driver.get("https://www.facebook.com")
    print("\nSteps:")
    print("  1. Log in to Facebook (if not already).")
    print("  2. Open the GROUP / PAGE / SEARCH RESULTS")
    print("     with Urdu mental health posts.")
    print("  3. Make sure you can see the first post.")
    target_url = ""

print()
input("Press ENTER when ready (page is open and posts are visible)...")

# Capture the URL we are actually scraping, for future auto-resume
try:
    target_url = driver.current_url
except Exception:
    pass

seen_ids     = set()
stall_count  = 0
MAX_STALLS   = 8
restarts     = 0

print(f"\nStarting collection...\n")

while len(collected) < TARGET_POSTS and restarts <= MAX_AUTO_RESTARTS:

    crashed_this_segment = False

    try:
        while len(collected) < TARGET_POSTS:

            if not browser_alive(driver):
                raise WebDriverException("Browser session lost")

            try:
                containers = find_post_containers(driver)
            except (WebDriverException, InvalidSessionIdException):
                raise

            new_this_round = 0

            for container in containers:
                if len(collected) >= TARGET_POSTS:
                    break

                try:
                    el_id = container.id
                except Exception:
                    continue
                if el_id in seen_ids:
                    continue
                seen_ids.add(el_id)

                try:
                    driver.execute_script(
                        "arguments[0].scrollIntoView({block:'center'});", container
                    )
                    time.sleep(random.uniform(0.3, 0.6))
                except (WebDriverException, InvalidSessionIdException):
                    raise
                except Exception:
                    continue

                expand_post(driver, container)

                text = read_text(container)
                if not text:
                    continue
                if text in seen_texts:
                    continue

                seen_texts.add(text)
                collected.append(text)
                new_this_round += 1

                save_posts(collected, target_url)

                pause = rp(PAUSE_BETWEEN_MIN, PAUSE_BETWEEN_MAX)
                print(f"  Post {len(collected):>5}/{TARGET_POSTS}  "
                      f"({len(text)} chars)  saved (paused {pause:.1f}s)")

            # Scroll for more
            if len(collected) < TARGET_POSTS:
                try:
                    prev_h = driver.execute_script("return document.body.scrollHeight")
                    driver.execute_script(f"window.scrollBy(0, {SCROLL_STEP});")
                    pause = rp(PAUSE_SCROLL_MIN, PAUSE_SCROLL_MAX)
                    print(f"  [scrolled - paused {pause:.1f}s]")
                    new_h = driver.execute_script("return document.body.scrollHeight")
                except (WebDriverException, InvalidSessionIdException):
                    raise

                if new_h == prev_h and new_this_round == 0:
                    stall_count += 1
                    print(f"  [no new content - stall {stall_count}/{MAX_STALLS}]")
                    if stall_count >= MAX_STALLS:
                        print("\n  Feed ended naturally. Stopping.")
                        restarts = MAX_AUTO_RESTARTS + 1   # force outer loop to exit
                        break
                else:
                    stall_count = 0

    except KeyboardInterrupt:
        print("\n\n  Interrupted by user (Ctrl+C). Saving and exiting.")
        break

    except (WebDriverException, InvalidSessionIdException) as e:
        crashed_this_segment = True
        restarts += 1
        print(f"\n  ⚠ Browser crashed ({type(e).__name__}).")
        print(f"  Progress so far ({len(collected)} posts) is already saved.")
        print(f"  Auto-restarting browser... (attempt {restarts}/{MAX_AUTO_RESTARTS})")

        try:
            driver.quit()
        except Exception:
            pass

        time.sleep(random.uniform(3.0, 6.0))

        try:
            driver = launch_browser()
            driver.get(target_url if target_url else "https://www.facebook.com")
            time.sleep(random.uniform(4.0, 7.0))
            seen_ids = set()   # fresh DOM after relaunch — old IDs are meaningless
            print("  ✓ Browser relaunched. Resuming collection automatically.")
            print(f"  (Already have {len(collected)} posts — duplicates will be skipped.)\n")
        except Exception as relaunch_err:
            print(f"  ✗ Could not relaunch browser: {relaunch_err}")
            print("  Stopping. Just re-run the script — it will resume from disk.")
            break

    except Exception as e:
        print(f"\n  ⚠ Unexpected error: {e}")
        break

# ───────────────────────────────────────────
# FINAL SAVE
# ───────────────────────────────────────────
save_posts(collected, target_url)

print(f"\n{'='*40}")
print(f"  Posts collected : {len(collected)}")
print(f"  Auto-restarts    : {restarts}")
print(f"  Saved to         : {SAVE_FILE_TXT}")
print(f"  Saved to         : {SAVE_FILE_CSV}")
print(f"  Resume file      : {PROGRESS_FILE}")
print(f"{'='*40}\n")

try:
    input("Press ENTER to close browser...")
    driver.quit()
except Exception:
    pass













#from selenium import webdriver
#from selenium.webdriver.common.by import By
#from selenium.webdriver.chrome.options import Options
#from selenium.webdriver.chrome.service import Service
#from selenium.common.exceptions import StaleElementReferenceException
#from webdriver_manager.chrome import ChromeDriverManager
#import time
#import csv
#
# ═══════════════════════════════════════════
#  SETTINGS
# ═══════════════════════════════════════════
#TARGET_POSTS  = 100
#SCROLL_STEP   = 600
#SCROLL_PAUSE  = 1.8
#SAVE_FILE_TXT = "posts_dataset.txt"
#SAVE_FILE_CSV = "posts_dataset.csv"
# ═══════════════════════════════════════════
#
#options = Options()
#options.add_argument("--user-data-dir=selenium_profile")
#options.add_argument("--disable-notifications")
#options.add_argument("--start-maximized")
#
#driver = webdriver.Chrome(
#    service=Service(ChromeDriverManager().install()),
#    options=options
#)
#
#def save_posts(posts):
#    with open(SAVE_FILE_TXT, "w", encoding="utf-8") as f:
#        for i, p in enumerate(posts, 1):
#            f.write(f"--- Post {i} ---\n{p}\n\n")
#    with open(SAVE_FILE_CSV, "w", encoding="utf-8-sig", newline="") as f:
#        w = csv.writer(f)
#        w.writerow(["id", "post_text"])
#        for i, p in enumerate(posts, 1):
#            w.writerow([i, p])
#
#def find_post_containers():
#    try:
#        elements = driver.find_elements(
#            By.XPATH, "//*[@data-ad-preview='message']"
#        )
#        def get_y(el):
#            try:
#                return el.location['y']
#            except Exception:
#                return 999999
#        elements.sort(key=get_y)
#        return elements
#    except Exception:
#        return []
#
#def expand_post(container):
#    for label in ["See more", "See More", "مزید دیکھیں"]:
#        try:
#            btns = container.find_elements(
#                By.XPATH,
#                f".//*[normalize-space(text())='{label}']"
#            )
#            for btn in btns:
#                try:
#                    driver.execute_script(
#                        "arguments[0].scrollIntoView({block:'center'});", btn
#                    )
#                    time.sleep(0.3)
#                    driver.execute_script("arguments[0].click();", btn)
#                    time.sleep(0.7)
#                except Exception:
#                    pass
#        except Exception:
#            pass
#
#def read_text(container):
#    try:
#        text = container.text.strip()
#        return text if len(text) >= 40 else None
#    except Exception:
#        return None
#
#def print_preview(text, post_num):
#    """Print a clean preview of the post for the user to review."""
#    line = "─" * 60
#    print(f"\n{line}")
#    print(f"  POST PREVIEW  (collected so far: {post_num})")
#    print(line)
#    # Show up to 600 chars so the terminal is not flooded
#    preview = text if len(text) <= 600 else text[:600] + "..."
#    print(preview)
#    print(line)
#
# ───────────────────────────────────────────
# STARTUP
# ───────────────────────────────────────────
#driver.get("https://www.facebook.com")
#
#print("\n========================================")
#print("  Facebook Post Collector - Serenity AI")
#print("========================================")
#print(f"  Target : {TARGET_POSTS} posts")
#print("  Mode   : Manual review (yes/no per post)")
#print("========================================")
#print("\nSteps:")
#print("  1. Log in to Facebook (if not already).")
#print("  2. Open the GROUP / PAGE / SEARCH RESULTS")
#print("     with Urdu mental health posts.")
#print("  3. Make sure you can see the first post.")
#print("  4. Come back here and press ENTER.\n")
#input("Press ENTER when ready...")
#
#print("\n  Controls:")
#print("  Enter / y  → Save this post")
#print("  n          → Skip this post")
#print("  q          → Stop and save what you have\n")
#
# ───────────────────────────────────────────
# MAIN LOOP
# ───────────────────────────────────────────
#collected   = []
#seen_texts  = set()
#seen_ids    = set()
#stall_count = 0
#MAX_STALLS  = 8
#stop_now    = False
#
#while len(collected) < TARGET_POSTS and not stop_now:
#
#    containers = find_post_containers()
#    new_this_round = 0
#
#    for container in containers:
#        if len(collected) >= TARGET_POSTS or stop_now:
#            break
#
#        try:
#            el_id = container.id
#        except Exception:
#            continue
#        if el_id in seen_ids:
#            continue
#        seen_ids.add(el_id)
#
#        # Scroll into view
#        try:
#            driver.execute_script(
#                "arguments[0].scrollIntoView({block:'center'});", container
#            )
#            time.sleep(0.4)
#        except Exception:
#            continue
#
#        # Expand See more
#        expand_post(container)
#
#        # Read full text
#        text = read_text(container)
#        if not text:
#            continue
#
#        # Deduplicate
#        if text in seen_texts:
#            continue
#        seen_texts.add(text)
#        new_this_round += 1
#
#        # ── Show preview and ask user ──
#        print_preview(text, len(collected))
#
#        while True:
#            try:
#                answer = input("  Save this post? [Enter/y = yes | n = skip | q = quit]: ").strip().lower()
#            except EOFError:
#                answer = "q"
#
#            if answer in ("", "y", "yes"):
#                collected.append(text)
#                save_posts(collected)
#                print(f"  ✓ Saved  →  total saved: {len(collected)}/{TARGET_POSTS}")
#                break
#            elif answer in ("n", "no"):
#                print("  ✗ Skipped.")
#                break
#            elif answer in ("q", "quit"):
#                print("\n  Stopping early at your request.")
#                stop_now = True
#                break
#            else:
#                print("  Please press Enter, type y, n, or q.")
#
#    # Scroll down to load more posts
#    if not stop_now and len(collected) < TARGET_POSTS:
#        prev_h = driver.execute_script("return document.body.scrollHeight")
#        driver.execute_script(f"window.scrollBy(0, {SCROLL_STEP});")
#        time.sleep(SCROLL_PAUSE)
#        new_h = driver.execute_script("return document.body.scrollHeight")
#
#        if new_h == prev_h and new_this_round == 0:
#            stall_count += 1
#            print(f"\n  [no new content — stall {stall_count}/{MAX_STALLS}]")
#            if stall_count >= MAX_STALLS:
#                print("\n  Feed ended. Saving what we have and stopping.")
#                break
#        else:
#            stall_count = 0
#
# Final save
#save_posts(collected)
#
#print(f"\n{'='*40}")
#print(f"  Done.")
#print(f"  Posts saved     : {len(collected)}")
#print(f"  Saved to        : {SAVE_FILE_TXT}")
#print(f"  Saved to        : {SAVE_FILE_CSV}")
#print(f"{'='*40}\n")
#
#input("Press ENTER to close browser...")
#driver.quit()
