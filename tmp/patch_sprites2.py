"""Scratch patch round 2 for the StormArena sprite author geometry."""
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


# --- head: shorter tips, narrower nape lock so the hair stops reading as a hat
rep("""    for (ax, ay, aw, tx, ty) in [(34, 10, 4.4, 29, 4), (39, 9, 4.8, 37, 3),
                                 (45, 10, 4.4, 46, 5), (50, 13, 3.8, 53, 10)]:
        p.taper(ax, ay, aw, tx, ty, HAIR)
    # nape lock that falls behind the collar
    p.strip([(17, 30, 3.8), (26, 29, 3.2), (31, 29, 2.2)], HAIR)""",
    """    for (ax, ay, aw, tx, ty) in [(34, 11, 4.2, 30, 6), (39, 10, 4.6, 38, 4),
                                 (45, 11, 4.2, 46, 7), (50, 13, 3.6, 53, 11)]:
        p.taper(ax, ay, aw, tx, ty, HAIR)
    # nape lock that falls behind the collar
    p.strip([(18, 29, 3.4), (26, 28, 2.8), (31, 28, 1.8)], HAIR)""")

# --- torso: wider chest, deeper hem, larger pocket blocks
rep("""    p.strip([(34, 40, 16.0), (42, 40, 19.4), (58, 40, 19.6),
             (70, 40, 18.0), (76, 40, 15.4)], VEST)""",
    """    p.strip([(33, 40, 16.6), (42, 40, 20.4), (58, 40, 20.6),
             (72, 40, 19.0), (78, 40, 15.8)], VEST)""")

rep("""    for px0 in (26, 44):
        p.rect(px0, 47, 11, 14, VEST_D)
        p.rect(px0 - 1, 44, 13, 4, VEST)
        p.hline(px0 - 1, px0 + 11, 48, VEST)       # flap highlight
        for k in range(1, 4):
            p.hline(px0 + 1, px0 + 9, 47 + k * 3, VEST_D)
    p.strip([(74, 40, 15.6), (77, 40, 14.8)], VEST_D)   # hem shadow""",
    """    for px0 in (25, 44):
        p.rect(px0, 46, 12, 16, VEST_D)
        p.rect(px0 - 1, 43, 14, 4, VEST)
        p.hline(px0 - 1, px0 + 12, 47, VEST)       # flap highlight
        for k in range(1, 5):
            p.hline(px0 + 1, px0 + 10, 46 + k * 3, VEST_D)
    p.strip([(76, 40, 16.0), (79, 40, 15.0)], VEST_D)   # hem shadow""")

rep("    p.strip([(37, 40.5, 0.9), (75, 40.5, 0.9)], VEST_D)",
    "    p.strip([(36, 40.5, 0.9), (77, 40.5, 0.9)], VEST_D)")

# --- arms: push them outside the vest silhouette, shrink the armband to a band
rep("""    p.tube(SH_L, SH_Y + 2, 5.8, 18, 54, 5.2, CLOTH)
    p.tube(18, 54, 5.2, 15, 72, 4.4, CLOTH)
    p.tube(20, 43, 5.9, 19, 51, 5.4, ACCENT)                   # armband patch
    p.tube(17, 58, 5.2, 15, 70, 4.5, WRAP)                     # forearm bandage
    p.tube(15, 72, 4.2, 14, 78, 3.8, SKIN)                     # bare wrist
    p.ellipse(14, 84, 4.8, 6.0, GLOVE)
    p.hline(10, 18, 82, CLOTH)                                 # glove strap
    p.tube(12, 88, 2.6, 17, 90, 2.2, SKIN)                     # knuckles""",
    """    p.tube(SH_L, SH_Y + 2, 5.6, 15, 54, 5.0, CLOTH)
    p.tube(15, 54, 5.0, 12, 72, 4.2, CLOTH)
    p.strip([(45, 14.6, 5.4), (50, 13.8, 5.1)], ACCENT)        # armband
    p.strip([(57, 14.0, 4.9), (67, 12.4, 4.3)], WRAP)          # forearm bandage
    p.tube(12, 72, 4.0, 11, 78, 3.6, SKIN)                     # bare wrist
    p.ellipse(11, 84, 4.6, 6.0, GLOVE)
    p.hline(7, 15, 82, CLOTH)                                  # glove strap
    p.tube(9, 88, 2.5, 14, 90, 2.1, SKIN)                      # knuckles""")

