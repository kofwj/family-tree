import os
import urllib.request, urllib.parse, json

BASE = os.environ.get("API_BASE", "http://localhost:3000")


def env_value(key, default=None):
    if key in os.environ:
        return os.environ[key]
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    try:
        with open(env_path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                k, v = line.split('=', 1)
                if k == key:
                    return v
    except FileNotFoundError:
        pass
    return default

ADMIN_USERNAME = env_value('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = env_value('ADMIN_PASSWORD')
if not ADMIN_PASSWORD:
    raise RuntimeError('请先设置 ADMIN_PASSWORD 环境变量，或在本地 .env 中配置 ADMIN_PASSWORD')


def login():
    data = urllib.parse.urlencode({"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}).encode()
    req = urllib.request.Request(BASE + "/auth/login", data=data, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"error": e.code, "detail": e.read().decode()}

def api(path, method="GET", data=None, token=None):
    url = BASE + path
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = None
    if data:
        headers["Content-Type"] = "application/json"
        body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return {"error": e.code, "detail": e.read().decode()}

login = login()
print("LOGIN:", login)
token = login["access_token"]

# GET /members/1
m1 = api("/members/1", token=token)
print("GET/1:", m1.get("name"), "spouse:", m1.get("spouse"), "father:", m1.get("fatherName"))

# CREATE
new = api("/members", method="POST", data={
    "name": "测试验收", "gender": "男", "generation": 3,
    "spouse_name": "验收配偶", "father_name": "王金龙"
}, token=token)
print("CREATE:", new.get("name"), "id:", new.get("id"))
new_id = new.get("id")

if new_id:
    upd = api(f"/members/{new_id}", method="PUT", data={
        "name": "测试验收改", "gender": "男", "generation": 5,
    }, token=token)
    print("UPDATE:", upd.get("name"), "gen:", upd.get("generation"))

    d = api(f"/members/{new_id}", method="DELETE", token=token)
    print("DELETE:", d.get("ok"))

    # verify deleted
    check = api(f"/members/{new_id}", token=token)
    print("CHECK DELETED:", check.get("error"), check.get("detail", "")[:50])