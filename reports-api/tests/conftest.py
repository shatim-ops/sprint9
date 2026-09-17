import time
from datetime import date, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app import auth, config
from app.main import app
from app.storage import get_storage

PROCESSED_UNTIL = date(2026, 9, 16)

private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
foreign_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class FakeSigningKey:
    key = private_key.public_key()


class FakeJwks:
    def get_signing_key_from_jwt(self, token):
        return FakeSigningKey()


class FakeStorage:
    """Витрина в памяти: по два дня на протез, у prothetic1 два протеза."""

    def __init__(self, until=PROCESSED_UNTIL):
        self.until = until
        self.requested = []

    def processed_until(self):
        return self.until

    def daily_rows(self, login, date_from, date_to):
        self.requested.append((login, date_from, date_to))
        owners = {"prothetic1": [1, 2], "prothetic2": [3]}
        rows = []
        for prosthesis_id in owners.get(login, []):
            for offset in (1, 0):
                day = PROCESSED_UNTIL - timedelta(days=offset)
                if date_from <= day <= date_to:
                    rows.append({
                        "prosthesis_id": prosthesis_id, "serial_number": f"BP-{prosthesis_id}",
                        "model": "BionicHand 2", "side": "right", "report_date": day,
                        "movements_total": 100, "movements_failed": 5,
                        "avg_response_ms": 70.0, "p95_response_ms": 110.0, "max_response_ms": 150,
                        "slow_responses": 10, "active_hours": 16, "battery_min": 12,
                        "battery_avg": 55.0, "avg_signal_noise": 0.17, "top_movement": "grip",
                    })
        return rows


def make_token(login="prothetic1", roles=("prothetic_user",), key=private_key, **overrides):
    now = int(time.time())
    claims = {
        "iss": config.KEYCLOAK_ISSUER, "iat": now, "exp": now + 300,
        "azp": "reports-frontend", "preferred_username": login,
        "realm_access": {"roles": list(roles)},
    }
    claims.update(overrides)
    return jwt.encode(claims, key, algorithm="RS256")


@pytest.fixture
def storage():
    return FakeStorage()


@pytest.fixture
def client(storage, monkeypatch):
    monkeypatch.setattr(auth, "jwks_client", FakeJwks())
    app.dependency_overrides[get_storage] = lambda: storage
    yield TestClient(app)
    app.dependency_overrides.clear()


def bearer(token):
    return {"Authorization": f"Bearer {token}"}
