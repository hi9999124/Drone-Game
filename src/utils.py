def lerp(a, b, t):
    return a + (b - a) * t


def lerp_color(c1, c2, t):
    return tuple(int(lerp(c1[i], c2[i], t)) for i in range(3))


def clamp(value, low, high):
    return low if value < low else high if value > high else value


def approach(current, target, rate, dt):
    """Move `current` toward `target` at `rate` units/second (never overshooting)."""
    step = rate * dt
    if current < target:
        return min(current + step, target)
    return max(current - step, target)
