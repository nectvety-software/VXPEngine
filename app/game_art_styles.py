"""Game palettes and alpha-preserving pixel quantization."""
from PySide6.QtGui import QColor, QImage

GAME_ART_STYLES = {
    "Game · Cozy Farm": ("Màu đất ấm và cỏ xanh cho nông trại/top-down.",
        "#242331 #493b35 #77523d #aa7345 #d8a65b #f5d98d #fff1c1 #35483c #557447 #83a65b #b8cc76 #426c86 #71a7bc #c55d56 #ec9980 #8b658c"),
    "Game · Dark Fantasy": ("Bóng xanh tím, đá lạnh và điểm sáng vàng cho dungeon.",
        "#10121e #202235 #34334c #514762 #71627b #948699 #c1b6bb #e7dfd1 #183d3c #326158 #65806c #a5ad82 #674039 #a76b48 #d3a159 #f5d58b"),
    "Game · Neon Action": ("Nền tối với cyan/magenta cho phép thuật và hành động.",
        "#0b1020 #192438 #304257 #59647e #8995ae #c8dbef #ffffff #174c56 #218fa2 #46dbe0 #a6fff3 #492850 #852b8d #d54bcc #ff9be9 #ffd482"),
    "Game · Pastel Platformer": ("Màu pastel mềm cho platformer và game dễ thương.",
        "#38364f #67617b #9188a0 #c5bac8 #eee3df #fff5df #815e66 #bd8586 #edb1ad #f7d1b8 #a38766 #dbbf91 #68888b #9bbfc0 #779374 #b7cda0"),
    "Game · Retro Handheld": ("Bốn màu xanh kiểu handheld cho sprite/tileset nhỏ.",
        "#182f28 #426b42 #8ca65a #d8e6a3"),
}


def apply_game_palette(image: QImage, style: str) -> QImage:
    """Map to weighted nearest RGB; preserve dimensions and original alpha."""
    palette = [QColor(code) for code in GAME_ART_STYLES[style][1].split()]
    output = image.convertToFormat(QImage.Format.Format_ARGB32)
    cache = {}
    for y in range(output.height()):
        for x in range(output.width()):
            color = image.pixelColor(x, y)
            if color.alpha() == 0:
                continue
            key = (color.red(), color.green(), color.blue())
            nearest = cache.get(key)
            if nearest is None:
                nearest = min(palette, key=lambda p:
                    2 * (key[0] - p.red()) ** 2 +
                    4 * (key[1] - p.green()) ** 2 +
                    (key[2] - p.blue()) ** 2)
                if len(cache) < 4096:
                    cache[key] = nearest
            output.setPixelColor(x, y, QColor(nearest.red(), nearest.green(), nearest.blue(), color.alpha()))
    return output


