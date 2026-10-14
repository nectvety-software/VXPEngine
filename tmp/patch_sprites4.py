"""Scratch patch round 4: boxier vest, four pockets, wider hips, undersuit."""
import io

p = 'tools/generate_stormarena_sprites.py'
s = io.open(p, encoding='utf-8').read()
miss = []


def rep(a, b):
    global s
    if a not in s:
        miss.append(a.split('\n')[0][:70])
        return
    s = s.replace(a, b, 1)


rep("""    p.strip([(33, 40, 16.2), (42, 40, 19.2), (58, 40, 19.4),
             (72, 40, 18.0), (78, 40, 15.2)], VEST)""",
    """    p.strip([(33, 40, 16.6), (40, 40, 20.2), (56, 40, 20.4),
             (68, 40, 19.4), (74, 40, 16.4)], VEST)""")

rep("""    # centre seam and the four pocket blocks with flaps and ridges
    p.strip([(36, 40.5, 0.9), (77, 40.5, 0.9)], VEST_D)
    for px0 in (25, 44):
        p.rect(px0, 46, 12, 16, VEST_D)
        p.rect(px0 - 1, 43, 14, 4, VEST)
        p.hline(px0 - 1, px0 + 12, 47, VEST)       # flap highlight
        for k in range(1, 5):
            p.hline(px0 + 1, px0 + 10, 46 + k * 3, VEST_D)
    p.strip([(76, 40, 16.0), (79, 40, 15.0)], VEST_D)   # hem shadow""",
    """    # centre seam, then the four flak-jacket pockets with flaps and ridges
    p.strip([(36, 40.5, 0.9), (73, 40.5, 0.9)], VEST_D)
    for px0 in (24, 45):
        for py0, ph in ((44, 11), (57, 11)):
            p.rect(px0, py0, 11, ph, VEST_D)
            p.rect(px0 - 1, py0 - 3, 13, 4, VEST)
            p.hline(px0 - 1, px0 + 11, py0, VEST)  # flap highlight
            for k in range(1, 4):
                p.hline(px0 + 1, px0 + 9, py0 + k * 3, VEST_D)
    p.strip([(72, 40, 16.8), (75, 40, 15.8)], VEST_D)   # hem shadow
    # dark undersuit showing between the vest hem and the pants waistband
    p.strip([(74, 40, 15.4), (82, 40, 14.2)], CLOTH)""")

rep("""    mid_x = (hip_x + knee_x) / 2.0
    p.tube(hip_x, hip_y, 11.4, mid_x, 100, 10.2, PANTS)
    p.tube(mid_x, 100, 10.2, knee_x, knee_y, 8.4, PANTS)""",
    """    mid_x = (hip_x + knee_x) / 2.0
    p.tube(hip_x, hip_y, 12.2, mid_x, 100, 10.6, PANTS)
    p.tube(mid_x, 100, 10.6, knee_x, knee_y, 8.4, PANTS)""")

rep("""    thigh = ((mid_x, 100, 10.2), (knee_x, knee_y, 8.4))""",
    """    thigh = ((mid_x, 100, 10.6), (knee_x, knee_y, 8.4))""")

rep("""    p.tube(HIP_L, HIP_Y, 11.4, 26, 96, 9.6, PANTS)""",
    """    p.tube(HIP_L, HIP_Y, 12.2, 26, 96, 10.0, PANTS)""")
rep("""    p.tube(HIP_R, HIP_Y, 11.4, 54, 94, 9.6, PANTS)""",
    """    p.tube(HIP_R, HIP_Y, 12.2, 54, 94, 10.0, PANTS)""")
rep("""    p.tube(HIP_R, HIP_Y + 2, 11.2, 66, HIP_Y + 6, 9.4, PANTS)""",
    """    p.tube(HIP_R, HIP_Y + 2, 12.0, 66, HIP_Y + 6, 9.8, PANTS)""")

# the head sat a touch low in the shoulders; lift the whole hair mass 1 px
rep("""    p.ellipse(40, 15, 10.6, 9.0, HAIR)""",
    """    p.ellipse(40, 14, 10.6, 9.0, HAIR)""")

io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('misses:', miss if miss else 'none')
