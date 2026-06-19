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
