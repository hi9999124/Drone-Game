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
    #
    # SDL_WINDOWS_DPI_AWARENESS is the ONLY thing that should set this --
    # Windows lets a process declare its DPI-awareness mode exactly once,
    # so a manual ctypes.windll.user32.SetProcessDPIAware() call here would
    # lock in the older "system aware" mode first and silently block SDL's
    # own (more correct, per-monitor-v2) attempt when pygame.init() runs
    # right after, leaving the process in a worse, inconsistent state than
    # just letting SDL handle it alone.
    os.environ.setdefault("SDL_WINDOWS_DPI_AWARENESS", "permonitorv2")

from src.game import Game

if __name__ == "__main__":
    Game().run()
