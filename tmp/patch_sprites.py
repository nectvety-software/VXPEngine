"""One-shot patcher for the StormArena sprite author geometry (scratch tool)."""
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


rep("""    p.ellipse(40, 15, 11.6, 9.8, HAIR)
    p.strip([(7, 38, 10.6), (12, 39, 11.6), (18, 40, 11.2),
             (24, 41, 8.4)], HAIR)
    for (ax, ay, aw, tx, ty) in [(34, 10, 5.0, 28, 3), (39, 9, 5.4, 37, 2),
                                 (45, 10, 5.0, 48, 4), (50, 13, 4.4, 55, 9)]:
        p.taper(ax, ay, aw, tx, ty, HAIR)
    # nape lock that falls behind the collar
    p.strip([(17, 29, 4.4), (26, 28, 3.8), (31, 28, 2.6)], HAIR)
    # face: only the eye band and cheek are bare skin
    p.ellipse(42, 21, 7.2, 7.4, SKIN)
    p.strip([(20, 42, 6.8), (25, 42, 6.2)], SKIN)
    # mask over nose, chin and throat, curved top edge
    p.strip([(24, 41, 7.2), (28, 41, 7.0), (31, 41, 5.6),
             (34, 41, 3.6)], CLOTH)
    # headband worn low over the brow, small plate
    p.strip([(11, 40, 11.6), (14, 40, 12.0), (17, 40, 11.8),
             (20, 40, 10.8)], CLOTH)
    p.poly([(35, 12), (45, 12), (46, 17), (34, 17)], METAL)
    p.rect(38, 14, 4, 2, CLOTH)          # plate slit
    # the near eye; the far one sits under a hair lock
    p.rect(43, 22, 4, 2, EYE)
    p.hline(42, 47, 21, CLOTH)           # brow shadow
    p.taper(31, 15, 3.8, 34, 26, HAIR)""",
    """    p.ellipse(40, 15, 10.6, 9.0, HAIR)
    p.strip([(8, 39, 9.4), (12, 39, 10.4), (18, 40, 10.2),
             (24, 41, 7.8)], HAIR)
    for (ax, ay, aw, tx, ty) in [(34, 10, 4.4, 29, 4), (39, 9, 4.8, 37, 3),
                                 (45, 10, 4.4, 46, 5), (50, 13, 3.8, 53, 10)]:
        p.taper(ax, ay, aw, tx, ty, HAIR)
    # nape lock that falls behind the collar
    p.strip([(17, 30, 3.8), (26, 29, 3.2), (31, 29, 2.2)], HAIR)
    # face: only the eye band and cheek are bare skin
    p.ellipse(42, 20, 6.6, 6.8, SKIN)
    p.strip([(17, 42, 6.2), (22, 42, 5.8)], SKIN)
    # mask over nose, chin and throat, curved top edge
    p.strip([(22, 41, 6.4), (26, 41, 6.2), (30, 41, 4.8),
             (33, 41, 3.0)], CLOTH)
    # headband worn low over the brow, small plate
    p.strip([(10, 40, 10.4), (13, 40, 10.8), (16, 40, 10.6),
             (19, 40, 9.6)], CLOTH)
    p.poly([(35, 11), (44, 11), (45, 16), (34, 16)], METAL)
    p.rect(38, 13, 4, 2, CLOTH)          # plate slit
    # the near eye; the far one sits under a hair lock
    p.rect(43, 19, 4, 2, EYE)
    p.hline(42, 47, 18, CLOTH)           # brow shadow
    p.taper(31, 13, 3.2, 34, 24, HAIR)""")