ART_STYLE_PROFILES = {
    "Game · Dungeon Synth": {"runtime_preset":"VXPE_ARTSTYLE_DUNGEON_SYNTH","posterize":12,"saturation":1.17,"contrast":1.21,"outline_px":0,"fog":"#190C2C","fog_strength":65,"trail":"#804CEB","description":"Torch-lit stone, aged brass, bone and violet cosmic magic."},
    "Game · Urban Toon": {"runtime_preset":"VXPE_ARTSTYLE_URBAN_TOON","posterize":8,"saturation":1.25,"contrast":1.20,"outline_px":2,"fog":"#85BAD6","fog_strength":28,"trail":"#2CF6E9","description":"Urban cel shading with black ink, bright yellow/cyan accents, stepped colour and blue distance fog."},
    "Game · Cozy Farm": {"runtime_preset":"VXPE_ARTSTYLE_COZY_FARM","posterize":24,"saturation":1.08,"contrast":0.98,"outline_px":0,"fog":"#BED3AF","fog_strength":22,"trail":None,"description":"Warm top-down/farm profile with soft shadows and light atmospheric fog."},
    "Game · Dark Fantasy": {"runtime_preset":"VXPE_ARTSTYLE_DARK_FANTASY","posterize":18,"saturation":0.82,"contrast":1.20,"outline_px":1,"fog":"#202A41","fog_strength":90,"trail":None,"description":"Cold low-key fantasy profile with vignette, dense fog and strong silhouettes."},
    "Game · Neon Action": {"runtime_preset":"VXPE_ARTSTYLE_NEON_ACTION","posterize":24,"saturation":1.38,"contrast":1.18,"outline_px":0,"fog":"#112D44","fog_strength":40,"trail":"#46E6FF","description":"Dark neon action profile with cyan glow, additive light and speed trails."},
    "Game · Pastel Platformer": {"runtime_preset":"VXPE_ARTSTYLE_PASTEL_PLATFORMER","posterize":24,"saturation":0.92,"contrast":0.90,"outline_px":1,"fog":"#BCD2DA","fog_strength":20,"trail":None,"description":"Soft pastel platformer profile with gentle contrast and coloured outlines."},
    "Game · Retro Handheld": {"runtime_preset":"VXPE_ARTSTYLE_RETRO_HANDHELD","posterize":4,"saturation":0.50,"contrast":1.20,"outline_px":1,"fog":"#80A55C","fog_strength":0,"trail":None,"description":"Four-tone handheld look for tiny sprites and low-memory scenes."},
    "Game · Cel-Shaded Cartoon": {"runtime_preset":"VXPE_ARTSTYLE_CEL_SHADED","posterize":12,"saturation":1.18,"contrast":1.18,"outline_px":2,"fog":"#78969A","fog_strength":20,"trail":None,"description":"Graphic cartoon/cel shading with bold silhouettes and stepped colour bands."},
    "Game · Saturated Adventure": {"runtime_preset":"VXPE_ARTSTYLE_SATURATED_ADVENTURE","posterize":28,"saturation":1.34,"contrast":1.08,"outline_px":1,"fog":"#227E7D","fog_strength":46,"trail":"#CAF8FF","description":"Vivid jungle/adventure profile: teal depth fog, warm shafts and bright movement trails."},
    "Game · Strategy Kingdom": {"runtime_preset":"VXPE_ARTSTYLE_STRATEGY_RPG","posterize":20,"saturation":1.12,"contrast":1.16,"outline_px":1,"fog":"#A9B6A2","fog_strength":14,"trail":None,"description":"Readable strategy-RPG profile for maps, units, ornate UI and battle sprites."},
    "Game · Painterly Fantasy": {"runtime_preset":"VXPE_ARTSTYLE_PAINTERLY","posterize":32,"saturation":0.94,"contrast":0.94,"outline_px":0,"fog":"#A7B4B5","fog_strength":30,"trail":None,"description":"Soft painterly fantasy with broad colour masses and atmospheric depth."},
    "Game · Low-Poly 2.5D": {"runtime_preset":"VXPE_ARTSTYLE_LOW_POLY_25D","posterize":16,"saturation":1.10,"contrast":1.10,"outline_px":1,"fog":"#68949B","fog_strength":35,"trail":None,"description":"Low-poly/2.5D profile for pre-rendered geometry, billboards and depth fog."},
}

GAME_ART_STYLES.update({
    "Game · Dungeon Synth": ("Dungeon synth: warm torchlight against violet mana, weathered stone and bone.", "#09070f #190c2c #352840 #514a44 #736956 #a99a70 #e3d6a4 #fff0c4 #b34423 #f28c32 #ffc957 #493177 #804ceb #3894c9 #61ede9 #ffffff"),
    "Game · Urban Toon": ("Urban toon palette: bold ink, yellow clothing, blue sky, teal graffiti and saturated street accents.", "#0d1620 #26353d #4c595f #7c8581 #b1b4a4 #ebead5 #ffd427 #e6a91d #3a94c7 #1262bb #12c6bd #64e496 #f06557 #e52d8a #9f73cb #ffffff"),
    "Game · Cel-Shaded Cartoon": ("Cel-shaded cartoon with strong outlines and compact colour bands.", "#101820 #26343d #44575d #6d7f78 #9eaa7f #d9c77b #fff0a0 #0a625d #0c9482 #36c88b #7ee65c #b9f36a #2d78a2 #5cb7d6 #f06a3f #ffb84d"),
    "Game · Saturated Adventure": ("Vivid jungle adventure palette based on teal depth, lime foliage, warm wood and cyan trails.", "#092f38 #07565a #087b70 #0aa184 #15cf86 #69e84f #b7f34a #eefb75 #1d6b9b #42a9cf #88dff1 #d8f8f0 #7b3d1e #b85f25 #ed9337 #ffd35a"),
    "Game · Strategy Kingdom": ("High-readability strategy RPG palette for terrain, units and ornate gold UI.", "#111923 #1e2b38 #324455 #596b72 #8c927d #c5b26a #f2d06b #fff1b0 #315f48 #4f8a4e #7fc35a #b8df78 #7c3e2e #b96836 #dca34a #f2c86a"),
    "Game · Painterly Fantasy": ("Muted painterly fantasy palette with atmospheric blue-greens and warm accents.", "#242c37 #3a4855 #596a72 #7f8d8c #a8afa1 #d0c5a8 #ead8b9 #f5e9d4 #365d5c #527d72 #7f9d7b #b3b891 #86584a #ad7962 #d3a07b #efc99e"),
    "Game · Low-Poly 2.5D": ("Compact low-poly palette for billboard/2.5D scenes and geometric lighting.", "#14232d #24404b #37606a #56818a #7fa0a1 #aab9ad #d5ceb0 #f0e0bd #2f6f58 #4d9469 #76b878 #a6d28b #8c4d35 #bd7140 #dfa455 #f3cf78"),
})
