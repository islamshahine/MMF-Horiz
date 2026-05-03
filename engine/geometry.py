import math

def segment_area(h, D):
    R = D / 2
    if h <= 0:
        return 0.0
    if h >= D:
        return math.pi * R**2

    val = max(-1.0, min(1.0, (R - h) / R))
    theta = 2 * math.acos(val)
    return 0.5 * R**2 * (theta - math.sin(theta))


def dish_volume(h, D, h_dish, end_type):
    if end_type == "Elliptic 2:1":
        factor = 1/3
    else:
        factor = 4/15

    total_dish_vol = factor * (math.pi/4) * (D**2) * h_dish

    if h >= D:
        return total_dish_vol

    ratio = h / D
    return total_dish_vol * (3 * ratio**2 - 2 * ratio**3)