rep("""    p.strip([(29, 40, 6.4), (34, 40, 7.2), (38, 40, 8.2)], CLOTH)
    # flak vest: shoulder caps, chest, tapered hem
    p.strip([(34, 40, 15.0), (42, 40, 18.0), (58, 40, 18.2),
             (70, 40, 17.0), (76, 40, 15.0)], VEST)
    for sx in (SH_L, SH_R):
        p.ellipse(sx, 38, 7.4, 5.8, VEST)
        p.strip([(33, sx, 6.8), (41, sx, 6.2)], VEST)
    # centre seam and the four pocket blocks with flaps and ridges
    p.strip([(37, 40.5, 0.9), (75, 40.5, 0.9)], VEST_D)
    for px0 in (25, 45):
        p.rect(px0, 48, 12, 13, VEST_D)
        p.rect(px0 - 1, 45, 14, 4, VEST)
        for k in range(1, 4):
            p.hline(px0 + 1, px0 + 11, 48 + k * 3, VEST_D)
    p.strip([(74, 40, 15.2), (77, 40, 14.4)], VEST_D)   # hem shadow""",
    """    p.strip([(29, 40, 6.0), (34, 40, 7.0), (38, 40, 8.0)], CLOTH)
    # flak vest: shoulder caps, wide chest, tapered hem
    p.strip([(34, 40, 16.0), (42, 40, 19.4), (58, 40, 19.6),
             (70, 40, 18.0), (76, 40, 15.4)], VEST)
    for sx in (SH_L, SH_R):
        p.ellipse(sx, 38, 7.8, 6.0, VEST)
        p.strip([(33, sx, 7.2), (41, sx, 6.6)], VEST)
    # centre seam and the four pocket blocks with flaps and ridges
    p.strip([(37, 40.5, 0.9), (75, 40.5, 0.9)], VEST_D)
    for px0 in (26, 44):
        p.rect(px0, 47, 11, 14, VEST_D)
        p.rect(px0 - 1, 44, 13, 4, VEST)
        p.hline(px0 - 1, px0 + 11, 48, VEST)       # flap highlight
        for k in range(1, 4):
            p.hline(px0 + 1, px0 + 9, 47 + k * 3, VEST_D)
    p.strip([(74, 40, 15.6), (77, 40, 14.8)], VEST_D)   # hem shadow""")

rep('def arm_hang():\n    """Back arm: dark sleeve, red armband, grey forearm wrap, fingerless glove."""\n'
    '    p = Part("arm_hang")\n'
    '    p.tube(SH_L, SH_Y + 2, 6.2, 18, 54, 5.4, CLOTH)\n'
    '    p.tube(18, 54, 5.4, 15, 72, 4.6, CLOTH)\n'
    '    p.poly([(12, 42), (24, 42), (23, 51), (11, 51)], ACCENT)   # armband\n'
    '    p.strip([(58, 17, 5.2), (68, 16, 4.8)], WRAP)              # forearm bandage\n'
    '    p.tube(15, 74, 4.2, 14, 80, 3.8, SKIN)                     # bare wrist\n'
    '    p.ellipse(14, 85, 5.0, 6.2, GLOVE)\n'
    '    p.hline(10, 18, 83, CLOTH)                                 # glove strap\n'
    '    p.tube(12, 89, 2.6, 17, 91, 2.2, SKIN)                     # knuckles\n'
    '    return p',
    'def _arm_hang(p):\n'
    '    """Hanging arm: dark sleeve, red armband, grey wrap, fingerless glove."""\n'
    '    p.tube(SH_L, SH_Y + 2, 5.8, 18, 54, 5.2, CLOTH)\n'
    '    p.tube(18, 54, 5.2, 15, 72, 4.4, CLOTH)\n'
    '    p.tube(20, 43, 5.9, 19, 51, 5.4, ACCENT)                   # armband patch\n'
    '    p.tube(17, 58, 5.2, 15, 70, 4.5, WRAP)                     # forearm bandage\n'
    '    p.tube(15, 72, 4.2, 14, 78, 3.8, SKIN)                     # bare wrist\n'
    '    p.ellipse(14, 84, 4.8, 6.0, GLOVE)\n'
    '    p.hline(10, 18, 82, CLOTH)                                 # glove strap\n'
    '    p.tube(12, 88, 2.6, 17, 90, 2.2, SKIN)                     # knuckles\n'
    '\n'
    '\n'
    'def arm_hang():\n'
    '    p = Part("arm_hang")\n'
    '    _arm_hang(p)\n'
    '    return p\n'
    '\n'
    '\n'
    'def arm_hang_r():\n'
    '    """Near-side copy: same shape, baked on the lit half of the figure."""\n'
    '    p = Part("arm_hang_r", flip=True)\n'
    '    _arm_hang(p)\n'
    '    return p')

