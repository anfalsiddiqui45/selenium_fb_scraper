from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import StaleElementReferenceException
from webdriver_manager.chrome import ChromeDriverManager
import time
import csv
import random
import os

# ═══════════════════════════════════════════
#  SETTINGS
# ═══════════════════════════════════════════
TARGET_POSTS   = 10000
SCROLL_STEP    = 600
SAVE_FILE_TXT  = "posts_dataset.txt"
SAVE_FILE_CSV  = "posts_dataset.csv"

# Random pause ranges (seconds)
PAUSE_SCROLL_MIN   = 1.6   # after each scroll
PAUSE_SCROLL_MAX   = 10.0
PAUSE_BETWEEN_MIN  = 1.6   # between processing posts
PAUSE_BETWEEN_MAX  = 10.0
PAUSE_SEE_MORE     = 0.7   # after clicking See more (kept short, it's a UI wait)
# ═══════════════════════════════════════════

def rp(lo, hi):
    """Return a random pause between lo and hi seconds, then sleep."""
    t = random.uniform(lo, hi)
    time.sleep(t)
    return t

options = Options()
USER_DATA_DIR = os.environ.get("USER_DATA_DIR", "selenium_profile")
options.add_argument(f"--user-data-dir={USER_DATA_DIR}")
options.add_argument("--disable-notifications")
options.add_argument("--start-maximized")

driver = webdriver.Chrome(
    service=Service(ChromeDriverManager().install()),
    options=options
)

def save_posts(posts):
    with open(SAVE_FILE_TXT, "w", encoding="utf-8") as f:
        for i, p in enumerate(posts, 1):
            f.write(f"--- Post {i} ---\n{p}\n\n")
    with open(SAVE_FILE_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "post_text"])
        for i, p in enumerate(posts, 1):
            w.writerow([i, p])

def find_post_containers():
    try:
        elements = driver.find_elements(
            By.XPATH, "//*[@data-ad-preview='message']"
        )
        def get_y(el):
            try:
                return el.location['y']
            except Exception:
                return 999999
        elements.sort(key=get_y)
        return elements
    except Exception:
        return []

def expand_post(container):
    for label in ["See more", "See More", "مزید دیکھیں"]:
        try:
            btns = container.find_elements(
                By.XPATH,
                f".//*[normalize-space(text())='{label}']"
            )
            for btn in btns:
                try:
                    driver.execute_script(
                        "arguments[0].scrollIntoView({block:'center'});", btn
                    )
                    time.sleep(random.uniform(0.2, 0.5))   # randomised
                    driver.execute_script("arguments[0].click();", btn)
                    time.sleep(PAUSE_SEE_MORE)
                except Exception:
                    pass
        except Exception:
            pass

def read_text(container):
    try:
        text = container.text.strip()
        return text if len(text) >= 40 else None
    except Exception:
        return None

# ───────────────────────────────────────────
# STARTUP
# ───────────────────────────────────────────
driver.get("https://www.facebook.com")

print("\n========================================")
print("  Facebook Post Collector - Serenity AI")
print("========================================")
print(f"  Target      : {TARGET_POSTS} posts")
print(f"  Scroll pause: {PAUSE_SCROLL_MIN}–{PAUSE_SCROLL_MAX}s (random)")
print(f"  Post pause  : {PAUSE_BETWEEN_MIN}–{PAUSE_BETWEEN_MAX}s (random)")
print("========================================")
print("\nSteps:")
print("  1. Log in to Facebook (if not already).")
print("  2. Open the GROUP / PAGE / SEARCH RESULTS")
print("     with Urdu mental health posts.")
print("  3. Make sure you can see the first post.")
print("  4. Come back here and press ENTER.\n")
input("Press ENTER when ready...")

# ───────────────────────────────────────────
# MAIN LOOP
# ───────────────────────────────────────────
collected   = []
seen_texts  = set()
seen_ids    = set()
stall_count = 0
MAX_STALLS  = 8

print(f"\nStarting collection...\n")

while len(collected) < TARGET_POSTS:

    containers = find_post_containers()
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

        # Scroll into view
        try:
            driver.execute_script(
                "arguments[0].scrollIntoView({block:'center'});", container
            )
            time.sleep(random.uniform(0.3, 0.6))   # randomised
        except Exception:
            continue

        # Expand See more
        expand_post(container)

        # Read text
        text = read_text(container)
        if not text:
            continue

        # Deduplicate
        if text in seen_texts:
            continue
        seen_texts.add(text)
        collected.append(text)
        new_this_round += 1

        # Save immediately
        save_posts(collected)

        pause = rp(PAUSE_BETWEEN_MIN, PAUSE_BETWEEN_MAX)
        print(f"  Post {len(collected):>5}/{TARGET_POSTS}  "
              f"({len(text)} chars)  saved ✓  (paused {pause:.1f}s)")

    # Scroll down to load more
    if len(collected) < TARGET_POSTS:
        prev_h = driver.execute_script("return document.body.scrollHeight")
        driver.execute_script(f"window.scrollBy(0, {SCROLL_STEP});")
        pause = rp(PAUSE_SCROLL_MIN, PAUSE_SCROLL_MAX)
        print(f"  [scrolled — paused {pause:.1f}s]")
        new_h = driver.execute_script("return document.body.scrollHeight")

        if new_h == prev_h and new_this_round == 0:
            stall_count += 1
            print(f"  [no new content — stall {stall_count}/{MAX_STALLS}]")
            if stall_count >= MAX_STALLS:
                print("\n  Feed ended. Saving what we have and stopping.")
                break
        else:
            stall_count = 0

