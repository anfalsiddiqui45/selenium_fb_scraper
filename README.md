# Facebook Group Scraper

This repository contains two lightweight Selenium scripts to collect post text from Facebook groups/pages:

- `manual.py` — robust collector with crash recovery and resume
- `mental_health_scraper.py` — simpler collector loop

Security first: do NOT commit your browser profile or credentials. This project intentionally reads the Chrome user-data directory from the `USER_DATA_DIR` environment variable and `.gitignore` excludes the `selenium_profile/` folder and `data/`.

Quick start

1. Create a Python virtual environment and install dependencies:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. Configure a Chrome profile outside this repository and set `USER_DATA_DIR`:

```bash
export USER_DATA_DIR="$HOME/.config/google-chrome/Default"
# or copy config.example.env -> .env and export variables from it
```

3. Run a script and follow the on-screen steps (log in to Facebook in the opened browser):

```bash
python manual.py
# or
python mental_health_scraper.py
```

Preparing for GitHub

- This repo adds `.gitignore` to exclude profiles and data. If you previously committed `selenium_profile/`, remove it from history before pushing (see below).

Pushing to GitHub (local steps)

```bash
git init
git add .
git commit -m "Initial: scrub sensitive defaults, add examples and docs"
# create a repository on github.com then:
git remote add origin git@github.com:yourusername/your-repo.git
git push -u origin main
```

If you accidentally committed sensitive files, do NOT push — instead remove them and rewrite history. Ask if you want help with that.

License: MIT
