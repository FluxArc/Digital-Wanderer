from flask import Flask, request, render_template
import urllib.parse
import requests
from bs4 import BeautifulSoup
import concurrent.futures

app = Flask(__name__)

CATEGORIES = {
    "Google Drive": [
        ('inurl:"drive.google.com" "{}"', 'Any Public Google Drive Content'),
        ('inurl:"drive.google.com"', 'All Public Google Drive Links')
    ],
    "Photos": [
        ('intitle:"index of /" "parent directory" (jpg|jpeg|png|gif|bmp|tiff|webp) "{}" -html -htm -php -asp -aspx -jsp', 'Photo Archive'),
        ('intitle:"index of /" "parent directory" (DCIM|Camera|Photos) "{}" -html -htm -php', 'Camera Dump Folders'),
        ('intitle:"index of /" "{}" (wallpapers|screenshots|albums) -html -htm -php', 'Wallpapers or Screenshots')
    ],
    # ... (other categories truncated for brevity)
}

SEARCH_ENGINES = {
    "Google": "https://www.google.com/search?q=",
    "DuckDuckGo": "https://duckduckgo.com/?q=",
    "Bing": "https://www.bing.com/search?q=",
    "Yandex": "https://yandex.com/search/?text="
}

def extract_result_urls(html):
    soup = BeautifulSoup(html, 'html.parser')
    urls = []
    for a in soup.select('a'):
        href = a.get('href')
        if href and href.startswith('http'):
            urls.append(href)
    return urls[:10]

def is_open_index(url):
    try:
        r = requests.get(url, timeout=5)
        if "Index of /" in r.text:
            return True, r.status_code
    except:
        pass
    return False, None

@app.route('/', methods=['GET', 'POST'])
def index():
    links = []
    selected_category = ''
    keywords_raw = ''
    check_live = False
    selected_engines = []
    discover = False

    if request.method == 'POST':
        selected_category = request.form.get('category', '')
        keywords_raw = request.form.get('keywords', '')
        check_live = request.form.get('check_live') == 'on'
        discover = request.form.get('discover') == 'on'

        selected_engines = request.form.getlist('engines')
        if not selected_engines:
            selected_engines = list(SEARCH_ENGINES.keys())

        keyword_combined = ' '.join([kw.strip() for kw in keywords_raw.split(',') if kw.strip()])
        keywords = [keyword_combined] if keyword_combined else ['']
        queries = CATEGORIES.get(selected_category, [])

        for keyword in keywords:
            for template, label in queries:
                for engine_name, engine_url in SEARCH_ENGINES.items():
                    if engine_name not in selected_engines:
                        continue

                    full_query = template.format(keyword)
                    encoded = urllib.parse.quote_plus(full_query)
                    search_url = f"{engine_url}{encoded}&num=100"
                    label_full = f"[{engine_name}] {label} for \"{keyword}\"" if keyword else f"[{engine_name}] {label}"

                    if discover:
                        # Fetch search results page
                        try:
                            resp = requests.get(search_url, timeout=5)
                        except:
                            continue
                        result_urls = extract_result_urls(resp.text)
                        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                            futures = {executor.submit(is_open_index, u): u for u in result_urls}
                            for future in concurrent.futures.as_completed(futures):
                                url = futures[future]
                                open_idx, status = future.result()
                                if open_idx:
                                    links.append((f"[{engine_name}] 🔍 Open Index @ {url}", url, status, "Directory Listing"))
                    else:
                        if check_live:
                            try:
                                response = requests.get(search_url, timeout=5)
                                status = response.status_code
                                soup = BeautifulSoup(response.text, 'html.parser')
                                title = soup.title.string.strip() if soup.title else "No title"
                            except Exception as e:
                                status, title = "Error", str(e)
                            links.append((label_full, search_url, status, title))
                        else:
                            links.append((label_full, search_url, None, None))

    return render_template(
        "index.html",
        categories=CATEGORIES.keys(),
        SEARCH_ENGINES=SEARCH_ENGINES,
        selected_category=selected_category,
        keywords=keywords_raw,
        check_live=check_live,
        selected_engines=selected_engines,
        discover=discover,
        links=links
    )

if __name__ == '__main__':
    app.run(debug=True)
