import json
import os
import re
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import requests

BASE_URL = "https://www.hoce-slivnica.si"
URL = f"{BASE_URL}/objave"
STATE_FILE = "seen_posts.json"
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "hoce-obvestila-moj-kanal")


def load_seen_posts():
  if os.path.exists(STATE_FILE):
    try:
      with open(STATE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)
    except Exception:
      return []
  return []


def save_seen_posts(posts):
  with open(STATE_FILE, "w", encoding="utf-8") as f:
    json.dump(posts, f, ensure_ascii=False, indent=2)


def send_notification(post):
  message = f"📅 {post['date']}\n\n{post['details']}"

  headers = {
      "Title": post["title"].encode("utf-8"),
      "Click": post["link"],
      "Priority": "default",
      "Tags": "loudspeaker,hoce",
      "Actions": f"view, Odpri objavo, {post['link']}".encode("utf-8"),
  }

  if post.get("image"):
    headers["Attach"] = post["image"]

  try:
    response = requests.post(
        f"https://ntfy.sh/{NTFY_TOPIC}",
        data=message.encode("utf-8"),
        headers=headers,
        timeout=15,
    )
    response.raise_for_status()
    print(f"Obvestilo uspešno poslano na ntfy.sh/{NTFY_TOPIC}")
  except Exception as e:
    print(f"Napaka pri pošiljanju obvestila za '{post['title']}': {e}")


def fetch_rendered_html():
  with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            " (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
    )
    page.goto(URL, wait_until="networkidle", timeout=30000)
    # Počakamo do 10 sekund, da se v DOM pojavi vsaj ena objava
    try:
      page.wait_for_selector("a.ListType1.ListItem", timeout=10000)
    except Exception:
      print("Čakanje na selector 'a.ListType1.ListItem' je poteklo.")
    html = page.content()
    browser.close()
    return html


def parse_posts(html_content):
  soup = BeautifulSoup(html_content, "html.parser")
  posts = []

  items = soup.select("a.ListType1.ListItem")
  print(f"Najdenih elementov 'a.ListType1.ListItem': {len(items)}")

  for item in items:
    href = item.get("href", "").strip()
    if not href:
      continue

    full_link = href if href.startswith("http") else f"{BASE_URL}{href}"

    title_el = item.select_one(".title")
    title = (
        title_el.get_text(" ", strip=True)
        if title_el
        else item.get("title", "").strip()
    )
    title = re.sub(r"\s+", " ", title)

    date_el = item.select_one(".date .text")
    date_str = date_el.get_text(strip=True) if date_el else "Neznan datum"

    details_el = item.select_one(".details")
    details = details_el.get_text(" ", strip=True) if details_el else ""
    details = re.sub(r"\s+", " ", details)

    image_url = None
    image_el = item.select_one(".image")
    if image_el and image_el.has_attr("style"):
      match = re.search(r"url\(['\"]?(.*?)['\"]?\)", image_el["style"])
      if match:
        img_path = match.group(1)
        image_url = (
            img_path if img_path.startswith("http") else f"{BASE_URL}{img_path}"
        )

    if title and full_link:
      posts.append({
          "id": full_link,
          "title": title,
          "date": date_str,
          "details": details,
          "link": full_link,
          "image": image_url,
      })

  return posts


def main():
  print("Preverjam nove objave za Občino Hoče-Slivnica...")

  try:
    html = fetch_rendered_html()
  except Exception as e:
    print(f"Napaka pri nalaganju strani z brskalnikom: {e}")
    return

  posts = parse_posts(html)
  if not posts:
    print("Opozorilo: Na strani ni bilo najdenih nobenih objav.")
    return

  seen_posts = load_seen_posts()
  seen_ids = {p["id"] for p in seen_posts}

  is_first_run = len(seen_posts) == 0
  new_posts = [p for p in posts if p["id"] not in seen_ids]

  if not new_posts:
    print("Ni novih objav.")
    return

  if is_first_run:
    print("Prvi zagon: pošiljam samo zadnjo objavo za test, ostale shranim.")
    send_notification(new_posts[0])
    seen_posts.extend(reversed(posts))
  else:
    for post in reversed(new_posts):
      print(f"Pošiljam obvestilo: {post['title']} ({post['date']})")
      send_notification(post)
      seen_posts.append(post)

  save_seen_posts(seen_posts[-150:])
  print("Stanje uspešno shranjeno.")


if __name__ == "__main__":
  main()