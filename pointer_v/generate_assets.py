"""
Pointer V - Branding Asset Generator
Generates original logo.svg, multi-resolution .ico (16..256), tray icons, and splash image.
"""

import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

def generate_assets():
    base_dir = Path(__file__).resolve().parent
    icons_dir = base_dir / "assets" / "icons"
    images_dir = base_dir / "assets" / "images"
    icons_dir.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)

    svg_content = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" width="256" height="256">
  <rect width="256" height="256" rx="48" fill="#0B0E13"/>
  <rect x="8" y="8" width="240" height="240" rx="40" fill="#11151C" stroke="#232A36" stroke-width="2"/>
  <polyline points="64,76 128,196 192,60" fill="none" stroke="#2F7BFF" stroke-width="22" stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="192" cy="60" r="15" fill="#22D3EE" stroke="#5BA0FF" stroke-width="3"/>
</svg>"""

    with open(icons_dir / "logo.svg", "w", encoding="utf-8") as f:
        f.write(svg_content)

    def draw_logo(size: int) -> Image.Image:
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        scale = size / 256.0

        r = int(48 * scale)
        draw.rounded_rectangle(
            [0, 0, size, size],
            radius=r,
            fill=(17, 21, 28, 255),
            outline=(35, 42, 54, 255),
            width=max(1, int(2 * scale))
        )

        p1 = (int(64 * scale), int(76 * scale))
        p2 = (int(128 * scale), int(196 * scale))
        p3 = (int(192 * scale), int(60 * scale))
        w = max(2, int(22 * scale))
        draw.line([p1, p2, p3], fill=(47, 123, 255, 255), width=w, joint="round")

        dot_r = max(2, int(15 * scale))
        draw.ellipse(
            [p3[0] - dot_r, p3[1] - dot_r, p3[0] + dot_r, p3[1] + dot_r],
            fill=(34, 211, 238, 255),
            outline=(91, 160, 255, 255),
            width=max(1, int(3 * scale))
        )
        return img

    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = [draw_logo(s) for s in sizes]

    # Multi-resolution ICO
    ico_path = icons_dir / "pointer_v.ico"
    images[-1].save(str(ico_path), format="ICO", sizes=[(s, s) for s in sizes])
    images[-1].save(str(icons_dir / "pointer_v_256.png"), format="PNG")
    images[2].save(str(icons_dir / "pointer_v_32.png"), format="PNG")

    # Tray Icons (32x32)
    def draw_tray(dot_color):
        img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse([2, 2, 30, 30], fill=(17, 21, 28, 240), outline=(47, 57, 72, 255), width=1)
        draw.line([(9, 10), (16, 22), (23, 9)], fill=(47, 123, 255, 255), width=3, joint="round")
        draw.ellipse([21, 7, 26, 12], fill=dot_color)
        return img

    draw_tray((47, 123, 255, 255)).save(str(icons_dir / "tray_pointer.png"))
    draw_tray((139, 124, 255, 255)).save(str(icons_dir / "tray_keyboard.png"))
    draw_tray((245, 165, 36, 255)).save(str(icons_dir / "tray_paint.png"))
    draw_tray((100, 116, 139, 255)).save(str(icons_dir / "tray_paused.png"))
    draw_tray((50, 60, 75, 255)).save(str(icons_dir / "tray_off.png"))

    # Splash Image (520x320)
    splash = Image.new("RGBA", (520, 320), (11, 14, 19, 255))
    s_draw = ImageDraw.Draw(splash)
    s_draw.rectangle([0, 0, 519, 319], outline=(35, 42, 54, 255), width=1)
    logo_splash = draw_logo(110)
    splash.paste(logo_splash, (48, 105), logo_splash)

    font_path = base_dir / "assets" / "fonts" / "Inter-Variable.ttf"
    title_font = None
    sub_font = None
    if font_path.exists():
        try:
            title_font = ImageFont.truetype(str(font_path), 28)
            sub_font = ImageFont.truetype(str(font_path), 13)
        except Exception:
            pass

    s_draw.text((184, 115), "Pointer V", fill=(230, 234, 242, 255), font=title_font)
    s_draw.text((184, 158), "Control your PC in the air with one hand.", fill=(154, 164, 181, 255), font=sub_font)
    s_draw.text((184, 186), "Version 2.0.0 · Veera Akash A", fill=(91, 101, 117, 255), font=sub_font)
    splash.save(str(images_dir / "splash.png"))

    print("All branding assets generated successfully.")

if __name__ == "__main__":
    generate_assets()

