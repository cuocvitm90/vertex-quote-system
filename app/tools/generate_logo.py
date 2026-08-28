"""
Script to create high-resolution Vertex Construction logo and assets (Light & Dark backgrounds)
Matches the brand identity: Central Navy Tower + Two Flanking Orange Towers + 'VERTEX CONSTRUCTION'
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

img_dir = Path("app/static/images")
img_dir.mkdir(parents=True, exist_ok=True)

# 1. Standard SVG Logo (for light backgrounds)
svg_content = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 420 100" width="100%" height="100%">
  <defs>
    <linearGradient id="orangeGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#FF7D47" />
      <stop offset="100%" stop-color="#E8590C" />
    </linearGradient>
    <linearGradient id="navyGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#242E46" />
      <stop offset="100%" stop-color="#141B2D" />
    </linearGradient>
    <filter id="subtleShadow" x="-10%" y="-10%" width="130%" height="130%">
      <feDropShadow dx="0" dy="4" stdDeviation="4" flood-opacity="0.18"/>
    </filter>
  </defs>

  <g transform="translate(10, 8)" filter="url(#subtleShadow)">
    <path d="M 6 82 L 6 36 L 24 22 L 24 82 Z" fill="url(#orangeGrad)" />
    <line x1="12" y1="36" x2="18" y2="32" stroke="#FFFFFF" stroke-width="2" stroke-linecap="round" opacity="0.6"/>
    <line x1="12" y1="48" x2="18" y2="44" stroke="#FFFFFF" stroke-width="2" stroke-linecap="round" opacity="0.6"/>
    <line x1="12" y1="60" x2="18" y2="56" stroke="#FFFFFF" stroke-width="2" stroke-linecap="round" opacity="0.6"/>
    <line x1="12" y1="72" x2="18" y2="68" stroke="#FFFFFF" stroke-width="2" stroke-linecap="round" opacity="0.6"/>

    <path d="M 28 82 L 28 10 L 52 2 L 52 82 Z" fill="url(#navyGrad)" stroke="#FF6B35" stroke-width="1.5" />
    <polygon points="40,2 40,82 52,82 52,2" fill="#1B2234" opacity="0.4" />
    
    <rect x="33" y="16" width="6" height="6" rx="1" fill="#FF6B35" opacity="0.9"/>
    <rect x="43" y="16" width="6" height="6" rx="1" fill="#FFFFFF" opacity="0.8"/>
    <rect x="33" y="28" width="6" height="6" rx="1" fill="#FFFFFF" opacity="0.8"/>
    <rect x="43" y="28" width="6" height="6" rx="1" fill="#FF6B35" opacity="0.9"/>
    <rect x="33" y="40" width="6" height="6" rx="1" fill="#FFFFFF" opacity="0.8"/>
    <rect x="43" y="40" width="6" height="6" rx="1" fill="#FFFFFF" opacity="0.8"/>
    <rect x="33" y="52" width="6" height="6" rx="1" fill="#FF6B35" opacity="0.9"/>
    <rect x="43" y="52" width="6" height="6" rx="1" fill="#FFFFFF" opacity="0.8"/>
    <rect x="33" y="64" width="6" height="6" rx="1" fill="#FFFFFF" opacity="0.8"/>
    <rect x="43" y="64" width="6" height="6" rx="1" fill="#FF6B35" opacity="0.9"/>

    <path d="M 56 82 L 56 22 L 74 36 L 74 82 Z" fill="url(#orangeGrad)" />
    <line x1="62" y1="32" x2="68" y2="36" stroke="#FFFFFF" stroke-width="2" stroke-linecap="round" opacity="0.6"/>
    <line x1="62" y1="44" x2="68" y2="48" stroke="#FFFFFF" stroke-width="2" stroke-linecap="round" opacity="0.6"/>
    <line x1="62" y1="56" x2="68" y2="60" stroke="#FFFFFF" stroke-width="2" stroke-linecap="round" opacity="0.6"/>
    <line x1="62" y1="68" x2="68" y2="72" stroke="#FFFFFF" stroke-width="2" stroke-linecap="round" opacity="0.6"/>

    <rect x="2" y="82" width="76" height="4" rx="2" fill="#FF6B35" />
  </g>

  <g transform="translate(98, 12)">
    <text x="0" y="40" font-family="'Plus Jakarta Sans', 'Segoe UI', Arial, sans-serif" font-size="36" font-weight="900" fill="#1B2234" letter-spacing="1.5">VERTEX</text>
    <text x="2" y="65" font-family="'Plus Jakarta Sans', 'Segoe UI', Arial, sans-serif" font-size="16" font-weight="800" fill="#FF6B35" letter-spacing="4.5">CONSTRUCTION</text>
    <text x="3" y="78" font-family="'Plus Jakarta Sans', 'Segoe UI', Arial, sans-serif" font-size="8.5" font-weight="600" fill="#64748B" letter-spacing="1.2">HVAC &amp; MEP QUOTE AUTOMATION</text>
  </g>
</svg>"""

