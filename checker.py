import os, json, time, subprocess, socket, requests, base64, re
from urllib.parse import urlparse

# БЕРЁМ ССЫЛКИ ИЗ ПЕРЕМЕННОЙ ОКРУЖЕНИЯ (настроим на Render)
SOURCE_URLS = os.environ.get("SOURCE_URLS", "").split(",")

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GITHUB_REPO = os.environ.get("GITHUB_REPO") # Например: "username/my-checked-servers"
GITHUB_FILE_PATH = "checked_servers.txt"
TEST_URLS = ["https://www.youtube.com", "https://web.telegram.org"]
XRAY_PATH = "/usr/local/bin/xray"
LOCAL_PORT = 10809

def extract_links(text):
    try:
        decoded = base64.b64decode(text).decode('utf-8')
        if "vless://" in decoded: text = decoded
    except: pass
    return list(set(re.findall(r'(vless://[^\s]+)', text)))

def get_all_links():
    all_l = set()
    for url in SOURCE_URLS:
        url = url.strip()
        if not url: continue
        print(f"Загрузка: {url}")
        try:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            links = extract_links(r.text)
            print(f"  Найдено: {len(links)}")
            all_l.update(links)
        except Exception as e: print(f"  Ошибка: {e}")
    return list(all_l)

def vless_to_xray(link, port):
    p = urlparse(link)
    params = {}
    if p.query:
        for pair in p.query.split("&"):
            if "=" in pair: k, v = pair.split("=", 1); params[k] = v
    cfg = {"inbounds": [{"port": port, "listen": "127.0.0.1", "protocol": "http", "settings": {}}],
           "outbounds": [{"protocol": "vless", "settings": {"vnext": [{"address": p.hostname, "port": p.port or 443, "users": [{"id": p.username, "encryption": params.get("encryption", "none"), "flow": params.get("flow", "")}]}]}, "streamSettings": {"network": params.get("type", "tcp"), "security": params.get("security", "none")}}]}
    if params.get("security") == "tls":
        cfg["outbounds"][0]["streamSettings"]["tlsSettings"] = {"serverName": params.get("sni", p.hostname), "allowInsecure": False}
    elif params.get("security") == "reality":
        cfg["outbounds"][0]["streamSettings"]["realitySettings"] = {"serverName": params.get("sni", p.hostname), "publicKey": params.get("pbk", ""), "shortId": params.get("sid", ""), "fingerprint": params.get("fp", "chrome")}
    if params.get("type") == "ws":
        cfg["outbounds"][0]["streamSettings"]["wsSettings"] = {"path": params.get("path", "/"), "headers": {"Host": params.get("host", p.hostname)}}
    return cfg

def check(link):
    cfg = vless_to_xray(link, LOCAL_PORT)
    with open("tmp.json", "w") as f: json.dump(cfg, f)
    proc = None
    try:
        proc = subprocess.Popen([XRAY_PATH, "run", "-config", "tmp.json"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        start = time.time()
        while time.time() - start < 5:
            try:
                with socket.create_connection(("127.0.0.1", LOCAL_PORT), timeout=2): break
            except: time.sleep(0.3)
        else: return False
        proxies = {"http": f"http://127.0.0.1:{LOCAL_PORT}", "https": f"http://127.0.0.1:{LOCAL_PORT}"}
        for url in TEST_URLS:
            try:
                if requests.get(url, proxies=proxies, timeout=10, allow_redirects=True).status_code >= 400: return False
            except: return False
        return True
    except: return False
    finally:
        if proc: proc.terminate(); proc.wait()
        if os.path.exists("tmp.json"): os.remove("tmp.json")

def upload(content):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    r = requests.get(url, headers=headers)
    sha = r.json().get("sha") if r.status_code == 200 else None
    data = {"message": f"Update {time.strftime('%Y-%m-%d %H:%M')}", "content": base64.b64encode(content.encode()).decode(), "sha": sha}
    r = requests.put(url, headers=headers, json=data)
    print("✅ GitHub обновлён" if r.status_code in (200, 201) else f"❌ Ошибка: {r.text}")

if __name__ == "__main__":
    links = get_all_links()
    if not links: print("Нет серверов."); exit()
    working = []
    for i, l in enumerate(links, 1):
        print(f"[{i}/{len(links)}] {l[:50]}...")
        if check(l): working.append(l); print("  ✅ OK")
        else: print("  ❌ FAIL")
    if working: upload("\n".join(working))
    else: print("Рабочих нет, файл не обновляем.")
