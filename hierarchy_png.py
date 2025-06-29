from pathlib import Path
import json
from tqdm import tqdm
import cv2
import numpy as np
import re
import inquirer
from matplotlib.colors import to_rgba
import xml.etree.ElementTree as ET
from svgpathtools import parse_path
from shapely.geometry import Polygon, Point
from shapely.affinity import scale


SEGMENTS_DIR = Path("segmented_svgs")
SEGMENTS_DIR_PLUS = Path("segmented_svgs_plus")
HIGHLIGHTED_DIR = Path("highlighted_pngs_no_overlay")
FALLBACK_WHITE_DIR = Path("white_pngs") 
RESPONSES_DIR = Path("gemini_responses")
OUTPUT_ROOT = Path("hierarchy_output_from_png")
OUTPUT_ROOT.mkdir(exist_ok=True)

def extract_index_from_filename(name: str) -> int:
    match = re.search(r'_element_(\d+)', name)
    if match:
        return int(match.group(1))
    match = re.search(r'Layer[_ ]?(\d+)', name)
    if match:
        return int(match.group(1))
    return -1

def sort_key(seg):
    name = seg["filename"]
    if "Layer" in name:
        return (0, extract_index_from_filename(name))
    return (1, extract_index_from_filename(name))


def parse_svg_color_to_rgba(color_str: str) -> str | None:
    if not color_str:
        return None

    color_str = color_str.strip().lower()

    # Handle rgb(r, g, b) manually
    if color_str.startswith("rgb("):
        try:
            nums = re.findall(r"[\d.]+", color_str)
            r, g, b = map(int, nums[:3])
            return f"rgba({r}, {g}, {b}, 1.0)"
        except Exception:
            return None

    try:
        rgba = to_rgba(color_str)  # handles hex, names, rgba()
        r, g, b, a = [round(v * 255) if i < 3 else round(v, 2) for i, v in enumerate(rgba)]
        return f"rgba({r}, {g}, {b}, {a})"
    except Exception:
        return None
    
def parse_svg_color_to_rgba1(color_str):
    try:
        rgba = to_rgba(color_str)  # Returns (r, g, b, a) as 0–1 floats
        r, g, b, a = [round(v * 255) if i < 3 else round(v, 2) for i, v in enumerate(rgba)]
        return f"rgba({r}, {g}, {b}, {a})"
    except Exception:
        return None

def get_combined_svg_color(segment_filename: str, selected_folder: str) -> str | None:
    """
    Tries to extract the fill color from the main SVGs first, then falls back to segmented_svgs_plus if needed.
    """
    main_svg_path = SEGMENTS_DIR / selected_folder / segment_filename
    if main_svg_path.exists():
        color = extract_svg_fill_color(main_svg_path)
        if color:
            return color

    plus_svg_path = SEGMENTS_DIR_PLUS / selected_folder / segment_filename
    if plus_svg_path.exists():
        color = extract_svg_fill_color(plus_svg_path)
        if color:
            return color

    return None


def extract_svg_fill_color(svg_path: Path) -> str | None:
    try:
        tree = ET.parse(svg_path)
        root = tree.getroot()

        # Build style map from <style> block
        style_map = {}
        styles = root.findall(".//{http://www.w3.org/2000/svg}style") or root.findall(".//style")
        for style_el in styles:
            if not style_el.text:
                continue
            for block in style_el.text.split("}"):
                if "{" not in block:
                    continue
                selector_block, properties = block.split("{", 1)
                props = dict(
                    pair.strip().split(":")
                    for pair in properties.strip().strip(";").split(";")
                    if ":" in pair
                )
                fill = props.get("fill")
                if not fill:
                    continue
                selectors = selector_block.split(",")
                for sel in selectors:
                    sel_name = sel.strip().lstrip(".").split(":")[0]  # remove pseudo-classes
                    style_map[sel_name] = fill.strip()

        best_fill = None
        max_score = -1

        for el in root.iter():
            tag = el.tag.lower()
            if not any(tag.endswith(s) for s in ["path", "polygon", "rect", "circle", "ellipse", "polyline"]):
                continue

            style = el.attrib.get("style", "")
            if "display:none" in style or el.attrib.get("display") == "none":
                continue

            fill = el.attrib.get("fill")
            source = "fill attribute"

            if not fill:
                for prop in style.split(";"):
                    if prop.strip().startswith("fill:"):
                        fill = prop.split(":", 1)[1].strip()
                        source = "style attribute"
                        break

            if not fill and "class" in el.attrib:
                for cls in el.attrib["class"].split():
                    if cls in style_map:
                        fill = style_map[cls]
                        source = f"class '{cls}'"
                        break

            if fill and fill not in ("none", "transparent"):
                # Estimate visual size using attribute complexity
                d_attr = el.attrib.get("d", "")
                pts_attr = el.attrib.get("points", "")
                score = len(d_attr) + len(pts_attr)

                for attr in ("width", "height", "r", "rx", "ry"):
                    if attr in el.attrib:
                        try:
                            score += float(el.attrib[attr])
                        except:
                            pass

                if score > max_score:
                    max_score = score
                    best_fill = fill
                    best_source = source

        if not best_fill:
            print(f"⚠️ No fill color found in {svg_path.name}")
        elif best_fill.startswith("url("):
            print(f"🎨 Gradient fill in {svg_path.name}: {best_fill}")
        else:
            print(f"🎯 Found fill in {svg_path.name} from {best_source}: {best_fill}")

        return parse_svg_color_to_rgba(best_fill) if best_fill else None

    except Exception as e:
        print(f"⚠️ Failed to parse color from {svg_path.name}: {e}")
        return None
    
