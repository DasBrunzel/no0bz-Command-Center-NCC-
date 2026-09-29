from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from ncc.app import app
from ncc.config import get_settings
from ncc.models import Profile
from pydantic import ValidationError


def test_profile_limits_user_content() -> None:
    with pytest.raises(ValidationError):
        Profile(alias="x" * 49, pc_name="pc")


def test_profile_get_returns_persisted_profile() -> None:
    payload = {"alias": "Commander", "pc_name": "Nightmare", "avatar": "crown", "role": "admin", "bio": "NCC"}
    with TestClient(app, base_url="http://127.0.0.1:8350") as client:
        saved = client.post("/api/profile", json=payload, headers={"X-NCC-Token": get_settings().token})
        assert saved.status_code == 200
        response = client.get("/api/profile")
        assert response.status_code == 200
        assert response.json() == payload

