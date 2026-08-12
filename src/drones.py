from dataclasses import dataclass


@dataclass(frozen=True)
class DroneType:
    key: str
    name: str
    subtitle: str
    # How this airframe kills things:
    #   "ram"    - the drone itself is the warhead; hitting a target detonates it
    #   "bomb"   - drops gravity-fed bombs that need altitude and lead
    #   "rocket" - fires forward-flying rockets
    attack: str
    max_hp: float
    units: int  # airframes available; ram strikes and crashes consume one
    thrust: float
    reverse_thrust: float
    turn_speed: float  # degrees/second
    drag: float  # fraction of speed shed per second
    max_speed: float
    climb_speed: float
    ammo: int  # bombs/rockets per airframe (ignored by ram types)
    blast_radius: float
    blast_damage: float
    ability_name: str
    ability_desc: str
    cooldown: float
    unlock_score: int
    body_color: tuple
    accent_color: tuple
    size: float


DRONE_TYPES = [
    DroneType(
        key="fpv",
        name="FPV Kamikaze",
        subtitle="Cheap, fast, expendable",
        attack="ram",
        max_hp=2,
        units=5,
        thrust=640.0,
        reverse_thrust=300.0,
        turn_speed=250.0,
        drag=0.85,
        max_speed=560.0,
        climb_speed=150.0,
        ammo=0,
        blast_radius=95.0,
        # One-shot vs. a standard target's 260 HP: each airframe is a single
        # use, so a ram that doesn't destroy its target on impact would mean
        # you could never actually complete a mission (destroying all 5
        # targets would cost 3 airframes each -- 15 units against a loadout
        # of 5). "Kamikaze" implies a decisive hit, not a chip-damage one.
        blast_damage=270.0,
        ability_name="Boost",
        ability_desc="Short burst of speed to close the last 50 m before impact.",
        cooldown=2.5,
        unlock_score=0,
        body_color=(150, 235, 255),
        accent_color=(56, 214, 255),
        size=15.0,
    ),
    DroneType(
        key="baba",
        name="Baba Yaga",
        subtitle="Heavy night bomber",
        attack="bomb",
        max_hp=7,
        units=1,
        thrust=310.0,
        reverse_thrust=190.0,
        turn_speed=115.0,
        drag=0.55,
        max_speed=290.0,
        climb_speed=110.0,
        # A target has 260 hp and a direct hit deals 170, so even flawless
        # play (every bomb a dead-center hit, zero misses) needs 10 bombs
        # for 5 targets -- 8 was mathematically short regardless of skill.
        # 12 leaves a couple spare for the near-misses that are inevitable
        # given a bomb's gravity-drop aiming is inherently imprecise.
        ammo=12,
        blast_radius=145.0,
        blast_damage=170.0,
        ability_name="Drop Bomb",
        ability_desc="Releases a bomb that falls under gravity -- fly high and lead the target.",
        cooldown=0.8,
        unlock_score=500,
        body_color=(178, 198, 210),
        accent_color=(120, 200, 160),
        size=22.0,
    ),
    DroneType(
        key="shahed",
        name="Shahed-256",
        subtitle="Long-range loitering munition",
        attack="ram",
        max_hp=4,
        # A mission always spawns exactly 5 targets (see world.py's
        # _generate_city), and a ram-type drone consumes one airframe per
        # strike whether it hits or misses -- 2 units meant this drone could
        # never destroy more than 2/5 targets no matter how it was flown.
        # Matches FPV Kamikaze's unit count so a flawless run can actually win.
        units=5,
        thrust=800.0,
        reverse_thrust=140.0,
        turn_speed=72.0,
        drag=0.45,
        max_speed=740.0,
        climb_speed=95.0,
        ammo=0,
        blast_radius=200.0,
        blast_damage=280.0,
        ability_name="Terminal Dive",
        ability_desc="Commits to a screaming powered dive. Huge blast, almost no steering.",
        cooldown=6.0,
        unlock_score=1500,
        body_color=(206, 196, 160),
        accent_color=(255, 176, 66),
        size=20.0,
    ),
    DroneType(
        key="hornet",
        name="Hornet FPV",
        subtitle="Reusable rocket platform",
        attack="rocket",
        max_hp=4,
        units=1,
        thrust=470.0,
        reverse_thrust=260.0,
        turn_speed=185.0,
        drag=0.8,
        max_speed=470.0,
        climb_speed=130.0,
        ammo=14,
        blast_radius=75.0,
        blast_damage=95.0,
        ability_name="Fire Rocket",
        ability_desc="Flat-flying rocket. You keep the airframe -- line up and stay alive.",
        cooldown=0.35,
        unlock_score=3000,
        body_color=(198, 170, 235),
        accent_color=(186, 130, 255),
        size=17.0,
    ),
]

DRONES_BY_KEY = {d.key: d for d in DRONE_TYPES}


def get(key):
    return DRONES_BY_KEY.get(key, DRONE_TYPES[0])


def is_unlocked(drone_type, total_score):
    return total_score >= drone_type.unlock_score
