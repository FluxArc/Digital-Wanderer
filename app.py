from flask import Flask, request, render_template, jsonify
import urllib.parse
import requests
from bs4 import BeautifulSoup
import concurrent.futures
from urllib.parse import urlparse

app = Flask(__name__)

# Broadened discovery patterns with toggle for strict index filter
CATEGORIES = {
    "General Directories": [
        ('"parent directory" "{}"', 'Parent Directory Mention'),
        ('inurl:"/files/" "{}"', 'Files Folder'),
        ('"Directory Listing" "{}"', 'Directory Listing Title'),
        ('inurl:"/?C=N;O=D" "{}"', 'Apache Sort Pattern')
    ],
    "NAS / Cloud Devices": [
        ('site:synology.me "{}" inurl:photo OR inurl:music', 'Synology NAS Share'),
        ('site:qnapcloud.com "{}" inurl:share', 'QNAP NAS Share'),
        ('site:myqnapcloud.com "{}"', 'MyQNAPCloud Public File'),
        ('intitle:"QNAP Turbo Station" "{}"', 'Exposed QNAP Panel'),
        ('intitle:"Synology DiskStation" "{}"', 'Exposed Synology Panel')
    ],
    "Cameras & IP Devices": [
        ('intitle:"Live View / - AXIS" "{}"', 'AXIS Live View'),
        ('inurl:"/view/view.shtml" "{}"', 'Axis Webcam Interface'),
        ('inurl:"/mjpg/video.mjpg" "{}"', 'MJPEG Video Feed'),
        ('inurl:"/Streaming/channels" "{}"', 'Hikvision Stream'),
        ('intitle:"WebcamXP" "{}"', 'WebcamXP Dashboard'),
        ('intitle:"NetSurveillance Web" "{}"', 'Dahua/Netsurveillance'),
        ('inurl:"/cgi-bin/video.cgi" "{}"', 'Generic IP Cam CGI')
    ],
    "Google Drive": [
        ('inurl:"drive.google.com" "{}"', 'Any Public Google Drive Content'),
        ('inurl:"drive.google.com" "{}" -html -htm', 'Drive Links')
    ],
    "Photos": [
        ('"parent directory" (jpg|jpeg|png|gif|bmp|tiff|webp) "{}"', 'Any Image File Folders'),
        ('inurl:photos "{}"', 'Photo Path')
    ],
    "Videos": [
        ('"parent directory" (mp4|avi|mkv|mov|wmv|flv|webm) "{}"', 'Any Video File Folders'),
        ('inurl:videos "{}"', 'Video Path')
    ],
    "Music": [
        ('"parent directory" (mp3|flac|wav|aac|ogg|wma) "{}"', 'Any Audio File Folders'),
        ('inurl:music "{}"', 'Music Path')
    ],
    "Text & Docs": [
        ('"parent directory" (pdf|epub|mobi|doc|docx|txt) "{}"', 'Any Document Folders'),
        ('inurl:docs "{}"', 'Docs Path')
    ],
    "Backups & Dumps": [
        ('"parent directory" (zip|rar|tar|gz|bak|sql) "{}"', 'Backup Archives')
    ],
    "Config & Credentials": [
        ('"parent directory" (config|.env|credentials|settings) "{}"', 'Config & Credential Files')
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
    return [a['href'] for a in soup.select('a[href^="http"]')][:10]

def is_open_index(url):
    try:
        r = requests.get(url, timeout=5)
        text = r.text
        if "Index of" in text or "Parent Directory" in text:
            return True, r.status_code
    except:
        pass
    return False, None

def do_search(form):
    category        = form.get('category', '')
    keywords_raw    = form.get('keywords', '')
    check_live      = form.get('check_live') == 'on'
    discover        = form.get('discover') == 'on'
    require_front   = form.get('require_frontend') == 'on'
    include_index   = form.get('include_index') == 'on'
    engines         = form.getlist('engines') or list(SEARCH_ENGINES.keys())

    kw_combined = ' '.join([kw.strip() for kw in keywords_raw.split(',') if kw.strip()])
    keywords    = [kw_combined] if kw_combined else ['']
    results     = []

    for kw in keywords:
        for template, label in CATEGORIES.get(category, []):
            if include_index:
                template = 'intitle:"index of /" ' + template
            for name, base_url in SEARCH_ENGINES.items():
                if name not in engines:
                    continue
                query      = urllib.parse.quote_plus(template.format(kw))
                search_url = f"{base_url}{query}&num=100"

                if discover:
                    try:
                        resp = requests.get(search_url, timeout=5)
                        urls = extract_result_urls(resp.text)
                    except:
                        continue
                    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
                        futures = {pool.submit(is_open_index, u): u for u in urls}
                        for fut in concurrent.futures.as_completed(futures):
                            url, status = futures[fut], None
                            open_idx, status = fut.result()
                            if not open_idx:
                                continue
                            if require_front:
                                p    = urlparse(url)
                                root = f"{p.scheme}://{p.netloc}/"
                                try:
                                    r2 = requests.get(root, timeout=5)
                                    if r2.status_code != 200 or "Index of" in r2.text:
                                        continue
                                except:
                                    continue
                                title = 'Directory + Front-End'
                                lbl   = f"[{name}] ✔️ {p.netloc}"
                            else:
                                title = 'Directory Listing'
                                lbl   = f"[{name}] 🔍 Open Index"
                            results.append({'label': lbl, 'url': url, 'status': status, 'title': title})
                else:
                    status, page_title = None, ''
                    if check_live:
                        try:
                            r  = requests.get(search_url, timeout=5)
                            status = r.status_code
                            soup   = BeautifulSoup(r.text, 'html.parser')
                            page_title = soup.title.string.strip() if soup.title else ''
                        except:
                            pass
                    lbl = f'[{name}] {label} for "{kw}"' if kw else f'[{name}] {label}'
                    results.append({'label': lbl, 'url': search_url, 'status': status, 'title': page_title})
    return results

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html', categories=CATEGORIES.keys(), SEARCH_ENGINES=SEARCH_ENGINES)

@app.route('/search', methods=['POST'])
def search():
    data   = do_search(request.form)
    params = {
        'category':         request.form.get('category',''),
        'keywords':         request.form.get('keywords',''),
        'check_live':       request.form.get('check_live')=='on',
        'discover':         request.form.get('discover')=='on',
        'require_frontend': request.form.get('require_frontend')=='on',
        'include_index':    request.form.get('include_index')=='on',
        'selected_engines': request.form.getlist('engines') or list(SEARCH_ENGINES.keys())
    }
    return jsonify({'results': data, 'params': params})

if __name__ == '__main__':
    app.run(debug=True)
