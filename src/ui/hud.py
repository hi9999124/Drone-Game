import pygame

from .. import constants
from ..utils import clamp
from .fonts import get_font


class HUD:
    def draw(self, surface, world, camera, show_fps=False, fps=0.0):
        if world.mode == "defense":
            self._draw_defense_hud(surface, world, camera)
        else:
            self._draw_strike_hud(surface, world, camera)
        if show_fps:
            text = get_font(15, mono=True).render(f"{fps:.0f} FPS", True, constants.TEXT_FAINT)
            surface.blit(text, (constants.WIDTH - text.get_width() - 14, 12))
        if world.message_timer > 0.0:
            self._draw_message(surface, world.message)

    def _draw_strike_hud(self, surface, world, camera):
        player = world.player
        if player is not None and player.alive:
            self._draw_flight_panel(surface, player)
            self._draw_ability(surface, player)
        self._draw_mission_panel(surface, world)
        self._draw_compass(surface, world, camera)
        self._draw_pvo_lock(surface, world)

    def _draw_defense_hud(self, surface, world, camera):
        player = world.player
        if player is not None and player.alive:
            self._draw_turret_panel(surface, player)
        self._draw_defense_mission_panel(surface, world)
        self._draw_raider_compass(surface, world, camera)

    def _panel(self, surface, rect):
        panel = pygame.Surface(rect.size, pygame.SRCALPHA)
        panel.fill((*constants.PANEL_BG, 195))
        surface.blit(panel, rect.topleft)
        pygame.draw.rect(surface, constants.PANEL_EDGE, rect, width=1, border_radius=8)

    def _draw_flight_panel(self, surface, player):
        rect = pygame.Rect(18, 18, 250, 118)
        self._panel(surface, rect)

        name = get_font(16, bold=True).render(player.type.name, True, player.type.accent_color)
        surface.blit(name, (rect.x + 14, rect.y + 10))

        readout = get_font(15, mono=True).render(
            f"SPD {player.speed:5.0f}   ALT {player.altitude:4.0f}", True, constants.TEXT_COLOR
        )
        surface.blit(readout, (rect.x + 14, rect.y + 34))

        # Altitude bar -- the key new readout for a 2.5D world.
        self._bar(
            surface,
            pygame.Rect(rect.x + 14, rect.y + 60, rect.width - 28, 8),
            player.altitude / constants.MAX_ALTITUDE,
            constants.ACCENT,
            "ALTITUDE",
        )
        self._bar(
            surface,
            pygame.Rect(rect.x + 14, rect.y + 90, rect.width - 28, 8),
            player.hp / player.type.max_hp,
            constants.GOOD if player.hp > player.type.max_hp * 0.35 else constants.DANGER,
            "INTEGRITY",
        )

    def _bar(self, surface, rect, fraction, color, label):
        pygame.draw.rect(surface, (34, 38, 48), rect, border_radius=4)
        width = int(rect.width * clamp(fraction, 0.0, 1.0))
        if width > 0:
            pygame.draw.rect(surface, color, (rect.x, rect.y, width, rect.height), border_radius=4)
        text = get_font(11, mono=True).render(label, True, constants.TEXT_FAINT)
        surface.blit(text, (rect.x, rect.y + 10))

    def _draw_ability(self, surface, player):
        rect = pygame.Rect(18, constants.HEIGHT - 92, 250, 74)
        self._panel(surface, rect)

        ready = player.cooldown <= 0.0
        has_ammo = player.type.attack == "ram" or player.ammo > 0
        if not has_ammo:
            status, color = "NO ORDNANCE", constants.DANGER
        elif ready:
            status, color = "READY", constants.GOOD
        else:
            status, color = f"{player.cooldown:.1f}s", constants.WARN

        name = get_font(16, bold=True).render(player.type.ability_name, True, constants.TEXT_COLOR)
        surface.blit(name, (rect.x + 14, rect.y + 10))
        status_surf = get_font(14, bold=True, mono=True).render(status, True, color)
        surface.blit(status_surf, (rect.right - status_surf.get_width() - 14, rect.y + 12))

        if player.type.attack == "ram":
            detail = f"AIRFRAMES {player.type.units}"
        else:
            detail = f"ORDNANCE {player.ammo}"
        detail_surf = get_font(13, mono=True).render(detail, True, constants.TEXT_DIM)
        surface.blit(detail_surf, (rect.x + 14, rect.y + 38))

        key_hint = get_font(12, mono=True).render("[F] / left click", True, constants.TEXT_FAINT)
        surface.blit(key_hint, (rect.x + 14, rect.y + 55))

    def _draw_mission_panel(self, surface, world):
        rect = pygame.Rect(constants.WIDTH - 268, 18, 250, 116)
        self._panel(surface, rect)

        title = get_font(15, bold=True).render("MISSION", True, constants.TEXT_DIM)
        surface.blit(title, (rect.x + 14, rect.y + 10))

        remaining = world.targets_remaining
        total = len(world.targets)
        targets = get_font(17, bold=True, mono=True).render(
            f"TARGETS  {total - remaining}/{total}", True, constants.DANGER if remaining else constants.GOOD
        )
        surface.blit(targets, (rect.x + 14, rect.y + 32))

        score = get_font(17, bold=True, mono=True).render(f"SCORE   {world.score:6d}", True, constants.ACCENT)
        surface.blit(score, (rect.x + 14, rect.y + 56))

        units = get_font(13, mono=True).render(
            f"units {world.units_left}   hostiles {len(world.enemies)}", True, constants.TEXT_FAINT
        )
        surface.blit(units, (rect.x + 14, rect.y + 76))

        if world.pvo_total:
            pvo = get_font(13, mono=True).render(
                f"air defense {world.pvo_destroyed}/{world.pvo_total}", True, constants.TEXT_FAINT
            )
            surface.blit(pvo, (rect.x + 14, rect.y + 96))

    def _draw_compass(self, surface, world, camera):
        """Edge arrows pointing at surviving targets that are off-screen."""
        player = world.player
        if player is None or not player.alive:
            return
        center = pygame.Vector2(constants.WIDTH * 0.5, constants.HEIGHT * 0.5)
        for building in world.targets:
            if building.destroyed:
                continue
            if camera.is_visible(building.rect.centerx, building.rect.centery, 0):
                continue
            direction = building.center - player.pos
            if direction.length_squared() < 1:
                continue
            direction = direction.normalize()
            edge = center + direction * (min(constants.WIDTH, constants.HEIGHT) * 0.42)
            perpendicular = pygame.Vector2(-direction.y, direction.x)
            tip = edge + direction * 12
            left = edge - direction * 6 + perpendicular * 7
            right = edge - direction * 6 - perpendicular * 7
            pygame.draw.polygon(surface, constants.DANGER, [tip, left, right])

    def _draw_pvo_lock(self, surface, world):
        """Fair warning before a SAM/flak site can actually fire -- the lock
        bar is the player's real window to break line of sight, leave
        detection range, or just outrun it before `lock_time` runs out."""
        from ..entities.pvo import STATE_LOCKED, STATE_TRACKING

        active = [t for t in world.pvo_units if t.alive and t.state in (STATE_TRACKING, STATE_LOCKED)]
        if not active:
            return
        turret = max(active, key=lambda t: t.lock_progress)
        locked = turret.state == STATE_LOCKED
        color = constants.DANGER if locked else constants.WARN
        label = f"{turret.type.name.upper()} {'LOCK' if locked else 'TRACKING'}"

        text = get_font(20, bold=True, mono=True).render(label, True, color)
        rect = text.get_rect(center=(constants.WIDTH // 2, 100))
        surface.blit(text, rect)

        bar_w, bar_h = 220, 8
        bar_x = constants.WIDTH // 2 - bar_w // 2
        bar_y = rect.bottom + 8
        pygame.draw.rect(surface, (40, 20, 24), (bar_x, bar_y, bar_w, bar_h), border_radius=4)
        fill_w = int(bar_w * clamp(turret.lock_progress, 0.0, 1.0))
        if fill_w > 0:
            pygame.draw.rect(surface, color, (bar_x, bar_y, fill_w, bar_h), border_radius=4)

    def _draw_turret_panel(self, surface, player):
        rect = pygame.Rect(18, 18, 250, 128)
        self._panel(surface, rect)

        name = get_font(16, bold=True).render(player.type.name, True, player.type.accent_color)
        surface.blit(name, (rect.x + 14, rect.y + 10))

        self._bar(
            surface,
            pygame.Rect(rect.x + 14, rect.y + 40, rect.width - 28, 8),
            player.hp / player.max_hp,
            constants.GOOD if player.hp > player.max_hp * 0.35 else constants.DANGER,
            "INTEGRITY",
        )

        ready = player.cooldown <= 0.0
        if player.ammo <= 0:
            status, color = "NO AMMO", constants.DANGER
        elif ready:
            status, color = "READY", constants.GOOD
        else:
            status, color = f"{player.cooldown:.1f}s", constants.WARN
        status_surf = get_font(14, bold=True, mono=True).render(status, True, color)
        surface.blit(status_surf, (rect.x + 14, rect.y + 70))

        ammo_label = "MISSILES" if player.type.homing else "ROUNDS"
        ammo_surf = get_font(13, mono=True).render(f"{ammo_label} {player.ammo}", True, constants.TEXT_DIM)
        surface.blit(ammo_surf, (rect.x + 14, rect.y + 92))

        key_hint = get_font(12, mono=True).render("A/D aim  -  [F] / left click fire", True, constants.TEXT_FAINT)
        surface.blit(key_hint, (rect.x + 14, rect.y + 112))

    def _draw_defense_mission_panel(self, surface, world):
        rect = pygame.Rect(constants.WIDTH - 268, 18, 250, 116)
        self._panel(surface, rect)

        title = get_font(15, bold=True).render("AIR DEFENSE", True, constants.TEXT_DIM)
        surface.blit(title, (rect.x + 14, rect.y + 10))

        remaining = world.protected_remaining
        total = len(world.protected)
        structures = get_font(17, bold=True, mono=True).render(
            f"SAVED    {remaining}/{total}", True, constants.GOOD if remaining == total else constants.WARN
        )
        surface.blit(structures, (rect.x + 14, rect.y + 32))

        score = get_font(17, bold=True, mono=True).render(f"SCORE   {world.score:6d}", True, constants.ACCENT)
        surface.blit(score, (rect.x + 14, rect.y + 56))

        wave = get_font(13, mono=True).render(
            f"wave {world.wave}/{world.wave_total}   raiders {len(world.raiders)}", True, constants.TEXT_FAINT
        )
        surface.blit(wave, (rect.x + 14, rect.y + 76))

        downed = get_font(13, mono=True).render(
            f"downed {world.raiders_destroyed}", True, constants.TEXT_FAINT
        )
        surface.blit(downed, (rect.x + 14, rect.y + 96))

    def _draw_raider_compass(self, surface, world, camera):
        """Edge arrows pointing at incoming raiders that are off-screen --
        the defense-mode analog of _draw_compass, pointing at threats
        instead of objectives."""
        player = world.player
        if player is None or not player.alive:
            return
        center = pygame.Vector2(constants.WIDTH * 0.5, constants.HEIGHT * 0.5)
        for raider in world.raiders:
            if not raider.alive:
                continue
            if camera.is_visible(raider.pos.x, raider.pos.y, 0):
                continue
            direction = raider.pos - player.pos
            if direction.length_squared() < 1:
                continue
            direction = direction.normalize()
            edge = center + direction * (min(constants.WIDTH, constants.HEIGHT) * 0.42)
            perpendicular = pygame.Vector2(-direction.y, direction.x)
            tip = edge + direction * 12
            left = edge - direction * 6 + perpendicular * 7
            right = edge - direction * 6 - perpendicular * 7
            pygame.draw.polygon(surface, constants.WARN, [tip, left, right])

    def _draw_message(self, surface, message):
        text = get_font(26, bold=True).render(message, True, constants.WARN)
        rect = text.get_rect(center=(constants.WIDTH // 2, 150))
        backdrop = pygame.Surface((rect.width + 32, rect.height + 16), pygame.SRCALPHA)
        backdrop.fill((*constants.PANEL_BG, 190))
        surface.blit(backdrop, (rect.x - 16, rect.y - 8))
        surface.blit(text, rect)