# Final save
save_posts(collected)

print(f"\n{'='*40}")
print(f"  Done.")
print(f"  Posts collected : {len(collected)}")
print(f"  Saved to        : {SAVE_FILE_TXT}")
print(f"  Saved to        : {SAVE_FILE_CSV}")
print(f"{'='*40}\n")

input("Press ENTER to close browser...")
driver.quit()





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
#TARGET_POSTS  = 1000      # stop after this many posts
#SCROLL_STEP   = 600      # pixels to scroll down each step
#SCROLL_PAUSE  = 1.8      # seconds to wait after each scroll
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
# ───────────────────────────────────────────
# SAVE HELPER  (called after every new post)
# ───────────────────────────────────────────
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
#
# ───────────────────────────────────────────
# FIND ALL POST-BODY CONTAINERS ON THE PAGE
#
# Facebook wraps every post body in a div that has
#   data-ad-preview="message"
# This attribute ONLY appears on the post text itself —
# never on comments, headers, buttons, or sidebars.
# We collect ALL such elements currently in the DOM,
# sorted top-to-bottom by their Y position.
# ───────────────────────────────────────────
#def find_post_containers():
#    try:
#        elements = driver.find_elements(
#            By.XPATH, "//*[@data-ad-preview='message']"
#        )
#        # sort by vertical position so we process top → bottom
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
#
# ───────────────────────────────────────────
# CLICK "SEE MORE" INSIDE ONE CONTAINER
# ───────────────────────────────────────────
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
#                    time.sleep(0.7)   # wait for full text to load
#                except Exception:
#                    pass
#        except StaleElementReferenceException:
#            pass
#        except Exception:
#            pass
#
#
# ───────────────────────────────────────────
# READ TEXT FROM ONE CONTAINER
# ───────────────────────────────────────────
#def read_text(container):
#    try:
#        text = container.text.strip()
#        return text if len(text) >= 40 else None
#    except StaleElementReferenceException:
#        return None
#    except Exception:
#        return None
#
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
#print("========================================")
#print("\nSteps:")
#print("  1. Log in to Facebook (if not already).")
#print("  2. Open the GROUP / PAGE / SEARCH RESULTS")
#print("     with Urdu mental health posts.")
#print("  3. Make sure you can see the first post.")
#print("  4. Come back here and press ENTER.\n")
#input("Press ENTER when ready...")
#
# ───────────────────────────────────────────
# MAIN LOOP
# ───────────────────────────────────────────
#collected   = []       # post texts in order
#seen_texts  = set()    # for deduplication
#seen_ids    = set()    # Selenium element IDs already processed
#stall_count = 0
#MAX_STALLS  = 8        # how many scrolls with zero new posts before giving up
#
#print(f"\nStarting collection...\n")
#
#while len(collected) < TARGET_POSTS:
#
#    # ── Find all post containers currently visible in DOM ──
#    containers = find_post_containers()
#
#    new_this_round = 0
#
#    for container in containers:
#        if len(collected) >= TARGET_POSTS:
#            break
#
#        # Skip already-processed elements
#        try:
#            el_id = container.id
#        except Exception:
#            continue
#        if el_id in seen_ids:
#            continue
#        seen_ids.add(el_id)
#
#        # ── Step 1: scroll this post into view ──
#        try:
#            driver.execute_script(
#                "arguments[0].scrollIntoView({block:'center'});", container
#            )
#            time.sleep(0.4)
#        except Exception:
#            continue
#
#        # ── Step 2: click "See more" if present ──
#        expand_post(container)
#
#        # ── Step 3: read the full text ──
#        text = read_text(container)
#        if not text:
#            continue
#
#        # ── Step 4: deduplicate ──
#        if text in seen_texts:
#            continue
#        seen_texts.add(text)
#        collected.append(text)
#        new_this_round += 1
#
#        # ── Step 5: save immediately ──
#        save_posts(collected)
#
#        print(f"  Post {len(collected):>3}/{TARGET_POSTS}  "
#              f"({len(text)} chars)  saved ✓")
#
#    # ── Scroll down to reveal more posts ──
#    if len(collected) < TARGET_POSTS:
#        prev_h = driver.execute_script("return document.body.scrollHeight")
#        driver.execute_script(f"window.scrollBy(0, {SCROLL_STEP});")
#        time.sleep(SCROLL_PAUSE)
#        new_h = driver.execute_script("return document.body.scrollHeight")
#
#        if new_h == prev_h and new_this_round == 0:
#            stall_count += 1
#            print(f"  [no new content — stall {stall_count}/{MAX_STALLS}]")
#            if stall_count >= MAX_STALLS:
#                print("\n  Feed ended. Saving what we have and stopping.")
#                break
#        else:
#            stall_count = 0
#
# ── Final save ──
#save_posts(collected)
#
#print(f"\n{'='*40}")
#print(f"  Done.")
#print(f"  Posts collected : {len(collected)}")
#print(f"  Saved to        : {SAVE_FILE_TXT}")
#print(f"  Saved to        : {SAVE_FILE_CSV}")
#print(f"{'='*40}\n")
#
#input("Press ENTER to close browser...")
#driver.quit()