rep("""    p.tube(SH_R, SH_Y + 2, 5.8, 64, 54, 5.2, CLOTH)
    p.tube(64, 54, 5.2, 56, 46, 4.4, CLOTH)
    p.tube(62, 41, 5.4, 63, 49, 5.0, ACCENT)
    p.tube(61, 50, 4.6, 58, 47, 4.2, WRAP)
    p.tube(56, 46, 4.0, 52, 43, 3.6, SKIN)
    p.ellipse(49, 41, 5.0, 5.2, GLOVE)
    p.hline(45, 50, 37, SKIN)                   # finger tips""",
    """    p.tube(SH_R, SH_Y + 2, 5.6, 66, 54, 5.0, CLOTH)
    p.tube(66, 54, 5.0, 58, 46, 4.2, CLOTH)
    p.strip([(44, 65.4, 5.2), (49, 64.4, 5.0)], ACCENT)
    p.strip([(50, 63.0, 4.6), (55, 61.0, 4.3)], WRAP)
    p.tube(58, 46, 3.9, 53, 43, 3.5, SKIN)
    p.ellipse(50, 41, 4.9, 5.1, GLOVE)
    p.hline(46, 51, 37, SKIN)                    # finger tips""")

rep("""    p.tube(SH_R, SH_Y + 4, 5.8, 70, SH_Y + 6, 5.0, CLOTH)
    p.tube(60, SH_Y + 3, 5.5, 66, SH_Y + 9, 5.1, ACCENT)
    p.tube(70, SH_Y + 2, 4.8, 70, SH_Y + 10, 4.4, WRAP)
    p.tube(72, SH_Y + 6, 4.0, 79, SH_Y + 6, 3.6, SKIN)""",
    """    p.tube(SH_R, SH_Y + 4, 5.6, 70, SH_Y + 6, 4.9, CLOTH)
    p.strip([(SH_Y + 2, 63, 5.4), (SH_Y + 8, 63, 5.2)], ACCENT)
    p.strip([(SH_Y + 2, 70, 4.8), (SH_Y + 10, 70, 4.4)], WRAP)
    p.tube(72, SH_Y + 6, 4.0, 79, SH_Y + 6, 3.6, SKIN)""")

rep("""    p.tube(SH_R, SH_Y + 2, 5.8, 66, 26, 5.2, CLOTH)
    p.tube(66, 26, 5.2, 63, 14, 4.4, CLOTH)
    p.tube(65, 20, 4.8, 64, 27, 4.4, WRAP)""",
    """    p.tube(SH_R, SH_Y + 2, 5.6, 68, 26, 5.0, CLOTH)
    p.tube(68, 26, 5.0, 65, 14, 4.2, CLOTH)
    p.strip([(21, 67.4, 4.7), (27, 66.6, 4.4)], WRAP)""")

