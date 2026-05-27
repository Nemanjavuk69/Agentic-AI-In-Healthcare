import json
import time
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

def clean_text(html):
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "meta", "link"]):
        tag.decompose()
    lines = [line.strip() for line in soup.get_text(separator="\n").splitlines()]
    return "\n".join(line for line in lines if line)

def scrape_deptriage():
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        print("Opening deptriage.dk...")
        page.goto("https://www.deptriage.dk", wait_until="networkidle")
        time.sleep(4)

        # Find the navigation frame (the sidebar with all symptom links)
        nav_frame = None
        for frame in page.frames:
            if "tabstrip" in frame.url:
                nav_frame = frame
                print(f"Found navigation frame: {frame.url}")
                break

        if not nav_frame:
            print("Could not find navigation frame. Printing all frames:")
            for frame in page.frames:
                print(" -", frame.url)
            browser.close()
            return

        # Get all clickable links from the navigation
        links = nav_frame.query_selector_all("a")
        link_texts = []
        for link in links:
            text = link.inner_text().strip()
            if text:
                link_texts.append(text)

        print(f"Found {len(link_texts)} symptom cards to scrape")
        print("Cards found:", link_texts[:10], "...")

        # Click each link and capture the content frame
        for i, link_text in enumerate(link_texts):
            try:
                print(f"[{i+1}/{len(link_texts)}] Scraping: {link_text}")

                # Re-find the link by text (page may have refreshed)
                nav_frame = None
                for frame in page.frames:
                    if "tabstrip" in frame.url:
                        nav_frame = frame
                        break

                link = nav_frame.get_by_text(link_text, exact=True).first
                link.click()
                time.sleep(2)  # Wait for content frame to load

                # Find the content frame (the main display frame)
                content_frame = None
                for frame in page.frames:
                    if "tabstrip" not in frame.url and "index" not in frame.url and frame.url != "about:blank":
                        if "deptriageweb" in frame.url or "backblaze" in frame.url:
                            content_frame = frame
                            break

                if content_frame:
                    html = content_frame.content()
                    text = clean_text(html)
                    if len(text) > 100:
                        results.append({
                            "card_name": link_text,
                            "source_url": content_frame.url,
                            "text": text
                        })
                        print(f"   ✓ Got {len(text)} characters")
                    else:
                        print(f"   ✗ Content too short, skipping")
                else:
                    print(f"   ✗ No content frame found")

            except Exception as e:
                print(f"   ✗ Error on '{link_text}': {e}")

        browser.close()

    # Save raw scraped cards
    with open("dept_raw.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nDone. Scraped {len(results)} symptom cards → saved to dept_raw.json")
    return results

if __name__ == "__main__":
    scrape_deptriage()
