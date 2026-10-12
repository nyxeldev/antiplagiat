"""Headless Edge, fresh contexts, synthetic accounts/documents only."""
from playwright.sync_api import sync_playwright, expect


def browser_checks(origin, password):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="msedge", headless=True)
        try:
            for width, height in [(1440, 1000), (375, 812)]:
                context = browser.new_context(viewport={"width": width, "height": height})
                other = browser.new_context(viewport={"width": width, "height": height})
                try:
                    page = context.new_page()
                    page.goto(origin)
                    expect(page.get_by_role("heading", name="Hisobga kirish")).to_be_visible()
                    page.get_by_label("Login", exact=True).fill("test-a")
                    page.get_by_label("Parol", exact=True).fill("wrong")
                    page.get_by_role("button", name="Kirish", exact=True).click()
                    expect(page.locator("p[role=alert]")).to_contain_text("Login yoki parol noto‘g‘ri")
                    page.get_by_label("Parol", exact=True).fill(password)
                    page.get_by_role("button", name="Kirish", exact=True).click()
                    expect(page.get_by_role("heading", name="Hujjatlarni solishtirish")).to_be_visible()
                    name = f"browser-{width}.txt"
                    plain = "lotin matn uchun aniq manba nusxa هَذا نص عربي واضح للاختبار فقط"
                    changed = plain.replace("lotin", "lo\u200btin")
                    page.locator("#document").set_input_files({"name": name, "mimeType": "text/plain", "buffer": changed.encode()})
                    page.locator("#sources").set_input_files({"name": "source.txt", "mimeType": "text/plain", "buffer": plain.encode()})
                    page.get_by_role("button", name="Solishtirish", exact=True).click()
                    expect(page.get_by_role("status")).to_contain_text("Hisobot shaxsiy tarixingizga saqlandi", timeout=30000)
                    link = page.get_by_role("link", name="Saqlangan hisobotni ochish")
                    saved_path = link.get_attribute("href")
                    page.get_by_role("button", name="Solishtirish", exact=True).click()
                    expect(page.get_by_role("status")).to_contain_text("Hisobot shaxsiy tarixingizga saqlandi", timeout=30000)
                    assert link.get_attribute("href") == saved_path
                    link.click()
                    expect(page.get_by_role("heading", name="Solishtirish hisoboti")).to_be_visible()
                    expect(page.get_by_text("Arab harakatlari bo‘yicha tokenizatsiya hali ishonchli emas", exact=False)).to_be_visible()
                    expect(page.get_by_text("Lotin harflari orasidagi ko‘rinmas belgilar", exact=False)).to_be_visible()
                    assert "lo\u200btin" in page.locator("mark").first.text_content()
                    assert "Normallashtirilgan shingle" in page.locator("#match").text_content()
                    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
                    page.get_by_role("link", name="Tekshiruvlar tarixi", exact=True).click()
                    expect(page.get_by_role("link", name=name, exact=True)).to_be_visible()
                    assert page.get_by_role("link", name=name, exact=True).count() == 1
                    page.get_by_role("link", name=name, exact=True).click()
                    expect(page.get_by_role("heading", name="Solishtirish hisoboti")).to_be_visible()
                    # Cancel confirmation leaves the report readable.
                    page.once("dialog", lambda dialog: dialog.dismiss())
                    page.get_by_role("button", name="Hisobotni o‘chirish", exact=True).click()
                    expect(page.get_by_role("heading", name="Solishtirish hisoboti")).to_be_visible()
                    b = other.new_page()
                    b.goto(origin + saved_path)
                    b.get_by_label("Login", exact=True).fill("test-b")
                    b.get_by_label("Parol", exact=True).fill(password)
                    b.get_by_role("button", name="Kirish", exact=True).click()
                    expect(b.locator("p[role=alert]")).to_contain_text("Hisobot topilmadi")
                    page.once("dialog", lambda dialog: dialog.accept())
                    page.get_by_role("button", name="Hisobotni o‘chirish", exact=True).click()
                    expect(page.get_by_role("heading", name="Tekshiruvlar tarixi", exact=True)).to_be_visible()
                    expect(page.get_by_role("link", name=name, exact=True)).to_have_count(0)
                    page.goto(origin + saved_path)
                    expect(page.locator("p[role=alert]")).to_contain_text("Hisobot topilmadi")
                    page.get_by_role("button", name="Chiqish", exact=True).click()
                    expect(page.get_by_role("heading", name="Hisobga kirish")).to_be_visible()
                    page.reload()
                    expect(page.get_by_role("heading", name="Hisobga kirish")).to_be_visible()
                    print(f"PASS: headless Edge {width}x{height}: login, compare/retry, saved highlights/warnings, history, owner denial, cancel/delete, logout.")
                finally:
                    context.close()
                    other.close()
        finally:
            browser.close()
