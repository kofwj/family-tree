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


data = urllib.parse.urlencode({"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD}).encode()
req = urllib.request.Request(BASE + "/auth/login", data=data, method="POST")
token = json.loads(urllib.request.urlopen(req).read())["access_token"]

def api(path):
    req = urllib.request.Request(BASE + path, headers={"Authorization": f"Bearer {token}"})
    return json.loads(urllib.request.urlopen(req).read())

# Get tree
tree = api("/tree")

def find(nodes, name, path=""):
    res = []
    for n in nodes:
        p = f"{path}/{n['name']}" if path else n['name']
        if name in n.get('name', ''):
            res.append((n, p))
        if 'children' in n:
            res.extend(find(n['children'], name, p))
    return res

print("=== 成小青 ===")
results = find(tree, '成小青')
for n, p in results:
    print(f"\nPath: {p}")
    print(f"  id={n['id']} name={n['name']} gen={n.get('generation')} fatherId={n.get('fatherId')}")
    spouses = n.get('spouses', [])
    print(f"  spouses={spouses}")
    for c in n.get('children', []):
        print(f"  child: id={c['id']} name={c['name']} gen={c.get('generation')} fatherId={c.get('fatherId')} motherId={c.get('motherId')}")


# Check members with 成 in their data
members = api("/members")
print("\n=== Members with 成 ===")
for m in members:
    if '成' in str(m.values()):
        print(f"  id={m['id']} name={m['name']} gen={m.get('generation')} fatherName={m.get('fatherName')} motherName={m.get('motherName')}")

# Also check 孙永芳's children (the other spouse case)
results2 = find(tree, '孙永芳')
print("\n=== 孙永芳 ===")
for n, p in results2:
    print(f"Path: {p}")
    print(f"  id={n['id']} name={n['name']}")
    for c in n.get('children', []):
        print(f"  child: id={c['id']} name={c['name']} gen={c.get('generation')} fatherId={c.get('fatherId')} motherId={c.get('motherId')}")

# Check all roots
print("\n=== ROOT NODES ===")
for n in tree:
    print(f"  id={n['id']} name={n['name']} gen={n.get('generation')}")
    for c in n.get('children', [])[:3]:
        print(f"    {c['name']} gen={c.get('generation')}")