def parse_polygon_from_png(png_path: Path):
    image = cv2.imread(str(png_path), cv2.IMREAD_UNCHANGED)
    if image is None:
        return None
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    # _, binary = cv2.threshold(gray, 1, 255, cv2.THRESH_BINARY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    largest = max(contours, key=cv2.contourArea)
    coords = [(int(pt[0][0]), int(pt[0][1])) for pt in largest]
    polygon = Polygon(coords).buffer(0)

    # real pixel area from mask
    pixel_area = np.count_nonzero(binary)

    return polygon, pixel_area

def load_png_segments(png_folder: Path, svg_segments_root: Path, selected_folder: str):
    segments = []
    group_name = png_folder.name
    fallback_dir = FALLBACK_WHITE_DIR / selected_folder / group_name

    for idx, png_path in enumerate(sorted(png_folder.glob("*.png"), key=lambda p: extract_index_from_filename(p.name))):
        if "full" in png_path.name.lower():
            continue

        # Read and threshold
        image = cv2.imread(str(png_path), cv2.IMREAD_UNCHANGED)
        if image is None:
            continue
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        _, binary = cv2.threshold(gray, 10, 255, cv2.THRESH_BINARY)

        white_ratio = np.count_nonzero(binary) / (binary.shape[0] * binary.shape[1])

        # If mostly black, try fallback PNG
        if white_ratio < 0.05:
            if "Layer" not in png_path.name and (fallback_dir / png_path.name).exists():
                # print(f"{png_path.name} is dark — using fallback.")
                png_path = fallback_dir / png_path.name
                image = cv2.imread(str(png_path), cv2.IMREAD_UNCHANGED)
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                _, binary = cv2.threshold(gray, 10, 255, cv2.THRESH_BINARY)
            

        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue

        largest = max(contours, key=cv2.contourArea)
        coords = [(int(pt[0][0]), int(pt[0][1])) for pt in largest]
        polygon = Polygon(coords).buffer(0)
        pixel_area = np.count_nonzero(binary)
        x, y, w, h = cv2.boundingRect(binary)

    
        segment_base = png_path.name.replace("_highlighted.png", ".svg")
        svg_path = svg_segments_root / segment_base
        color = extract_svg_fill_color(svg_path) if svg_path.exists() else None

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
        best_parent = None
        best_area = float("inf")
        cx, cy, cw, ch = child["bbox"]
        child_area = cw * ch

        for candidate in segments:
            if candidate["id"] == child["id"]:
                continue

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


def load_gemini_responses(group_name: str):
    response_path = RESPONSES_DIR / group_name / "response.json"
    
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

def export_hierarchy_json(segments, output_path: Path, group_name: str):
    response_path = RESPONSES_DIR / group_name / "response.json"
    metadata_path = RESPONSES_DIR / group_name / "scene_metadata.json"

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

    result = []

    # Add full image as root
    result.append({
        "id": 0,
        "filename": f"Full {group_name}",
        "parent": -1,
        "description": description,
    })

    # Sort segments
    sorted_segments = sorted(segments, key=sort_key)

    # Assign new IDs
    id_mapping = {seg["id"]: new_id for new_id, seg in enumerate(sorted_segments, start=1)}

    for seg in sorted_segments:
        old_id = seg["id"]
        seg["id"] = id_mapping[old_id]
        seg["parent"] = id_mapping.get(seg["parent"], 0) if seg["parent"] != 0 else 0

    # Append segments with color
    for seg in sorted_segments:
        key = seg["filename"]
        gemini = gemini_index.get(key, {})
        result.append({
            "id": seg["id"],
            "filename": seg["filename"],
            "parent": seg["parent"],
            "mask_path": gemini.get("mask_path"),
            "description": gemini.get("description"),
            "color": seg["color"], 
        })

    final_output = {
        "global_style": global_style,
        "scene": result
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(final_output, f, indent=2)


def main():
    # Prompt user to select a folder in highlighted_pngs
    folders = [f.name for f in HIGHLIGHTED_DIR.iterdir() if f.is_dir()]
    if not folders:
        print("❌ No folders found in highlighted_pngs/")
        return

    question = [
        inquirer.List("selected", message="Select a folder to process", choices=folders)
    ]
    answers = inquirer.prompt(question)
    if not answers:
        print("❌ No selection made.")
        return

    selected_folder = answers["selected"]
    selected_path = HIGHLIGHTED_DIR / selected_folder
    subfolders = [d for d in selected_path.iterdir() if d.is_dir()]

    for group in tqdm(subfolders, desc=f"Processing '{selected_folder}'"):
        if not group.is_dir():
            continue
        svg_dir = SEGMENTS_DIR / selected_folder / group.name
        if not svg_dir.exists():
            svg_dir = SEGMENTS_DIR / selected_folder / group.name

        plus_folder = SEGMENTS_DIR_PLUS / svg_dir.name
        segments = load_png_segments(group, svg_dir, selected_folder)

        if not segments:
            print(f"⚠️ No valid PNGs in {group.name}")
            continue
        segments_with_parents = build_hierarchy_bbox(segments)

        output_path = OUTPUT_ROOT / selected_folder / f"{group.name}_hierarchy.json"
        export_hierarchy_json(segments_with_parents, output_path, group.name)
        tqdm.write(f"✅ Saved: {output_path}")

if __name__ == "__main__":
    main()
