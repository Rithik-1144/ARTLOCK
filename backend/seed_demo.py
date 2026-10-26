"""Generate and register ten local ArtLock demo artworks for an existing account."""

import argparse
import io
import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT.parent / ".env")
sys.path.insert(0, str(ROOT))

from app import create_app, db  # noqa: E402
from app.models import Artwork, User, VerificationRecord, WorkspaceMembership  # noqa: E402

DEMO_ITEMS = [
    ("Moonlit Archipelago", "A quiet chain of islands beneath an oversized lavender moon.", ("#101d31", "#52627d", "#f3c89e", "#354b55")),
    ("Citrus After Rain", "Warm citrus forms and rain-softened botanical greens.", ("#172c2a", "#78926d", "#efb878", "#425c47")),
    ("The Blue Hour", "Layered blue ridgelines fading into a violet evening sky.", ("#1c2442", "#6b69a0", "#e7bbac", "#3d5772")),
    ("Desert Frequency", "Terracotta dunes crossed by a bright, graphic sun.", ("#36202b", "#b45e52", "#f4c27c", "#744248")),
    ("Glasshouse No. 4", "An imagined conservatory of silhouettes and late afternoon light.", ("#172d30", "#779b89", "#edd49b", "#365f57")),
    ("Orbiting Garden", "A small surreal garden suspended among celestial rings.", ("#27203b", "#79649d", "#edc4bd", "#46556e")),
    ("Saltwater Atlas", "Coastal strata, tidal lines, and a sea-glass palette.", ("#18313d", "#6a9291", "#ecc99f", "#3b6870")),
    ("Quiet Geometry", "A study in softened shapes, warm stone, and negative space.", ("#2a2531", "#81736f", "#e7c79f", "#514d5d")),
    ("Wildflower Signal", "A colorful field of abstract blooms beneath a spring sky.", ("#27233a", "#7e73a0", "#efb5a2", "#556c6a")),
    ("North Window", "The final light on an imagined northern landscape.", ("#182331", "#677d91", "#e6b89c", "#3d535c")),
]
DEMO_CATEGORIES = [
    "Digital painting",
    "Illustration",
    "Digital painting",
    "Graphic design",
    "Illustration",
    "3D art",
    "Photography",
    "Graphic design",
    "Illustration",
    "Photography",
]


