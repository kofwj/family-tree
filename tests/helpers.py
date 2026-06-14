def login(client, username="admin", password="TestPass123"):
    response = client.post("/auth/login", data={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def create_member(client, token, **payload):
    response = client.post("/members", json=payload, headers=auth_headers(token))
    assert response.status_code == 200, response.text
    return response.json()
