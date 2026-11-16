import base64
import json
import os
import re
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import requests

# Konstante
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
    print(f"Obvestilo uspešno poslano: {post['title']}")
  except Exception as e:
    print(f"Napaka pri pošiljanju obvestila za '{post['title']}': {e}")


def parse_posts_from_html(html_content):
  soup = BeautifulSoup(html_content, "html.parser")
  posts = []

  for item in soup.select("a.ListType1.ListItem"):
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


def fetch_all_new_posts():
  seen_posts = load_seen_posts()
  seen_ids = {p["id"] for p in seen_posts}
  is_first_run = len(seen_posts) == 0

  all_fetched_posts = []

  with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            " (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
    )

    print(f"Nalagam osnovno stran ({URL})...")
    try:
      page.goto(URL, wait_until="networkidle", timeout=30000)
      page.wait_for_selector("a.ListType1.ListItem", timeout=10000)
    except Exception as e:
      print(f"Napaka pri nalaganju prve strani: {e}")
      browser.close()
      return [], seen_posts

    page_num = 1
    max_safety_pages = 10  # Varnostna meja, da se skripta ne vrti v nedogled

    while page_num <= max_safety_pages:
      print(f"Obdelujem stran {page_num}...")
      html = page.content()
      page_posts = parse_posts_from_html(html)

      if not page_posts:
        print(f"Na strani {page_num} ni več objav.")
        break

      # Preverimo, ali je katera od objav na tej strani že v bazi videnih
      found_known_post = False
      for post in page_posts:
        all_fetched_posts.append(post)
        if not is_first_run and post["id"] in seen_ids:
          found_known_post = True

      # Če je bil to prvi zagon, prenesemo samo prvo stran in končamo
      if is_first_run:
        print("Prvi zagon: zajemam samo prvo stran za začetno bazo.")
        break

      # Če smo na tej strani našli vsaj eno že znano objavo, pomeni,
      # da smo dosegli mejo starih objav in lahko prenehamo z listanjem naprej.
      if found_known_post:
        print("Našli smo že znano objavo. Prekinjam nadaljnje listanje.")
        break

      # Sicer poskusimo preiti na naslednjo stran preko tvoje JS funkcije
      page_num += 1
      print(f"Kličem openPageNumber({page_num})...")
      try:
        page.evaluate(f"openPageNumber({page_num})")
        page.wait_for_timeout(2000)  # Počakaj da AJAX osveži seznam
      except Exception as ex:
        print(f"Ni uspelo preklopiti na stran {page_num}: {ex}")
        break

    browser.close()

  return all_fetched_posts, seen_posts


def main():
  print("Preverjam objave za Občino Hoče-Slivnica...")

  posts, seen_posts = fetch_all_new_posts()
  if not posts:
    print("Opozorilo: Na straneh ni bilo najdenih nobenih objav.")
    return

  seen_ids = {p["id"] for p in seen_posts}
  is_first_run = len(seen_posts) == 0

  # Filtriramo samo tiste objave, ki jih še ni v bazi
  new_posts = [p for p in posts if p["id"] not in seen_ids]

  if not new_posts:
    print("Ni novih objav.")
    return

  if is_first_run:
    print("Prvi zagon: shranjujem zgodovino, pošiljam zadnjo objavo za test.")
    send_notification(new_posts[0])
    # Obrnemo vrstni red, da gredo od najstarejše proti novejši v bazo
    seen_posts = list(reversed(posts))
  else:
    # Obvestila pošiljamo od starejših novih proti novejšim
    for post in reversed(new_posts):
      print(f"Pošiljam obvestilo: {post['title']} ({post['date']})")
      send_notification(post)
      seen_posts.append(post)

  save_seen_posts(seen_posts[-300:])  # Povečana meja na 300 shranjenih
  print("Stanje uspešno shranjeno.")


if __name__ == "__main__":
  main()