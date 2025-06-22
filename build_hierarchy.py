from pathlib import Path
from shapely.geometry import Polygon
from shapely.ops import unary_union
import xml.etree.ElementTree as ET
import re
import json
import inquirer
from tqdm import tqdm

SEGMENTS_DIR = Path("segmented_svgs")
RESPONSES_DIR = Path("gemini_responses")
OUTPUT_ROOT = Path("hierarchy_output")
OUTPUT_ROOT.mkdir(exist_ok=True)

def extract_index_from_filename(name: str) -> int:
    match = re.search(r'_(\d+)', name)
    return int(match.group(1)) if match else -1

def parse_polygon_from_svg(svg_path):
    tree = ET.parse(svg_path)
    root = tree.getroot()
    for el in root.iter():
        if 'd' in el.attrib:
            from svgpathtools import parse_path
            import numpy as np
            path = parse_path(el.attrib['d'])
            points = [seg.point(t) for seg in path for t in np.linspace(0, 1, 100)]
            coords = [(pt.real, pt.imag) for pt in points]
            return Polygon(coords).buffer(0)  # clean polygon
    return None

def load_all_segments(segment_dir):
    segment_paths = sorted(Path(segment_dir).glob("*.svg"))
    segments = []
    for idx, svg_path in enumerate(segment_paths):
        polygon = parse_polygon_from_svg(svg_path)
        if polygon and polygon.is_valid:
            segments.append({
                "id": idx,
                "filename": svg_path.name,
                "polygon": polygon,
            })
    return segments

def build_hierarchy(segments):
    for seg in segments:
        seg["parent"] = 0  # default

    for i, outer in enumerate(segments):
        for j, inner in enumerate(segments):
            if i == j:
                continue
            if outer["polygon"].contains(inner["polygon"]):
                # Check if it's the closest parent (smallest containing polygon)
                if segments[j]["parent"] == 0 or outer["polygon"].area < segments[segments[j]["parent"]]["polygon"].area:
                    segments[j]["parent"] = i

    return segments

def load_gemini_responses(svg_name: str):
    response_path = RESPONSES_DIR / svg_name / "response.json"
    
    if not response_path.exists():
        print(f"❌ No response.json found at {response_path}")
        return []

    with open(response_path) as f:
        try:
            responses = json.load(f)
        except json.JSONDecodeError:
            print(f"❌ Invalid JSON format in {response_path}")
            return []

    result = []
    for entry in responses:
        result.append({
            "mask_path": entry.get("id"),           # filename of the PNG
            "description": entry.get("description") # descriptive text
        })

    return result

def export_hierarchy_json(segments, output_path, svg_name):
    # Load Gemini responses
    response_path = RESPONSES_DIR / svg_name / "response.json"
    metadata_path = RESPONSES_DIR / svg_name / "scene_metadata.json"

    # Load segmented element responses
    gemini_data = []
    if response_path.exists():
        with open(response_path) as f:
            try:
                gemini_data = json.load(f)
            except json.JSONDecodeError:
                print(f"❌ Invalid JSON format in {response_path}")

    # Load global style + description from metadata
    global_style = ""
    description = ""
    if metadata_path.exists():
        try:
            with open(metadata_path) as f:
                metadata = json.load(f)
                global_style = metadata.get("global_style", "")
                description = metadata.get("description", "")
        except Exception as e:
            print(f"⚠️ Failed to load scene metadata from {metadata_path}: {e}")

    # Index gemini data by numeric id extracted from 'id' (fallback if 'mask_path' is missing)
    gemini_index = {}
    for entry in gemini_data:
        filename = entry.get("mask_path") or entry.get("id")
        if not filename:
            continue
        idx = extract_index_from_filename(filename)
        gemini_index[idx] = {
            "mask_path": filename,
            "description": entry.get("description")
        }


    # Shift all IDs by +1 to leave 0 for full SVG
    for seg in segments:
        seg["id"] += 1
        seg["parent"] = seg["parent"] + 1 if seg["parent"] != 0 else 0  # remap parents

    result = []

    # ID 0 is the full image
    result.append({
        "id": 0,
        "filename": "Full " + svg_name,
        "parent": -1,
        "mask_path": None,
        "description": description,
    })

    # Add the segmented shapes
    for seg in segments:
        idx = extract_index_from_filename(seg["filename"])
        gemini = gemini_index.get(idx, {})
        result.append({
            "id": seg["id"],
            "filename": seg["filename"],
            "parent": seg["parent"],
            "mask_path": gemini.get("mask_path", None),
            "description": gemini.get("description", None),
        })

    final_output = {
        "global_style": global_style,
        "scene": result
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(final_output, f, indent=2)

def main():
    # Step 1: Prompt user to select folder
    folders = [f.name for f in SEGMENTS_DIR.iterdir() if f.is_dir()]
    if not folders:
        print("❌ No valid folders found.")
        exit()

    question = [
        inquirer.List('selected_folder', message="Select a folder:", choices=folders)
    ]
    answers = inquirer.prompt(question)
    if not answers:
        print("❌ No selection made.")
        exit()

    selected_folder = answers["selected_folder"]
    selected_folder_path = SEGMENTS_DIR / selected_folder

    # Step 2: Process each subfolder inside selected
    subfolders = [d for d in selected_folder_path.iterdir() if d.is_dir()]
    for svg_dir in tqdm(subfolders, desc="Processing folders", unit="folder"):
        print(f"\n📂 Processing: {svg_dir.name}")
        segments = load_all_segments(svg_dir)
        if not segments:
            print(f"⚠️ No valid SVGs in {svg_dir.name}")
            continue

        segments_with_parents = build_hierarchy(segments)
        svg_name = svg_dir.name 
        output_json_path = OUTPUT_ROOT / selected_folder / svg_dir.name / f"{svg_name}_hierarchy.json"
        export_hierarchy_json(segments_with_parents, output_json_path, svg_name)

        tqdm.write(f"✅ Saved: {output_json_path}")


if __name__ == "__main__":
    main()
