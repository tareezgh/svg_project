# run_pipeline.py

import inquirer
from main import process_directory as segment_svgs
from highlight_segmented_parts import highlight_segments, convert_full_svg_to_png
from convert_svg_highlights_to_png import convert_svg_folder
from send_pngs import send_grouped_pngs
from build_hierarchy import build_hierarchy_for_folder  # You'll need to move main logic into a function

from pathlib import Path

def select_input_folder(base_dir='svgs'):
    base_path = Path(base_dir)
    subfolders = [f.name for f in base_path.iterdir() if f.is_dir()]
    if not subfolders:
        print(f"❌ No subfolders found in '{base_dir}'.")
        return None

    question = [inquirer.List('selected_folder', message="Select input folder:", choices=subfolders)]
    answers = inquirer.prompt(question)
    return answers['selected_folder'] if answers else None

def run_pipeline():
    folder = select_input_folder()
    if not folder:
        return

    print(f"\n🔁 Running pipeline for: {folder}")

    # Step 1: Segment SVGs
    print("\n🧩 Segmenting SVGs...")
    segment_svgs(f"svgs/{folder}", f"segmented_svgs/{folder}")

    # Step 2: Highlight segments + convert to PNG
    print("\n🎯 Highlighting segments...")
    highlight_segments("svgs", "segmented_svgs", "highlighted_svgs", folder)
    input_highlighted = Path("highlighted_svgs") / folder
    convert_svg_folder(input_highlighted, Path("highlighted_pngs") / folder)

    for svg_subdir in (Path("segmented_svgs") / folder).iterdir():
        if svg_subdir.is_dir():
            convert_full_svg_to_png("svgs", folder, svg_subdir.name, "highlighted_pngs")

    # Step 3: Send PNGs to Gemini
    print("\n🚀 Sending PNGs to Gemini...")
    send_grouped_pngs(Path("highlighted_pngs") / folder, Path("gemini_responses"), prompt="Describe each region...")

    # Step 4: Build hierarchy
    print("\n🌳 Building hierarchy...")
    build_hierarchy_for_folder(folder)

if __name__ == "__main__":
    run_pipeline()
