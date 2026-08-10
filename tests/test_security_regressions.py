import pytest
from helpers import auth_headers, login


def test_non_admin_cannot_see_unauthorized_families(client, app_module):
    # 1. Create a non-admin user and families
    with app_module.Session(app_module.engine) as session:
        viewer_user = app_module.User(
            username="viewer_test",
            display_name="Viewer Test",
            password_hash=app_module.hash_password("ViewerPass123"),
            role="viewer",
            is_active=True
        )
        session.add(viewer_user)
        
        f_auth = app_module.FamilyGroup(name="授权家族", surname="张", is_active=True)
        f_unauth = app_module.FamilyGroup(name="未授权家族", surname="李", is_active=True)
        session.add(f_auth)
        session.add(f_unauth)
        session.commit()
        session.refresh(viewer_user)
        session.refresh(f_auth)
        session.refresh(f_unauth)
        
        # Authorize viewer_user for f_auth
        role = app_module.UserFamilyRole(
            user_id=viewer_user.id,
            family_id=f_auth.id,
            role="viewer"
        )
        session.add(role)
        session.commit()
        
        f_auth_id = f_auth.id
        f_unauth_id = f_unauth.id

    # 2. Login as the non-admin user
    viewer_token = login(client, username="viewer_test", password="ViewerPass123")
    
    # 3. Request families list
    response = client.get("/families", headers=auth_headers(viewer_token))
    assert response.status_code == 200
    families = response.json()
    
    # Verify that f_auth is visible, but f_unauth is not
    family_ids = [f["id"] for f in families]
    assert f_auth_id in family_ids
    assert f_unauth_id not in family_ids
    
    # 4. Request unauthorized family detail directly by ID
    detail_response = client.get(f"/families/{f_unauth_id}", headers=auth_headers(viewer_token))
    assert detail_response.status_code == 403
    
    # 5. Request authorized family detail directly by ID
    auth_detail_response = client.get(f"/families/{f_auth_id}", headers=auth_headers(viewer_token))
    assert auth_detail_response.status_code == 200

    tree_response = client.get(f"/families/{f_unauth_id}/tree", headers=auth_headers(viewer_token))
    assert tree_response.status_code == 403


def test_non_admin_cannot_read_other_family_users(client, app_module):
    # 1. Create a non-admin user and families
    with app_module.Session(app_module.engine) as session:
        viewer_user = app_module.User(
            username="viewer_test_2",
            display_name="Viewer Test 2",
            password_hash=app_module.hash_password("ViewerPass123"),
            role="viewer",
            is_active=True
        )
        session.add(viewer_user)
        
        f_auth = app_module.FamilyGroup(name="授权家族2", surname="张", is_active=True)
        f_unauth = app_module.FamilyGroup(name="未授权家族2", surname="李", is_active=True)
        session.add(f_auth)
        session.add(f_unauth)
        session.commit()
        session.refresh(viewer_user)
        session.refresh(f_auth)
        session.refresh(f_unauth)
        
        # Authorize viewer_user for f_auth
        role = app_module.UserFamilyRole(
            user_id=viewer_user.id,
            family_id=f_auth.id,
            role="viewer"
        )
        session.add(role)
        session.commit()
        
        f_auth_id = f_auth.id
        f_unauth_id = f_unauth.id

    viewer_token = login(client, username="viewer_test_2", password="ViewerPass123")
    
    # 1. Request users of authorized family
    response = client.get(f"/families/{f_auth_id}/users", headers=auth_headers(viewer_token))
    assert response.status_code == 200
    
    # 2. Request users of unauthorized family
    response_unauth = client.get(f"/families/{f_unauth_id}/users", headers=auth_headers(viewer_token))
    assert response_unauth.status_code == 403


def test_backup_upload_exceeds_limit_returns_413(client, app_module, monkeypatch):
    token = login(client)
    
    # Set BACKUP_MAX_BYTES to a tiny value (5 bytes)
    monkeypatch.setattr(app_module, "BACKUP_MAX_BYTES", 5, raising=False)
    
    # Try uploading a mock database backup of 10 bytes
    backup_data = b"sqlite data exceeds 5 bytes"
    response = client.post(
        "/admin/backups/upload",
        files={"file": ("family.db", backup_data, "application/octet-stream")},
        headers=auth_headers(token),
    )
    
    assert response.status_code == 413
    assert "超过" in response.text


