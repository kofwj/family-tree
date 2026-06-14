import pandas as pd
import pytest

from helpers import auth_headers, create_member, login


def test_settings_requires_authentication(client):
    response = client.get("/settings")
    assert response.status_code in (401, 403)


def test_public_settings_is_anonymous_and_allowlisted(client):
    response = client.get("/public-settings")
    assert response.status_code == 200
    assert set(response.json()) == {"siteTitle", "familySurname", "subtitle", "coverKicker"}


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
