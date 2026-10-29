"""Detect a running game from installed launcher libraries.

The provider only reads launcher manifests, the registry and the process list.
It never attaches to, injects into or inspects a game process, so anti-cheat
systems see nothing but an ordinary process enumeration.
"""

from __future__ import annotations

import json
import os
import platform
import re
import string
import time
import xml.etree.ElementTree as ElementTree
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psutil

from ncc.collectors.base import Capabilities, SensorProvider

# Installed libraries rarely change; re-reading them every sample would only
# cost disk I/O.
LIBRARY_REFRESH_SECONDS = 300.0

# Steam "apps" that are tools rather than games.
EXCLUDED_STEAM_APP_IDS = frozenset({
    "228980",  # Steamworks Common Redistributables
    "431960",  # Wallpaper Engine
    "1070560", "1391110", "1628350",  # Steam Linux Runtime
    "250820",  # SteamVR
    "1905180",  # OBS Studio
    "993090",  # Lossless Scaling, runs next to the actual game
})
EXCLUDED_STEAM_TITLE_PATTERN = re.compile(r"^(proton|steam linux runtime|steamworks|steamvr)\b", re.IGNORECASE)

# Helpers that live inside game folders but are not the game itself.
EXCLUDED_EXECUTABLE_PATTERN = re.compile(
    r"(crash|report|launcher|setup|install|redist|vc_?redist|dxsetup|directx|"
    r"easyanticheat|battleye|beservice|eac_|update|patcher|uninst|unins\d*|"
    r"helper|overlay|cefprocess|webhelper|unitycrashhandler)",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class InstalledGame:
    title: str
    launcher: str
    install_dir: str
    app_id: str | None = None


def parse_vdf_paths(text: str) -> list[str]:
    """Return library paths from Steam's ``libraryfolders.vdf``."""
    return [value.replace("\\\\", "\\") for value in re.findall(r'"path"\s+"([^"]+)"', text)]


def parse_acf(text: str) -> dict[str, str]:
    """Return the flat top-level keys of a Steam ``appmanifest_*.acf``."""
    return {key.lower(): value for key, value in re.findall(r'^\s*"(\w+)"\s+"([^"]*)"', text, re.MULTILINE)}


def steam_games(steam_root: Path) -> list[InstalledGame]:
    libraries = [steam_root]
    try:
        text = (steam_root / "steamapps" / "libraryfolders.vdf").read_text(encoding="utf-8", errors="ignore")
        libraries.extend(Path(path) for path in parse_vdf_paths(text))
    except OSError:
        pass
    games: list[InstalledGame] = []
    seen: set[str] = set()
    for library in libraries:
        apps = library / "steamapps"
        try:
            manifests = list(apps.glob("appmanifest_*.acf"))
        except OSError:
            continue
        for manifest in manifests:
            try:
                values = parse_acf(manifest.read_text(encoding="utf-8", errors="ignore"))
            except OSError:
                continue
            app_id, name, folder = values.get("appid"), values.get("name"), values.get("installdir")
            if not app_id or not name or not folder or app_id in seen or app_id in EXCLUDED_STEAM_APP_IDS:
                continue
            if EXCLUDED_STEAM_TITLE_PATTERN.match(name):
                continue
            seen.add(app_id)
            games.append(InstalledGame(name, "steam", str(apps / "common" / folder), app_id))
    return games


def epic_games(manifest_dir: Path) -> list[InstalledGame]:
    games: list[InstalledGame] = []
    try:
        manifests = list(manifest_dir.glob("*.item"))
    except OSError:
        return games
    for manifest in manifests:
        try:
            values = json.loads(manifest.read_text(encoding="utf-8", errors="ignore"))
        except (OSError, ValueError):
            continue
        if not isinstance(values, dict):
            continue
        categories = values.get("AppCategories") or []
        if isinstance(categories, list) and categories and "games" not in categories:
            continue
        title, location = values.get("DisplayName"), values.get("InstallLocation")
        if isinstance(title, str) and isinstance(location, str) and title and location:
            app_name = values.get("AppName")
            games.append(InstalledGame(title, "epic", location, app_name if isinstance(app_name, str) else None))
    return games


def xbox_games(roots: Iterable[Path]) -> list[InstalledGame]:
    games: list[InstalledGame] = []
    for root in roots:
        try:
            folders = [entry for entry in root.iterdir() if entry.is_dir()]
        except OSError:
            continue
        for folder in folders:
            config = folder / "Content" / "MicrosoftGame.config"
            if not config.is_file():
                continue
            title = folder.name
            try:
                tree = ElementTree.parse(config)
                visuals = tree.getroot().find(".//ShellVisuals")
                display_name = visuals.get("DefaultDisplayName") if visuals is not None else None
                # Store games may use a resource reference such as "ms-resource:".
                if display_name and not display_name.startswith("ms-resource"):
                    title = display_name
            except (OSError, ElementTree.ParseError):
                pass
            games.append(InstalledGame(title, "xbox", str(folder)))
    return games


def match_process(executable: str, games: list[InstalledGame]) -> InstalledGame | None:
    """Return the game whose install folder contains this executable."""
    name = os.path.basename(executable)
    if EXCLUDED_EXECUTABLE_PATTERN.search(name):
        return None
    normalized = os.path.normcase(os.path.normpath(executable))
    best: InstalledGame | None = None
    best_length = 0
    for game in games:
        folder = os.path.normcase(os.path.normpath(game.install_dir))
        if normalized.startswith(folder + os.sep) and len(folder) > best_length:
            best, best_length = game, len(folder)
    return best


class GamesProvider(SensorProvider):
    name = "games"
    platforms = {"windows"}
    priority = 95

    def __init__(
        self,
        *,
        library_loader: Callable[[], list[InstalledGame]] | None = None,
        process_source: Callable[[], list[tuple[str, int]]] | None = None,
        running_steam_app: Callable[[], str | None] | None = None,
        windows: bool | None = None,
    ) -> None:
        self._windows = platform.system() == "Windows" if windows is None else windows
        self._library_loader = library_loader or _windows_library
        self._process_source = process_source or _processes
        self._running_steam_app = running_steam_app or _running_steam_app_id
        self._games: list[InstalledGame] = []
        self._loaded_at = float("-inf")

    def is_available(self) -> bool:
        return self._windows

    def probe(self) -> Capabilities:
        if not self._windows:
            return Capabilities(self.name, False, [], "Spielerkennung ist nur unter Windows verfügbar")
        return Capabilities(self.name, True, ["game"])

    def collect(self) -> dict[str, Any]:
        now = time.monotonic()
        if now - self._loaded_at >= LIBRARY_REFRESH_SECONDS:
            self._games = self._library_loader()
            self._loaded_at = now
        candidates: dict[InstalledGame, tuple[int, str]] = {}
        for executable, memory in self._process_source():
            game = match_process(executable, self._games)
            if game is not None and memory > candidates.get(game, (-1, ""))[0]:
                candidates[game] = (memory, os.path.basename(executable))
        steam_app = self._running_steam_app()
        if steam_app and steam_app not in EXCLUDED_STEAM_APP_IDS:
            steam_game = next((game for game in self._games if game.launcher == "steam" and game.app_id == steam_app), None)
            if steam_game is not None:
                # Steam's own flag is the most precise signal, even when the
                # game runs from a folder outside the Steam library.
                return {"game": _game_metric(steam_game, candidates.get(steam_game, (0, None))[1])}
        if not candidates:
            return {}
        # The game with the largest process is the one being played; a second
        # one is usually a launcher left open in the background.
        game, (_, executable) = max(candidates.items(), key=lambda item: item[1][0])
        return {"game": _game_metric(game, executable)}


def _game_metric(game: InstalledGame, executable: str | None) -> dict[str, Any]:
    return {"title": game.title[:128], "launcher": game.launcher, "app_id": game.app_id, "executable": executable}


def _processes() -> list[tuple[str, int]]:
    result: list[tuple[str, int]] = []
    for process in psutil.process_iter(["exe", "memory_info"]):
        try:
            executable = process.info.get("exe")
            memory = process.info.get("memory_info")
            if executable:
                result.append((str(executable), int(memory.rss) if memory else 0))
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return result


def _windows_library() -> list[InstalledGame]:
    games: list[InstalledGame] = []
    steam_root = _registry_value("HKLM", r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath")
    if steam_root:
        games.extend(steam_games(Path(steam_root)))
    program_data = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData"))
    games.extend(epic_games(program_data / "Epic" / "EpicGamesLauncher" / "Data" / "Manifests"))
    games.extend(_gog_games())
    games.extend(xbox_games(_xbox_roots()))
    return games


def _xbox_roots() -> list[Path]:
    roots: list[Path] = []
    for partition in psutil.disk_partitions(all=False):
        if "fixed" in partition.opts or not partition.opts:
            root = Path(partition.mountpoint) / "XboxGames"
            if root.is_dir():
                roots.append(root)
    if not roots:
        roots.extend(Path(f"{letter}:\\XboxGames") for letter in string.ascii_uppercase if Path(f"{letter}:\\XboxGames").is_dir())
    return roots


def _gog_games() -> list[InstalledGame]:
    try:
        import winreg
    except ImportError:
        return []
    games: list[InstalledGame] = []
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\GOG.com\Games") as root:  # type: ignore[attr-defined,unused-ignore]
            index = 0
            while True:
                try:
                    game_id = winreg.EnumKey(root, index)  # type: ignore[attr-defined,unused-ignore]
                except OSError:
                    break
                index += 1
                try:
                    with winreg.OpenKey(root, game_id) as key:  # type: ignore[attr-defined,unused-ignore]
                        title = winreg.QueryValueEx(key, "gameName")[0]  # type: ignore[attr-defined,unused-ignore]
                        path = winreg.QueryValueEx(key, "path")[0]  # type: ignore[attr-defined,unused-ignore]
                except OSError:
                    continue
                if title and path:
                    games.append(InstalledGame(str(title), "gog", str(path), game_id))
    except OSError:
        pass
    return games


def _running_steam_app_id() -> str | None:
    """Read Steam's running app from every loaded user hive.

    The payload runs as SYSTEM, so HKEY_CURRENT_USER is not the player's hive.
    """
    try:
        import winreg
    except ImportError:
        return None
    try:
        with winreg.OpenKey(winreg.HKEY_USERS, "") as users:  # type: ignore[attr-defined,unused-ignore]
            index = 0
            while True:
                try:
                    sid = winreg.EnumKey(users, index)  # type: ignore[attr-defined,unused-ignore]
                except OSError:
                    break
                index += 1
                if not sid.startswith("S-1-5-21-") or sid.endswith("_Classes"):
                    continue
                try:
                    with winreg.OpenKey(users, sid + r"\Software\Valve\Steam") as key:  # type: ignore[attr-defined,unused-ignore]
                        value = int(winreg.QueryValueEx(key, "RunningAppID")[0])  # type: ignore[attr-defined,unused-ignore]
                except (OSError, ValueError, TypeError):
                    continue
                if value > 0:
                    return str(value)
    except OSError:
        pass
    return None


def _registry_value(hive: str, path: str, name: str) -> str | None:
    try:
        import winreg
    except ImportError:
        return None
    root = winreg.HKEY_LOCAL_MACHINE if hive == "HKLM" else winreg.HKEY_CURRENT_USER  # type: ignore[attr-defined,unused-ignore]
    try:
        with winreg.OpenKey(root, path) as key:  # type: ignore[attr-defined,unused-ignore]
            value = winreg.QueryValueEx(key, name)[0]  # type: ignore[attr-defined,unused-ignore]
    except OSError:
        return None
    return str(value) if value else None