def test_family_role_invalid_value_returns_400(client, app_module):
    token = login(client)
    
    with app_module.Session(app_module.engine) as session:
        family = app_module.FamilyGroup(name="测试家族", surname="孙", is_active=True)
        session.add(family)
        test_user = app_module.User(
            username="role_test_user",
            display_name="Role Test",
            password_hash=app_module.hash_password("Pass1234567"),
            role="viewer",
            is_active=True
        )
        session.add(test_user)
        session.commit()
        session.refresh(family)
        session.refresh(test_user)
        
        family_id = family.id
        target_user_id = test_user.id

    # Try assigning invalid role 'hacker'
    response = client.post(
        f"/families/{family_id}/users",
        json={"userId": target_user_id, "role": "hacker"},
        headers=auth_headers(token),
    )
    assert response.status_code == 400
    assert "角色" in response.text or "invalid" in response.text
    
    # Try assigning valid role 'editor'
    response_valid = client.post(
        f"/families/{family_id}/users",
        json={"userId": target_user_id, "role": "editor"},
        headers=auth_headers(token),
    )
    assert response_valid.status_code == 200


def test_cookie_attributes(client, app_module, monkeypatch):
    # Test case 1: SECURE_COOKIE = True
    monkeypatch.setattr(app_module, "SECURE_COOKIE", True, raising=False)
    response = client.post("/auth/login", data={"username": "admin", "password": "TestPass123"})
    assert response.status_code == 200
    cookies = response.headers.get("set-cookie", "")
    assert "access_token=" in cookies
    assert "Secure" in cookies
    assert "HttpOnly" in cookies
    assert "samesite=lax" in cookies.lower()
    assert "path=/" in cookies.lower()

    # Test case 2: SECURE_COOKIE = False
    monkeypatch.setattr(app_module, "SECURE_COOKIE", False, raising=False)
    response2 = client.post("/auth/login", data={"username": "admin", "password": "TestPass123"})
    assert response2.status_code == 200
    cookies2 = response2.headers.get("set-cookie", "")
    assert "access_token=" in cookies2
    assert "Secure" not in cookies2
    assert "HttpOnly" in cookies2
    assert "samesite=lax" in cookies2.lower()
    assert "path=/" in cookies2.lower()


