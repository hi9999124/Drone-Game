# Mirrors backend/src/levels.js exactly, so offline play (no account) and
# server-synced totals never disagree once a device signs in and catches up.

RANK_THRESHOLDS = [
    (1, "Rookie"),
    (5, "Cadet"),
    (10, "Veteran"),
    (20, "Ace"),
    (30, "Legend"),
]


def cumulative_xp_for_level(level):
    """XP required to have already reached the start of `level`."""
    return 50 * (level - 1) * level


def level_for_xp(xp):
    level = 1
    while cumulative_xp_for_level(level + 1) <= xp:
        level += 1
    return level


def xp_progress(xp):
    """(level, xp_into_level, xp_needed_for_level) for a level-progress bar."""
    level = level_for_xp(xp)
    start = cumulative_xp_for_level(level)
    end = cumulative_xp_for_level(level + 1)
    return level, xp - start, end - start


def rank_for_level(level):
    name = RANK_THRESHOLDS[0][1]
    for min_level, rank_name in RANK_THRESHOLDS:
        if level >= min_level:
            name = rank_name
    return name


def rewards_for_score(score):
    score = max(0, round(score))
    xp = score
    coins = max(0, score // 20)
    return xp, coins