rep("""    p.tube(SH_R, SH_Y + 2, 6.2, 64, 54, 5.4, CLOTH)
    p.tube(64, 54, 5.4, 56, 46, 4.4, CLOTH)
    p.poly([(56, 38), (68, 38), (67, 48), (55, 48)], ACCENT)
    p.strip([(48, 60, 4.6), (54, 59, 4.2)], WRAP)
    p.tube(56, 46, 4.0, 52, 43, 3.6, SKIN)
    p.ellipse(49, 41, 5.0, 5.2, GLOVE)
    p.hline(45, 50, 37, SKIN)                                  # finger tips""",
    """    p.tube(SH_R, SH_Y + 2, 5.8, 64, 54, 5.2, CLOTH)
    p.tube(64, 54, 5.2, 56, 46, 4.4, CLOTH)
    p.tube(62, 41, 5.4, 63, 49, 5.0, ACCENT)
    p.tube(61, 50, 4.6, 58, 47, 4.2, WRAP)
    p.tube(56, 46, 4.0, 52, 43, 3.6, SKIN)
    p.ellipse(49, 41, 5.0, 5.2, GLOVE)
    p.hline(45, 50, 37, SKIN)                   # finger tips""")

rep("""    p.tube(SH_R, SH_Y + 4, 6.2, 70, SH_Y + 6, 5.2, CLOTH)
    p.poly([(57, 32), (67, 32), (67, 42), (57, 42)], ACCENT)
    p.strip([(34, 72, 4.8), (42, 72, 4.4)], WRAP)
    p.tube(72, SH_Y + 6, 4.0, 79, SH_Y + 6, 3.6, SKIN)""",
    """    p.tube(SH_R, SH_Y + 4, 5.8, 70, SH_Y + 6, 5.0, CLOTH)
    p.tube(60, SH_Y + 3, 5.5, 66, SH_Y + 9, 5.1, ACCENT)
    p.tube(70, SH_Y + 2, 4.8, 70, SH_Y + 10, 4.4, WRAP)
    p.tube(72, SH_Y + 6, 4.0, 79, SH_Y + 6, 3.6, SKIN)""")

rep("""    p.tube(SH_R, SH_Y + 2, 6.2, 66, 26, 5.4, CLOTH)
    p.tube(66, 26, 5.4, 63, 14, 4.4, CLOTH)
    p.strip([(18, 65, 4.8), (25, 65, 4.4)], WRAP)""",
    """    p.tube(SH_R, SH_Y + 2, 5.8, 66, 26, 5.2, CLOTH)
    p.tube(66, 26, 5.2, 63, 14, 4.4, CLOTH)
    p.tube(65, 20, 4.8, 64, 27, 4.4, WRAP)""")

