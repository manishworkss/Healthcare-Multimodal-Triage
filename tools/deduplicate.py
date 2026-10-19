#!/usr/bin/env python3
"""
Project Aid — Deduplication Tool
Detects exact duplicates (SHA-256) and perceptual near-duplicates (dHash) across dataset images.

Enforces PDF Rule (Page 6):
"No duplicate or similar images. If a reviewer placed your new image next to one already
in the dataset and could not quickly tell them apart, it is too similar and will be rejected."
"""

import os
import hashlib
import argparse
from typing import Dict, List, Tuple, Any
from PIL import Image


def compute_sha256(filepath: str) -> str:
    """Computes SHA-256 hash of a file for exact duplicate detection."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def compute_dhash(filepath: str, hash_size: int = 8) -> int:
    """
    Computes difference hash (dHash) of an image:
    1. Grayscale conversion.
    2. Resize to (hash_size + 1, hash_size).
    3. Compare adjacent pixels in each row.
    Returns a 64-bit integer.
    """
    try:
        with Image.open(filepath) as img:
            # Convert to grayscale and resize
            img = img.convert("L").resize((hash_size + 1, hash_size), Image.Resampling.LANCZOS)
            pixels = list(img.getdata())
            
            diff = []
            for row in range(hash_size):
                row_pixels = pixels[row * (hash_size + 1):(row + 1) * (hash_size + 1)]
                for col in range(hash_size):
                    diff.append(row_pixels[col] > row_pixels[col + 1])
            
            # Convert boolean array to 64-bit integer
            decimal_value = 0
            for index, value in enumerate(diff):
                if value:
                    decimal_value += 2 ** index
            return decimal_value
    except Exception as e:
        print(f"Warning: Failed to compute dHash for {filepath}: {e}")
        return 0


def hamming_distance(h1: int, h2: int) -> int:
    """Computes the Hamming distance (number of differing bits) between two 64-bit hashes."""
    return bin(h1 ^ h2).count("1")


def scan_images(dataset_dir: str) -> List[str]:
    """Finds all image files in the dataset directory."""
    valid_exts = {".jpg", ".jpeg", ".png", ".webp"}
    images = []
    for root, _, files in os.walk(dataset_dir):
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in valid_exts:
                images.append(os.path.join(root, f))
    return sorted(images)


def check_duplicates(dataset_dir: str, threshold: int = 6) -> Dict[str, Any]:
    images = scan_images(dataset_dir)
    print(f"Scanning {len(images)} images in '{dataset_dir}' for exact and near duplicates...")

    sha_map: Dict[str, List[str]] = {}
    dhashes: Dict[str, int] = {}

    for img_path in images:
        # Exact hash
        sha = compute_sha256(img_path)
        sha_map.setdefault(sha, []).append(img_path)

        # Perceptual hash
        dh = compute_dhash(img_path)
        dhashes[img_path] = dh

    exact_duplicates = [paths for paths in sha_map.values() if len(paths) > 1]

    # Pairwise comparison for near duplicates
    near_duplicates: List[Tuple[str, str, int]] = []
    img_list = list(dhashes.keys())
    for i in range(len(img_list)):
        for j in range(i + 1, len(img_list)):
            p1, p2 = img_list[i], img_list[j]
            # Skip if already identified as exact duplicate
            if dhashes[p1] == dhashes[p2] and compute_sha256(p1) == compute_sha256(p2):
                continue
            dist = hamming_distance(dhashes[p1], dhashes[p2])
            if dist <= threshold:
                near_duplicates.append((p1, p2, dist))

    return {
        "total_images": len(images),
        "exact_duplicates": exact_duplicates,
        "near_duplicates": near_duplicates,
    }


def main():
    parser = argparse.ArgumentParser(description="Find duplicate and visually similar images in Project Aid dataset.")
    parser.add_argument("--dir", default="datasets", help="Directory containing dataset images")
    parser.add_argument("--threshold", type=int, default=6, help="Hamming distance threshold for near-duplicates (default: 6)")
    args = parser.parse_args()

    if not os.path.exists(args.dir):
        print(f"Directory {args.dir} does not exist.")
        return 1

    report = check_duplicates(args.dir, threshold=args.threshold)

    print("\n========================================================")
    print("             Deduplication Audit Results                ")
    print("========================================================")
    print(f"Total Images Evaluated: {report['total_images']}")
    print(f"Exact Duplicate Clusters: {len(report['exact_duplicates'])}")
    print(f"Near-Duplicate Pairs Flagged (Hamming <= {args.threshold}): {len(report['near_duplicates'])}")
    print("--------------------------------------------------------")

    if report["exact_duplicates"]:
        print("\n❌ EXACT DUPLICATES FOUND (Must remove all but one):")
        for cluster in report["exact_duplicates"]:
            print(f"  Cluster: {cluster}")

    if report["near_duplicates"]:
        print(f"\n⚠️  NEAR-DUPLICATES FLAGGED FOR HUMAN REVIEW:")
        for p1, p2, dist in report["near_duplicates"]:
            print(f"  [Dist: {dist}/64] Pair:")
            print(f"    - {p1}")
            print(f"    - {p2}")
            print(f"    Action: Verify visual distinctness across body site / presentation per PDF page 6.")
    else:
        print("\n✅ No near-duplicates detected below threshold.")

    print("\n========================================================\n")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
