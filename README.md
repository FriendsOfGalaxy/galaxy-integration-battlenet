# Galaxy plugin for Battle.net

Install required packages for building and testing:
```bash
pip install -r requirements/dev.txt
```

Run tests:
```bash
inv test
```

Build package
```bash
inv build [--output=<output_folder>] [--ziparchive=<zip_package_name.zip>]
```

If you have classic blizzard games which are not properly detected as installed or don't launch when clicking 'play' 
please provide the name and values of the games key under

```Computer\HKEY_LOCAL_MACHINE\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\```

registry path.

If on MAC please provide the games bundle_id which can be found by calling

```/System/Library/Frameworks/CoreServices.framework/Versions/A/Frameworks/LaunchServices.framework/Versions/A/Support/lsregister -dump | grep {game_name}```

## Installation

### Windows
Extract to `%LOCALAPPDATA%\GOG.com\Galaxy\plugins\installed\battlenet`
