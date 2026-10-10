"""Deterministic cell scatter; identical hash to native VxpScatter2D."""
def cell_hash(x, y, seed=1):
    v = ((x & 0xffffffff) * 0x8da6b343 ^ (y & 0xffffffff) * 0xd8163841 ^ seed) & 0xffffffff
    v ^= v >> 16
    v = (v * 0x7feb352d) & 0xffffffff
    v ^= v >> 15
    return v

def scatter_cells(tilemap, coords, variants, density=35, spacing=1, seed=1):
    layer = tilemap.active_layer
    if layer.locked or not variants:
        return []
    edits = []
    gap = max(1, min(32, int(spacing)))
    for x, y in sorted(set(coords), key=lambda p: (p[1], p[0])):
        if not layer.inside(x, y) or layer.get(x, y) != -1:
            continue
        h = cell_hash(x, y, seed)
        if h % 100 >= max(0, min(100, density)):
            continue
        if any(layer.get(nx, ny) != -1 for ny in range(y-gap+1, y+gap)
               for nx in range(x-gap+1, x+gap)):
            continue
        tile = variants[(h >> 8) % len(variants)]
        edits.extend(tilemap.paint(x, y, tile))
    return edits
