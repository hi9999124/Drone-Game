import json
import os

SAVE_VERSION = 1
DIFFICULTIES = ["Easy", "Normal", "Hard", "Insane"]

DEFAULT_DATA = {
    "version": SAVE_VERSION,
    "profile": {
        "best_score": 0,
        "total_score": 0,
        "missions_completed": 0,
        "targets_destroyed": 0,
        "enemies_destroyed": 0,
        "last_drone": "fpv",
    },
    "settings": {
        "difficulty": "Normal",
        "show_fps": False,
        "screen_shake": True,
        "touch_controls": "Auto",  # Auto / On / Off
    },
}


def _save_dir():
    # On Android the app can only write inside its private directory, which
    # python-for-android exposes via ANDROID_PRIVATE. Everywhere else a dotfolder
    # in the user's home is the conventional spot (and survives reinstalling).
    android_private = os.environ.get("ANDROID_PRIVATE")
    if android_private:
        return android_private
    return os.path.join(os.path.expanduser("~"), ".dronepvo")


SAVE_PATH = os.path.join(_save_dir(), "savegame.json")


def _merge_defaults(loaded):
    """Fill in any keys a save file is missing, so old saves survive new fields."""
    data = json.loads(json.dumps(DEFAULT_DATA))  # deep copy
    for section in ("profile", "settings"):
        for key, value in loaded.get(section, {}).items():
            if key in data[section]:
                data[section][key] = value
    return data


def load():
    try:
        with open(SAVE_PATH, "r", encoding="utf-8") as handle:
            return _merge_defaults(json.load(handle))
    except (OSError, ValueError):
        # No save yet, unreadable file, or corrupt JSON -- a fresh profile is
        # always a better outcome here than crashing on startup.
        return json.loads(json.dumps(DEFAULT_DATA))


def save(data):
    """Best-effort persist. Returns True on success; never raises."""
    try:
        os.makedirs(os.path.dirname(SAVE_PATH), exist_ok=True)
        # Write to a temp file then replace, so an interrupted write (alt-F4,
        # phone killing the app) can't leave behind a half-written save.
        temp_path = SAVE_PATH + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
        os.replace(temp_path, SAVE_PATH)
        return True
    except OSError:
        return False
