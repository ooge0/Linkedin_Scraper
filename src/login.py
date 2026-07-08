from playwright.sync_api import sync_playwright

USER_DATA = "user_data"

with sync_playwright() as p:

    browser = p.chromium.launch_persistent_context(
        USER_DATA,
        headless=False,
        channel="chrome",
    )

    page = browser.new_page()

    page.goto("https://www.linkedin.com/login")

    print("=" * 60)
    print("Login manually.")
    print("When LinkedIn home page is opened")
    print("close browser.")
    print("=" * 60)

    page.wait_for_timeout(600000)

    browser.close()