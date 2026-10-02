from __future__ import annotations

from ncc_server.unraid_service import _containers, _cpu_temperature, _disks, _vms


def test_unraid_storage_preserves_spindown_and_temperatures() -> None:
    disks = _disks(
        {
            "caches": [
                {"name": "cache", "fsSize": 100 * 1024**3, "fsUsed": 20 * 1024**3, "temp": 31}
            ],
            "disks": [
                {"idx": 1, "fsSize": 200 * 1024**3, "fsUsed": 100 * 1024**3, "temp": 42, "isSpinning": True},
                {"idx": 2, "fsSize": 200 * 1024**3, "fsUsed": 50 * 1024**3, "temp": 0, "isSpinning": False},
            ],
        }
    )

    assert [disk["name"] for disk in disks] == ["Cache", "Disk 1", "Disk 2"]
    assert disks[0]["temperature_c"] == 31.0
    assert disks[1]["temperature_c"] == 42.0
    assert disks[2]["temperature_c"] is None
    assert disks[2]["spinning"] is False


def test_unraid_workloads_use_short_dashboard_records() -> None:
    assert _vms({"domains": [{"name": "Home Assistant", "state": "RUNNING"}]}) == [
        {"name": "Home Assistant", "state": "RUNNING"}
    ]
    assert _containers({"containers": [{"names": ["/plex"], "state": "running", "status": "Up 3 hours", "autoStart": True}]}) == [
        {"name": "plex", "state": "running", "status": "Up 3 hours", "auto_start": True}
    ]


def test_unraid_cpu_temperature_uses_the_hottest_package_sensor() -> None:
    assert _cpu_temperature({"packages": {"temp": [47, 61, 58]}}) == 61.0
