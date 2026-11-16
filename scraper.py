import json
import os
import re
from bs4 import BeautifulSoup
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
  # Oblikujemo vsebino obvestila (datum + kratek povzetek)
  message = f"{post['date']}\n\n{post['details']}"

  headers = {
      "Title": post["title"].encode("utf-8"),
      "Click": post["link"],
      "Priority": "default",
      "Tags": "loudspeaker,hoce",
      # Dodamo še gumb pod obvestilom za hitro odpiranje v brskalniku
      "Actions": f"view, Odpri objavo, {post['link']}".encode("utf-8"),
  }

  # Če ima objava sliko, jo pripnemo v obvestilo
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
  except Exception as e:
    print(f"Napaka pri pošiljanju obvestila za '{post['title']}': {e}")


def parse_posts(html_content):
  soup = BeautifulSoup(html_content, "html.parser")
  posts = []

  # Poiščemo vse elemente <a> z razredoma ListType1 in ListItem
  for item in soup.select("a.ListType1.ListItem"):
    href = item.get("href", "").strip()
    if not href:
      continue

    full_link = href if href.startswith("http") else f"{BASE_URL}{href}"

    # 1. Naslov (najprej iz div.title, sicer iz atributa title)
    title_el = item.select_one(".title")
    title = (
        title_el.get_text(" ", strip=True)
        if title_el
        else item.get("title", "").strip()
    )
    title = re.sub(r"\s+", " ", title)

    # 2. Datum iz .date .text
    date_el = item.select_one(".date .text")
    date_str = date_el.get_text(strip=True) if date_el else "Neznan datum"

    # 3. Opis iz .details (počistimo večkratne presledke in &nbsp;)
    details_el = item.select_one(".details")
    details = details_el.get_text(" ", strip=True) if details_el else ""
    details = re.sub(r"\s+", " ", details)

    # 4. Opcijsko: slika iz background-image sloga
    image_url = None
    image_el = item.select_one(".image")
    if image_el and image_el.has_attr("style"):
      match = re.search(
          r"url\(['\"]?(.*?)['\"]?\)", image_el["style"]
      )
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
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }
    response = requests.get(URL, headers=headers, timeout=15)
    response.raise_for_status()
  except Exception as e:
    print(f"Napaka pri dostopu do spletne strani: {e}")
    return

  posts = parse_posts(response.text)
  if not posts:
    print("Opozorilo: Na strani ni bilo najdenih nobenih objav.")
    return

  seen_posts = load_seen_posts()
  seen_ids = {p["id"] for p in seen_posts}

  # Pomembno: ob prvem zagonu (ko seen_posts.json še ne obstaja ali je prazen)
  # pošljemo samo najnovejšo objavo, ostale pa označimo kot prebrane,
  # da družina ne dobi 15 obvestil naenkrat!
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
    # Pošljemo od najstarejše nove proti najnovejši
    for post in reversed(new_posts):
      print(f"Pošiljam obvestilo: {post['title']} ({post['date']})")
      send_notification(post)
      seen_posts.append(post)

  # Ohranimo zadnjih 150 zapisov v zgodovini
  save_seen_posts(seen_posts[-150:])
  print("Stanje uspešno shranjeno.")


if __name__ == "__main__":
  main()