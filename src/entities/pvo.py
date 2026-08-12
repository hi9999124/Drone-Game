from dataclasses import dataclass

import pygame

from .. import constants
from ..utils import clamp

STATE_IDLE = "idle"
STATE_TRACKING = "tracking"
STATE_LOCKED = "locked"


@dataclass(frozen=True)
class PVOUnitType:
    key: str
    name: str
    subtitle: str
    max_hp: float
    detect_range: float  # radar/visual detection radius
    detect_ceiling: float  # None = detects at any altitude; else max altitude it can see
    lock_time: float  # seconds of continuous track before it's allowed to fire
    fire_range: float
    cooldown: float
    damage: float
    blast_radius: float
    projectile_speed: float
    homing: bool  # guided missile that steers toward the target vs. dumb flak
    turn_rate: float  # missile homing turn rate, deg/sec -- irrelevant if not homing
    body_color: tuple
    accent_color: tuple
    size: float


PVO_UNIT_TYPES = [
    PVOUnitType(
        key="aagun",
        name="ZU-23 Flak",
        subtitle="Rapid-fire anti-air gun",
        max_hp=40.0,
        detect_range=420.0,
        # Real flak is a low-altitude threat -- radar-guided SAMs are what
        # reach up high, not visually-aimed autocannons. This keeps the
        # "climb above 200m" lesson still meaningfully true against guns,
        # while SAMs (below) add a reason to not just loiter up there either.
        detect_ceiling=180.0,
        lock_time=0.35,
        fire_range=380.0,
        cooldown=0.3,
        damage=1.1,
        blast_radius=28.0,
        projectile_speed=900.0,
        homing=False,
        turn_rate=0.0,
        body_color=(150, 160, 140),
        accent_color=(214, 196, 90),
        size=15.0,
    ),
    PVOUnitType(
        key="sam",
        name="Buk Battery",
        subtitle="Long-range guided SAM",
        max_hp=70.0,
        detect_range=900.0,
        detect_ceiling=None,
        # Long enough to be a fair, visible warning (see HUD lock indicator)
        # rather than an instant unavoidable hit -- the point is "get out of
        # its envelope or break the lock", not "die if it sees you".
        lock_time=2.2,
        fire_range=850.0,
        cooldown=5.5,
        damage=3.2,
        blast_radius=95.0,
        projectile_speed=460.0,
        homing=True,
        turn_rate=110.0,
        body_color=(120, 130, 118),
        accent_color=(230, 100, 90),
        size=24.0,
    ),
]

PVO_UNITS_BY_KEY = {u.key: u for u in PVO_UNIT_TYPES}


class PVOTurret:
    """Ground-based air defence: ZU-23 flak or a Buk-style SAM battery.

    Static (no movement), but not passive -- it detects, tracks, and only
    fires once it's held a lock for `lock_time`, which is also the player's
    fair-warning window (see HUD.draw_pvo_lock). SAM missiles home in on the
    target rather than flying straight, unlike the flak gun's unguided burst.
    """

    def __init__(self, x, y, unit_type):
        self.pos = pygame.Vector2(x, y)
        self.altitude = 0.0
        self.type = unit_type
        self.hp = unit_type.max_hp
        self.alive = True
        self.state = STATE_IDLE
        self.lock_progress = 0.0  # 0..1, drives the HUD warning bar
        self.cooldown = 0.0
        self.radius = unit_type.size

    def take_damage(self, amount):
        self.hp -= amount
        if self.hp <= 0:
            self.alive = False
            return True
        return False

    def update(self, dt, player):
        if not self.alive:
            return None
        self.cooldown = max(0.0, self.cooldown - dt)

        detected = self._can_detect(player)
        if detected:
            self.state = STATE_TRACKING if self.lock_progress < 1.0 else STATE_LOCKED
            self.lock_progress = clamp(self.lock_progress + dt / self.type.lock_time, 0.0, 1.0)
        else:
            self.state = STATE_IDLE
            # Lock decays rather than resetting instantly -- a brief dip
            # behind cover shouldn't fully undo several seconds of tracking,
            # but sustained evasion does.
            self.lock_progress = clamp(self.lock_progress - dt / self.type.lock_time * 0.5, 0.0, 1.0)

        if detected and self.lock_progress >= 1.0 and self.cooldown <= 0.0:
            self.cooldown = self.type.cooldown
            return self._fire(player)
        return None

    def _can_detect(self, player):
        if player is None or not player.alive_and_well:
            return False
        if self.type.detect_ceiling is not None and player.altitude > self.type.detect_ceiling:
            return False
        dist = (player.pos - self.pos).length()
        return dist <= self.type.detect_range

    def _fire(self, player):
        to_player = pygame.Vector2(player.pos) - self.pos
        if to_player.length_squared() < 1e-4:
            to_player = pygame.Vector2(1, 0)
        direction = to_player.normalize()
        return {
            "pos": pygame.Vector2(self.pos),
            "altitude": self.altitude + self.type.size * 0.5,
            "velocity": direction * self.type.projectile_speed,
            "damage": self.type.damage,
            "blast_radius": self.type.blast_radius,
            "homing": self.type.homing,
            "turn_rate": self.type.turn_rate,
        }

    def draw(self, surface, camera):
        sx, sy = camera.to_screen(self.pos.x, self.pos.y, 0.0)
        size = self.radius
        pygame.draw.circle(surface, (30, 34, 40), (int(sx), int(sy + 4)), int(size * 0.9))
        pygame.draw.rect(
            surface,
            self.type.body_color,
            (int(sx - size * 0.55), int(sy - size * 0.35), int(size * 1.1), int(size * 0.7)),
            border_radius=3,
        )
        barrel_len = size * (1.3 if self.type.key == "sam" else 1.0)
        pygame.draw.line(
            surface,
            self.type.accent_color,
            (sx, sy - size * 0.15),
            (sx, sy - size * 0.15 - barrel_len),
            4 if self.type.key == "sam" else 2,
        )

        if self.state != STATE_IDLE:
            ring_color = constants.DANGER if self.state == STATE_LOCKED else constants.WARN
            pygame.draw.circle(surface, ring_color, (int(sx), int(sy)), int(size * 1.6), width=2)

        if self.hp < self.type.max_hp:
            bar_w = size * 1.8
            frac = clamp(self.hp / self.type.max_hp, 0.0, 1.0)
            pygame.draw.rect(surface, (40, 20, 24), (sx - bar_w / 2, sy - size * 1.9, bar_w, 4))
            pygame.draw.rect(surface, constants.DANGER, (sx - bar_w / 2, sy - size * 1.9, bar_w * frac, 4))
