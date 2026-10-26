import io
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError


SIMILARITY_METHOD = "dhash-8x8-v1"


def image_fingerprint(content):
    """Return oriented dimensions and a 64-bit horizontal difference hash."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(content)) as source:
                image = ImageOps.exif_transpose(source)
                width, height = image.size
                pixels = list(image.convert("L").resize((9, 8)).get_flattened_data())
    except (
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise ValueError("Image could not be analyzed safely.") from exc

    fingerprint = 0
    for row in range(8):
        for column in range(8):
            left = pixels[row * 9 + column]
            right = pixels[row * 9 + column + 1]
            fingerprint = (fingerprint << 1) | int(left > right)
    return width, height, f"{fingerprint:016x}"


def similarity_percent(first_hash, second_hash):
    distance = (int(first_hash, 16) ^ int(second_hash, 16)).bit_count()
    return round((64 - distance) * 100 / 64)
