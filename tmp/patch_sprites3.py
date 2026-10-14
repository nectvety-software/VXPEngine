"""Scratch patch round 3: bands that follow the limb axis, arms inboard."""
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


# helper: a flat band that hugs a tapered limb instead of floating off it
rep('''    def band(self, y0, y1, cx, hw, mat):
        self.strip([(y0, cx, hw), (y1, cx, hw)], mat)''',
    '''    def band(self, y0, y1, cx, hw, mat):
        self.strip([(y0, cx, hw), (y1, cx, hw)], mat)

    def limb_band(self, limb, y0, y1, mat, inset=0.4):
        """Clip a horizontal band to a tube's axis over the y0..y1 range."""
        (ax, ay, ar), (bx, by, br) = limb

        def at(y):
            t = (y - ay) / float(by - ay)
            return (y, ax + (bx - ax) * t, ar + (br - ar) * t - inset)

        self.strip([at(y0), at(y1)], mat)''')

# --- back/near arm: shoulder tucked under the vest cap, bands on the axis
rep("""    p.tube(SH_L, SH_Y + 2, 5.6, 15, 54, 5.0, CLOTH)
    p.tube(15, 54, 5.0, 12, 72, 4.2, CLOTH)
    p.strip([(45, 14.6, 5.4), (50, 13.8, 5.1)], ACCENT)        # armband
    p.strip([(57, 14.0, 4.9), (67, 12.4, 4.3)], WRAP)          # forearm bandage
    p.tube(12, 72, 4.0, 11, 78, 3.6, SKIN)                     # bare wrist
    p.ellipse(11, 84, 4.6, 6.0, GLOVE)
    p.hline(7, 15, 82, CLOTH)                                  # glove strap
    p.tube(9, 88, 2.5, 14, 90, 2.1, SKIN)                      # knuckles""",
    """    up = ((SH_L, SH_Y + 2, 5.6), (18, 54, 5.0))
    lo = ((18, 54, 5.0), (16, 72, 4.2))
    p.tube(*up[0], *up[1], CLOTH)
    p.tube(*lo[0], *lo[1], CLOTH)
    p.limb_band(up, 44, 49, ACCENT)                            # armband
    p.limb_band(lo, 58, 68, WRAP)                              # forearm bandage
    p.tube(16, 70, 4.0, 15, 77, 3.6, SKIN)                     # bare wrist
    p.ellipse(14, 83, 4.6, 6.0, GLOVE)
    p.hline(10, 18, 81, CLOTH)                                 # glove strap
    p.tube(12, 87, 2.5, 17, 89, 2.1, SKIN)                     # knuckles""")

rep("""    p.tube(SH_R, SH_Y + 2, 5.6, 66, 54, 5.0, CLOTH)
    p.tube(66, 54, 5.0, 58, 46, 4.2, CLOTH)
    p.strip([(44, 65.4, 5.2), (49, 64.4, 5.0)], ACCENT)
    p.strip([(50, 63.0, 4.6), (55, 61.0, 4.3)], WRAP)
    p.tube(58, 46, 3.9, 53, 43, 3.5, SKIN)
    p.ellipse(50, 41, 4.9, 5.1, GLOVE)
    p.hline(46, 51, 37, SKIN)                    # finger tips""",
    """    up = ((SH_R, SH_Y + 2, 5.6), (64, 54, 5.0))
    lo = ((64, 54, 5.0), (57, 46, 4.2))
    p.tube(*up[0], *up[1], CLOTH)
    p.tube(*lo[0], *lo[1], CLOTH)
    p.limb_band(up, 43, 48, ACCENT)
    p.limb_band(lo, 48, 53, WRAP)
    p.tube(57, 46, 3.9, 53, 43, 3.5, SKIN)
    p.ellipse(50, 41, 4.9, 5.1, GLOVE)
    p.hline(46, 51, 37, SKIN)                    # finger tips""")