with open(img_dir / "logo.svg", "w", encoding="utf-8") as f:
    f.write(svg_content)

# 2. White SVG Logo (for dark navy headers)
svg_white_content = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 420 100" width="100%" height="100%">
  <defs>
    <linearGradient id="wOrangeGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#FF7D47" />
      <stop offset="100%" stop-color="#E8590C" />
    </linearGradient>
    <linearGradient id="wNavyGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#FFFFFF" />
      <stop offset="100%" stop-color="#E2E8F0" />
    </linearGradient>
    <filter id="subtleGlow" x="-10%" y="-10%" width="130%" height="130%">
      <feDropShadow dx="0" dy="2" stdDeviation="3" flood-color="#FF6B35" flood-opacity="0.3"/>
    </filter>
  </defs>

  <g transform="translate(10, 8)" filter="url(#subtleGlow)">
    <path d="M 6 82 L 6 36 L 24 22 L 24 82 Z" fill="url(#wOrangeGrad)" />
    <line x1="12" y1="36" x2="18" y2="32" stroke="#FFFFFF" stroke-width="2" stroke-linecap="round" opacity="0.6"/>
    <line x1="12" y1="48" x2="18" y2="44" stroke="#FFFFFF" stroke-width="2" stroke-linecap="round" opacity="0.6"/>
    <line x1="12" y1="60" x2="18" y2="56" stroke="#FFFFFF" stroke-width="2" stroke-linecap="round" opacity="0.6"/>
    <line x1="12" y1="72" x2="18" y2="68" stroke="#FFFFFF" stroke-width="2" stroke-linecap="round" opacity="0.6"/>

    <path d="M 28 82 L 28 10 L 52 2 L 52 82 Z" fill="#1B2234" stroke="#FF6B35" stroke-width="1.5" />
    
    <rect x="33" y="16" width="6" height="6" rx="1" fill="#FF6B35" />
    <rect x="43" y="16" width="6" height="6" rx="1" fill="#FFFFFF" />
    <rect x="33" y="28" width="6" height="6" rx="1" fill="#FFFFFF" />
    <rect x="43" y="28" width="6" height="6" rx="1" fill="#FF6B35" />
    <rect x="33" y="40" width="6" height="6" rx="1" fill="#FFFFFF" />
    <rect x="43" y="40" width="6" height="6" rx="1" fill="#FFFFFF" />
    <rect x="33" y="52" width="6" height="6" rx="1" fill="#FF6B35" />
    <rect x="43" y="52" width="6" height="6" rx="1" fill="#FFFFFF" />
    <rect x="33" y="64" width="6" height="6" rx="1" fill="#FFFFFF" />
    <rect x="43" y="64" width="6" height="6" rx="1" fill="#FF6B35" />

    <path d="M 56 82 L 56 22 L 74 36 L 74 82 Z" fill="url(#wOrangeGrad)" />
    <line x1="62" y1="32" x2="68" y2="36" stroke="#FFFFFF" stroke-width="2" stroke-linecap="round" opacity="0.6"/>
    <line x1="62" y1="44" x2="68" y2="48" stroke="#FFFFFF" stroke-width="2" stroke-linecap="round" opacity="0.6"/>
    <line x1="62" y1="56" x2="68" y2="60" stroke="#FFFFFF" stroke-width="2" stroke-linecap="round" opacity="0.6"/>
    <line x1="62" y1="68" x2="68" y2="72" stroke="#FFFFFF" stroke-width="2" stroke-linecap="round" opacity="0.6"/>

    <rect x="2" y="82" width="76" height="4" rx="2" fill="#FF6B35" />
  </g>

  <g transform="translate(98, 12)">
    <text x="0" y="40" font-family="'Plus Jakarta Sans', 'Segoe UI', Arial, sans-serif" font-size="36" font-weight="900" fill="#FFFFFF" letter-spacing="1.5">VERTEX</text>
    <text x="2" y="65" font-family="'Plus Jakarta Sans', 'Segoe UI', Arial, sans-serif" font-size="16" font-weight="800" fill="#FF6B35" letter-spacing="4.5">CONSTRUCTION</text>
    <text x="3" y="78" font-family="'Plus Jakarta Sans', 'Segoe UI', Arial, sans-serif" font-size="8.5" font-weight="600" fill="#94A3B8" letter-spacing="1.2">HVAC &amp; MEP QUOTE AUTOMATION</text>
  </g>
