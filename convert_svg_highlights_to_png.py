#!/usr/bin/env python3

import io
import os
from pathlib import Path
from PIL import Image
from lxml import etree
import cairosvg
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor

def crop_svg_to_content(svg_path, output_path, scale=1.5, output_width=512, output_height=512):
    """
    Crop an SVG file to its visible content and convert it to PNG.
    """
    try:
        # Step 1: Render to in-memory PNG with transparent background
        buf = io.BytesIO()
        cairosvg.svg2png(
            url=str(svg_path),
            write_to=buf,
            output_width=int(output_width * scale),
            output_height=int(output_height * scale),
            background_color='transparent'
        )
        buf.seek(0)

        # Step 2: Use PIL to get bounding box of non-transparent pixels
        with Image.open(buf).convert("RGBA") as im:
            alpha = im.getchannel("A")
            bbox = alpha.getbbox()  # returns (left, upper, right, lower)

            if not bbox:
                print(f"⚠️ Could not detect bounding box for {svg_path.name}")
                # fallback: render without cropping
                cairosvg.svg2png(
                    url=str(svg_path),
                    write_to=str(output_path),
                    output_width=output_width,
                    output_height=output_height
                )
                return

            # Step 3: Crop and resize to target resolution
            cropped = im.crop(bbox).resize((output_width, output_height), Image.LANCZOS)
            cropped.save(output_path)
    except Exception as e:
        print(f"❌ Error processing {svg_path.name}: {e}")


def convert_svg_folder(input_dir, output_dir, output_width=512, output_height=512):
    """
    Convert all SVG files in a directory (recursively) to cropped PNGs.
    """
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)
    svg_files = list(input_dir.rglob('*.svg'))

    if not svg_files:
        print(f"⚠️ No SVG files found in {input_dir}")
        return

    print(f"🔄 Converting {len(svg_files)} SVG files from {input_dir} to PNGs in {output_dir}")

    def process_file(svg_file):
        relative_path = svg_file.relative_to(input_dir)
        output_png = output_dir / relative_path.with_suffix('.png')
        output_png.parent.mkdir(parents=True, exist_ok=True)
        crop_svg_to_content(svg_file, output_png, output_width=output_width, output_height=output_height)

    with ThreadPoolExecutor() as executor:
        list(tqdm(executor.map(process_file, svg_files), total=len(svg_files), desc="Converting SVGs", unit="file"))

