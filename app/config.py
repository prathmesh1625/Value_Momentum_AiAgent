import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
# Check https://console.groq.com/docs/models if this model is ever retired.
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
# "embedded" runs the mock PolicyCenter inside this process (no second server needed).
# Set a URL such as http://127.0.0.1:8001 to call a separately running API instead.
POLICYCENTER_URL = os.getenv("POLICYCENTER_URL", "embedded")
ENABLE_GEOCODING = os.getenv("ENABLE_GEOCODING", "true").lower() == "true"

DATA_DIR = ROOT / "data"
SUBMISSIONS_DIR = DATA_DIR / "submissions"
GUIDELINES_PATH = DATA_DIR / "guidelines" / "underwriting_guidelines.md"
EXISTING_SUBMISSIONS_PATH = DATA_DIR / "existing_submissions.json"
RUNTIME_DIR = ROOT / "runtime"
RUNTIME_DIR.mkdir(exist_ok=True)
CHECKPOINT_DB = RUNTIME_DIR / "checkpoints.sqlite"
AUDIT_DB = RUNTIME_DIR / "audit.sqlite"
