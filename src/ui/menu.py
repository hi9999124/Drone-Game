import pygame

from .. import constants, drones
from ..save_system import DIFFICULTIES
from ..utils import clamp
from .button import Button, OptionRow
from .fonts import get_font


def _overlay():
    surface = pygame.Surface((constants.WIDTH, constants.HEIGHT), pygame.SRCALPHA)
    surface.fill(constants.OVERLAY)
    return surface


class Screen:
    """Base for every menu: a list of widgets plus a title."""

    title = ""
    subtitle = ""
    dim_background = False

    def __init__(self):
        self.widgets = []
        self._overlay_surface = _overlay() if self.dim_background else None

    def handle_event(self, event, mouse_pos):
        for widget in self.widgets:
            if widget.handle_event(event, mouse_pos):
                return True
        return False

    def update(self, mouse_pos, dt):
        for widget in self.widgets:
            widget.update(mouse_pos, dt)

    def draw(self, surface):
        if self._overlay_surface is not None:
            surface.blit(self._overlay_surface, (0, 0))
        if self.title:
            font = get_font(46, bold=True)
            text = font.render(self.title, True, constants.TEXT_COLOR)
            surface.blit(text, text.get_rect(center=(constants.WIDTH // 2, 78)))
        if self.subtitle:
            font = get_font(19)
            text = font.render(self.subtitle, True, constants.TEXT_DIM)
            surface.blit(text, text.get_rect(center=(constants.WIDTH // 2, 118)))
        for widget in self.widgets:
            widget.draw(surface)


class MainMenu(Screen):
    def __init__(self, profile, on_play, on_settings, on_quit):
        super().__init__()
        self.profile = profile
        cx = constants.WIDTH // 2
        self.widgets = [
            Button((cx - 130, 300, 260, 56), "PLAY", on_play, font_size=26),
            Button((cx - 130, 368, 260, 52), "SETTINGS", on_settings),
            Button((cx - 130, 430, 260, 52), "QUIT", on_quit),
        ]

    def draw(self, surface):
        title_font = get_font(66, bold=True)
        title = title_font.render("DRONE / PVO", True, constants.ACCENT)
        surface.blit(title, title.get_rect(center=(constants.WIDTH // 2, 180)))

        sub = get_font(20).render(
            "Urban strike operations", True, constants.TEXT_DIM
        )
        surface.blit(sub, sub.get_rect(center=(constants.WIDTH // 2, 232)))

        for widget in self.widgets:
            widget.draw(surface)

        stats = (
            f"BEST {self.profile['best_score']}    "
            f"MISSIONS {self.profile['missions_completed']}    "
            f"CAREER {self.profile['total_score']}"
        )
        stats_surf = get_font(17, mono=True).render(stats, True, constants.TEXT_FAINT)
        surface.blit(stats_surf, stats_surf.get_rect(center=(constants.WIDTH // 2, 520)))

        hint = get_font(16, mono=True).render(
            "W/S thrust  -  A/D turn  -  SPACE/SHIFT altitude  -  F fire  -  ESC pause",
            True,
            constants.TEXT_FAINT,
        )
        surface.blit(hint, hint.get_rect(center=(constants.WIDTH // 2, constants.HEIGHT - 38)))


class DroneSelectMenu(Screen):
    """Card picker. Locked airframes show the score needed to unlock them."""

    title = "SELECT AIRFRAME"

    def __init__(self, profile, on_start, on_back, selected_key=None):
        super().__init__()
        self.profile = profile
        self.on_start = on_start
        self.selected_key = selected_key or profile.get("last_drone", "fpv")
        self.total_score = profile.get("total_score", 0)

        if not self._is_unlocked(drones.get(self.selected_key)):
            self.selected_key = "fpv"

        self.cards = []
        count = len(drones.DRONE_TYPES)
        gap = 22
        # Shrink the cards to fit rather than letting them run off the edge of a
        # narrow (phone) screen.
        available = constants.WIDTH - 60 - gap * (count - 1)
        card_w = min(268, available // count)
        card_h = min(330, constants.HEIGHT - 300)
        total_w = count * card_w + (count - 1) * gap
        start_x = (constants.WIDTH - total_w) // 2
        for index, drone_type in enumerate(drones.DRONE_TYPES):
            rect = pygame.Rect(start_x + index * (card_w + gap), 160, card_w, card_h)
            self.cards.append((rect, drone_type))

        cx = constants.WIDTH // 2
        button_y = min(530, 170 + card_h + 20)
        self.start_button = Button((cx - 240, button_y, 220, 54), "START MISSION", self._start, font_size=24)
        self.widgets = [
            self.start_button,
            Button((cx + 20, button_y, 220, 54), "BACK", on_back, font_size=24),
        ]
        self._sync_start_button()

    def _is_unlocked(self, drone_type):
        return drones.is_unlocked(drone_type, self.total_score)

    def _sync_start_button(self):
        self.start_button.enabled = self._is_unlocked(drones.get(self.selected_key))

    def _start(self):
        self.on_start(self.selected_key)

    def handle_event(self, event, mouse_pos):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for rect, drone_type in self.cards:
                if rect.collidepoint(mouse_pos) and self._is_unlocked(drone_type):
                    self.selected_key = drone_type.key
                    self._sync_start_button()
                    return True
        return super().handle_event(event, mouse_pos)

    def draw(self, surface):
        super().draw(surface)
        for rect, drone_type in self.cards:
            self._draw_card(surface, rect, drone_type)

    def _draw_card(self, surface, rect, drone_type):
        unlocked = self._is_unlocked(drone_type)
        selected = drone_type.key == self.selected_key and unlocked

        bg = (24, 30, 42) if selected else constants.PANEL_BG
        pygame.draw.rect(surface, bg, rect, border_radius=12)
        edge = drone_type.accent_color if selected else constants.PANEL_EDGE
        pygame.draw.rect(surface, edge, rect, width=3 if selected else 1, border_radius=12)

        name_color = constants.TEXT_COLOR if unlocked else constants.TEXT_FAINT
        name = get_font(23, bold=True).render(drone_type.name, True, name_color)
        surface.blit(name, (rect.x + 16, rect.y + 14))

        sub = get_font(15).render(drone_type.subtitle, True, constants.TEXT_FAINT)
        surface.blit(sub, (rect.x + 16, rect.y + 44))

        self._draw_silhouette(surface, rect, drone_type, unlocked)

        stats = [
            ("SPEED", drone_type.max_speed / 800.0),
            ("AGILITY", drone_type.turn_speed / 260.0),
            ("ARMOUR", drone_type.max_hp / 7.0),
            ("BLAST", drone_type.blast_radius / 200.0),
        ]
        y = rect.y + 150
        for label, value in stats:
            self._draw_stat_bar(surface, rect.x + 16, y, rect.width - 32, label, value, drone_type, unlocked)
            y += 26

        if unlocked:
            loadout = (
                f"{drone_type.units} airframe(s)"
                if drone_type.attack == "ram"
                else f"{drone_type.ammo} x {drone_type.ability_name.lower()}"
            )
            info = get_font(14, mono=True).render(loadout, True, constants.TEXT_DIM)
            surface.blit(info, (rect.x + 16, y + 6))

            ability = get_font(15, bold=True).render(drone_type.ability_name, True, drone_type.accent_color)
            surface.blit(ability, (rect.x + 16, y + 28))
            self._draw_wrapped(
                surface, drone_type.ability_desc, rect.x + 16, y + 50, rect.width - 32, constants.TEXT_FAINT
            )
        else:
            lock = get_font(16, bold=True).render("LOCKED", True, constants.WARN)
            surface.blit(lock, (rect.x + 16, y + 10))
            need = get_font(14, mono=True).render(
                f"Career score {drone_type.unlock_score}", True, constants.TEXT_FAINT
            )
            surface.blit(need, (rect.x + 16, y + 34))

    def _draw_silhouette(self, surface, rect, drone_type, unlocked):
        cx = rect.centerx
        cy = rect.y + 108
        color = drone_type.body_color if unlocked else (60, 66, 78)
        accent = drone_type.accent_color if unlocked else (70, 76, 90)
        size = 22
        points = [(cx + size * 1.2, cy), (cx - size * 0.8, cy + size * 0.75), (cx - size * 0.8, cy - size * 0.75)]
        pygame.draw.polygon(surface, color, points)
        pygame.draw.polygon(surface, accent, points, width=2)
        if drone_type.attack == "bomb":
            for dy in (-size, size):
                pygame.draw.circle(surface, accent, (int(cx), int(cy + dy)), 6, width=2)
        elif drone_type.key == "shahed":
            pygame.draw.line(surface, accent, (cx - 4, cy - size * 1.4), (cx - 4, cy + size * 1.4), 3)

    def _draw_stat_bar(self, surface, x, y, width, label, value, drone_type, unlocked):
        label_surf = get_font(12, mono=True).render(label, True, constants.TEXT_FAINT)
        surface.blit(label_surf, (x, y))
        bar_x = x + 66
        bar_w = width - 66
        pygame.draw.rect(surface, (32, 36, 46), (bar_x, y + 3, bar_w, 8), border_radius=4)
        fill = int(bar_w * clamp(value, 0.05, 1.0))
        color = drone_type.accent_color if unlocked else (60, 66, 78)
        pygame.draw.rect(surface, color, (bar_x, y + 3, fill, 8), border_radius=4)

    def _draw_wrapped(self, surface, text, x, y, width, color):
        font = get_font(13)
        words = text.split()
        line = ""
        line_y = y
        for word in words:
            probe = f"{line} {word}".strip()
            if font.size(probe)[0] > width and line:
                surface.blit(font.render(line, True, color), (x, line_y))
                line_y += 16
                line = word
            else:
                line = probe
        if line:
            surface.blit(font.render(line, True, color), (x, line_y))


class SettingsMenu(Screen):
    title = "SETTINGS"
    dim_background = True

    def __init__(self, settings, on_back, on_change):
        super().__init__()
        self.settings = settings
        cx = constants.WIDTH // 2
        row_w, row_h = 620, 56
        rows = [
            ("Difficulty", DIFFICULTIES, "difficulty"),
            ("Show FPS", ["Off", "On"], "show_fps"),
            ("Screen shake", ["Off", "On"], "screen_shake"),
            ("Touch controls", ["Auto", "On", "Off"], "touch_controls"),
        ]
        y = 200
        for label, values, key in rows:
            self.widgets.append(
                OptionRow(
                    (cx - row_w // 2, y, row_w, row_h),
                    label,
                    values,
                    self._make_getter(key, values),
                    self._make_setter(key, on_change),
                )
            )
            y += row_h + 14

        self.widgets.append(Button((cx - 110, y + 20, 220, 52), "BACK", on_back, font_size=24))

    def _make_getter(self, key, values):
        def getter():
            raw = self.settings.get(key)
            if isinstance(raw, bool):
                raw = "On" if raw else "Off"
            try:
                return values.index(raw)
            except ValueError:
                return 0

        return getter

    def _make_setter(self, key, on_change):
        def setter(value):
            if value in ("On", "Off") and key in ("show_fps", "screen_shake"):
                self.settings[key] = value == "On"
            else:
                self.settings[key] = value
            on_change()

        return setter

    def draw(self, surface):
        super().draw(surface)
        note = get_font(15).render(
            "Settings save automatically.", True, constants.TEXT_FAINT
        )
        surface.blit(note, note.get_rect(center=(constants.WIDTH // 2, constants.HEIGHT - 46)))


class PauseMenu(Screen):
    title = "PAUSED"
    dim_background = True

    def __init__(self, on_resume, on_change_drone, on_settings, on_main_menu, on_quit):
        super().__init__()
        cx = constants.WIDTH // 2
        y = 200
        for label, callback in (
            ("RESUME", on_resume),
            ("CHANGE AIRFRAME", on_change_drone),
            ("SETTINGS", on_settings),
            ("MAIN MENU", on_main_menu),
            ("QUIT GAME", on_quit),
        ):
            self.widgets.append(Button((cx - 140, y, 280, 52), label, callback, font_size=22))
            y += 62


class ResultMenu(Screen):
    """Shown after a mission ends -- win or lose."""

    dim_background = True

    def __init__(self, won, summary, on_retry, on_change_drone, on_main_menu):
        super().__init__()
        self.won = won
        self.summary = summary
        cx = constants.WIDTH // 2
        y = 430
        for label, callback in (
            ("FLY AGAIN", on_retry),
            ("CHANGE AIRFRAME", on_change_drone),
            ("MAIN MENU", on_main_menu),
        ):
            self.widgets.append(Button((cx - 140, y, 280, 52), label, callback, font_size=22))
            y += 62

    def draw(self, surface):
        if self._overlay_surface is not None:
            surface.blit(self._overlay_surface, (0, 0))

        heading = "MISSION COMPLETE" if self.won else "MISSION FAILED"
        color = constants.GOOD if self.won else constants.DANGER
        title = get_font(52, bold=True).render(heading, True, color)
        surface.blit(title, title.get_rect(center=(constants.WIDTH // 2, 150)))

        y = 232
        for label, value in self.summary:
            label_surf = get_font(20, mono=True).render(label, True, constants.TEXT_DIM)
            value_surf = get_font(20, bold=True, mono=True).render(str(value), True, constants.TEXT_COLOR)
            surface.blit(label_surf, (constants.WIDTH // 2 - 210, y))
            surface.blit(value_surf, (constants.WIDTH // 2 + 130 - value_surf.get_width(), y))
            y += 32

        for widget in self.widgets:
            widget.draw(surface)
