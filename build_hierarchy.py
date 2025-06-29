from pathlib import Path
from shapely.geometry import Polygon
from shapely.ops import unary_union
import xml.etree.ElementTree as ET
import re
import json
import inquirer
from tqdm import tqdm
from matplotlib.colors import to_rgba
import numpy as np
from svgpathtools import parse_path
from shapely.geometry import Polygon, Point
from shapely.affinity import scale

from typing import List, Dict

SEGMENTS_DIR = Path("segmented_svgs")
SEGMENTS_PLUS_DIR = Path("segmented_svgs_plus")
RESPONSES_DIR = Path("gemini_responses")
OUTPUT_ROOT = Path("hierarchy_output")
OUTPUT_ROOT.mkdir(exist_ok=True)

def extract_index_from_filename(name: str) -> int:
    # Try "_element_XX" pattern
    match = re.search(r'_element_(\d+)', name)
    if match:
        return int(match.group(1))
    # Try "Layer XX" pattern
    match = re.search(r'Layer[_ ]?(\d+)', name)
    if match:
        return int(match.group(1))
    return -1

def sort_key(seg):
    name = seg["filename"]
    if "Layer" in name:
        return (0, extract_index_from_filename(name))
    return (1, extract_index_from_filename(name))

def parse_svg_color_to_rgba(color_str):
    try:
        rgba = to_rgba(color_str)  # Returns (r, g, b, a) as 0–1 floats
        r, g, b, a = [round(v * 255) if i < 3 else round(v, 2) for i, v in enumerate(rgba)]
        return f"rgba({r}, {g}, {b}, {a})"
    except Exception:
        return None



def parse_polygon_from_svg(svg_path):
    tree = ET.parse(svg_path)
    root = tree.getroot()

    # Parse <style> blocks (handles both <style> and <svg:style>)
    style_map = {}
    styles = root.findall(".//{http://www.w3.org/2000/svg}style") or root.findall(".//style")
    for style_el in styles:
        style_text = style_el.text
        if style_text:
            for line in style_text.split("}"):
                if "{" in line:
                    selector, block = line.split("{", 1)
                    props = dict(
                        pair.split(":") for pair in block.strip().strip(";").split(";") if ":" in pair
                    )
                    fill = props.get("fill")
                    if fill:
                        # Support multiple class selectors per rule
                        selectors = selector.strip().split(",")
                        for sel in selectors:
                            sel = sel.strip().lstrip(".").split(":")[0]
                            style_map[sel] = fill.strip()

    for el in root.iter():
        tag = el.tag.lower()
        raw_color = el.attrib.get("fill")

        if not raw_color:
            class_attr = el.attrib.get("class")
            if class_attr:
                class_names = class_attr.strip().split()
                for cls in class_names:
                    if cls in style_map:
                        raw_color = style_map[cls]
                        break

        color = parse_svg_color_to_rgba(raw_color) if raw_color else None

        # Create polygon shape
        if 'd' in el.attrib:  # path
            path = parse_path(el.attrib['d'])
            points = [seg.point(t) for seg in path for t in np.linspace(0, 1, 100)]
            coords = [(pt.real, pt.imag) for pt in points]
            return Polygon(coords).buffer(0), color

        elif tag.endswith("rect"):
            x = float(el.attrib.get("x", 0))
            y = float(el.attrib.get("y", 0))
            w = float(el.attrib.get("width", 0))
            h = float(el.attrib.get("height", 0))
            return Polygon([(x, y), (x + w, y), (x + w, y + h), (x, y + h)]), color

        elif tag.endswith("circle"):
            cx = float(el.attrib.get("cx", 0))
            cy = float(el.attrib.get("cy", 0))
            r = float(el.attrib.get("r", 0))
            return Point(cx, cy).buffer(r), color

        elif tag.endswith("ellipse"):
            cx = float(el.attrib.get("cx", 0))
            cy = float(el.attrib.get("cy", 0))
            rx = float(el.attrib.get("rx", 0))
            ry = float(el.attrib.get("ry", 0))
            return scale(Point(cx, cy).buffer(1), rx, ry), color

        elif tag.endswith("polygon") or tag.endswith("polyline"):
            points_str = el.attrib.get("points", "")
            try:
                points = [tuple(map(float, p.split(","))) for p in points_str.strip().split()]
                return Polygon(points).buffer(0), color
            except:
                continue

    return None, None

def load_all_segments(*segment_dirs):
    segments = []
    idx = 0

    for segment_dir in segment_dirs:
        segment_paths = sorted(
            Path(segment_dir).glob("*.svg"),
            key=lambda p: extract_index_from_filename(p.name)
        )

        for svg_path in segment_paths:
            polygon, color = parse_polygon_from_svg(svg_path)
            if polygon and polygon.is_valid:
                segments.append({
                    "id": idx,
                    "filename": svg_path.name,
                    "polygon": polygon,
                    "color": color,
                })
                idx += 1

    return segments

