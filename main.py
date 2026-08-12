import os
import sys

if sys.platform == "win32":
    # Windows virtualizes/scales coordinates for any process that hasn't
    # opted into DPI awareness, and a PyInstaller-built .exe carries no
    # manifest declaring it -- so without this, pygame's fullscreen mode
    # only ever covers the top-left corner of the real screen instead of
    # the whole monitor (SDL asks for "the desktop size" and Windows lies
    # about what that is). Must run before pygame/SDL initializes.
    # See https://github.com/pygame/pygame/issues/1680.
    os.environ.setdefault("SDL_WINDOWS_DPI_AWARENESS", "permonitorv2")
    try:
        import ctypes

        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

from src.game import Game

if __name__ == "__main__":
    Game().run()
