@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0backup_ncc_postgres.ps1" -InstallSchedule -RetentionDays 14
