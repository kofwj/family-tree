import pandas as pd
import pytest

from helpers import auth_headers, create_member, login


def test_settings_requires_authentication(client):
    response = client.get("/settings")
    assert response.status_code in (401, 403)


def test_public_settings_is_anonymous_and_allowlisted(client):
    response = client.get("/public-settings")
    assert response.status_code == 200
    assert set(response.json()) == {"siteTitle", "familySurname", "subtitle", "coverKicker", "treeDescription"}


def test_member_photo_requires_member_visibility(client):
    token = login(client)
    member = create_member(client, token, name="隐私成员", gender="男", generation=1)
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
    uploaded = client.post(
        f"/members/{member['id']}/photo",
        files={"file": ("avatar.png", png, "image/png")},
        headers=auth_headers(token),
    )
    assert uploaded.status_code == 200, uploaded.text
    photo_path = uploaded.json()["photoUrl"]

    client.cookies.clear()
    anonymous = client.get(photo_path.replace("/api", ""))
    assert anonymous.status_code in (401, 403)


def test_rejects_parent_cycle(client):
    token = login(client)
    parent = create_member(client, token, name="父", gender="男", generation=1)
    child = create_member(client, token, name="子", gender="男", generation=2, father_id=parent["id"])

    response = client.put(
        f"/members/{parent['id']}",
        json={"father_id": child["id"]},
        headers=auth_headers(token),
    )
    assert response.status_code == 400
    assert "循环" in response.text or "后代" in response.text


def test_failed_replace_import_keeps_existing_members_and_links(client, app_module, monkeypatch, tmp_path):
    token = login(client)
    existing = create_member(client, token, name="原成员", gender="男", generation=1)
    with app_module.Session(app_module.engine) as session:
        source = app_module.SourceRecord(title="原资料")
        session.add(source)
        session.commit()
        session.refresh(source)
        session.add(app_module.Citation(member_id=existing["id"], source_id=source.id, field_name="name"))
        session.commit()

    good_df = pd.DataFrame([
        {"姓名": "新成员", "性别": "男", "世代": 1, "字辈": "", "排行序号": "", "排行称谓": "", "出生日期": "", "去世日期": "", "出生地": "", "去世地": "", "现居住地": "", "配偶": "", "父亲": "", "母亲": ""}
    ])
    bad_path = tmp_path / "bad.xlsx"
    good_df.to_excel(bad_path, index=False)

    original_iterrows = pd.DataFrame.iterrows

    def exploding_iterrows(self):
        raise RuntimeError("simulated import failure")
        yield from original_iterrows(self)

    monkeypatch.setattr(pd.DataFrame, "iterrows", exploding_iterrows)
    with pytest.raises(RuntimeError):
        app_module.import_excel(str(bad_path), replace=True)

    with app_module.Session(app_module.engine) as session:
        members = session.exec(app_module.select(app_module.Member)).all()
        citations = session.exec(app_module.select(app_module.Citation)).all()
        assert [m.name for m in members] == ["原成员"]
        assert len(citations) == 1
        assert citations[0].member_id == existing["id"]


def test_successful_replace_import_clears_member_dependent_records(client, app_module, tmp_path):
    token = login(client)
    existing = create_member(client, token, name="原成员", gender="男", generation=1)
    with app_module.Session(app_module.engine) as session:
        source = app_module.SourceRecord(title="原资料")
        session.add(source)
        session.commit()
        session.refresh(source)
        session.add(app_module.Citation(member_id=existing["id"], source_id=source.id, field_name="name"))
        session.add(app_module.ReviewRequest(member_id=existing["id"], payload_json="{}"))
        user = session.exec(app_module.select(app_module.User).where(app_module.User.username == "admin")).first()
        user.member_id = existing["id"]
        session.add(user)
        session.commit()

    df = pd.DataFrame([
        {"姓名": "新成员", "性别": "男", "世代": 1, "字辈": "", "排行序号": "", "排行称谓": "", "出生日期": "", "去世日期": "", "出生地": "", "去世地": "", "现居住地": "", "配偶": "", "父亲": "", "母亲": ""}
    ])
    path = tmp_path / "good.xlsx"
    df.to_excel(path, index=False)

    count = app_module.import_excel(str(path), replace=True)
    assert count == 1

    with app_module.Session(app_module.engine) as session:
        members = session.exec(app_module.select(app_module.Member)).all()
        citations = session.exec(app_module.select(app_module.Citation)).all()
        reviews = session.exec(app_module.select(app_module.ReviewRequest)).all()
        user = session.exec(app_module.select(app_module.User).where(app_module.User.username == "admin")).first()
        assert [m.name for m in members] == ["新成员"]
        assert citations == []
        assert reviews == []
        assert user.member_id is None