</svg>"""

with open(img_dir / "logo-white.svg", "w", encoding="utf-8") as f:
    f.write(svg_white_content)

# 3. Favicon SVG
favicon_svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100%" height="100%">
  <defs>
    <linearGradient id="oGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="#FF7D47" />
      <stop offset="100%" stop-color="#E8590C" />
    </linearGradient>
  </defs>
  <rect width="100" height="100" rx="22" fill="#1B2234" />
  <g transform="translate(10, 8)">
    <path d="M 6 80 L 6 36 L 24 22 L 24 80 Z" fill="url(#oGrad)" />
    <path d="M 28 80 L 28 10 L 52 2 L 52 80 Z" fill="#FFFFFF" stroke="#FF6B35" stroke-width="1.5" />
    <rect x="33" y="16" width="6" height="6" rx="1" fill="#FF6B35" />
    <rect x="43" y="16" width="6" height="6" rx="1" fill="#1B2234" />
    <rect x="33" y="28" width="6" height="6" rx="1" fill="#1B2234" />
    <rect x="43" y="28" width="6" height="6" rx="1" fill="#FF6B35" />
    <rect x="33" y="40" width="6" height="6" rx="1" fill="#FF6B35" />
    <rect x="43" y="40" width="6" height="6" rx="1" fill="#1B2234" />
    <rect x="33" y="52" width="6" height="6" rx="1" fill="#1B2234" />
    <rect x="43" y="52" width="6" height="6" rx="1" fill="#FF6B35" />
    <path d="M 56 80 L 56 22 L 74 36 L 74 80 Z" fill="url(#oGrad)" />
    <rect x="2" y="80" width="76" height="4" rx="2" fill="#FF6B35" />
  </g>
</svg>"""

with open(img_dir / "favicon.svg", "w", encoding="utf-8") as f:
    f.write(favicon_svg)

