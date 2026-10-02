from pathlib import Path


def test_windows_backup_script_installs_daily_retained_backup_task() -> None:
    script = (Path(__file__).parents[1] / "scripts" / "backup_ncc_postgres.ps1").read_text(encoding="utf-8")

    assert "[int]$RetentionDays = 14" in script
    assert 'New-ScheduledTaskTrigger -Daily -At 3:30AM' in script
    assert 'TaskName "NCC PostgreSQL Backup"' in script
    assert 'UserId "SYSTEM"' in script
    assert 'Join-Path $root "backups"' in script
    assert "PGPASSWORD" in script
    assert "--dbname=$databaseUrl" not in script


def test_telegram_setup_script_keeps_the_secret_out_of_the_dashboard() -> None:
    script = (Path(__file__).parents[1] / "scripts" / "configure_ncc_telegram.ps1").read_text(
        encoding="utf-8"
    )

    assert "Read-Host \"Bot-Token\" -AsSecureString" in script
    assert "getUpdates" in script
    assert "NCC_SERVER_TELEGRAM_BOT_TOKEN" in script
    assert "Restart-Service -Name \"NccServer\"" in script
