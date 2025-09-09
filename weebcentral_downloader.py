import os
import re
import sys
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

BASE_URL = "https://weebcentral.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
    "accept": "*/*",
    "hx-request": "true",
}

# --- Utility ---
def get_gallery_id(url):
    match = re.search(r"/(?:series|chapters)/([^/#?]+)", url)
    return match.group(1) if match else None

# --- Step 1: Get manga info ---
def get_manga_info(series_url):
    r = requests.get(series_url, headers=HEADERS)
    soup = BeautifulSoup(r.text, "html.parser")

    title = soup.select_one("h1").get_text(strip=True)
    desc = soup.select_one("strong:contains('Description') + p")
    desc = desc.get_text(strip=True) if desc else ""

    authors = [a.get_text(strip=True) for a in soup.select("strong:contains('Author') ~ a")]
    tags = [a.get_text(strip=True) for a in soup.select("strong:contains('Tags') ~ a")]

    return {
        "title": title,
        "description": desc,
        "authors": authors,
        "tags": tags,
    }

# --- Step 2: Get chapter list ---
def get_chapters(series_url):
    gid = get_gallery_id(series_url)
    endpoint = f"{BASE_URL}/series/{gid}/full-chapter-list"

    r = requests.get(endpoint, headers=HEADERS)
    chapters = []

    try:
        data = r.json()
        for chap in data.get("chapters", []):
            chapters.append((BASE_URL + chap["url"], chap["title"]))
    except:
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.select("a[href]"):
            href = a.get("href")
            if href.startswith("#"):
                continue
            title = a.get_text(strip=True)
            chapters.append((BASE_URL + href, title))

    chapters.reverse()
    return chapters

# --- Step 3: Get pages from chapter ---
def get_pages(chapter_url):
    gid = get_gallery_id(chapter_url)
    endpoint = f"{BASE_URL}/chapters/{gid}/images?is_prev=False&reading_style=long_strip"

    r = requests.get(endpoint, headers=HEADERS)
    try:
        data = r.json()
        return [img["src"] for img in data.get("images", [])]
    except:
        soup = BeautifulSoup(r.text, "html.parser")
        return [img["src"] for img in soup.select('img[alt*="Page"]:not([x-show])')]

# --- Step 4: Download chapter ---
def download_chapter(manga_title, chapter_title, page_urls, chapter_url, save_path):
    match = re.search(r"(Episode\s*\d+|Chapter\s*\d+)", chapter_title, re.IGNORECASE)
    if match:
        chapter_title = match.group(1)

    safe_title = "".join(c for c in manga_title if c.isalnum() or c in " _-")
    safe_chapter = "".join(c for c in chapter_title if c.isalnum() or c in " _-")

    folder = os.path.join(save_path, safe_title, safe_chapter)
    os.makedirs(folder, exist_ok=True)
    print(f"\n📖 Downloading chapter: {chapter_title} ({len(page_urls)} pages) into {folder}")

    for i, page_url in enumerate(tqdm(page_urls, desc="Pages", unit="page"), 1):
        ext = os.path.splitext(page_url)[-1].split("?")[0]
        filename = os.path.join(folder, f"page_{i}{ext}")
        try:
            headers = HEADERS.copy()
            headers["Referer"] = chapter_url
            with requests.get(page_url, headers=headers, stream=True) as r:
                r.raise_for_status()
                with open(filename, "wb") as f:
                    for chunk in r.iter_content(1024):
                        f.write(chunk)
        except requests.RequestException as e:
            print(f"⚠️ Failed to download {page_url}: {e}")
    print(f"✅ Chapter '{chapter_title}' downloaded successfully!")

# --- Main ---
def main():
    last_url = None  # remembers last URL
    while True:
        series_url = input("Enter WeebCentral series URL (or press Enter to reuse last): ").strip()
        if not series_url:
            if last_url:
                series_url = last_url
                print(f"↩️ Reusing last URL: {series_url}")
            else:
                print("⚠️ No previous URL to reuse.")
                continue
        last_url = series_url

        save_path = input("Enter folder to save manga (press Enter for Downloads): ").strip()
        if not save_path:
            save_path = os.path.join(os.path.expanduser("~"), "Downloads")

        info = get_manga_info(series_url)
        print(f"\n📚 Manga: {info['title']}")
        print(f"✍️ Authors: {', '.join(info['authors'])}")
        print(f"🏷️ Tags: {', '.join(info['tags'])}")
        print(f"📝 Description: {info['description']}\n")

        chapters = get_chapters(series_url)
        print(f"Found {len(chapters)} chapters.\n")

        for idx, (chap_url, chap_title) in enumerate(chapters, 1):
            match = re.search(r"(Episode\s*\d+|Chapter\s*\d+)", chap_title, re.IGNORECASE)
            clean_title = match.group(1) if match else chap_title
            pages = get_pages(chap_url)
            print(f"{idx}. {clean_title} ({len(pages)} pages)")

        choice = input("\nEnter chapter numbers to download (e.g., 1,3,5 or 2-4 or 'all'): ").strip().lower()
        
        if choice == "all":
            selected = list(range(1, len(chapters)+1))
        else:
            selected = set()
            for part in choice.split(","):
                if "-" in part:
                    start, end = map(int, part.split("-"))
                    selected.update(range(start, end+1))
                else:
                    selected.add(int(part))
            selected = sorted(selected)

        for idx in selected:
            chap_url, chap_title = chapters[idx-1]
            pages = get_pages(chap_url)
            if not pages:
                print(f"⚠️ No pages found for {chap_title}, skipping...")
                continue
            download_chapter(info["title"], chap_title, pages, chap_url, save_path)

        print("\n🎉 Download finished!")

        restart = input("\nDo you want to download more? (y/n): ").strip().lower()
        if restart != "y":
            break


if __name__ == "__main__":
    main()