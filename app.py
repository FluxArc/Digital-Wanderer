from flask import Flask, request, render_template, jsonify
import urllib.parse
import requests
from bs4 import BeautifulSoup
import concurrent.futures
from urllib.parse import urlparse

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
    "Videos": [
        ('intitle:"index of /" "parent directory" (mp4|avi|mkv|mov|wmv|flv|webm) "{}" -html -htm -php -asp -aspx -jsp', 'Video Directories'),
        ('intitle:"index of /" "{}" (movie|series|anime|clips) -html -htm -php', 'Named Video Collections')
    ],
    "Music": [
        ('intitle:"index of /" "parent directory" (mp3|flac|wav|aac|ogg|wma) "{}" -html -htm -php -asp -aspx -jsp', 'Music Archives'),
        ('intitle:"index of /" "{}" (albums|soundtracks|mixes) -html -htm -php', 'Album or Soundtrack Collections')
    ],
    "Config & Credentials": [
        ('intitle:"index of /" "parent directory" (config.php|.env|settings.xml|credentials.json) "{}"', 'Config Files & Credentials')
    ],
    "Repositories": [
        ('inurl:".git/" "index of /" "{}"', 'Exposed Git Repository'),
        ('inurl:".svn/" "index of /" "{}"', 'Exposed SVN Repository')
    ],
    "CMS Uploads": [
        ('intitle:"index of /wp-content/uploads" "{}"', 'WordPress Uploads'),
        ('intitle:"index of /sites/default/files" "{}"', 'Drupal Uploads')
    ],
    "Backups & Dumps": [
        ('intitle:"index of /" "parent directory" (sql|bak|zip|tar.gz) "{}"', 'Database & Backup Dumps')
    ],
    "Logs": [
        ('intitle:"index of /" "parent directory" (log|txt|dump) "{}"', 'Log & Crash Dumps')
    ],
    "FTP Shares": [
        ('inurl:"ftp://" "index of /" "{}"', 'FTP Share'),
        ('site:ftp.* "Index of /" "{}"', 'FTP Server Index')
    ],
    "IoT Devices": [
        ('inurl:"/video.cgi" "parent directory" "{}"', 'DVR/NVR Video CGI'),
        ('inurl:"/axis-cgi" "index of /" "{}"', 'Axis-CGI Exposure')
    ],
    "All Indexes": [
        ('intitle:"index of /" "parent directory" "{}" -html -htm -php -asp -aspx -jsp', 'General Open Directory')
    ]
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

def do_search(form):
    selected_category = form.get('category', '')
    keywords_raw = form.get('keywords', '')
    check_live = form.get('check_live') == 'on'
    discover = form.get('discover') == 'on'
    require_frontend = form.get('require_frontend') == 'on'
    selected_engines = form.getlist('engines') or list(SEARCH_ENGINES.keys())

    keyword_combined = ' '.join([kw.strip() for kw in keywords_raw.split(',') if kw.strip()])
    keywords = [keyword_combined] if keyword_combined else ['']
    results = []
    for keyword in keywords:
        for template, label in CATEGORIES.get(selected_category, []):
            for engine_name, engine_url in SEARCH_ENGINES.items():
                if engine_name not in selected_engines:
                    continue
                full_query = template.format(keyword)
                encoded = urllib.parse.quote_plus(full_query)
                search_url = f"{engine_url}{encoded}&num=100"
                if discover:
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
                                if require_frontend:
                                    parsed = urlparse(url)
                                    root = f"{parsed.scheme}://{parsed.netloc}/"
                                    try:
                                        r2 = requests.get(root, timeout=5)
                                        if r2.status_code == 200 and "Index of /" not in r2.text:
                                            results.append({
                                                'label': f"[{engine_name}] 🔍 {parsed.netloc}",
                                                'url': url,
                                                'status': status,
                                                'title': 'Directory + Front-End'
                                            })
                                    except:
                                        pass
                                else:
                                    results.append({
                                        'label': f"[{engine_name}] 🔍 Open Index",
                                        'url': url,
                                        'status': status,
                                        'title': 'Directory Listing'
                                    })
                else:
                    status = None
                    title = ''
                    if check_live:
                        try:
                            resp = requests.get(search_url, timeout=5)
                            status = resp.status_code
                            soup = BeautifulSoup(resp.text, 'html.parser')
                            title = soup.title.string.strip() if soup.title else ''
                        except:
                            status = None
                    results.append({
                        'label': f"[{engine_name}] {label} for \"{keyword}\"" if keyword else f"[{engine_name}] {label}",
                        'url': search_url,
                        'status': status,
                        'title': title
                    })
    return results

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html',
        categories=CATEGORIES.keys(),
        SEARCH_ENGINES=SEARCH_ENGINES,
    )

@app.route('/search', methods=['POST'])
def search():
    results = do_search(request.form)
    params = {
        'category': request.form.get('category', ''),
        'keywords': request.form.get('keywords', ''),
        'check_live': request.form.get('check_live') == 'on',
        'discover': request.form.get('discover') == 'on',
        'require_frontend': request.form.get('require_frontend') == 'on',
        'selected_engines': request.form.getlist('engines') or list(SEARCH_ENGINES.keys())
    }
    return jsonify({'results': results, 'params': params})

if __name__ == '__main__':
    app.run(debug=True)
