from pathlib import Path

from loguru import logger
from playwright.sync_api import sync_playwright
from playwright.sync_api import Error as PlaywrightError
from playwright._impl._errors import TargetClosedError

USER_DATA = "user_data"
LOGIN_URL = "https://www.linkedin.com/login"

Path("logs").mkdir(exist_ok=True)
logger.add("logs/login.log", rotation="5 MB", retention=5, level="DEBUG")


def main():
    logger.info("Starting LinkedIn login bootstrap")
    logger.info("Using persistent browser profile: {}", USER_DATA)

    with sync_playwright() as p:
        browser = None
        try:
            logger.debug("Launching visible Chrome context")
            browser = p.chromium.launch_persistent_context(
                USER_DATA,
                headless=False,
                channel="chrome",
            )

            page = browser.new_page()
            logger.debug("Navigating to {}", LOGIN_URL)
            page.goto(LOGIN_URL)
            logger.info("Login page opened; waiting for manual login")

            print("=" * 60)
            print("Login manually.")
            print("When LinkedIn home page is opened")
            print("close browser or press Enter here.")
            print("=" * 60)

            input("Press Enter after logging in and reaching LinkedIn home...")
            logger.info("Manual login confirmation received")
        except PlaywrightError:
            logger.exception("Playwright error during login bootstrap")
            raise
        finally:
            if browser is not None:
                try:
                    logger.debug("Closing login browser context")
                    browser.close()
                    logger.info("Login browser context closed")
                except TargetClosedError:
                    logger.info("Login browser was already closed manually")

    logger.info("Login bootstrap finished")


if __name__ == "__main__":
    main()