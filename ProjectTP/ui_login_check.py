from playwright.sync_api import sync_playwright


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.on("console", lambda m: print(f"CONSOLE[{m.type}]={m.text}"))
        page.on("pageerror", lambda e: print(f"PAGEERROR={e}"))
        page.goto("http://127.0.0.1:8080/login.html", wait_until="domcontentloaded")

        page.fill("#loginUsername", "admin")
        page.fill("#loginPassword", "admin")
        page.click("button[type='submit']")
        page.wait_for_timeout(1200)

        url = page.url
        has_graph = page.locator("button[data-tab='graph']").count() > 0
        has_reports = page.locator("button[data-tab='reports']").count() > 0
        has_admin = page.locator("button[data-tab='admin']").count() > 0

        print(f"URL={url}")
        print(f"GRAPH={has_graph}")
        print(f"REPORTS={has_reports}")
        print(f"ADMIN={has_admin}")

        err = ""
        if page.locator("#loginError").count() > 0:
            try:
                err = page.locator("#loginError").inner_text().strip()
            except Exception:
                err = ""
        print(f"LOGIN_ERROR={err}")
        browser.close()


if __name__ == "__main__":
    main()
