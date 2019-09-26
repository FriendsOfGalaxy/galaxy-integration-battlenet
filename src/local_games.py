from threading import Thread, Lock

import logging as log
import subprocess
import os
from pathlib import Path

from consts import Platform, SYSTEM, WINDOWS_UNINSTALL_LOCATION, LS_REGISTER
from psutil import Process, AccessDenied

from definitions import BlizzardGame, ClassicGame, Blizzard
from pathfinder import PathFinder
import time

if SYSTEM == Platform.WINDOWS:
    import winreg

pathfinder = PathFinder(SYSTEM)


class InstalledGame(object):
    def __init__(self, info: BlizzardGame, uninstall_tag: str, version: str, last_played: str, install_path: str, playable: bool):
        self.info = info
        self.uninstall_tag = uninstall_tag
        self.version = version
        self.last_played = last_played
        self.install_path = install_path
        self.playable = playable

        self.execs = pathfinder.find_executables(self.install_path)
        self._processes = set()

    @property
    def local_game_args(self):
        return (self.info.blizzard_id, self.is_running)

    def add_process(self, process: Process):
        try:
            if process.exe() in self.execs:
                self._processes.add(process)
            else:
                raise ValueError(f"The process exe [{process.exe()}] doesn't match with the game execs: {self.execs}")
        except AccessDenied:
            if isinstance(self.info, ClassicGame):
                if self.info.exe in process.name():
                    self._processes.add(process)
                else:
                    raise ValueError(
                        f"The process name [{process.name()}] doesn't match with the game exe: {self.info.exe}")

    def is_running(self):
        for process in self._processes:
            if process.is_running():
                return True
        else:
            self._processes = set()
            return False

    def wait_until_game_stops(self):
        while self.is_running():
            time.sleep(0.5)

class LocalGames():
    def __init__(self):

        self.installed_classic_games_lock = Lock()
        self.installed_classic_games = {}
        self.parsed_classics = False

        self.installed_battlenet_games = {}
        self.installed_battlenet_games_lock = Lock()
        self.parsed_battlenet = False

        self._classic_games_thread = None
        self._battlenet_games_thread = None

    def _add_classic_game(self, game, key):
        if game.registry_path:
            try:
                with winreg.OpenKey(key, game.registry_path) as game_key:
                    log.debug(f"Found classic game registry entry! {game.registry_path}")
                    install_path = winreg.QueryValueEx(game_key, game.registry_installation_key)[0]
                    if install_path.endswith('.exe'):
                        install_path = Path(install_path).parent
                    uninstall_path = winreg.QueryValueEx(game_key, "UninstallString")[0]
                    if os.path.exists(install_path):
                        log.debug(f"Found classic game is installed! {game.registry_path}")
                        return InstalledGame(
                            game,
                            uninstall_path,
                            '1.0',
                            '',
                            install_path,
                            True
                        )
            except OSError:
                return None
        return None

    def _find_classic_games(self):
        classic_games = {}
        log.debug("Looking for classic games")
        if SYSTEM == Platform.WINDOWS:
            try:
                reg = winreg.ConnectRegistry(None, winreg.HKEY_LOCAL_MACHINE)
                with winreg.OpenKey(reg, WINDOWS_UNINSTALL_LOCATION) as key:
                    for game in Blizzard.legacy_games:
                        log.debug(f"Checking if {game} is in registry ")
                        installed_game = self._add_classic_game(game, key)
                        if installed_game:
                            classic_games[game.id] = installed_game
            except OSError as e:
                log.exception(f"Exception while looking for installed classic games {e}")
        else:
            proc = subprocess.run([LS_REGISTER,"-dump"], encoding='utf-8',stdout=subprocess.PIPE)
            for game in Blizzard.legacy_games:
                if game.bundle_id:
                    if game.bundle_id in proc.stdout:
                        classic_games[game.id] = InstalledGame(
                                                    game,
                                                    '',
                                                    '1.0',
                                                    '',
                                                    '',
                                                    True
                                                )
        self.installed_classic_games_lock.acquire()
        self.installed_classic_games = classic_games
        self.installed_classic_games_lock.release()
        if not self.parsed_classics:
            self.parsed_classics = True

    def parse_local_battlenet_games(self, database_parser_games, config_parser_games):
        """Game is considered as installed when present in both config and product.db"""
        # give threads 4 seconds to finish
        join_timeout = 4

        log.info(f"Games found in db {database_parser_games}")
        log.info(f"Games found in config {config_parser_games}")

        try:
            if not self._battlenet_games_thread or not self._battlenet_games_thread.isAlive():
                self._battlenet_games_thread = Thread(target=self._get_battlenet_installed_games, daemon=True, args=[database_parser_games, config_parser_games])
                self._battlenet_games_thread.start()
                log.info("Started battlenet games thread")
        except Exception as e:
            log.exception(str(e))
        finally:
            self._battlenet_games_thread.join(join_timeout)

    async def parse_local_classic_games(self):
        # give threads 4 seconds to finish
        join_timeout = 4

        if not self._classic_games_thread or not self._classic_games_thread.isAlive():
            self._classic_games_thread = Thread(target=self._find_classic_games, daemon=True)
            self._classic_games_thread.start()
            log.info("Started classic games thread")

        self._classic_games_thread.join(join_timeout)

    def _get_battlenet_installed_games(self, database_parser_games, config_parser_games):

        def _add_battlenet_game(config_game, db_game):
            if config_game.uninstall_tag != db_game.uninstall_tag:
                return None
            try:
                blizzard_game = Blizzard[config_game.uid]
            except KeyError:
                log.warning(f'[{config_game.uid}] is not known blizzard game. Skipping')
                return None
            try:
                log.info(f"Adding {blizzard_game.blizzard_id} {blizzard_game.name} to installed games")
                return InstalledGame(
                    blizzard_game,
                    config_game.uninstall_tag,
                    db_game.version,
                    config_game.last_played,
                    db_game.install_path,
                    db_game.playable
                )
            except FileNotFoundError as e:
                log.warning(str(e) + '. Probably outdated product.db after uninstall. Skipping')
            return None

        games = {}
        for db_game in database_parser_games:
            for config_game in config_parser_games:
                installed_game = _add_battlenet_game(config_game, db_game)
                if installed_game:
                    games[installed_game.info.id] = installed_game
        self.installed_battlenet_games_lock.acquire()
        self.installed_battlenet_games = games
        self.installed_battlenet_games_lock.release()
        if not self.parsed_battlenet:
            self.parsed_battlenet = True