rep("""    p.tube(hip_x, hip_y, 10.4, (hip_x + knee_x) / 2.0, 100, 9.2, PANTS)
    p.tube((hip_x + knee_x) / 2.0, 100, 9.2, knee_x, knee_y, 7.6, PANTS)
    p.tube(knee_x, knee_y, 6.4, ankle_x, ankle_y, 5.4, PANTS)
    if bands:                                                  # near-leg bands
        p.strip([(103, knee_x + 0.6, 8.8), (107, knee_x + 0.6, 8.4)], WRAP)
        p.strip([(112, knee_x + 0.8, 8.0), (116, knee_x + 0.8, 7.6)], WRAP)
    p.strip([(knee_y + 8, ankle_x, 5.8), (ankle_y + 1, ankle_x, 5.0)], WRAP)
    # sandal: instep, sole plank, exposed toes, strap over the instep
    p.tube(ankle_x - 1, ankle_y + 3, 5.2, ankle_x + 5, ankle_y + 8, 4.6,
           SANDAL)
    p.poly([(ankle_x - 8, SOLE_Y - 5), (ankle_x + 12, SOLE_Y - 5),
            (ankle_x + 13, SOLE_Y), (ankle_x - 9, SOLE_Y)], SANDAL)
    p.ellipse(ankle_x + 9, SOLE_Y - 7, 4.0, 2.8, SKIN)
    p.tube(ankle_x - 3, ankle_y + 6, 1.7, ankle_x + 8, SOLE_Y - 7, 1.4, SANDAL)""",
    """    mid_x = (hip_x + knee_x) / 2.0
    p.tube(hip_x, hip_y, 11.4, mid_x, 100, 10.2, PANTS)
    p.tube(mid_x, 100, 10.2, knee_x, knee_y, 8.4, PANTS)
    p.tube(knee_x, knee_y, 6.8, ankle_x, ankle_y, 5.4, PANTS)
    if bands:                                      # the near leg's two bands
        p.tube(knee_x + 0.4, 103, 8.8, knee_x + 0.4, 107, 8.4, WRAP)
        p.tube(knee_x + 0.8, 111, 8.2, knee_x + 0.8, 115, 7.8, WRAP)
    p.tube(ankle_x - 0.4, knee_y + 10, 5.8, ankle_x, ankle_y + 1, 5.0, WRAP)
    # sandal: instep, sole plank, exposed toes, strap over the instep
    p.tube(ankle_x - 1, ankle_y + 3, 5.6, ankle_x + 5, ankle_y + 8, 5.0,
           SANDAL)
    p.poly([(ankle_x - 8, SOLE_Y - 6), (ankle_x + 13, SOLE_Y - 6),
            (ankle_x + 14, SOLE_Y), (ankle_x - 9, SOLE_Y)], SANDAL)
    p.ellipse(ankle_x + 10, SOLE_Y - 7, 4.4, 3.2, SKIN)
    p.tube(ankle_x - 3, ankle_y + 6, 1.8, ankle_x + 8, SOLE_Y - 8, 1.5, SANDAL)""")

rep("""    p.tube(HIP_R, HIP_Y + 2, 10.4, 66, HIP_Y + 6, 8.6, PANTS)
    p.tube(66, HIP_Y + 6, 8.6, 84, HIP_Y + 10, 6.0, PANTS)
    p.strip([(88, 76, 6.6), (96, 77, 6.0)], WRAP)""",
    """    p.tube(HIP_R, HIP_Y + 2, 11.2, 66, HIP_Y + 6, 9.4, PANTS)
    p.tube(66, HIP_Y + 6, 9.4, 84, HIP_Y + 10, 6.4, PANTS)
    p.tube(78, HIP_Y + 6, 7.0, 84, HIP_Y + 9, 6.0, WRAP)""")

rep("""    p.tube(HIP_L, HIP_Y, 10.4, 26, 96, 8.8, PANTS)
    p.tube(26, 96, 8.8, 33, 112, 5.6, PANTS)""",
    """    p.tube(HIP_L, HIP_Y, 11.4, 26, 96, 9.6, PANTS)
    p.tube(26, 96, 9.6, 33, 112, 6.2, PANTS)""")

rep("""    p.tube(HIP_R, HIP_Y, 10.4, 54, 94, 8.8, PANTS)
    p.tube(54, 94, 8.8, 49, 112, 5.6, PANTS)""",
    """    p.tube(HIP_R, HIP_Y, 11.4, 54, 94, 9.6, PANTS)
    p.tube(54, 94, 9.6, 49, 112, 6.2, PANTS)""")

