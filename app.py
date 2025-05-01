from flask import Flask, request, render_template
import urllib.parse
import requests
from bs4 import BeautifulSoup

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
    "Books & Text": [
        ('intitle:"index of /" "parent directory" (pdf|epub|mobi|doc|docx|txt) "{}" -html -htm -php -asp -aspx -jsp', 'Book Archives (PDF, ePub, Docs)'),
        ('intitle:"index of /" "{}" (ebooks|books|manuals|guides) -html -htm -php', 'General Book Directories'),
        ('intitle:"index of /" "{}" (readme|changelog|notes|log) -html -htm -php', 'Log and Text Dump Folders')
    ],
    "Software & Projects": [
        ('intitle:"index of /" "parent directory" (zip|rar|7z|tar|gz|iso|img|apk|exe) "{}" -html -htm -php -asp -aspx -jsp', 'Software Installers & Archives'),
        ('intitle:"index of /" "{}" (projects|code|tools|apps) -html -htm -php', 'Project & Dev Dump Folders'),
        ('intitle:"index of /" "{}" (firmware|setup|drivers|release) -html -htm -php', 'Firmware and Tools Folders')
    ],
    "Backups & Dumps": [
        ('intitle:"index of /" "parent directory" (backup|dump|db|sql|tar|gz|old) "{}" -html -htm -php -asp -aspx -jsp', 'Backup or Database Dumps'),
        ('intitle:"index of /" "{}" (logs|archives|crash|core) -html -htm -php', 'Log & Crash Dump Folders')
    ],
    "Open NAS/Cloud Boxes": [
        ('site:synology.me "{}" inurl:photo OR inurl:music', 'Synology NAS Share'),
        ('site:qnapcloud.com "{}" inurl:share', 'QNAP NAS Share'),
        ('site:myqnapcloud.com "{}"', 'MyQNAPCloud Public File'),
        ('intitle:"QNAP Turbo Station" "{}"', 'Exposed QNAP Interface'),
        ('intitle:"Synology DiskStation" "{}"', 'Exposed Synology Panel'),
        ('intitle:"NAS Login" "{}"', 'Generic NAS Login Portals')
    ],
    "Public Cameras / IP Devices": [
        ('intitle:"Live View / - AXIS" "{}"', 'AXIS Live View'),
        ('inurl:view/view.shtml "{}"', 'Live Axis Webcam'),
        ('inurl:top.htm inurl:currenttime "{}"', 'Webcam Dashboard View'),
        ('inurl:axis-cgi/mjpg "{}"', 'MJPEG Stream (Axis or Similar)'),
        ('inurl:/mjpg/video.mjpg "{}"', 'MJPEG Video Feed'),
        ('inurl:/cgi-bin/video.cgi "{}"', 'Generic Live Video Feed'),
        ('inurl:"/liveview.cgi" "{}"', 'Live View CGI Stream'),
        ('intitle:"Live Cam" inurl:.cgi "{}"', 'Generic CGI Webcam'),
        ('intitle:"WebcamXP" "{}"', 'WebcamXP Dashboard'),
        ('intitle:"NetSurveillance Web" "{}"', 'NetSurveillance/Dahua Panel'),
        ('inurl:"/Streaming/channels" "{}"', 'Hikvision Streaming Endpoint'),
        ('intitle:"IP Camera Viewer" "{}"', 'Generic IP Cam Viewer'),
        ('inurl:"/cgi-bin/guestimage.html" "{}"', 'Snapshot Guest Image'),
        ('inurl:"/videostream.cgi" "{}"', 'MJPEG Video Stream'),
        ('intitle:"Remote Viewer" inurl:/viewerframe?mode= "{}"', 'Remote Viewer Frame'),
        ('intitle:"Wisenet" "{}"', 'Hanwha Wisenet Camera')
    ],
    "All Indexes": [
        ('intitle:"index of /" "parent directory" "{}" -html -htm -php -asp -aspx -jsp', 'General Open Directory'),
        ('intitle:"index of /" "{}" (downloads|storage|files) -html -htm -php', 'Common Shared File Directories'),
        ('intitle:"index of /" "{}" (misc|dump|random|temp) -html -htm -php', 'Loose Dump Folders')
    ]
}

SEARCH_ENGINES = {
    "Google": "https://www.google.com/search?q=",
    "DuckDuckGo": "https://duckduckgo.com/?q=",
    "Bing": "https://www.bing.com/search?q=",
    "Yandex": "https://yandex.com/search/?text="
}

@app.route('/', methods=['GET', 'POST'])
def index():
    links = []
    selected_category = ''
    keywords_raw = ''
    check_live = False

    if request.method == 'POST':
        selected_category = request.form.get('category', '')
        keywords_raw = request.form.get('keywords', '')
        check_live = request.form.get('check_live') == 'on'

        keyword_combined = ' '.join([kw.strip() for kw in keywords_raw.split(',') if kw.strip()])
        keywords = [keyword_combined] if keyword_combined else ['']
        queries = CATEGORIES.get(selected_category, [])

        for keyword in keywords:
            for template, label in queries:
                for engine_name, engine_url in SEARCH_ENGINES.items():
                    full_query = template.format(keyword)
                    encoded = urllib.parse.quote_plus(full_query)
                    search_url = f"{engine_url}{encoded}&num=100"
                    label_full = f"[{engine_name}] {label} for \"{keyword}\"" if keyword else f"[{engine_name}] {label}"

                    if check_live:
                        try:
                            response = requests.get(search_url, timeout=5)
                            status = response.status_code
                            soup = BeautifulSoup(response.text, 'html.parser')
                            title = soup.title.string.strip() if soup.title else "No title"
                        except Exception as e:
                            status = "Error"
                            title = str(e)
                        links.append((label_full, search_url, status, title))
                    else:
                        links.append((label_full, search_url, None, None))

    return render_template("index.html",
        categories=CATEGORIES.keys(),
        selected_category=selected_category,
        keywords=keywords_raw,
        check_live=check_live,
        links=links
    )

if __name__ == '__main__':
    app.run(debug=True)
