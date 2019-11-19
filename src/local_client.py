import re
import os
import asyncio
import logging as log
import subprocess
from time import time

import psutil

from definitions import ClassicGame
from consts import Platform, SYSTEM, AGENT_PATH

if SYSTEM == Platform.WINDOWS:
    import winreg
    import ctypes
elif SYSTEM == Platform.MACOS:
    from Quartz import CGWindowListCopyWindowInfo, kCGNullWindowID, kCGWindowListExcludeDesktopElements
    from AppKit import NSWorkspace

from local_client_base import BaseLocalClient
import pathlib

class WinUninstaller(object):
    def __init__(self, path):
        self.path = path
        if not os.path.exists(self.path):
            raise FileNotFoundError("Uninstaller not found")

    def uninstall_game(self, game, uninstall_tag, lang):
        if isinstance(game.info, ClassicGame):
            log.info(f"Uninstalling classic game by {uninstall_tag}")
            subprocess.Popen(uninstall_tag, shell=True)
            return
        args = [
            str(self.path),
            f'--lang={lang}',
            f'--uid={uninstall_tag}',
            f'--displayname={game.info.name}'
        ]
        subprocess.Popen(args, cwd=os.path.dirname(self.path))

class WinLocalClient(BaseLocalClient):
    def __init__(self, update_statuses):
        self._WIN_REG_SHELL = (winreg.HKEY_CLASSES_ROOT, r"battlenet\shell\open\command")
        super().__init__(update_statuses)
        self.uninstaller = self.set_uninstaller()
        self._exe = self._find_exe()

    def set_uninstaller(self):
        try:
            if SYSTEM == Platform.WINDOWS and self.uninstaller is None:
                uninstaller_path = pathlib.Path(AGENT_PATH) / 'Blizzard Uninstaller.exe'
                return WinUninstaller(uninstaller_path)
        except FileNotFoundError as e:
            log.warning('uninstaller not found' + str(e))

    def _find_exe(self):
        shell_reg_value = self.__search_registry_for_run_cmd(*self._WIN_REG_SHELL)
        if shell_reg_value is None:
            return None
        reg = re.compile("\"(.*?)\"")  # any chars in double quotes
        return reg.search(shell_reg_value).groups()[0]

    def _find_main_renderer_window(self):
        """Get Blizzard renderer window (main window, not login)
        :return     int number of window; 0 if window not found"""
        return ctypes.windll.user32.FindWindowW(None, "Blizzard Battle.net")

    def _is_main_window_open(self):
        return bool(self._find_main_renderer_window())

    @property
    def is_installed(self):
        return bool(self._exe)

    def close_window(self):
        """Closes Blizzard renderer using native API (but not login window)"""
        bnet_handle = self._find_main_renderer_window()
        if not bnet_handle:
            return False
        if ctypes.windll.user32.IsWindowVisible(bnet_handle):
            ctypes.windll.user32.CloseWindow(bnet_handle)
            if ctypes.windll.user32.IsWindowVisible(bnet_handle):
                return False
            return True
        return False

    async def prevent_battlenet_from_showing(self):
        client_popup_wait_time = 5
        check_frequency_delay = 0.02

        end_time = time() + client_popup_wait_time

        while not self.close_window():
            if time() >= end_time:
                log.info("Timed out closing bnet popup")
                break
            await asyncio.sleep(check_frequency_delay)

    async def shutdown_platform_client(self):
        subprocess.Popen("taskkill.exe /im \"Battle.net.exe\"")
        # Battle.net probably never exits on WM_CLOSE so make sure it will be hidden
        await self.prevent_battlenet_from_showing()

    def _check_for_game_process(self, game):
        try:
            if not self.is_running():
                return False
            with self._process.oneshot():
                for proc in self._process.children():
                    if proc.exe() in game.execs:
                        log.debug(f'Process has been found')
                        return True
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            pass
        except Exception as e:
            log.error(f'Error while waiting for process to be spawn: {repr(e)}')

    def __search_registry_for_run_cmd(self, *args):
        """
        :param args - arguments as for winreg.OpenKey()
        :returns value of the first string-type key or False if given registry does not exists
        """
        try:
            key = winreg.OpenKey(*args)
            for i in range(1024):
                try:
                    _, exe_cmd, _type = winreg.EnumValue(key, i)
                    if exe_cmd and _type == winreg.REG_SZ:  # null-terminated string
                        return exe_cmd
                except OSError:  # no more data
                    break
        except FileNotFoundError:
            return None


class MacLocalClient(BaseLocalClient):
    def __init__(self, update_statuses):
        super().__init__(update_statuses)
        self.uninstaller = None
        self._exe = self._find_exe()
    _PATH = "/Applications/Battle.net.app/Contents/MacOS/Battle.net"

    def _find_exe(self):
        return self._PATH

    def _is_main_window_open(self):
        """Main window, not login one"""
        windows = CGWindowListCopyWindowInfo(kCGWindowListExcludeDesktopElements, kCGNullWindowID)
        for window in windows:
            try:
                if 'Blizzard Battle.net' == window['kCGWindowName']:
                    log.debug('Main Battle.net window was found')
                    return True
            except KeyError:
                continue
        return False

    def close_window(self):
        workspace = NSWorkspace.sharedWorkspace()
        activeApps = workspace.runningApplications()

        for app in activeApps:
            if app.isActive() and app.localizedName() == "Blizzard Battle.net":
                app.hide()

    async def prevent_battlenet_from_showing(self):
        client_popup_wait_time = 5
        check_frequency_delay = 0.02

        workspace = NSWorkspace.sharedWorkspace()
        activeApps = workspace.runningApplications()

        end_time = time() + client_popup_wait_time
        while time() <= end_time:
            for app in activeApps:
                if app.isActive() and app.localizedName() == "Blizzard Battle.net":
                    app.hide()
                    return
            await asyncio.sleep(check_frequency_delay)
        log.info("Timed out on prevent battlenet from showing")

    async def shutdown_platform_client(self):
        subprocess.Popen("osascript -e 'quit app \"Battle.net\"'", shell=True)

    @property
    def is_installed(self):
        return os.path.exists(self._exe)

    def _check_for_game_process(self, game):
        """Check over all processes because on macOS games are spawn not as client children"""
        for proc in psutil.process_iter(attrs=['exe'], ad_value=''):
            if proc.info['exe'] in game.execs:
                return True
        return False


if SYSTEM == Platform.WINDOWS:
    LocalClient = WinLocalClient
elif SYSTEM == Platform.MACOS:
    LocalClient = MacLocalClient