rep("""PARTS = [head, torso, arm_hang, arm_guard, arm_punch, arm_up,
         leg_down, leg_fwd, leg_back, leg_kick, leg_tuck]""",
    """PARTS = [head, torso, arm_hang, arm_hang_r, arm_guard, arm_punch, arm_up,
         leg_down, leg_fwd, leg_back, leg_kick, leg_tuck]""")

rep("""# ids: 0 head, 1 torso, 2 arm_hang, 3 arm_guard, 4 arm_punch, 5 arm_up,
#      6 leg_down, 7 leg_fwd, 8 leg_back, 9 leg_kick, 10 leg_tuck
# The legs are authored on the left hip, so the right leg is the same part at
# dx=+14 (HIP_R - HIP_L).
SPREAD = HIP_R - HIP_L
POSE_TABLE = {
    "idle0": [(6, 0, 0), (6, SPREAD, 0), (1, 0, 0), (2, -1, 0), (3, 0, 0),
              (0, 0, 0)],
    "idle1": [(6, 0, 0), (6, SPREAD, 0), (1, 0, 2), (2, -1, 2), (3, 0, 2),
              (0, 0, 2)],
    "walk0": [(8, 0, 0), (7, SPREAD, 0), (1, 0, 1), (2, -2, 1), (3, 0, 0),
              (0, 0, 1)],
    "walk1": [(7, 0, 0), (8, SPREAD, 0), (1, 0, 1), (2, -2, 1), (3, 0, 0),
              (0, 0, 1)],
    "punch": [(6, -2, 0), (6, SPREAD + 2, 0), (1, 3, 0), (2, 0, 0),
              (4, 2, -1), (0, 4, 0)],
    "kick":  [(6, -6, 0), (1, -5, -1), (2, -6, 0), (3, -8, -1), (9, -2, 0),
              (0, -6, -1)],
    "hit":   [(6, -7, 0), (6, SPREAD - 2, 1), (1, -5, 1), (2, -6, 2),
              (5, -4, 1), (0, -8, 3)],
    "jump":  [(10, 0, -6), (1, 0, -2), (2, -1, -2), (3, 0, -3), (0, 0, -2)],
}""",
    """# ids: 0 head, 1 torso, 2 arm_hang, 3 arm_hang_r, 4 arm_guard, 5 arm_punch,
#      6 arm_up, 7 leg_down, 8 leg_fwd, 9 leg_back, 10 leg_kick, 11 leg_tuck
# The legs are authored on the left hip, so the right leg is the same part at
# dx=+14 (HIP_R - HIP_L).  Idle matches the reference stance: both arms down.
SPREAD = HIP_R - HIP_L
POSE_TABLE = {
    "idle0": [(7, 0, 0), (7, SPREAD, 0), (1, 0, 0), (2, 0, 0), (3, 0, 0),
              (0, 0, 0)],
    "idle1": [(7, 0, 0), (7, SPREAD, 0), (1, 0, 2), (2, 0, 2), (3, 0, 2),
              (0, 0, 2)],
    "walk0": [(9, 0, 0), (8, SPREAD, 0), (1, 0, 1), (2, 0, 1), (3, 0, 0),
              (0, 0, 1)],
    "walk1": [(8, 0, 0), (9, SPREAD, 0), (1, 0, 1), (2, 0, 1), (3, 0, 0),
              (0, 0, 1)],
    "punch": [(7, -2, 0), (7, SPREAD + 3, 0), (1, 3, 0), (2, 0, 0),
              (5, 2, -1), (0, 4, 0)],
    "kick":  [(7, -7, 0), (1, -5, -1), (2, -2, 0), (4, -8, -1), (10, -2, 0),
              (0, -6, -1)],
    "hit":   [(7, -7, 0), (7, SPREAD - 2, 1), (1, -5, 1), (2, -2, 2),
              (6, -4, 1), (0, -8, 3)],
    "jump":  [(11, 0, -6), (1, 0, -2), (2, 0, -2), (3, 0, -3), (0, 0, -2)],
}""")

io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('misses:', miss if miss else 'none')
