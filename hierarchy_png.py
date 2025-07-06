from pathlib import Path
import json
from tqdm import tqdm
import cv2
import numpy as np
import re
import inquirer
import xml.etree.ElementTree as ET
from shapely.geometry import Polygon, Point
from collections import deque

SEGMENTS_DIR = Path("segmented_svgs")
SEGMENTS_DIR_PLUS = Path("segmented_svgs_plus")
HIGHLIGHTED_DIR = Path("highlighted_pngs_no_overlay")
FALLBACK_WHITE_DIR = Path("white_pngs") 
RESPONSES_DIR = Path("gemini_responses")
OUTPUT_ROOT = Path("hierarchy_output")
OUTPUT_ROOT.mkdir(exist_ok=True)
SVG_NS = "http://www.w3.org/2000/svg"
NSMAP = {"svg": SVG_NS}

def extract_index_from_filename(name: str) -> int:
    patterns = [
        r'_element_(\d+)',
        r'Layer[_ ]?(\d+)',
        r'Item[_ ]?(\d+)',
    ]
    for pat in patterns:
        match = re.search(pat, name)
        if match:
            return int(match.group(1))
    return -1

def sort_key(seg):
    name = seg["filename"]
    if "Layer" in name:
        return (0, extract_index_from_filename(name))
    elif "Item" in name:
        return (1, extract_index_from_filename(name))
    else:
        return (2, extract_index_from_filename(name))

def parse_svg_style_block(css_text: str) -> dict:
    import re
    style_map = {}
    for rule in css_text.split("}"):
        if "{" not in rule:
            continue
        selector, props = rule.split("{", 1)
        selector = selector.strip()
        props = props.strip()
        for class_name in selector.split(","):
            class_name = class_name.strip().lstrip(".")
            fill_match = re.search(r"fill\s*:\s*([^;]+)", props)
            if fill_match:
                style_map[class_name] = fill_match.group(1).strip()
    return style_map

def parse_svg_color_to_rgba(color: str) -> str | None:
    import re
    color = color.strip().lower()
    if color.startswith("#"):
        hex = color[1:]
        if len(hex) == 3:
            r, g, b = [int(c*2, 16) for c in hex]
        elif len(hex) == 6:
            r, g, b = [int(hex[i:i+2], 16) for i in (0, 2, 4)]
        else:
            return None
        return f"rgba({r}, {g}, {b}, 1.0)"
    elif color.startswith("rgb"):
        return color.replace("rgb", "rgba").replace(")", ", 1.0)")
    elif color == "none":
        return None
    return None  # fallback

def extract_svg_fill_color(svg_path: Path) -> str | None:
    try:
        tree = ET.parse(svg_path)
        root = tree.getroot()

        # Load CSS styles from <style> and <svg:style>
        style_map = {}
        for style_el in (
            root.findall(".//{http://www.w3.org/2000/svg}style") +
            root.findall(".//svg:style", namespaces=NSMAP)
        ):
            if style_el.text:
                style_map.update(parse_svg_style_block(style_el.text))

        def is_display_none(style: str | None) -> bool:
            return style and "display:none" in style.replace(" ", "")

        def strip_ns(tag: str) -> str:
            return tag.split("}")[-1]

        def resolve_gradient_color(gradient_id: str) -> str | None:
            grad = root.find(f".//*[@id='{gradient_id}']")
            if grad is not None:
                stops = grad.findall(f"{{{SVG_NS}}}stop") or grad.findall("stop")
                if stops:
                    style = stops[-1].attrib.get("style", "")
                    for prop in style.split(";"):
                        if "stop-color" in prop:
                            color = prop.split(":")[1].strip()
                            return parse_svg_color_to_rgba(color)
            return None

        best_fill = None
        max_score = -1

        def walk(node, visible=True):
            nonlocal best_fill, max_score
            tag = strip_ns(node.tag).lower()
            style = node.attrib.get("style", "")
            display_none = is_display_none(style) or node.attrib.get("display") == "none"
            current_visible = visible and not display_none

            if current_visible and tag in {"path", "polygon", "rect", "circle", "ellipse", "polyline"}:
                fill = node.attrib.get("fill")

                if not fill:
                    for prop in style.split(";"):
                        if prop.strip().startswith("fill:"):
                            fill = prop.split(":", 1)[1].strip()
                            break

                if not fill:
                    class_name = node.attrib.get("class", "").strip()
                    if class_name in style_map:
                        fill = style_map[class_name]

                if fill and fill not in ("none", "transparent"):
                    score = len(node.attrib.get("d", "")) + len(node.attrib.get("points", ""))
                    for attr in ("width", "height", "r", "rx", "ry"):
                        try:
                            score += float(node.attrib.get(attr, 0))
                        except:
                            pass

                    if score > max_score:
                        best_fill = fill
                        max_score = score

            for child in list(node):
                walk(child, current_visible)

        walk(root)

        if best_fill and best_fill.startswith("url(#"):
            gradient_id = best_fill[5:-1]
            return resolve_gradient_color(gradient_id)

        return parse_svg_color_to_rgba(best_fill) if best_fill else None

    except Exception as e:
        print(f"⚠️ Failed to parse {svg_path.name}: {e}")
        return None

