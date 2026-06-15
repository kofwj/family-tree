import json
import base64
from urllib.parse import quote
from fastapi import APIRouter, Depends, HTTPException, Response
import backend.main as main

router = APIRouter(tags=["map"])

@router.get('/map/search')
def map_search(q: str, limit: int = 10, user: main.User = Depends(main.get_current_user)):
    import urllib.request
    import urllib.error
    encoded_q = quote(q)
    url = f"https://nominatim.openstreetmap.org/search?format=jsonv2&limit={limit}&q={encoded_q}&accept-language=zh-CN"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'FamilyTreeSystem/1.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.URLError as e:
        raise HTTPException(status_code=502, detail=f"无法从上游地图服务获取数据: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get('/map/reverse')
def map_reverse(lat: str, lon: str, user: main.User = Depends(main.get_current_user)):
    import urllib.request
    import urllib.error
    url = f"https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat={quote(lat)}&lon={quote(lon)}&accept-language=zh-CN"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'FamilyTreeSystem/1.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.URLError as e:
        raise HTTPException(status_code=502, detail=f"无法从上游地图服务获取数据: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get('/map/tile/{z}/{x}/{y}.png')
def map_tile(z: int, x: int, y: int, source: str = 'gaode', style: int = 7):
    import urllib.request
    import urllib.error
    if source == 'gaode':
        subdomain = (x % 4) + 1
        url = f"https://wprd0{subdomain}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scl=1&style={style}&x={x}&y={y}&z={z}"
    else:
        subdomains = ['a', 'b', 'c']
        subdomain = subdomains[x % 3]
        url = f"https://{subdomain}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'FamilyTreeSystem/1.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            tile_bytes = response.read()
            return Response(
                content=tile_bytes,
                media_type='image/png',
                headers={'Cache-Control': 'public, max-age=86400'}
            )
    except Exception:
        transparent_1x1 = base64.b64decode(b'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=')
        return Response(content=transparent_1x1, media_type='image/png')
