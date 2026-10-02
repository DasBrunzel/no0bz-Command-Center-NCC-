from __future__ import annotations

from ncc_server.unraid_service import _disks


def test_array_capacity_becomes_a_dashboard_disk() -> None:
    disks = _disks(
        {
            "state": "STARTED",
            "capacity": {"kilobytes": {"total": 2 * 1024 * 1024, "used": 1024 * 1024}},
        }
    )

    assert disks == [
        {
            "name": "Unraid Array",
            "mount": "Array",
            "percent": 50.0,
            "total_gb": 2.0,
            "used_gb": 1.0,
            "temperature_c": None,
            "status": "STARTED",
            "fstype": "unraid",
        }
    ]
