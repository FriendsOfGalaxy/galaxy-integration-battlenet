import os
import asyncio
import logging as log
import subprocess
import abc
from time import time
from pathlib import Path


from definitions import Blizzard
from process import ProcessProvider
from consts import Platform, SYSTEM, CONFIG_PATH, AGENT_PATH
from watcher import FileWatcher
from parsers import ConfigParser, DatabaseParser

from local_games import LocalGames, InstalledGame
import json
import errno


class ClientNotInstalledError(Exception):
    def __init__(self, message="Battle.net not installed", *args, **kwargs):
        super().__init__(message, *args, **kwargs)


def load_product_db(product_db_path):
    with open(product_db_path, 'rb') as f:
        pdb = f.read()
    return pdb


def load_config(battlenet_config_path):
    with open(battlenet_config_path, 'rb') as f:
        config = json.load(f)
    return config


class BaseLocalClient(abc.ABC):

    PRODUCT_DB_PATH = Path(AGENT_PATH) / 'product.db'
    CONFIG_PATH = CONFIG_PATH

    def __init__(self, update_statuses):
        self._update_statuses = update_statuses
        self._process_provider = ProcessProvider()
        self._process = None
        self._exe = self._find_exe()
        self._games_provider = LocalGames()

        self.database_parser = None
        self.config_parser = None
        self.uninstaller = None
        self.installed_games_cache = self.get_installed_games()

        loop = asyncio.get_event_loop()
        loop.create_task(self._register_local_data_watcher())
        loop.create_task(self._register_classic_games_updater())
        self.classic_games_parsing_task = None

    @abc.abstractproperty
    def is_installed(self):
        pass

    @abc.abstractmethod
    def _find_exe(self):
        """Returns Battlenet main executable"""
        pass

    @abc.abstractmethod
    def _is_main_window_open(self):
        """Return True if Blizzard main renderer window is present (main window, not login)"""
        pass

    @abc.abstractmethod
    def _check_for_game_process(self, game):
        """Returns True if process matching game if found"""
        pass

    def refresh(self):
        self._exe = self._find_exe()

    def is_running(self):
        if self._process and self._process.is_running():
            return True
        else:
            self._process = self._process_provider.get_process_by_path(self._exe)
            return bool(self._process)

    async def _prepare_to_launch(self, uid, timeout):
        """launches the client and waits till proper renderer is opened
        :param uid      str of game uid. Makes login window game oriented
        :param timeout  timestamp when a watch should be stopped
        """
        if self.is_running() and self._is_main_window_open():
            return

        subprocess.Popen([self._exe, f'--game={uid}'], cwd=os.path.dirname(self._exe))
        while time() < timeout:
            if self._is_main_window_open():
                log.debug('Preparing to launch ended {:.2f}s before timeout'.format(timeout - time()))
                return
            await asyncio.sleep(0.2)
        raise TimeoutError(f'Timeout reached when waiting for gameview from Battle.net')

    def install_game(self, id):
        if not self.is_installed:
            raise ClientNotInstalledError()
        game = Blizzard[id]
        args = [
            self._exe,
            "--install",
            f"--game={game.uid}"
        ]
        subprocess.Popen(args, cwd=os.path.dirname(self._exe))

    def open_battlenet(self, id=None):
        if not self.is_installed or not self._exe:
            raise ClientNotInstalledError()
        if id:
            game = Blizzard[id]
            args = {self._exe,
                    f"--game={game.uid}"}
        else:
            args = {self._exe}
        subprocess.Popen(args, cwd=os.path.dirname(self._exe))

    async def wait_until_game_stops(self, game: InstalledGame):
        if not self.is_running():
            return 'Client not running'
        for child in self._process.children():
            if child.exe() in game.execs:
                game_process = child
                break
        else:
            return 'No subprocess matches'
        while True:
            if not game_process.is_running():
                return 'Game process is no longer running'
            await asyncio.sleep(1)

    async def launch_game(self, game: InstalledGame, wait_sec):
        if not self.is_installed:
            raise ClientNotInstalledError()
        timeout = time() + wait_sec

        if game.info.family == 'WoW_wow_classic':
            if SYSTEM == Platform.WINDOWS:
                cmd = f"\"{Path(game.install_path)/'World of Warcraft Launcher.exe'}\" --productcode=wow_classic"
            else:
                cmd = f"open \"{Path(game.install_path)/'World of Warcraft Launcher.app'}\" --args productcode=wow_classic"
            subprocess.Popen(cmd, shell=True)
        else:
            await self._prepare_to_launch(game.info.uid, timeout)
            cmd = f'"{self._exe}" --exec="launch {game.info.family}"'
            subprocess.Popen(cmd, cwd=os.path.dirname(self._exe), shell=True)
        log.info(f"Launch game and start waiting for game process")
        while time() < timeout:
            if self._check_for_game_process(game):
                return
            await asyncio.sleep(0.5)
        raise TimeoutError(f"Game process has not appear within {wait_sec}s")

    def _load_local_files(self):
        try:
            product_db = load_product_db(self.PRODUCT_DB_PATH)
            self.database_parser = DatabaseParser(product_db)
        except FileNotFoundError as e:
            log.warning(f"product.db not found: {repr(e)}")
            return False
        except WindowsError as e:
            # 5 WindowsError access denied
            if e.winerror == 5:
                log.warning(f"product.db not accessible: {repr(e)}")
                self.config_parser = ConfigParser(None)
                return False
            else:
                raise ()
        except OSError as e:
            if e.errno == errno.EACCES:
                log.warning(f"product.db not accessible: {repr(e)}")
                self.config_parser = ConfigParser(None)
                return False
            else:
                raise ()
        else:
            if self.is_installed != self.database_parser.battlenet_present:
                self.refresh()

        try:
            config = load_config(self.CONFIG_PATH)
            self.config_parser = ConfigParser(config)
        except FileNotFoundError as e:
            log.warning(f"config file not found: {repr(e)}")
            self.config_parser = ConfigParser(None)
            return False
        except WindowsError as e:
            # 5 WindowsError access denied
            if e.winerror == 5:
                log.warning(f"config file not accessible: {repr(e)}")
                self.config_parser = ConfigParser(None)
                return False
            else:
                raise ()
        except OSError as e:
            if e.errno == errno.EACCES:
                log.warning(f"config file not accessible: {repr(e)}")
                self.config_parser = ConfigParser(None)
                return False
            else:
                raise ()
        return True

    async def _register_local_data_watcher(self):
        parse_local_data_event = asyncio.Event()
        FileWatcher(self.CONFIG_PATH, parse_local_data_event, interval=1)
        FileWatcher(self.PRODUCT_DB_PATH, parse_local_data_event, interval=2.5)
        parse_local_data_event.set()
        while True:
            await parse_local_data_event.wait()

            if not self._load_local_files():
                parse_local_data_event.clear()
                continue
            if self.is_installed != self.database_parser.battlenet_present:
                self.refresh()

            self._games_provider.parse_local_battlenet_games(self.database_parser.games, self.config_parser.games)
            refreshed_games = self.get_installed_games()

            self._update_statuses(refreshed_games, self.installed_games_cache)
            self.installed_games_cache = refreshed_games
            parse_local_data_event.clear()

    async def _register_classic_games_updater(self):
        tick_count = 0
        while True:
            tick_count += 1
            if tick_count % 30 == 0:
                if not self.classic_games_parsing_task or self.classic_games_parsing_task.done():
                    self.classic_games_parsing_task = asyncio.create_task(self._games_provider.parse_local_classic_games())
                    refreshed_games = self.get_installed_games()
                    self._update_statuses(refreshed_games, self.installed_games_cache)
                    self.installed_games_cache = refreshed_games
            await asyncio.sleep(1)

    def games_finished_parsing(self):
        return self._games_provider.parsed_classics and self._games_provider.parsed_battlenet

    def get_installed_games(self, timeout=1):
        games = {}

        if self._games_provider.installed_battlenet_games_lock.acquire(True, timeout):
            games = self._games_provider.installed_battlenet_games
            self._games_provider.installed_battlenet_games_lock.release()

        if self._games_provider.installed_classic_games_lock.acquire(True, timeout):
            games = {**games, **self._games_provider.installed_classic_games}
            self._games_provider.installed_classic_games_lock.release()

        return games

    def get_running_games(self):
        return ProcessProvider().update_games_processes(self.get_installed_games().values())
