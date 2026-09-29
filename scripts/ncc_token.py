from __future__ import annotations

import argparse
import os
import secrets
from pathlib import Path

DEFAULT_ENV = Path(__file__).resolve().parents[1] / ".env"


def read_token(env_path: Path) -> str:
    if not env_path.exists():
        return ""
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("NCC_TOKEN="):
            return line.partition("=")[2].strip()
    return ""


def write_token(env_path: Path, token: str) -> None:
    if len(token) < 32 or any(char.isspace() for char in token):
        raise ValueError("Ein NCC-Token muss mindestens 32 Zeichen lang sein und darf keine Leerzeichen enthalten.")
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    updated: list[str] = []
    replaced = False
    for line in lines:
        if line.startswith("NCC_TOKEN="):
            updated.append(f"NCC_TOKEN={token}")
            replaced = True
        else:
            updated.append(line)
    if not replaced:
        updated.append(f"NCC_TOKEN={token}")
    env_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = env_path.with_suffix(env_path.suffix + ".tmp")
    temporary.write_text("\n".join(updated) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(env_path)


def export_token(path: Path, token: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(token + "\n", encoding="utf-8")
    os.chmod(path, 0o600)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="NCC-Token sicher erzeugen, importieren und exportieren")
    result.add_argument("--env", type=Path, default=DEFAULT_ENV, help="Pfad zur NCC-.env-Datei")
    commands = result.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate", help="Neuen Token erzeugen")
    generate.add_argument("--force", action="store_true", help="Vorhandenen Token ersetzen")
    generate.add_argument("--export", type=Path, help="Token zusätzlich in eine Übergabedatei schreiben")
    commands.add_parser("show", help="Aktuellen Token anzeigen")
    commands.add_parser("value", help=argparse.SUPPRESS)
    export = commands.add_parser("export", help="Aktuellen Token in eine Übergabedatei schreiben")
    export.add_argument("path", type=Path)
    import_file = commands.add_parser("import-file", help="Token aus einer Übergabedatei übernehmen")
    import_file.add_argument("path", type=Path)
    import_value = commands.add_parser("import-value", help="Übergebenen Token übernehmen")
    import_value.add_argument("token")
    commands.add_parser("check", help="Prüfen, ob ein Token konfiguriert ist")
    return result


def main() -> int:
    args = parser().parse_args()
    token = read_token(args.env)
    if args.command == "generate":
        if token and not args.force:
            print("Es existiert bereits ein NCC_TOKEN. Nutze --force zum Ersetzen.")
            return 2
        token = secrets.token_urlsafe(32)
        write_token(args.env, token)
        if args.export:
            export_token(args.export, token)
            print(f"Übergabedatei erstellt: {args.export}")
        print(f"Neuer NCC_TOKEN: {token}")
        print("Nach einer Rotation müssen Server und alle Clients neu gestartet werden.")
        return 0
    if args.command in {"show", "value", "check", "export"} and not token:
        if args.command != "value":
            print("Kein NCC_TOKEN konfiguriert.")
        return 1
    if args.command in {"show", "value"}:
        print(token)
        return 0
    if args.command == "check":
        print("NCC_TOKEN ist konfiguriert.")
        return 0
    if args.command == "export":
        export_token(args.path, token)
        print(f"Übergabedatei erstellt: {args.path}")
        print("Datei nach dem Import auf dem Client sicher löschen.")
        return 0
    if args.command == "import-file":
        imported = args.path.read_text(encoding="utf-8").strip()
        write_token(args.env, imported)
        print("NCC_TOKEN wurde aus der Übergabedatei importiert.")
        return 0
    if args.command == "import-value":
        write_token(args.env, args.token.strip())
        print("NCC_TOKEN wurde übernommen.")
        return 0
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as error:
        print(f"Fehler: {error}")
        raise SystemExit(2) from None
