from __future__ import annotations

import json
import os
from pathlib import Path

from ncc.collectors.games import (
    GamesProvider,
    InstalledGame,
    epic_games,
    match_process,
    parse_vdf_paths,
    steam_games,
    xbox_games,
)


def _steam_library(root: Path) -> None:
    apps = root / "steamapps"
    (apps / "common" / "Cyberpunk 2077" / "bin" / "x64").mkdir(parents=True)
    (apps / "appmanifest_1091500.acf").write_text(
        '"AppState"\n{\n\t"appid"\t\t"1091500"\n\t"name"\t\t"Cyberpunk 2077"\n\t"installdir"\t\t"Cyberpunk 2077"\n}\n',
        encoding="utf-8",
    )
    (apps / "appmanifest_431960.acf").write_text(
        '"AppState"\n{\n\t"appid"\t\t"431960"\n\t"name"\t\t"Wallpaper Engine"\n\t"installdir"\t\t"wallpaper_engine"\n}\n',
        encoding="utf-8",
    )


def test_steam_library_reads_manifests_and_skips_tools(tmp_path: Path) -> None:
    _steam_library(tmp_path)
    games = steam_games(tmp_path)
    assert [(game.title, game.app_id) for game in games] == [("Cyberpunk 2077", "1091500")]
    (tmp_path / "steamapps" / "appmanifest_1493710.acf").write_text(
        '"AppState"\n{\n\t"appid"\t\t"1493710"\n\t"name"\t\t"Proton Experimental"\n\t"installdir"\t\t"Proton - Experimental"\n}\n',
        encoding="utf-8",
    )
    assert [game.title for game in steam_games(tmp_path)] == ["Cyberpunk 2077"]
    assert games[0].install_dir == str(tmp_path / "steamapps" / "common" / "Cyberpunk 2077")


def test_steam_library_follows_additional_library_folders(tmp_path: Path) -> None:
    main = tmp_path / "Steam"
    (main / "steamapps").mkdir(parents=True)
    extra = tmp_path / "Games"
    _steam_library(extra)
    escaped = str(extra).replace("\\", "\\\\")
    (main / "steamapps" / "libraryfolders.vdf").write_text(
        f'"libraryfolders"\n{{\n\t"0"\n\t{{\n\t\t"path"\t\t"{escaped}"\n\t}}\n}}\n', encoding="utf-8"
    )
    assert parse_vdf_paths(f'"path"  "{escaped}"') == [str(extra)]
    assert [game.title for game in steam_games(main)] == ["Cyberpunk 2077"]


def test_epic_manifests_keep_games_only(tmp_path: Path) -> None:
    (tmp_path / "a.item").write_text(json.dumps({
        "DisplayName": "Alan Wake 2", "InstallLocation": "D:\\Epic\\AlanWake2", "AppName": "Dill", "AppCategories": ["public", "games"],
    }), encoding="utf-8")
    (tmp_path / "b.item").write_text(json.dumps({
        "DisplayName": "Unreal Engine", "InstallLocation": "D:\\Epic\\UE", "AppCategories": ["engines"],
    }), encoding="utf-8")
    (tmp_path / "broken.item").write_text("{", encoding="utf-8")
    assert [(game.title, game.launcher, game.app_id) for game in epic_games(tmp_path)] == [("Alan Wake 2", "epic", "Dill")]


def test_xbox_games_use_the_display_name_from_the_game_config(tmp_path: Path) -> None:
    content = tmp_path / "Forza Horizon 5" / "Content"
    content.mkdir(parents=True)
    (content / "MicrosoftGame.config").write_text(
        '<Game configVersion="1"><ShellVisuals DefaultDisplayName="Forza Horizon 5"/></Game>', encoding="utf-8"
    )
    resource = tmp_path / "Starfield" / "Content"
    resource.mkdir(parents=True)
    (resource / "MicrosoftGame.config").write_text(
        '<Game><ShellVisuals DefaultDisplayName="ms-resource:Title"/></Game>', encoding="utf-8"
    )
    (tmp_path / "NotAGame").mkdir()
    assert sorted(game.title for game in xbox_games([tmp_path])) == ["Forza Horizon 5", "Starfield"]


def test_process_match_uses_the_install_folder_and_skips_helpers(tmp_path: Path) -> None:
    folder = str(tmp_path / "Game")
    game = InstalledGame("Game", "gog", folder)
    nested = InstalledGame("Nested", "gog", os.path.join(folder, "Nested"))
    assert match_process(os.path.join(folder, "bin", "game.exe"), [game]) == game
    assert match_process(os.path.join(folder, "Nested", "nested.exe"), [game, nested]) == nested
    assert match_process(os.path.join(folder, "UnityCrashHandler64.exe"), [game]) is None
    assert match_process(os.path.join(folder + "2", "other.exe"), [game]) is None


def test_provider_reports_the_largest_matching_process() -> None:
    small = InstalledGame("Launcher Left Open", "epic", os.path.normpath("/games/small"))
    big = InstalledGame("Elden Ring", "steam", os.path.normpath("/games/elden"), "1245620")
    provider = GamesProvider(
        windows=True,
        library_loader=lambda: [small, big],
        process_source=lambda: [
            (os.path.normpath("/games/small/app.exe"), 100),
            (os.path.normpath("/games/elden/eldenring.exe"), 5_000),
            (os.path.normpath("/windows/explorer.exe"), 9_000),
        ],
        running_steam_app=lambda: None,
    )
    assert provider.collect() == {"game": {"title": "Elden Ring", "launcher": "steam", "app_id": "1245620", "executable": "eldenring.exe"}}


def test_provider_prefers_steams_running_app_flag() -> None:
    steam = InstalledGame("Hades II", "steam", os.path.normpath("/steam/hades2"), "1145350")
    other = InstalledGame("Other", "gog", os.path.normpath("/gog/other"))
    provider = GamesProvider(
        windows=True,
        library_loader=lambda: [steam, other],
        process_source=lambda: [(os.path.normpath("/gog/other/other.exe"), 10_000)],
        running_steam_app=lambda: "1145350",
    )
    assert provider.collect()["game"]["title"] == "Hades II"


def test_provider_is_silent_without_a_game_and_off_windows() -> None:
    provider = GamesProvider(windows=True, library_loader=list, process_source=list, running_steam_app=lambda: None)
    assert provider.collect() == {}
    assert GamesProvider(windows=False).is_available() is False
