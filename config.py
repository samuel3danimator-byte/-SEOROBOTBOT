import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.environ["BOT_TOKEN"]
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///seorobot.db")
REPORT_HOUR = int(os.environ.get("REPORT_HOUR", 9))
MAX_RESULTS = int(os.environ.get("MAX_RESULTS", 100))
SCRAPE_DELAY_SECONDS = float(os.environ.get("SCRAPE_DELAY_SECONDS", 3))