def build_hierarchy(segments):
    """
    Assigns the most suitable parent for each segment based on geometric containment,
    considering both layers and elements as potential parents.
    """
    for seg in segments:
        seg["parent"] = -1  # Initialize all as root

    for inner in segments:
        best_parent = None
        best_area = float("inf")

        for outer in segments:
            if outer["id"] == inner["id"]:
                continue
            # Check if outer fully contains inner
            if outer["polygon"].contains(inner["polygon"]):
                area = outer["polygon"].area
                if area < best_area:
                    best_area = area
                    best_parent = outer["id"]

        if best_parent is not None:
            inner["parent"] = best_parent

    return segments


def build_hierarchy3(segments):
    """
    Assigns each non-layer segment to the smallest containing parent.
    If none contains it, uses intersects. Falls back to root if needed.
    """

    # Initialize all to root
    for s in segments:
        s["parent"] = 0

    for child in segments:
        child_poly = child["polygon"]
        child_id = child["id"]

        best_parent = None
        smallest_area = float("inf")

        for candidate in segments:
            if candidate["id"] == child_id:
                continue  # Don't compare to self

            candidate_poly = candidate["polygon"]
            candidate_area = candidate_poly.area

            # Must be strictly larger
            if candidate_area <= child_poly.area:
                continue

            # Prefer contains (stricter), fallback to intersects
            if candidate_poly.contains(child_poly) or candidate_poly.intersects(child_poly):
                if candidate_area < smallest_area:
                    best_parent = candidate["id"]
                    smallest_area = candidate_area

        # Assign the best match (or 0 = root)
        child["parent"] = best_parent if best_parent is not None else 0

    return segments

def build_hierarchy2(segments):
    # Pre-categorize layer segments
    layer_segments = [s for s in segments if "Layer" in s["filename"]]
    other_segments = [s for s in segments if "Layer" not in s["filename"]]

    # Start fresh
    for s in segments:
        s["parent"] = 0

    # Build hierarchy for non-layer elements
    for inner in other_segments:
        best_parent = None
        best_area = float('inf')

        for outer in segments:
            if outer["id"] == inner["id"]:
                continue
            if outer["polygon"].contains(inner["polygon"]):
                if outer["polygon"].area < best_area:
                    best_area = outer["polygon"].area
                    best_parent = outer["id"]

        if best_parent is not None:
            inner["parent"] = best_parent
        else:
            # Fallback: assign to first Layer if any, otherwise root
            inner["parent"] = layer_segments[0]["id"] if layer_segments else 0

    return segments


def build_hierarchy1(segments):
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
    # gemini_index = {}
    # for entry in gemini_data:
    #     filename = entry.get("mask_path") or entry.get("id")
    #     if not filename:
    #         continue
    #     idx = extract_index_from_filename(filename)
    #     gemini_index[idx] = {
    #         "mask_path": filename,
    #         "description": entry.get("description")
    #     }

    # Index gemini data by full filename
    gemini_index = {}
    for entry in gemini_data:
        raw_filename = entry.get("mask_path") or entry.get("id")
        if raw_filename:
            key = Path(raw_filename).stem.replace("_highlighted", "")  # e.g. "Layer 96"
            gemini_index[key] = {
                "mask_path": raw_filename,
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
        "description": description,
    })

    sorted_segments = sorted(segments, key=sort_key)

    # Reassign IDs based on new order (starting from 1)
    id_mapping = {}
    for new_id, seg in enumerate(sorted_segments, start=1):
        old_id = seg["id"]
        id_mapping[old_id] = new_id
        seg["id"] = new_id

    # Update parent IDs to reflect new mapping
    for seg in sorted_segments:
        if seg["parent"] in id_mapping:
            seg["parent"] = id_mapping[seg["parent"]]
        elif seg["parent"] == 0:
            seg["parent"] = 0  # root
        else:
            seg["parent"] = -1  # orphan fallback

    # segmented shapes
    for seg in sorted_segments:
        key = Path(seg["filename"]).stem
        gemini = gemini_index.get(key, {})


        # idx = extract_index_from_filename(seg["filename"])
        # gemini = gemini_index.get(idx, {})
        result.append({
            "id": seg["id"],
            "filename": seg["filename"],
            "parent": seg["parent"],
            "mask_path": gemini.get("mask_path", None),
            "description": gemini.get("description", None),
            "color": seg["color"]
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

        plus_folder = SEGMENTS_PLUS_DIR / svg_dir.name
        if plus_folder.exists() and plus_folder.is_dir():
            print(f"➕ Also loading segments from: {plus_folder}")
            segments = load_all_segments(svg_dir, plus_folder)
        else:
            segments = load_all_segments(svg_dir)

        if not segments:
            print(f"⚠️ No valid SVGs in {svg_dir.name}")
            continue

        segments_with_parents = build_hierarchy(segments)

        svg_name = svg_dir.name 
        output_json_path = OUTPUT_ROOT / selected_folder / f"{svg_name}_hierarchy.json"
        export_hierarchy_json(segments_with_parents, output_json_path, svg_name)

        tqdm.write(f"✅ Saved: {output_json_path}")

if __name__ == "__main__":
    main()