def load_font(size):
    candidates = [
        Path("C:/Windows/Fonts/segoeui.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ]
    for candidate in candidates:
        if candidate.exists():
            try:
                return ImageFont.truetype(str(candidate), size)
            except OSError:
                pass
    return ImageFont.load_default()


def rgb(color):
    color = color.lstrip("#")
    return tuple(int(color[index:index + 2], 16) for index in (0, 2, 4))


def blend(first, second, amount):
    return tuple(round(left + (right - left) * amount) for left, right in zip(first, second))


def create_artwork(index, title, palette):
    width, height = 960, 1200
    top, middle, light, dark = map(rgb, palette)
    image = Image.new("RGB", (width, height))
    pixels = image.load()
    for y in range(height):
        ratio = y / height
        shade = blend(top, middle, min(1, ratio * 1.55))
        for x in range(width):
            glow = max(0, 1 - math.sqrt(((x - width * .76) / width) ** 2 + ((y - height * .34) / height) ** 2)) * .13
            pixels[x, y] = blend(shade, light, glow)

    draw = ImageDraw.Draw(image, "RGBA")
    seed = 8091 + index * 97
    rng = random.Random(seed)
    cx = 690 - (index % 3) * 65
    cy = 348 + (index % 4) * 23
    radius = 155 - (index % 3) * 12
    draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=(*light, 234))
    draw.ellipse((cx - radius * .72, cy - radius * .72, cx + radius * .72, cy + radius * .72), outline=(*top, 70), width=2)

    # Fine orbital paths and print-like stars provide texture without using stock art.
    for offset in (40, 85, 130):
        draw.arc((cx - radius - offset, cy - radius - offset, cx + radius + offset, cy + radius + offset), 205, 345, fill=(244, 229, 220, 54), width=2)
    for _ in range(68):
        x, y = rng.randrange(45, width - 45), rng.randrange(75, 760)
        size = rng.choice((2, 3, 4))
        alpha = rng.randrange(40, 145)
        draw.ellipse((x, y, x + size, y + size), fill=(244, 229, 220, alpha))

    baseline = 805
    layer_colors = [blend(dark, top, .25), dark, blend(dark, top, .12)]
    for layer in range(3):
        points = [(0, height)]
        x = 0
        y = baseline + layer * 80
        points.append((x, y))
        while x < width:
            x = min(width, x + rng.randint(85, 185))
            y = baseline + layer * 78 + rng.randint(-115, 112)
            points.append((x, y))
        points.extend([(width, height), (0, height)])
        draw.polygon(points, fill=(*layer_colors[layer], 245 - layer * 10))

    # A few geometric botanical strokes make each generated composition distinct.
    foreground = blend(dark, light, .3)
    for stem in range(5 + index % 4):
        sx = 75 + stem * 43 + rng.randint(-14, 14)
        sy = 970 + rng.randint(-45, 45)
        ex = sx + rng.randint(-75, 75)
        ey = sy - rng.randint(110, 240)
        draw.line((sx, sy, ex, ey), fill=(*foreground, 170), width=rng.randint(3, 6))
        for leaf in range(2):
            ly = sy - (ey - sy) * (leaf + 1) / 3
            direction = -1 if (stem + leaf + index) % 2 else 1
            lx = sx + (ex - sx) * (leaf + 1) / 3
            center_x = lx + 9 * direction
            draw.ellipse((center_x - 22, ly - 10, center_x + 22, ly + 10), fill=(*foreground, 128))

    draw.rectangle((52, 62, width - 52, height - 62), outline=(255, 244, 230, 55), width=2)
    draw.text((77, 995), f"ARTLOCK  /  STUDY {index + 1:02d}", font=load_font(17), fill=(246, 231, 219, 220))
    draw.text((77, 1030), title.upper(), font=load_font(34), fill=(250, 238, 226, 245))
    draw.text((79, 1081), "AN ORIGINAL DEMONSTRATION ARTWORK", font=load_font(13), fill=(240, 222, 210, 175))
    return image


def generate_demo_files(output_dir):
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for index, (title, description, palette) in enumerate(DEMO_ITEMS):
        filename = f"demo_{index + 1:02d}_{title.lower().replace(' ', '_')}.png"
        path = output_dir / filename
        if not path.exists():
            create_artwork(index, title, palette).save(path, format="PNG", optimize=True)
        paths.append((title, description, path))
    return paths


def seed_account(email, output_dir):
    app = create_app()
    files = generate_demo_files(output_dir)
    with app.app_context():
        user = User.query.filter_by(email=email.strip().lower()).first()
        if not user:
            raise SystemExit(
                f"No account found for {email}. Register in ArtLock first, then run this command again."
            )
        membership = WorkspaceMembership.query.filter_by(user_id=user.id).first()
        if not membership:
            raise SystemExit("The account does not have a workspace membership.")
        user_id = user.id
        workspace_id = membership.workspace_id
        workspace_name = membership.workspace.name

    client = app.test_client()
    with client.session_transaction() as browser_session:
        import secrets

        token = secrets.token_urlsafe(32)
        browser_session["user_id"] = user_id
        browser_session["csrf_token"] = token
        browser_session.permanent = True

    added = []
    skipped = []
    checks_created = 0
    for title, description, path in files:
        with app.app_context():
            existing = Artwork.query.filter_by(
                workspace_id=workspace_id,
                title=f"Demo · {title}",
            ).first()
        if existing:
            item_index = next(i for i, item in enumerate(DEMO_ITEMS) if item[0] == title)
            category = DEMO_CATEGORIES[item_index]
            updated = client.patch(
                f"/api/v1/artworks/{existing.id}",
                headers={"X-CSRF-Token": token},
                json={
                    "category": category,
                    "tags": ["demo", "sample", category.lower()],
                    "favorite": item_index in {0, 3, 6},
                },
            )
            if updated.status_code != 200:
                raise RuntimeError(f"Could not organize demo artwork {title}: {updated.get_json()}")
            skipped.append(title)
            continue
        item_index = next(i for i, item in enumerate(DEMO_ITEMS) if item[0] == title)
        with path.open("rb") as artwork_file:
            response = client.post(
                "/api/v1/artworks",
                headers={"X-CSRF-Token": token},
                data={
                    "title": f"Demo · {title}",
                    "description": f"{description} Generated local sample for demonstration; not an uploaded customer original.",
                    "category": DEMO_CATEGORIES[item_index],
                    "file": (artwork_file, path.name, "image/png"),
                },
                content_type="multipart/form-data",
            )
        if response.status_code != 201:
            raise RuntimeError(f"Could not register {path.name}: {response.status_code} {response.get_json()}")
        added.append((title, response.get_json()["artwork"]["id"], path))
        updated = client.patch(
            f"/api/v1/artworks/{response.get_json()['artwork']['id']}",
            headers={"X-CSRF-Token": token},
            json={
                "tags": ["demo", "sample", DEMO_CATEGORIES[item_index].lower()],
                "favorite": item_index in {0, 3, 6},
            },
        )
        if updated.status_code != 200:
            raise RuntimeError(f"Could not organize demo artwork {title}: {updated.get_json()}")

    # Seed records only after performing genuine server-side file comparisons.
    for index, (title, artwork_id, path) in enumerate(added):
        if index >= 6:
            break
        with path.open("rb") as original:
            verification = client.post(
                f"/api/v1/artworks/{artwork_id}/verify",
                headers={"X-CSRF-Token": token},
                data={"file": (original, path.name)},
                content_type="multipart/form-data",
            )
        if verification.status_code != 200 or verification.get_json()["result"] != "MATCH":
            raise RuntimeError(f"Could not verify demonstration artwork {title}.")
        checks_created += 1

    with app.app_context():
        sample_artworks = Artwork.query.filter(
            Artwork.workspace_id == workspace_id,
            Artwork.title.like("Demo · %"),
        ).all()
        sample_ids = [artwork.id for artwork in sample_artworks]
        has_demo_mismatch = bool(
            sample_ids
            and VerificationRecord.query.filter(
                VerificationRecord.artwork_id.in_(sample_ids),
                VerificationRecord.result == "MISMATCH",
            ).first()
        )
    if sample_artworks and not has_demo_mismatch:
        sample_artwork = sample_artworks[0]
        with sample_artwork_path(sample_artwork, files) as candidate:
            mismatch = client.post(
                f"/api/v1/artworks/{sample_artwork.id}/verify",
                headers={"X-CSRF-Token": token},
                data={"file": (candidate, "modified-demo-candidate.png")},
                content_type="multipart/form-data",
            )
        if mismatch.status_code != 200 or mismatch.get_json()["result"] != "MISMATCH":
            raise RuntimeError("Could not record the demonstration mismatch comparison.")
        checks_created += 1

    summary = {
        "workspace": workspace_name,
        "registered": len(added),
        "already_present": len(skipped),
        "sample_count": len(files),
        "integrity_checks_created": checks_created,
    }
    print(f"Workspace: {workspace_name}")
    print(f"Registered this run: {len(added)}")
    print(f"Already present: {len(skipped)}")
    print(f"Valid sample files: {len(files)} in {output_dir}")
    print(f"New integrity checks this run: {checks_created} genuine server-side comparisons.")
    return summary


def sample_artwork_path(artwork, files):
    from contextlib import contextmanager

    @contextmanager
    def candidate_file():
        sample_path = next(
            path
            for title, _, path in files
            if artwork.title == f"Demo · {title}"
        )
        with Image.open(sample_path) as source:
            modified = source.convert("RGB")
            pixel = modified.getpixel((0, 0))
            modified.putpixel((0, 0), tuple(255 - channel for channel in pixel))
            candidate = io.BytesIO()
            modified.save(candidate, format="PNG")
            candidate.seek(0)
            yield candidate

    return candidate_file()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True, help="Existing ArtLock account email")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "demo_assets",
        help="Directory for generated, non-secret sample image files",
    )
    args = parser.parse_args()
    seed_account(args.email, args.output_dir.resolve())


if __name__ == "__main__":
    main()
