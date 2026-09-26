"""Pagoda-on-book mark built on a 240-unit grid. All shapes are filled (no strokes)."""
PHI = 1.618
CX = 120

def tier(ry, half, drop, thick, flare):
    """One roof tier: a crescent with sharp, upswept eave tips.
    ry = ridge y, half = half width, drop = ridge-to-eave height, thick = centre thickness."""
    ey = ry + drop
    tl, tr = (CX - half, ey - flare), (CX + half, ey - flare)
    return (f"M{tl[0]:.2f} {tl[1]:.2f} "
            f"Q {CX - half*0.42:.2f} {ey:.2f} {CX:.2f} {ry:.2f} "           # top slope, left (concave)
            f"Q {CX + half*0.42:.2f} {ey:.2f} {tr[0]:.2f} {tr[1]:.2f} "     # top slope, right
            f"Q {CX + half*0.46:.2f} {ey + thick*0.62:.2f} {CX:.2f} {ry + thick:.2f} "   # underside right
            f"Q {CX - half*0.46:.2f} {ey + thick*0.62:.2f} {tl[0]:.2f} {tl[1]:.2f} Z")   # underside left

def mark_shapes(gap=10.0):
    step = PHI ** 0.5                                          # sqrt(phi): wide, flat pagoda tiers
    halves = [48.0, 48.0 * step, 48.0 * step * step]           # 48, 61, 77.7
    drops = [h * 0.27 for h in halves]
    thick = [15.0, 17.0, 19.0]
    flare = [6.0, 7.5, 9.0]
    shapes, y = [], 74.0
    for h, d, t, f in zip(halves, drops, thick, flare):
        shapes.append(tier(y, h, d, t, f))
        y = y + t + gap                                       # next ridge sits one gap below this tier's centre
    # finial (gajur): a tapered spire + orb, one gap above the top ridge
    top = 74.0 - gap + 4
    # spire (gajur): tall, straight-sided, with a small collar where it meets the roof
    shapes.append(f"M{CX:.2f} {top-32:.2f} L {CX+4:.2f} {top-6:.2f} L {CX+7:.2f} {top:.2f} "
                  f"L {CX-7:.2f} {top:.2f} L {CX-4:.2f} {top-6:.2f} Z")
    # open book: two pages with a spine gap, one gap below the lowest tier's eaves
    bottom_tier_eave = y - thick[-1] - gap + drops[-1]
    by = bottom_tier_eave + gap + 5
    w, hgt, sag, spine = 58.0, 14.0, 6.0, 3.0
    left = (f"M{CX-spine:.2f} {by+sag:.2f} Q {CX-w*0.5:.2f} {by-sag*0.9:.2f} {CX-w:.2f} {by:.2f} "
            f"L {CX-w:.2f} {by+hgt:.2f} Q {CX-w*0.5:.2f} {by+hgt-sag*0.9:.2f} {CX-spine:.2f} {by+hgt+sag:.2f} Z")
    right = left.replace(f"{CX-spine:.2f}", "S1").replace(f"{CX-w*0.5:.2f}", "S2").replace(f"{CX-w:.2f}", "S3")
    right = right.replace("S1", f"{CX+spine:.2f}").replace("S2", f"{CX+w*0.5:.2f}").replace("S3", f"{CX+w:.2f}")
    shapes += [left, right]
    return shapes

def svg(shapes, fill, bg=None, circle=None, vb="0 0 240 240", extra="", dy=6):
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}">']
    if bg:
        parts.append(f'<rect width="100%" height="100%" fill="{bg}"/>')
    if circle:
        parts.append(f'<circle cx="120" cy="120" r="112" fill="{circle}"/>')
    parts.append(f'<g transform="translate(0 {dy})">')
    parts += [f'<path d="{d}" fill="{fill}"/>' for d in shapes]
    parts.append("</g>")
    parts.append(extra + "</svg>")
    return "".join(parts)