def test_cookie_session_bootstrap(client):
    # Log in and let client capture cookie
    response = client.post("/auth/login", data={"username": "admin", "password": "TestPass123"})
    assert response.status_code == 200
    
    # Verify that requesting /me without Authorization header succeeds using the cookie
    me_resp = client.get("/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["username"] == "admin"

    # Verify that requesting /members works using the cookie
    members_resp = client.get("/members")
    assert members_resp.status_code == 200


def test_ancestry_privacy_and_truncation(client, app_module):
    # Create members A -> B -> C (A is grandparent, B is parent, C is child)
    with app_module.Session(app_module.engine) as session:
        viewer_user = app_module.User(
            username="viewer_ancestry",
            display_name="Viewer Ancestry",
            password_hash=app_module.hash_password("ViewerPass123"),
            role="viewer",
            is_active=True
        )
        session.add(viewer_user)

        family = app_module.FamilyGroup(name="张氏支系", surname="张", is_active=True)
        session.add(family)
        session.commit()
        session.refresh(viewer_user)
        session.refresh(family)

        # Create members
        a = app_module.Member(name="祖先A", gender="男", primary_family_id=family.id, privacy_level="public")
        session.add(a)
        session.commit()
        session.refresh(a)

        b = app_module.Member(name="父亲B", gender="男", father_id=a.id, primary_family_id=family.id, privacy_level="private")
        session.add(b)
        session.commit()
        session.refresh(b)

        c = app_module.Member(name="孩子C", gender="男", father_id=b.id, primary_family_id=family.id, privacy_level="public")
        session.add(c)
        session.commit()
        session.refresh(c)

        viewer_user.member_id = c.id
        session.add(viewer_user)
        
        role = app_module.UserFamilyRole(user_id=viewer_user.id, family_id=family.id, role="viewer")
        session.add(role)
        session.commit()
        
        c_id = c.id
        b_id = b.id
        viewer_id = viewer_user.id

    viewer_token = login(client, username="viewer_ancestry", password="ViewerPass123")

    # Querying other member should return 403 Forbidden
    with app_module.Session(app_module.engine) as session:
        other_fam = app_module.FamilyGroup(name="李氏支系", surname="李", is_active=True)
        session.add(other_fam)
        session.commit()
        session.refresh(other_fam)
        other_member = app_module.Member(name="李某", gender="男", primary_family_id=other_fam.id, privacy_level="public")
        session.add(other_member)
        session.commit()
        session.refresh(other_member)
        other_member_id = other_member.id

    response_403 = client.get(f"/members/{other_member_id}/ancestry", headers=auth_headers(viewer_token))
    assert response_403.status_code == 403

    # Now let's test hard truncation (Scheme A)
    with app_module.Session(app_module.engine) as session:
        db_b = session.get(app_module.Member, b_id)
        db_b.privacy_level = "admin"
        session.add(db_b)
        session.commit()

    # Query ancestry of C: B is invisible ("admin"), so B is truncated, and A (father of B) is also truncated!
    response_trunc = client.get(f"/members/{c_id}/ancestry", headers=auth_headers(viewer_token))
    assert response_trunc.status_code == 200
    res_data = response_trunc.json()
    assert res_data["lines"]["paternal"] == []


def test_startup_side_effects(client, app_module, monkeypatch):
    import backend.helpers
    auto_org_called = False
    heal_called = False

    def mock_auto_org(session):
        nonlocal auto_org_called
        auto_org_called = True

    def mock_heal(session):
        nonlocal heal_called
        heal_called = True

    monkeypatch.setattr(backend.helpers, "run_auto_organization", mock_auto_org)
    monkeypatch.setattr(backend.helpers, "heal_unlinked_relations", mock_heal)

    # Test case 1: env is unset -> should not be called
    monkeypatch.setenv("AUTO_ORGANIZE_ON_STARTUP", "")
    app_module.init_db()
    assert not auto_org_called
    assert not heal_called

    # Test case 2: env is set to 'true' -> should be called
    monkeypatch.setenv("AUTO_ORGANIZE_ON_STARTUP", "true")
    app_module.init_db()
    assert auto_org_called
    assert heal_called


def test_fail_fast_credentials(monkeypatch):
    import subprocess
    import sys
    import os

    env = os.environ.copy()
    env["JWT_SECRET"] = ""
    env["ADMIN_PASSWORD"] = ""
    env.pop("TESTING", None)
    env.pop("PYTEST_CURRENT_TEST", None)
    
    res = subprocess.run(
        [sys.executable, "-c", "import sys; sys.path.insert(0, '.'); import backend.database"],
        cwd="/Users/jian/Downloads/family-tree-system",
        capture_output=True,
        text=True,
        env=env
    )
    assert res.returncode != 0
    assert "RuntimeError" in res.stderr

    env_test = env.copy()
    env_test["TESTING"] = "1"
    res_test = subprocess.run(
        [sys.executable, "-c", "import sys; sys.path.insert(0, '.'); import backend.database"],
        cwd="/Users/jian/Downloads/family-tree-system",
        capture_output=True,
        text=True,
        env=env_test
    )
    assert res_test.returncode == 0


def test_family_editor_cannot_manage_users(client, app_module):
    # 1. Create family, an editor user, an admin user, and a target user
    with app_module.Session(app_module.engine) as session:
        editor_user = app_module.User(
            username="family_editor_test",
            display_name="Family Editor",
            password_hash=app_module.hash_password("EditorPass123"),
            role="viewer",  # global role
            is_active=True
        )
        admin_user = app_module.User(
            username="family_admin_test",
            display_name="Family Admin",
            password_hash=app_module.hash_password("AdminPass123"),
            role="viewer",  # global role
            is_active=True
        )
        target_user = app_module.User(
            username="target_user_test",
            display_name="Target User",
            password_hash=app_module.hash_password("TargetPass123"),
            role="viewer",
            is_active=True
        )
        session.add(editor_user)
        session.add(admin_user)
        session.add(target_user)
        
        family = app_module.FamilyGroup(name="测试管理家族", surname="赵", is_active=True)
        session.add(family)
        session.commit()
        session.refresh(editor_user)
        session.refresh(admin_user)
        session.refresh(target_user)
        session.refresh(family)
        
        # Authorize editor_user as family editor
        role_editor = app_module.UserFamilyRole(
            user_id=editor_user.id,
            family_id=family.id,
            role="editor"
        )
        # Authorize admin_user as family admin
        role_admin = app_module.UserFamilyRole(
            user_id=admin_user.id,
            family_id=family.id,
            role="admin"
        )
        session.add(role_editor)
        session.add(role_admin)
        session.commit()
        
        family_id = family.id
        target_user_id = target_user.id
        editor_id = editor_user.id

    # 2. Login as the family-level editor
    editor_token = login(client, username="family_editor_test", password="EditorPass123")
    
    # Attempt to assign a role to the target user (should be 403)
    response_assign = client.post(
        f"/families/{family_id}/users",
        json={"userId": target_user_id, "role": "viewer"},
        headers=auth_headers(editor_token)
    )
    assert response_assign.status_code == 403

    # Attempt to delete the target user's role (should be 403)
    response_delete = client.delete(
        f"/families/{family_id}/users/{target_user_id}",
        headers=auth_headers(editor_token)
    )
    assert response_delete.status_code == 403

    # 3. Login as the family-level admin
    admin_token = login(client, username="family_admin_test", password="AdminPass123")
    
    # Assign a role to the target user (should succeed)
    response_assign_ok = client.post(
        f"/families/{family_id}/users",
        json={"userId": target_user_id, "role": "viewer"},
        headers=auth_headers(admin_token)
    )
    assert response_assign_ok.status_code == 200

    # Delete the target user's role (should succeed)
    response_delete_ok = client.delete(
        f"/families/{family_id}/users/{target_user_id}",
        headers=auth_headers(admin_token)
    )
    assert response_delete_ok.status_code == 200


def test_family_editor_cannot_modify_structural_fields(client, app_module):
    # 1. Create a family and a family-level editor user
    with app_module.Session(app_module.engine) as session:
        editor_user = app_module.User(
            username="structural_editor_test",
            display_name="Structural Editor",
            password_hash=app_module.hash_password("EditorPass123"),
            role="viewer",  # global role
            is_active=True
        )
        session.add(editor_user)
        
        family = app_module.FamilyGroup(name="旧名称", surname="赵", is_active=True, root_member_id=1, primary_line="paternal")
        session.add(family)
        session.commit()
        session.refresh(editor_user)
        session.refresh(family)
        
        role_editor = app_module.UserFamilyRole(
            user_id=editor_user.id,
            family_id=family.id,
            role="editor"
        )
        session.add(role_editor)
        session.commit()
        
        family_id = family.id

    editor_token = login(client, username="structural_editor_test", password="EditorPass123")

    # 2. Attempt to modify structural fields (e.g. rootMemberId, name) - should be 403
    response_root = client.put(
        f"/families/{family_id}",
        json={"rootMemberId": 999},
        headers=auth_headers(editor_token)
    )
    assert response_root.status_code == 403

    response_name = client.put(
        f"/families/{family_id}",
        json={"name": "新名称"},
        headers=auth_headers(editor_token)
    )
    assert response_name.status_code == 403

    # 3. Attempt to modify descriptive fields (e.g. siteTitle, subtitle, description) - should succeed (200)
    response_desc = client.put(
        f"/families/{family_id}",
        json={"siteTitle": "新网页标题", "description": "新简介"},
        headers=auth_headers(editor_token)
    )
    assert response_desc.status_code == 200
    
    with app_module.Session(app_module.engine) as session:
        db_family = session.get(app_module.FamilyGroup, family_id)
        assert db_family.site_title == "新网页标题"
        assert db_family.description == "新简介"
        # Confirm structural fields remained unchanged
        assert db_family.name == "旧名称"
        assert db_family.root_member_id == 1


