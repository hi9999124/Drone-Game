// Shared leveling/rank formula. Mirrored in src/leveling.py on the client so
// offline play (no account) computes the exact same level/rank locally.
//
// XP needed to go from level L to L+1 is 100*L, so cumulative XP to REACH
// level L works out to 100 * L * (L-1) / ... see cumulativeXpForLevel below.

export function cumulativeXpForLevel(level) {
  // XP required to have already reached the start of `level`.
  return 50 * (level - 1) * level;
}

export function levelForXp(xp) {
  let level = 1;
  while (cumulativeXpForLevel(level + 1) <= xp) {
    level += 1;
  }
  return level;
}

export function xpIntoLevel(xp) {
  const level = levelForXp(xp);
  return {
    level,
    xpAtLevelStart: cumulativeXpForLevel(level),
    xpForNextLevel: cumulativeXpForLevel(level + 1),
  };
}

const RANK_THRESHOLDS = [
  [1, "Rookie"],
  [5, "Cadet"],
  [10, "Veteran"],
  [20, "Ace"],
  [30, "Legend"],
];

export function rankForLevel(level) {
  let name = RANK_THRESHOLDS[0][1];
  for (const [minLevel, rankName] of RANK_THRESHOLDS) {
    if (level >= minLevel) {
      name = rankName;
    }
  }
  return name;
}

// Coins/XP earned from a single mission's score. Kept as a pure function of
// score (not e.g. wall-clock time) so there's nothing to game by idling.
export function rewardsForScore(score) {
  const xp = Math.max(0, Math.round(score));
  const coins = Math.max(0, Math.floor(score / 20));
  return { xp, coins };
}
