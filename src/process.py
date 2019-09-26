import psutil
from typing import Set, Iterable
from local_games import InstalledGame
from definitions import ClassicGame


class ProcessProvider(object):
    def __init__(self):
        pass

    def get_process_by_path(self, path):
        for p in psutil.process_iter(attrs=['exe'], ad_value=''):
            if p.info['exe'] == path:
                try:
                    if p.parent() and p.parent().exe() == path:
                        return p.parent()
                    return p
                except (psutil.AccessDenied, psutil.NoSuchProcess):
                    pass

    def update_games_processes(self, games: Iterable[InstalledGame]) -> Set[str]:
        """Matches currently running processes with the game executables and assigns those processes to games
        :returns     list of currently running games blizzard ids
        """
        running_games = set()
        for proc in psutil.process_iter(attrs=['exe', 'name'], ad_value=''):
            for game in games:
                if proc.info['exe'] in game.execs:
                    game.add_process(proc)
                    running_games.add(game.info.id)
                if isinstance(game.info, ClassicGame):
                    if game.info.exe in proc.info['name']:
                        game.add_process(proc)
                        running_games.add(game.info.id)

        return running_games
