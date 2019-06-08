import sys
from enum import Enum
import os


class Platform(Enum):
    WINDOWS = 1
    MACOS = 2
    LINUX = 3


if sys.platform == 'win32':
    SYSTEM = Platform.WINDOWS
elif sys.platform == 'darwin':
    SYSTEM = Platform.MACOS

if SYSTEM == Platform.WINDOWS:
    AGENT_PATH = os.path.expandvars(r'%ALLUSERSPROFILE%\Battle.net\Agent')
    CONFIG_PATH = os.path.expandvars(r'%APPDATA%\Battle.net\Battle.net.config')    
elif SYSTEM == Platform.MACOS:
    AGENT_PATH = '/Users/Shared/Battle.net/Agent'
    CONFIG_PATH = os.path.expanduser('~/Library/Application Support/Battle.net/Battle.net.config')

CLIENT_ID = "a1b2c3"
CLIENT_SECRET = "d4e5"

LOCALE = "en_US"
REDIRECT_URI = "http://example.com"

FIREFOX_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:67.0) Gecko/20100101 Firefox/67.0"