# --- legs: narrower, greyer shin wrap and knee bands; readable sandals
rep("""    if bands:                                      # the near leg's two bands
        p.tube(knee_x + 0.4, 103, 8.8, knee_x + 0.4, 107, 8.4, WRAP)
        p.tube(knee_x + 0.8, 111, 8.2, knee_x + 0.8, 115, 7.8, WRAP)
    p.tube(ankle_x - 0.4, knee_y + 10, 5.8, ankle_x, ankle_y + 1, 5.0, WRAP)
    # sandal: instep, sole plank, exposed toes, strap over the instep
    p.tube(ankle_x - 1, ankle_y + 3, 5.6, ankle_x + 5, ankle_y + 8, 5.0,
           SANDAL)
    p.poly([(ankle_x - 8, SOLE_Y - 6), (ankle_x + 13, SOLE_Y - 6),
            (ankle_x + 14, SOLE_Y), (ankle_x - 9, SOLE_Y)], SANDAL)
    p.ellipse(ankle_x + 10, SOLE_Y - 7, 4.4, 3.2, SKIN)
    p.tube(ankle_x - 3, ankle_y + 6, 1.8, ankle_x + 8, SOLE_Y - 8, 1.5, SANDAL)""",
    """    if bands:                                      # the near leg's two bands
        p.strip([(104, knee_x + 0.6, 8.4), (107, knee_x + 0.6, 8.2)], WRAP)
        p.strip([(112, knee_x + 0.8, 8.0), (115, knee_x + 0.8, 7.8)], WRAP)
    p.strip([(knee_y + 12, ankle_x - 0.2, 5.4), (ankle_y + 1, ankle_x, 4.6)],
            WRAP)
    # sandal: instep collar, sole plank, exposed toes, strap across the instep
    p.poly([(ankle_x - 6, ankle_y + 2), (ankle_x + 5, ankle_y + 3),
            (ankle_x + 6, ankle_y + 10), (ankle_x - 7, ankle_y + 9)], SANDAL)
    p.poly([(ankle_x - 7, SOLE_Y - 5), (ankle_x + 12, SOLE_Y - 6),
            (ankle_x + 13, SOLE_Y), (ankle_x - 8, SOLE_Y)], SANDAL)
    p.ellipse(ankle_x + 8, SOLE_Y - 8, 5.0, 3.0, SKIN)
    p.tube(ankle_x - 3, ankle_y + 6, 1.7, ankle_x + 5, SOLE_Y - 9, 1.4, SANDAL)""")

rep("""    p.tube(HIP_R, HIP_Y + 2, 11.2, 66, HIP_Y + 6, 9.4, PANTS)
    p.tube(66, HIP_Y + 6, 9.4, 84, HIP_Y + 10, 6.4, PANTS)
    p.tube(78, HIP_Y + 6, 7.0, 84, HIP_Y + 9, 6.0, WRAP)
    p.poly([(82, HIP_Y + 2), (94, HIP_Y + 6), (93, HIP_Y + 18),
            (81, HIP_Y + 16)], SANDAL)
    p.ellipse(90, HIP_Y + 10, 3.0, 3.4, SKIN)
    p.tube(84, HIP_Y + 4, 1.7, 92, HIP_Y + 9, 1.4, SANDAL)""",
    """    p.tube(HIP_R, HIP_Y + 2, 11.2, 66, HIP_Y + 6, 9.4, PANTS)
    p.tube(66, HIP_Y + 6, 9.4, 82, HIP_Y + 10, 6.6, PANTS)
    p.strip([(HIP_Y + 5, 78, 7.0), (HIP_Y + 12, 79, 6.4)], WRAP)
    p.poly([(82, HIP_Y + 3), (93, HIP_Y + 7), (92, HIP_Y + 18),
            (81, HIP_Y + 15)], SANDAL)
    p.ellipse(89, HIP_Y + 6, 3.4, 2.6, SKIN)
    p.tube(83, HIP_Y + 4, 1.7, 90, HIP_Y + 8, 1.4, SANDAL)""")

# --- palette: the bandages are linen grey, not paper white
rep("""               pants=(38, 41, 62), wrap=(198, 200, 208), sandal=(26, 27, 38),""",
    """               pants=(38, 41, 62), wrap=(172, 176, 188), sandal=(26, 27, 38),""")
rep("""                pants=(30, 31, 44), wrap=(212, 214, 220), sandal=(20, 20, 28),""",
    """                pants=(30, 31, 44), wrap=(184, 188, 198), sandal=(20, 20, 28),""")
rep("""               belt=(40, 44, 58), glove=(44, 47, 66), accent=(150, 28, 52)),""",
    """               belt=(40, 44, 58), glove=(44, 47, 66), accent=(132, 24, 44)),""")

io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('misses:', miss if miss else 'none')
