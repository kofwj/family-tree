import sqlite3

import pandas as pd
from fastapi.testclient import TestClient

from helpers import auth_headers, create_member, login


def make_excel_bytes(tmp_path):
    df = pd.DataFrame([
        {"姓名": "新成员", "性别": "男", "世代": 1, "字辈": "", "排行序号": "", "排行称谓": "", "出生日期": "", "去世日期": "", "出生地": "", "去世地": "", "现居住地": "", "配偶": "", "父亲": "", "母亲": ""}
    ])
    path = tmp_path / "members.xlsx"
    df.to_excel(path, index=False)
    return path.read_bytes()


def test_excel_upload_rejects_non_xlsx_extension(client, tmp_path):
    token = login(client)
    content = make_excel_bytes(tmp_path)

    response = client.post(
        "/import/excel",
        files={"file": ("members.txt", content, "text/plain")},
        headers=auth_headers(token),
    )

    assert response.status_code == 400
    assert "Excel" in response.text or "xlsx" in response.text


def test_excel_upload_rejects_oversized_file(client, app_module, tmp_path, monkeypatch):
    token = login(client)
    monkeypatch.setattr(app_module, "EXCEL_MAX_BYTES", 8, raising=False)
    content = make_excel_bytes(tmp_path)

    response = client.post(
        "/import/excel",
        files={"file": ("members.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        headers=auth_headers(token),
    )

    assert response.status_code == 413
    assert "超过" in response.text


def test_delete_member_referenced_as_parent_is_blocked(client):
    token = login(client)
    parent = create_member(client, token, name="父", gender="男", generation=1)
    create_member(client, token, name="子", gender="男", generation=2, father_id=parent["id"])

    response = client.delete(f"/members/{parent['id']}", headers=auth_headers(token))

    assert response.status_code == 409
    assert "子女" in response.text or "引用" in response.text


def test_restore_rejects_corrupt_sqlite_backup(client, app_module):
    token = login(client)
    corrupt = app_module.BACKUP_DIR / "family-20260101-000000-manual.db"
    corrupt.write_bytes(b"not a sqlite database")

    response = client.post(f"/admin/restore/{corrupt.name}", headers=auth_headers(token))

    assert response.status_code == 400
    assert "备份" in response.text and ("无效" in response.text or "损坏" in response.text)


def test_restore_rejects_sqlite_backup_missing_required_tables(client, app_module):
    token = login(client)
    invalid_schema = app_module.BACKUP_DIR / "family-20260101-000001-manual.db"
    conn = sqlite3.connect(invalid_schema)
    conn.execute("create table unrelated (id integer primary key)")
    conn.commit()
    conn.close()

    response = client.post(f"/admin/restore/{invalid_schema.name}", headers=auth_headers(token))

    assert response.status_code == 400
    assert "表结构" in response.text or "缺少" in response.text


def test_failed_restore_keeps_current_database_usable(app_module, monkeypatch):
    client = TestClient(app_module.app, raise_server_exceptions=False)
    token = login(client)
    existing = create_member(client, token, name="当前成员", gender="男", generation=1)
    backup = app_module.BACKUP_DIR / "family-20260101-000002-manual.db"
    sqlite3.connect(backup).close()
    app_module.SQLModel.metadata.create_all(app_module.create_engine(f"sqlite:///{backup}", connect_args={"check_same_thread": False}))

    real_replace = app_module.os.replace

    failed_once = False

    def corrupt_live_db_on_atomic_replace(src, dst, *args, **kwargs):
        nonlocal failed_once
        if str(dst) == str(app_module.sqlite_path()) and not failed_once:
            failed_once = True
            app_module.sqlite_path().write_bytes(b"not a sqlite database")
            raise OSError("simulated interrupted atomic replace")
        return real_replace(src, dst, *args, **kwargs)

    monkeypatch.setattr(app_module.os, "replace", corrupt_live_db_on_atomic_replace)

    response = client.post(f"/admin/restore/{backup.name}", headers=auth_headers(token))

    assert response.status_code >= 500
    with app_module.Session(app_module.engine) as session:
        member = session.get(app_module.Member, existing["id"])
        assert member is not None
        assert member.name == "当前成员"


def test_spouse_marriage_details_synchronization(client):
    token = login(client)
    
    # 1. Create husband and wife, linking them as spouses
    husband = create_member(client, token, name="张三", gender="男", generation=1)
    wife = create_member(client, token, name="李四", gender="女", generation=1, spouse_ids=[husband["id"]])
    
    # Verify that spouse link is created on husband too
    h_member = client.get(f"/members/{husband['id']}", headers=auth_headers(token)).json()
    assert wife["id"] in h_member["spouseIds"]
    
    # 2. Update husband's marriage year and note
    payload = {
        "marriage_year": "1999",
        "marriage_note": "原配",
    }
    client.put(f"/members/{husband['id']}", json=payload, headers=auth_headers(token))
    
    # Verify that wife's marriage details were updated automatically
    w_member = client.get(f"/members/{wife['id']}", headers=auth_headers(token)).json()
    assert w_member["marriageYear"] == "1999"
    assert w_member["marriageNote"] == "原配"


def test_map_proxy_endpoints(client, monkeypatch):
    token = login(client)
    
    class MockResponse:
        def __init__(self, data_bytes):
            self.data_bytes = data_bytes
        def read(self):
            return self.data_bytes
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    def mock_urlopen(req, timeout=None):
        if "search" in req.full_url:
            return MockResponse(b'[{"place_id":123,"lat":"1.0","lon":"2.0","display_name":"Mock Place"}]')
        elif "reverse" in req.full_url:
            return MockResponse(b'{"place_id":123,"lat":"1.0","lon":"2.0","display_name":"Mock Place"}')
        elif "appmaptile" in req.full_url or "tile.openstreetmap.org" in req.full_url:
            return MockResponse(b'fake_tile_bytes')
        raise ValueError("Unexpected url")

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

    # Test Search
    res_search = client.get("/map/search?q=Beijing", headers=auth_headers(token))
    assert res_search.status_code == 200
    assert res_search.json()[0]["display_name"] == "Mock Place"

    # Test Reverse
    res_reverse = client.get("/map/reverse?lat=1.0&lon=2.0", headers=auth_headers(token))
    assert res_reverse.status_code == 200
    assert res_reverse.json()["display_name"] == "Mock Place"

    # Test Tile Proxy (Gaode)
    res_tile_gaode = client.get("/map/tile/11/1713/796.png?source=gaode", headers=auth_headers(token))
    assert res_tile_gaode.status_code == 200
    assert res_tile_gaode.content == b'fake_tile_bytes'
    assert res_tile_gaode.headers['content-type'] == 'image/png'

    # Test Tile Proxy (OSM)
    res_tile_osm = client.get("/map/tile/11/1713/796.png?source=osm", headers=auth_headers(token))
    assert res_tile_osm.status_code == 200
    assert res_tile_osm.content == b'fake_tile_bytes'
    assert res_tile_osm.headers['content-type'] == 'image/png'