rep("""    p.strip([(SH_Y + 2, 63, 5.4), (SH_Y + 8, 63, 5.2)], ACCENT)
    p.strip([(SH_Y + 2, 70, 4.8), (SH_Y + 10, 70, 4.4)], WRAP)""",
    """    # the punching arm is horizontal, so its bands run on x
    p.limb_band_x(((SH_R, SH_Y + 4, 5.6), (70, SH_Y + 6, 4.9)), 61, 65, ACCENT)
    p.limb_band_x(((SH_R, SH_Y + 4, 5.6), (70, SH_Y + 6, 4.9)), 67, 71, WRAP)""")

rep("""    p.tube(SH_R, SH_Y + 2, 5.6, 68, 26, 5.0, CLOTH)
    p.tube(68, 26, 5.0, 65, 14, 4.2, CLOTH)
    p.strip([(21, 67.4, 4.7), (27, 66.6, 4.4)], WRAP)""",
    """    p.tube(SH_R, SH_Y + 2, 5.6, 68, 26, 5.0, CLOTH)
    p.tube(68, 26, 5.0, 65, 14, 4.2, CLOTH)
    p.limb_band(((68, 26, 5.0), (65, 14, 4.2)), 20, 26, WRAP)""")

# --- legs: knee bands and shin wrap on the thigh / shin axes
rep("""    if bands:                                      # the near leg's two bands
        p.strip([(104, knee_x + 0.6, 8.4), (107, knee_x + 0.6, 8.2)], WRAP)
        p.strip([(112, knee_x + 0.8, 8.0), (115, knee_x + 0.8, 7.8)], WRAP)
    p.strip([(knee_y + 12, ankle_x - 0.2, 5.4), (ankle_y + 1, ankle_x, 4.6)],
            WRAP)""",
    """    thigh = ((mid_x, 100, 10.2), (knee_x, knee_y, 8.4))
    shin = ((knee_x, knee_y, 6.8), (ankle_x, ankle_y, 5.4))
    if bands:                                      # the near leg's two bands
        p.limb_band(thigh, 104, 107, WRAP, 0.5)
        p.limb_band(thigh, 112, 115, WRAP, 0.6)
    p.limb_band(shin, knee_y + 12, ankle_y + 1, WRAP, 0.5)""")

rep("""    p.tube(HIP_R, HIP_Y + 2, 11.2, 66, HIP_Y + 6, 9.4, PANTS)
    p.tube(66, HIP_Y + 6, 9.4, 82, HIP_Y + 10, 6.6, PANTS)
    p.strip([(HIP_Y + 5, 78, 7.0), (HIP_Y + 12, 79, 6.4)], WRAP)""",
    """    sh = ((66, HIP_Y + 6, 9.4), (82, HIP_Y + 10, 6.6))
    p.tube(HIP_R, HIP_Y + 2, 11.2, 66, HIP_Y + 6, 9.4, PANTS)
    p.tube(*sh[0], *sh[1], PANTS)
    p.limb_band(sh, HIP_Y + 6, HIP_Y + 13, WRAP, 0.6)""")

# --- head: pull the hair in so it stops reading as a brim
rep("""    p.strip([(8, 39, 9.4), (12, 39, 10.4), (18, 40, 10.2),
             (24, 41, 7.8)], HAIR)""",
    """    p.strip([(8, 39, 9.0), (12, 39, 10.0), (18, 40, 9.6),
             (24, 41, 7.2)], HAIR)""")

# --- vest: slightly narrower now that the arms sit inboard
rep("""    p.strip([(33, 40, 16.6), (42, 40, 20.4), (58, 40, 20.6),
             (72, 40, 19.0), (78, 40, 15.8)], VEST)""",
    """    p.strip([(33, 40, 16.2), (42, 40, 19.2), (58, 40, 19.4),
             (72, 40, 18.0), (78, 40, 15.2)], VEST)""")

io.open(p, 'w', encoding='utf-8', newline='\n').write(s)
print('misses:', miss if miss else 'none')