def load_png_segments(png_folder: Path, svg_segments_root: Path, svg_segments_root_plus: Path, selected_folder: str):
    segments = []

    full_name = png_folder.parent.name 
    # Add full SVG color segment
    full_svg_path = Path("inputs") / selected_folder / f"{full_name}.svg"
    full_color = extract_svg_fill_color(full_svg_path) if full_svg_path and full_svg_path.exists() else None
    segments.append({
        "id": 0,
        "filename": f"Full {full_name}",
        "polygon": None,
        "pixel_area": None,
        "bbox": None,
        "color": full_color,
        "parent": -1  # root
    })

    fallback_dir = Path("outputs") / full_name / FALLBACK_WHITE_DIR
    # Process individual PNG segments
    for idx, png_path in enumerate(sorted(png_folder.glob("*.png"), key=lambda p: extract_index_from_filename(p.name)), start=1):
        if "full" in png_path.name.lower():
            continue
        image = cv2.imread(str(png_path), cv2.IMREAD_UNCHANGED)
        if image is None:
            continue
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 10, 255, cv2.THRESH_BINARY)

        white_ratio = np.count_nonzero(binary) / (binary.shape[0] * binary.shape[1])
        # if white_ratio < 0.05 and not any(k in png_path.name for k in ["Layer", "Item"]):
        is_named_element = any(k in png_path.name for k in ["Layer", "Item"])
        
        # Check for small visible area, fallback only if name isn't meaningful
        fallback_png = fallback_dir / png_path.name
        use_fallback = white_ratio < 0.05 and not is_named_element and fallback_png.exists()
        if use_fallback:
            png_path = fallback_png
            image = cv2.imread(str(png_path), cv2.IMREAD_UNCHANGED)
            if image is None:
                print(f"❌ Could not load fallback image: {fallback_png}")
                continue
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            _, binary = cv2.threshold(gray, 10, 255, cv2.THRESH_BINARY)

        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue

        largest = max(contours, key=cv2.contourArea)
        coords = [(int(pt[0][0]), int(pt[0][1])) for pt in largest]

        # Ensure there are at least 3 distinct points
        if len(coords) < 3:
            print(f"⚠️ Skipping {png_path.name} — not enough points to form a polygon.")
            continue

        # Ensure it's closed
        if coords[0] != coords[-1]:
            coords.append(coords[0])

        try:
            polygon = Polygon(coords).buffer(0)
        except Exception as e:
            print(f"❌ Failed to create polygon for {png_path.name}: {e}")
            continue

        pixel_area = np.count_nonzero(binary)
        x, y, w, h = cv2.boundingRect(binary)

        base_name = png_path.name.replace("_highlighted.png", "") if "_highlighted.png" in png_path.name else png_path.stem
        segment_svg_filename = f"{base_name}.svg"

        primary_svg_path = svg_segments_root / segment_svg_filename
        plus_svg_path = svg_segments_root_plus / segment_svg_filename

        svg_path = primary_svg_path if primary_svg_path.exists() else (plus_svg_path if plus_svg_path.exists() else None)
        color = extract_svg_fill_color(svg_path) if svg_path and svg_path.exists() else None

        segments.append({
            "id": idx,
            "filename": png_path.name,
            "polygon": polygon,
            "pixel_area": pixel_area,
            "bbox": (x, y, w, h),
            "color": color,
        })

    return segments

def build_hierarchy_bbox(segments, margin=5):
    """
    For each segment, assign the smallest parent segment whose bounding box contains it.
    """
    for seg in segments:
        seg["parent"] = 0  # default to root if no parent found

    for child in segments:
        if child.get("bbox") is None:
            continue # Skip full SVG or invalid segment

        best_parent = None
        best_area = float("inf")
        cx, cy, cw, ch = child["bbox"]
        child_area = cw * ch

        for candidate in segments:
            if candidate["id"] == child["id"]:
                continue
            if candidate.get("bbox") is None:
                continue  # Skip invalid candidate

            px, py, pw, ph = candidate["bbox"]
            parent_area = pw * ph

            # Must be strictly larger and contain the child
            if parent_area <= child_area:
                continue

            if (cx >= px - margin and cy >= py - margin and
                cx + cw <= px + pw + margin and
                cy + ch <= py + ph + margin):
                if parent_area < best_area:
                    best_area = parent_area
                    best_parent = candidate["id"]

        if best_parent is not None:
            child["parent"] = best_parent

    return segments