# 4. Generate PNG Logos (Light & Dark text versions)
def generate_pngs():
    width, height = 840, 200
    NAVY = (27, 34, 52, 255)
    ORANGE = (255, 107, 53, 255)
    WHITE = (255, 255, 255, 255)
    GRAY = (100, 116, 139, 255)
    GRAY_LIGHT = (148, 163, 184, 255)

    try:
        font_vertex = ImageFont.truetype("arialbd.ttf", 64)
        font_const = ImageFont.truetype("arialbd.ttf", 28)
        font_sub = ImageFont.truetype("arial.ttf", 16)
    except Exception:
        font_vertex = ImageFont.load_default()
        font_const = ImageFont.load_default()
        font_sub = ImageFont.load_default()

    ox, oy = 20, 20

    # 4a. logo.png (for light backgrounds)
    img_light = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d_light = ImageDraw.Draw(img_light)
    d_light.polygon([(ox + 10, oy + 150), (ox + 10, oy + 65), (ox + 45, oy + 40), (ox + 45, oy + 150)], fill=ORANGE)
    for y_off in [65, 87, 109, 131]:
        d_light.line([(ox + 20, oy + y_off), (ox + 35, oy + y_off - 8)], fill=WHITE, width=3)
    d_light.polygon([(ox + 52, oy + 150), (ox + 52, oy + 20), (ox + 98, oy + 5), (ox + 98, oy + 150)], fill=NAVY, outline=ORANGE, width=2)
    for row, y_w in enumerate([32, 54, 76, 98, 120]):
        col1_fill = ORANGE if row % 2 == 0 else WHITE
        col2_fill = WHITE if row % 2 == 0 else ORANGE
        d_light.rectangle([ox + 60, oy + y_w, ox + 72, oy + y_w + 12], fill=col1_fill)
        d_light.rectangle([ox + 78, oy + y_w, ox + 90, oy + y_w + 12], fill=col2_fill)
    d_light.polygon([(ox + 105, oy + 150), (ox + 105, oy + 40), (ox + 140, oy + 65), (ox + 140, oy + 150)], fill=ORANGE)
    for y_off in [65, 87, 109, 131]:
        d_light.line([(ox + 115, oy + y_off - 8), (ox + 130, oy + y_off)], fill=WHITE, width=3)
    d_light.rectangle([ox + 4, oy + 150, ox + 146, oy + 158], fill=ORANGE)

    tx = ox + 180
    d_light.text((tx, oy + 15), "VERTEX", fill=NAVY, font=font_vertex)
    d_light.text((tx + 4, oy + 88), "CONSTRUCTION", fill=ORANGE, font=font_const)
    d_light.text((tx + 6, oy + 128), "HVAC & MEP QUOTE AUTOMATION", fill=GRAY, font=font_sub)
    img_light.save(img_dir / "logo.png", "PNG")

    # 4b. logo-white.png (for dark backgrounds)
    img_dark = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d_dark = ImageDraw.Draw(img_dark)
    d_dark.polygon([(ox + 10, oy + 150), (ox + 10, oy + 65), (ox + 45, oy + 40), (ox + 45, oy + 150)], fill=ORANGE)
    for y_off in [65, 87, 109, 131]:
        d_dark.line([(ox + 20, oy + y_off), (ox + 35, oy + y_off - 8)], fill=WHITE, width=3)
    d_dark.polygon([(ox + 52, oy + 150), (ox + 52, oy + 20), (ox + 98, oy + 5), (ox + 98, oy + 150)], fill=NAVY, outline=ORANGE, width=2)
    for row, y_w in enumerate([32, 54, 76, 98, 120]):
        col1_fill = ORANGE if row % 2 == 0 else WHITE
        col2_fill = WHITE if row % 2 == 0 else ORANGE
        d_dark.rectangle([ox + 60, oy + y_w, ox + 72, oy + y_w + 12], fill=col1_fill)
        d_dark.rectangle([ox + 78, oy + y_w, ox + 90, oy + y_w + 12], fill=col2_fill)
    d_dark.polygon([(ox + 105, oy + 150), (ox + 105, oy + 40), (ox + 140, oy + 65), (ox + 140, oy + 150)], fill=ORANGE)
    for y_off in [65, 87, 109, 131]:
        d_dark.line([(ox + 115, oy + y_off - 8), (ox + 130, oy + y_off)], fill=WHITE, width=3)
    d_dark.rectangle([ox + 4, oy + 150, ox + 146, oy + 158], fill=ORANGE)

    d_dark.text((tx, oy + 15), "VERTEX", fill=WHITE, font=font_vertex)
    d_dark.text((tx + 4, oy + 88), "CONSTRUCTION", fill=ORANGE, font=font_const)
    d_dark.text((tx + 6, oy + 128), "HVAC & MEP QUOTE AUTOMATION", fill=GRAY_LIGHT, font=font_sub)
    img_dark.save(img_dir / "logo-white.png", "PNG")

    # 4c. Icon
    icon = Image.new("RGBA", (256, 256), (27, 34, 52, 255))
    draw_i = ImageDraw.Draw(icon)
    iox, ioy = 52, 45
    draw_i.polygon([(iox + 10, ioy + 140), (iox + 10, ioy + 65), (iox + 45, ioy + 40), (iox + 45, ioy + 140)], fill=ORANGE)
    draw_i.polygon([(iox + 52, ioy + 140), (iox + 52, ioy + 20), (iox + 98, ioy + 5), (iox + 98, ioy + 140)], fill=WHITE, outline=ORANGE, width=2)
    for row, y_w in enumerate([30, 50, 70, 90, 110]):
        c1 = ORANGE if row % 2 == 0 else NAVY
        c2 = NAVY if row % 2 == 0 else ORANGE
        draw_i.rectangle([iox + 60, ioy + y_w, iox + 72, ioy + y_w + 10], fill=c1)
        draw_i.rectangle([iox + 78, ioy + y_w, iox + 90, ioy + y_w + 10], fill=c2)
    draw_i.polygon([(iox + 105, ioy + 140), (iox + 105, ioy + 40), (iox + 140, ioy + 65), (iox + 140, ioy + 140)], fill=ORANGE)
    draw_i.rectangle([iox + 4, ioy + 140, iox + 146, ioy + 148], fill=ORANGE)
    icon.save(img_dir / "logo-icon.png", "PNG")
    print("All image assets generated successfully!")

generate_pngs()
