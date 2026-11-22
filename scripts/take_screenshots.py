"""Drive the running dashboard in a headless browser and save README screenshots.

Start these first (two terminals):
    uvicorn mock_policycenter.api:app --port 8001
    streamlit run ui/streamlit_app.py --server.headless true
Then:
    python scripts/take_screenshots.py
"""
from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Page, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "screenshots"
APP = "http://localhost:8501"
LLM_TIMEOUT = 180_000  # free-tier Groq can be slow


def pick_sample(page: Page, sample_id: str) -> None:
    # ARIA role "option" is stable across Streamlit versions (the HTML tags are not).
    page.locator('[data-testid="stSidebar"] [data-testid="stSelectbox"]').click()
    page.get_by_role("option").filter(has_text=f"{sample_id} -").first.click()
    page.wait_for_timeout(1200)


def run_agents(page: Page) -> None:
    page.get_by_role("button", name="Run agents").click()
    page.get_by_text("Ready for review", exact=False).wait_for(timeout=LLM_TIMEOUT)
    page.get_by_text("Total", exact=False).first.wait_for()  # score table rendered
    page.wait_for_timeout(3000)  # let widgets finish drawing


def decide(page: Page, action: str, notes: str, wait_text: str) -> None:
    form = page.locator('[data-testid="stForm"]')
    form.get_by_text(action, exact=True).click()
    form.locator("textarea").fill(notes)
    form.get_by_role("button", name="Submit decision").click()
    page.get_by_text(wait_text, exact=False).first.wait_for(timeout=LLM_TIMEOUT)
    page.wait_for_timeout(3000)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        # Streamlit scrolls inside its own container, so full_page can't grow the image:
        # a tall viewport is what captures the whole dashboard.
        page = browser.new_page(viewport={"width": 1440, "height": 1500}, device_scale_factor=1)
        page.goto(APP)
        page.get_by_role("button", name="Run agents").wait_for(timeout=60_000)

        # 1. Galveston restaurant: referral with CAT flags
        pick_sample(page, "S002")
        run_agents(page)
        page.screenshot(path=OUT / "01_triage_brief.png", full_page=True)
        page.get_by_role("tab", name="Appetite rules").click()
        page.wait_for_timeout(800)
        page.screenshot(path=OUT / "02_appetite_rules.png", clip={"x": 300, "y": 0, "width": 1140, "height": 1220})
        decide(page, "approve", "Refer approved; 2% wind deductible.", "Created in PolicyCenter")
        page.screenshot(path=OUT / "03_approved_policycenter.png", full_page=True)

        # 2. Dispensary that never says "cannabis": decline + broker email draft
        pick_sample(page, "S007")
        run_agents(page)
        decide(page, "decline", "", "Email draft to broker")
        page.screenshot(path=OUT / "04_decline_email.png", full_page=True)

        # 3. The mock core-system API
        page.goto("http://127.0.0.1:8001/docs")
        page.wait_for_timeout(2500)
        page.screenshot(path=OUT / "05_policycenter_api.png", clip={"x": 0, "y": 0, "width": 1440, "height": 760})
        browser.close()
    print(f"Saved screenshots to {OUT}")


if __name__ == "__main__":
    main()
