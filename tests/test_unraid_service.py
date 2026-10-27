from __future__ import annotations

from ncc_server.unraid_service import _containers, _cpu_temperature, _disks, _network_metrics, _vms


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


def test_unraid_network_uses_one_host_path_and_preserves_exact_counters() -> None:
    metrics = _network_metrics([
        {"name": "eth0", "rxSec": 1000, "txSec": 500, "bytesReceived": "9007199254741000", "bytesSent": "8000"},
        {"name": "br0", "rxSec": 1000, "txSec": 500, "bytesReceived": "9007199254741001", "bytesSent": "8001"},
        {"name": "tailscale1", "rxSec": 400, "txSec": 100, "bytesReceived": "400", "bytesSent": "100"},
        {"name": "docker0", "rxSec": 200, "txSec": 80, "bytesReceived": "200", "bytesSent": "80"},
    ])
    assert metrics == {
        "download_mbps": 0.008,
        "upload_mbps": 0.004,
        "interface": "br0",
        "bytes_recv": 9007199254741001,
        "bytes_sent": 8001,
    }


def test_unraid_network_without_counter_fields_retains_live_rates() -> None:
    metrics = _network_metrics([{"name": "br0", "rxSec": 2500, "txSec": 1250}])
    assert metrics["download_mbps"] == 0.02
    assert metrics["upload_mbps"] == 0.01
    assert "bytes_recv" not in metrics
