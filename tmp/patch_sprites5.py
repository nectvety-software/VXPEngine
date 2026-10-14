"""Scratch patch round 5: connect the action-pose limbs, rebuild the jump leg."""
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


# --- hips: leave a visible inner-thigh gap instead of one solid column
rep("""HIP_L, HIP_R = 33, 47      # left / right hip x""",
    """HIP_L, HIP_R = 32, 48      # left / right hip x""")
rep("""    p.tube(hip_x, hip_y, 12.2, mid_x, 100, 10.6, PANTS)""",
    """    p.tube(hip_x, hip_y, 11.4, mid_x, 100, 10.4, PANTS)""")
rep("""    thigh = ((mid_x, 100, 10.6), (knee_x, knee_y, 8.4))""",
    """    thigh = ((mid_x, 100, 10.4), (knee_x, knee_y, 8.4))""")

# --- punch: start the sleeve inside the vest so it cannot read as detached
rep("""    p.tube(SH_R, SH_Y + 4, 5.6, 70, SH_Y + 6, 4.9, CLOTH)
    p.limb_band_x(((SH_R, SH_Y + 4, 5.6), (70, SH_Y + 6, 4.9)), 61, 65, ACCENT)
    p.limb_band_x(((SH_R, SH_Y + 4, 5.6), (70, SH_Y + 6, 4.9)), 67, 71, WRAP)""",
    """    arm = ((SH_R - 7, SH_Y + 8, 5.8), (70, SH_Y + 7, 4.9))
    p.tube(*arm[0], *arm[1], CLOTH)
    p.limb_band_x(arm, 60, 64, ACCENT)
    p.limb_band_x(arm, 66, 70, WRAP)""")

# --- kick: foreshortened limb, so drop the club-like thigh width
rep("""    sh = ((66, HIP_Y + 6, 9.4), (82, HIP_Y + 10, 6.6))
    p.tube(HIP_R, HIP_Y + 2, 12.0, 66, HIP_Y + 6, 9.8, PANTS)""",
    """    sh = ((66, HIP_Y + 6, 8.4), (82, HIP_Y + 10, 6.0))
    p.tube(HIP_R - 2, HIP_Y + 2, 11.0, 66, HIP_Y + 6, 8.8, PANTS)""")
rep("""    p.limb_band(sh, HIP_Y + 6, HIP_Y + 13, WRAP, 0.6)""",
    """    p.limb_band_x(sh, 71, 78, WRAP, 0.6)""")

# --- recoil arm: thrown up and *back*, not straight up in greeting
rep("""    p.tube(SH_R, SH_Y + 2, 5.6, 68, 26, 5.0, CLOTH)
    p.tube(68, 26, 5.0, 65, 14, 4.2, CLOTH)
    p.limb_band(((68, 26, 5.0), (65, 14, 4.2)), 20, 26, WRAP)
    p.ellipse(62, 9, 5.2, 5.6, GLOVE)
    p.hline(59, 66, 4, SKIN)""",
    """    p.tube(SH_R, SH_Y + 2, 5.6, 68, 28, 5.0, CLOTH)
    p.tube(68, 28, 5.0, 70, 15, 4.2, CLOTH)
    p.limb_band(((68, 28, 5.0), (70, 15, 4.2)), 20, 26, WRAP)
    p.ellipse(70, 10, 5.2, 5.6, GLOVE)
    p.hline(67, 74, 5, SKIN)""")

# --- jump: near knee up, far leg trailing - two tucked legs merge into a lump
rep('''def leg_tuck():
    """Jump: both knees drawn up, soles tucked under."""
    p = Part("leg_tuck")
    p.tube(HIP_L, HIP_Y, 11.4, 26, 96, 9.6, PANTS)
    p.tube(26, 96, 9.6, 33, 112, 6.2, PANTS)
    p.poly([(26, 112), (44, 114), (43, 126), (25, 124)], SANDAL)
    p.tube(HIP_R, HIP_Y, 11.4, 54, 94, 9.6, PANTS)
    p.tube(54, 94, 9.6, 49, 112, 6.2, PANTS)
    p.poly([(43, 112), (60, 114), (59, 126), (42, 124)], SANDAL)
    p.strip([(96, 30, 7.6), (104, 30, 7.0)], WRAP)
    return p''',
    '''def leg_tuck():
    """Jump: the near knee comes up, the far leg trails down and back."""
    p = Part("leg_tuck")
    # trailing far leg
    p.tube(HIP_L, HIP_Y, 11.4, 28, 104, 10.0, PANTS)
    p.tube(28, 104, 10.0, 25, 132, 6.6, PANTS)
    p.limb_band(((28, 104, 10.0), (25, 132, 6.6)), 124, 133, WRAP, 0.5)
    p.poly([(18, 134), (31, 133), (32, 142), (17, 143)], SANDAL)
    p.ellipse(29, 137, 4.4, 2.6, SKIN)
    # raised near leg: knee forward, sole tucked under the hip
    p.tube(HIP_R, HIP_Y, 11.4, 58, 92, 10.0, PANTS)
    p.tube(58, 92, 10.0, 44, 100, 6.6, PANTS)
    p.limb_band(((58, 92, 10.0), (44, 100, 6.6)), 96, 101, WRAP, 0.5)
    p.poly([(36, 100), (50, 97), (52, 107), (38, 110)], SANDAL)
    p.ellipse(40, 104, 2.6, 4.2, SKIN)
    return p''')

io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('misses:', miss if miss else 'none')
