import time

from conftest import FakeStorage, bearer, foreign_key, make_token

from app.main import app
from app.storage import get_storage


def test_no_token(client):
    assert client.get("/reports").status_code == 401


def test_token_signed_by_other_key(client):
    assert client.get("/reports", headers=bearer(make_token(key=foreign_key))).status_code == 401


def test_expired_token(client):
    token = make_token(iat=int(time.time()) - 600, exp=int(time.time()) - 300)
    assert client.get("/reports", headers=bearer(token)).status_code == 401


def test_wrong_issuer(client):
    token = make_token(iss="http://evil.example/realms/reports-realm")
    assert client.get("/reports", headers=bearer(token)).status_code == 401


def test_token_of_other_client(client):
    assert client.get("/reports", headers=bearer(make_token(azp="some-other-app"))).status_code == 401


def test_role_required(client):
    token = make_token(login="user1", roles=("user",))
    assert client.get("/reports", headers=bearer(token)).status_code == 403


def test_own_report(client, storage):
    response = client.get("/reports", headers=bearer(make_token()))
    assert response.status_code == 200
    body = response.json()
    assert body["user"] == "prothetic1"
    assert [p["prosthesis_id"] for p in body["prostheses"]] == [1, 2]
    assert body["prostheses"][0]["summary"]["movements_total"] == 200
    # в базу ушёл логин из токена и ничего другого
    assert {login for login, _, _ in storage.requested} == {"prothetic1"}


def test_other_user_report_forbidden(client, storage):
    response = client.get("/reports/prothetic2", headers=bearer(make_token(login="prothetic1")))
    assert response.status_code == 403
    assert storage.requested == []


def test_own_report_by_login(client):
    response = client.get("/reports/prothetic2", headers=bearer(make_token(login="prothetic2")))
    assert response.status_code == 200
    assert response.json()["user"] == "prothetic2"


def test_period_is_cut_by_processed_date(client, storage):
    response = client.get(
        "/reports", params={"date_from": "2026-09-15", "date_to": "2026-09-30"}, headers=bearer(make_token())
    )
    period = response.json()["period"]
    assert period["date_to"] == "2026-09-16"
    assert period["truncated"] is True
    assert storage.requested[0][2].isoformat() == "2026-09-16"


def test_period_not_processed_yet(client, storage):
    response = client.get("/reports", params={"date_from": "2026-09-17"}, headers=bearer(make_token()))
    assert response.status_code == 404
    assert "2026-09-16" in response.json()["detail"]
    assert storage.requested == []


def test_mart_is_empty(client):
    app.dependency_overrides[get_storage] = lambda: FakeStorage(until=None)
    assert client.get("/reports", headers=bearer(make_token())).status_code == 404


def test_user_without_telemetry(client):
    response = client.get("/reports", headers=bearer(make_token(login="prothetic3")))
    assert response.status_code == 404


def test_bad_period(client):
    response = client.get(
        "/reports", params={"date_from": "2026-09-16", "date_to": "2026-09-10"}, headers=bearer(make_token())
    )
    assert response.status_code == 400
