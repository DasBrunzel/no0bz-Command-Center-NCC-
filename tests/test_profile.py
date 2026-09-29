from __future__ import annotations

import pytest
from ncc.models import Profile
from pydantic import ValidationError


def test_profile_limits_user_content() -> None:
    with pytest.raises(ValidationError):
        Profile(alias="x" * 49, pc_name="pc")