def export_hierarchy_json(segments, output_path: Path, group_name: str):
    response_path = Path("outputs") / group_name / RESPONSES_DIR  / "response.json"
    metadata_path = Path("outputs") / group_name / RESPONSES_DIR  / "scene_metadata.json"

    # Load Gemini response data
    gemini_data = []
    if response_path.exists():
        with open(response_path) as f:
            try:
                gemini_data = json.load(f)
            except json.JSONDecodeError:
                print(f"❌ Invalid JSON in {response_path}")

    # Load global style & description
    global_style = ""
    description = ""
    if metadata_path.exists():
        try:
            with open(metadata_path) as f:
                metadata = json.load(f)
                global_style = metadata.get("global_style", "")
                description = metadata.get("description", "")
        except:
            pass

    # Build index from Gemini response using full filename
    gemini_index = {}
    for entry in gemini_data:
        raw_filename = entry.get("mask_path") or entry.get("id")
        if raw_filename:
            gemini_index[raw_filename] = {
                "mask_path": raw_filename,
                "description": entry.get("description")
            }


    all_items = []

    for seg in segments:
        key = seg["filename"]
        gemini = gemini_index.get(key, {})
        entry = {
            "id": seg["id"],
            "filename": seg["filename"],
            "parent": seg["parent"],
            "mask_path": gemini.get("mask_path"),
            "description": gemini.get("description"),
            "color": seg.get("color"),
        }
        if "full" in key.lower():
            entry.pop("mask_path", None)
            entry["parent"] = -1  # force root
            full_id = seg["id"]
        all_items.append(entry)

    id_to_item = {item["id"]: item for item in all_items}
    parent_to_children = {}
    for item in all_items:
        parent_to_children.setdefault(item["parent"], []).append(item)

    # ✅ Find the true root (parent == -1)
    root_items = parent_to_children.get(-1, [])
    if not root_items:
        print("❌ No root segment found (parent == -1)")
        return

    # Start BFS from root segment(s)
    new_scene = []
    queue = deque()
    old_to_new_ids = {}
    current_id = 0

    for root in root_items:
        queue.append(root["id"])

        while queue:
            old_id = queue.popleft()
            item = id_to_item[old_id]

            new_id = current_id
            old_to_new_ids[old_id] = new_id
            current_id += 1

            is_root = item["parent"] == -1
            entry = {
                "id": new_id,
                "filename": item["filename"],
                "parent": old_to_new_ids.get(item["parent"], -1),
                "description": description if is_root else item.get("description"),
                "color": item.get("color")
            }

            if not is_root:
                entry["mask_path"] = item.get("mask_path")

            new_scene.append(entry)

            for child in sorted(parent_to_children.get(old_id, []), key=lambda x: x["filename"]):
                queue.append(child["id"])


    final_output = {
        "global_style": global_style,
        "scene": new_scene
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(final_output, f, indent=2)

def main():
    inputs_dir = Path("inputs")
    outputs_dir = Path("outputs")

    # Step 1: Select a folder from inputs/
    folders = [f.name for f in inputs_dir.iterdir() if f.is_dir()]
    if not folders:
        print("❌ No folders found in inputs/")
        return

    answers = inquirer.prompt([
        inquirer.List("selected", message="Select an inputs/<folder> to process", choices=folders)
    ])
    if not answers:
        print("❌ No selection made.")
        return

    selected_folder = answers["selected"]
    svg_files = list((inputs_dir / selected_folder).glob("*.svg"))
    if not svg_files:
        print(f"❌ No .svg files found in inputs/{selected_folder}")
        return

    print(f"📁 Selected folder: {selected_folder} — Found {len(svg_files)} SVG files.")

    for svg_file in tqdm(svg_files, desc="Processing SVGs"):
        svg_id = svg_file.stem
        print(f"\n🧩 Processing: {svg_id}")

        base_output = outputs_dir / svg_id
        png_dir = base_output / HIGHLIGHTED_DIR
        regular_svg_dir = base_output / "segmented_svgs"
        plus_svg_dir = SEGMENTS_DIR_PLUS / svg_id

        if not png_dir.exists():
            print(f"⚠️ Skipping {svg_id}: highlighted_pngs_no_overlay not found.")
            continue

        segments = load_png_segments(png_dir, regular_svg_dir, plus_svg_dir, selected_folder)

        if not segments:
            print(f"⚠️ No valid segments found for {svg_id}")
            continue
        
        print(f"segments length:  {len(segments)}")
        segments_with_parents = build_hierarchy_bbox(segments)
        output_path = base_output / "hierarchy_output" / f"{svg_id}_hierarchy.json"
        export_hierarchy_json(segments_with_parents, output_path, svg_id)
        tqdm.write(f"✅ Saved: {output_path}")

if __name__ == "__main__":
    main()
