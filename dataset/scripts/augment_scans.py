"""Apply scan-like augmentation to a subset of the demo invoice images.

Simulates the artifacts of a real office scanner: slight rotation, noise,
JPEG recompression, blur, contrast shift and a page shadow. Clean originals
are always kept so extraction accuracy can be compared with and without
augmentation. Deterministic given SEED.
"""

from __future__ import annotations

import random
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

SEED = 42
AUGMENT_FRACTION = 0.25
MAX_ROTATION_DEGREES = 2.0

DATASET_DIR = Path(__file__).resolve().parent.parent
DEMO_INVOICES_DIR = DATASET_DIR / "demo" / "invoices"


def add_gaussian_noise(image: np.ndarray, sigma: float = 6.0) -> np.ndarray:
    noise = np.random.normal(0, sigma, image.shape).astype(np.float32)
    noisy = image.astype(np.float32) + noise
    return np.clip(noisy, 0, 255).astype(np.uint8)


def add_page_shadow(image: np.ndarray) -> np.ndarray:
    h, w = image.shape[:2]
    gradient = np.tile(np.linspace(0.85, 1.0, w, dtype=np.float32), (h, 1))
    if image.ndim == 3:
        gradient = np.stack([gradient] * image.shape[2], axis=-1)
    shadowed = image.astype(np.float32) * gradient
    return np.clip(shadowed, 0, 255).astype(np.uint8)


def rotate_slightly(image: np.ndarray, rng: random.Random) -> np.ndarray:
    angle = rng.uniform(-MAX_ROTATION_DEGREES, MAX_ROTATION_DEGREES)
    h, w = image.shape[:2]
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(
        image, matrix, (w, h), flags=cv2.INTER_LINEAR, borderValue=(255, 255, 255)
    )


def shift_contrast(image: np.ndarray, rng: random.Random) -> np.ndarray:
    factor = rng.uniform(0.9, 1.1)
    shifted = image.astype(np.float32) * factor
    return np.clip(shifted, 0, 255).astype(np.uint8)


def augment_image(src_path: Path, dst_path: Path, rng: random.Random) -> None:
    image = cv2.imread(str(src_path), cv2.IMREAD_COLOR)
    if image is None:
        return

    image = rotate_slightly(image, rng)
    image = add_gaussian_noise(image)
    image = shift_contrast(image, rng)
    image = add_page_shadow(image)
    image = cv2.GaussianBlur(image, (3, 3), sigmaX=0.5)

    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    pil_image = Image.fromarray(rgb)
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    pil_image.save(dst_path, format="JPEG", quality=70)


def main() -> None:
    rng = random.Random(SEED)
    np.random.seed(SEED)

    if not DEMO_INVOICES_DIR.exists():
        print(f"{DEMO_INVOICES_DIR} does not exist. Run select_demo_set.py first.")
        return

    jpg_files = sorted(DEMO_INVOICES_DIR.glob("*.jpg")) + sorted(DEMO_INVOICES_DIR.glob("*.jpeg"))
    if not jpg_files:
        print("No JPG demo invoices found to augment.")
        return

    sample_size = max(1, int(len(jpg_files) * AUGMENT_FRACTION))
    chosen = rng.sample(jpg_files, sample_size)

    augmented_dir = DEMO_INVOICES_DIR.parent / "invoices_augmented"
    for src in chosen:
        dst = augmented_dir / src.name
        augment_image(src, dst, rng)

    print(f"Augmented {len(chosen)} of {len(jpg_files)} JPG demo invoices into {augmented_dir}")


if __name__ == "__main__":
    main()