def test_approve_review_request_blocks_relationship_cycle(client, app_module):
    token = login(client)
    a = create_member(client, token, name="成员A", gender="男", generation=1)
    b = create_member(client, token, name="成员B", gender="男", generation=2)
    with app_module.Session(app_module.engine) as session:
        req = app_module.ReviewRequest(
            actor_user_id=1,
            actor_username="editor",
            actor_role="editor",
            member_id=a["id"],
            target_label=a["name"],
            payload_json=f'{{"father_id": {b["id"]}}}',
            diff_json="{}",
            status="pending"
        )
        session.add(req)
        session.commit()
        req_id = req.id
        b_member = session.get(app_module.Member, b["id"])
        b_member.father_id = a["id"]
        session.add(b_member)
        session.commit()
    response = client.post(f"/admin/review-requests/{req_id}/approve", headers=auth_headers(token))
    assert response.status_code == 400
    assert "循环" in response.text or "后代" in response.text


def test_editor_can_set_relationships_on_creation(client, app_module):
    admin_token = login(client)
    response = client.post("/admin/users", json={
        "username": "editor1",
        "password": "EditorPass123!",
        "display_name": "编辑者",
        "role": "editor",
        "is_active": True
    }, headers=auth_headers(admin_token))
    assert response.status_code == 200, response.text
    editor_token = login(client, username="editor1", password="EditorPass123!")
    a = create_member(client, admin_token, name="老员A", gender="男")
    b = create_member(client, admin_token, name="老员B", gender="女")
    
    # 绑定 editor 到成员 A，从而授权其分支范围，并在 UserFamilyRole 中分配其为此家族的编辑者
    with app_module.Session(app_module.engine) as session:
        db_user = session.exec(app_module.select(app_module.User).where(app_module.User.username == "editor1")).first()
        db_user.member_id = a["id"]
        session.add(db_user)
        role = app_module.UserFamilyRole(user_id=db_user.id, family_id=a["primaryFamilyId"], role="editor")
        session.add(role)
        session.commit()

    response = client.post("/members", json={
        "name": "新员C",
        "gender": "男",
        "father_id": a["id"],
        "spouse_ids": [b["id"]]
    }, headers=auth_headers(editor_token))
    assert response.status_code == 200, response.text
    c = response.json()
    assert c["fatherId"] == a["id"]
    assert c["spouseIds"] == [b["id"]]


def test_get_member_photo_supports_custom_path_formats(client, app_module):
    token = login(client)
    m = create_member(client, token, name="照片测试成员", gender="男")
    with app_module.Session(app_module.engine) as session:
        db_m = session.get(app_module.Member, m["id"])
        db_m.photo_path = "test_avatar_xyz.png"
        session.add(db_m)
        session.commit()
    photo_file = app_module.PHOTO_DIR / "test_avatar_xyz.png"
    photo_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
    response = client.get("/member-photos/test_avatar_xyz.png", headers=auth_headers(token))
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"


def test_delete_member_cleans_up_family_links(client, app_module):
    token = login(client)
    response = client.get("/families", headers=auth_headers(token))
    family_id = response.json()[0]["id"]
    m = create_member(client, token, name="被删成员", gender="男", primary_family_id=family_id)
    with app_module.Session(app_module.engine) as session:
        links = session.exec(app_module.select(app_module.MemberFamilyLink).where(app_module.MemberFamilyLink.member_id == m["id"])).all()
        assert len(links) == 1
    del_resp = client.delete(f"/members/{m['id']}", headers=auth_headers(token))
    assert del_resp.status_code == 200
    with app_module.Session(app_module.engine) as session:
        links = session.exec(app_module.select(app_module.MemberFamilyLink).where(app_module.MemberFamilyLink.member_id == m["id"])).all()
        assert len(links) == 0


def test_excel_import_resolves_duplicate_names_and_family_restriction(client, app_module, tmp_path):
    token = login(client)
    response = client.get("/families", headers=auth_headers(token))
    primary_family_id = response.json()[0]["id"]
    with app_module.Session(app_module.engine) as session:
        extra_family = app_module.FamilyGroup(name="王氏家族", surname="王", is_primary=False)
        session.add(extra_family)
        session.commit()
        session.refresh(extra_family)
        extra_family_id = extra_family.id
        ts_g2 = app_module.Member(name="张三", gender="男", generation=2, primary_family_id=primary_family_id)
        ts_g4 = app_module.Member(name="张三", gender="男", generation=4, primary_family_id=primary_family_id)
        ts_extra = app_module.Member(name="张三", gender="男", generation=4, primary_family_id=extra_family_id)
        session.add(ts_g2)
        session.add(ts_g4)
        session.add(ts_extra)
        session.commit()
        ts_g2_id = ts_g2.id
        ts_g4_id = ts_g4.id
    df = pd.DataFrame([
        {
            "姓名": "张子", "性别": "男", "世代": 5, "字辈": "", "排行序号": "", "排行称谓": "",
            "出生日期": "", "去世日期": "", "出生地": "", "去世地": "", "现居住地": "",
            "配偶": "", "父亲": "张三", "母亲": ""
        }
    ])
    path = tmp_path / "dup_names.xlsx"
    df.to_excel(path, index=False)
    count = app_module.import_excel(str(path), replace=False)
    assert count == 1
    with app_module.Session(app_module.engine) as session:
        child = session.exec(app_module.select(app_module.Member).where(app_module.Member.name == "张子")).first()
        assert child is not None
        assert child.father_id == ts_g4_id



