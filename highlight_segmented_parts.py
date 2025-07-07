#!/usr/bin/env python3

import os
import xml.etree.ElementTree as ET
from pathlib import Path
import inquirer
from tqdm import tqdm
from convert_svg_highlights_to_png import convert_svg_folder
from collections import defaultdict

OUTPUT_ROOT = Path("outputs")

def find_original_svg(originals_dir, svg_id):
    """
    Search the parent directory of originals_dir for the original SVG file.
    """
    originals_base_path = Path(originals_dir).parent / "inputs"
    for folder in originals_base_path.iterdir():
        if not folder.is_dir():
            continue
        candidate = folder / f"{svg_id}.svg"
        if candidate.exists():
            return candidate.resolve()
    # Check also directly inside originals_dir
    direct_candidate = Path(originals_dir) / f"{svg_id}.svg"
    if direct_candidate.exists():
        return direct_candidate.resolve()
    return None

def add_black_overlay(svg_root, highlighted_group, opacity=0.9):
    """
    Add a dark overlay to dim the whole SVG, and reveal only the highlighted segment.
    Simulates a spotlight effect using an SVG mask.
    """
    svg_ns = 'http://www.w3.org/2000/svg'

    # Create <defs> if not present
    defs = svg_root.find(f'{{{svg_ns}}}defs')
    if defs is None:
        defs = ET.Element(f'{{{svg_ns}}}defs')
        svg_root.insert(0, defs)

    # Create a unique ID for the mask
    mask_id = 'spotlight-mask'

    # Build mask: black overlay with transparent cutout
    mask = ET.Element(f'{{{svg_ns}}}mask', {'id': mask_id})
    # Fully opaque black background
    mask.append(ET.Element(f'{{{svg_ns}}}rect', {
        'x': '0', 'y': '0',
        'width': '100%', 'height': '100%',
        'fill': 'white', 'opacity': str(opacity)
    }))

    # Add the shape to the mask as a transparent area (black = reveal)
    for elem in highlighted_group:
        visible_shape = ET.Element(elem.tag, elem.attrib)
        visible_shape.attrib['fill'] = 'black'
        visible_shape.attrib.pop('stroke', None)
        mask.append(visible_shape)

    defs.append(mask)

    # Create full black rect and apply the mask
    overlay = ET.Element(f'{{{svg_ns}}}rect', {
        'x': '0', 'y': '0',
        'width': '100%', 'height': '100%',
        'fill': 'black',
        'mask': f'url(#{mask_id})'
    })

    svg_root.append(overlay)
    svg_root.append(highlighted_group)


def convert_full_svg_to_png(originals_dir, selected_folder, svg_id):
    """
    Converts full SVG to PNG and saves it as:
    outputs/<svg_id>/highlighted_pngs/<svg_id>-full.png
    """
    import cairosvg

    svg_path = Path(originals_dir) / selected_folder / f"{svg_id}.svg"
    output_path = Path("outputs") / svg_id / "highlighted_pngs" / f"{svg_id}-full.png"

    if not svg_path.exists():
        print(f"⚠️ Full SVG not found at: {svg_path}")
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        cairosvg.svg2png(
            url=str(svg_path),
            write_to=str(output_path),
            output_width=512,
            output_height=512
        )
        print(f"✅ Saved full PNG: {output_path}")
    except Exception as e:
        print(f"❌ Failed to convert full SVG to PNG for {svg_id}: {e}")


def highlight_segments(originals_dir, selected_folder, svg_id):
    base_output = OUTPUT_ROOT / svg_id
    highlighted_dir, white_dir, no_overlay_dir = prepare_output_dirs(base_output)
    
    segment_files = collect_segment_files(svg_id, base_output)
    if not segment_files:
        print(f"⚠️ No segment files found for: {svg_id}")
        return

    original_root = load_original_svg(originals_dir, selected_folder, svg_id)
    if original_root is None:
        return

    print(f"📦 Processing {svg_id} ({len(segment_files)} segments)")
    for segment_file in tqdm(segment_files, desc=f"🔧 {svg_id}", unit="segment"):
        process_segment_file(
            segment_file,
            original_root,
            svg_id,
            selected_folder,
            highlighted_dir,
            white_dir,
            no_overlay_dir
        )

def prepare_output_dirs(base_output):
    highlighted_dir = base_output / "highlighted_svgs"
    white_dir = base_output / "white_svgs"
    no_overlay_dir = base_output / "highlighted_svgs_no_overlay"
    for path in [highlighted_dir, white_dir, no_overlay_dir]:
        path.mkdir(parents=True, exist_ok=True)
    return highlighted_dir, white_dir, no_overlay_dir

def collect_segment_files(svg_id, base_output):
    plus_dir = Path("segmented_svgs_plus") / svg_id
    seg_dir = base_output / "segmented_svgs"

    segment_dirs = []
    if seg_dir.exists() and seg_dir.is_dir():
        segment_dirs.append(seg_dir)
        print(f"✅ Found in outputs/{svg_id}/segmented_svgs")
    if plus_dir.exists() and any(plus_dir.glob("*.svg")):
        segment_dirs.append(plus_dir)
        print(f"✅ Also found in segmented_svg_plus/{svg_id}")
    elif plus_dir.exists():
        print(f"⚠️ No SVGs in segmented_svg_plus/{svg_id}")

    segment_files = []
    for source in segment_dirs:
        found = list(source.glob("*.svg"))
        if found:
            print(f"   🔹 Found {len(found)} segments in {source}")
            segment_files.extend(found)
    return segment_files

def load_original_svg(originals_dir, selected_folder, svg_id):
    original_path = Path(originals_dir) / selected_folder / f"{svg_id}.svg"
    if not original_path.exists():
        print(f"⚠️ Original SVG not found: {original_path}")
        return None
    try:
        return ET.parse(original_path).getroot()
    except ET.ParseError as e:
        print(f"⚠️ Failed to parse original SVG {svg_id}: {e}")
        return None

def extract_visible_elements(segment_root):
    """
    Extract visible elements from a segment root, handling both regular and plus folder structures.
    Returns a list of visible elements.
    """
    visible_elements = []
    
    # Check if this is a plus folder structure (multiple groups with display:none)
    has_plus_structure = False
    for child in segment_root:
        if child.tag.endswith('defs'):
            continue
        if child.tag.endswith('g') and 'style' in child.attrib:
            style = child.attrib['style']
            if 'display:none' in style:
                has_plus_structure = True
                break
    
    if has_plus_structure:
        # Plus folder structure: find the group that should be visible
        for child in segment_root:
            if child.tag.endswith('defs'):
                continue
            if child.tag.endswith('g'):
                style = child.attrib.get('style', '')
                # Look for groups that are NOT display:none
                if 'display:none' not in style:
                    # This is the visible group, extract its children
                    for grandchild in child:
                        if grandchild.tag.endswith('defs'):
                            continue
                        visible_elements.append(grandchild)
                    break
    else:
        # Regular structure: all direct children are visible
        for child in list(segment_root):
            if child.tag.endswith('defs'):
                continue
            visible_elements.append(child)
    
    return visible_elements

def process_segment_file(segment_file, original_root, svg_id, selected_folder, highlighted_dir, white_dir, no_overlay_dir):
    try:
        segment_tree = ET.parse(segment_file)
        segment_root = segment_tree.getroot()
    except ET.ParseError as e:
        print(f"⚠️ Error parsing {segment_file.name}: {e}")
        return

    # Create overlay version
    combined_svg = create_combined_svg_with_overlay(original_root, segment_root)
    highlighted_path = highlighted_dir / f"{segment_file.stem}_highlighted.svg"
    ET.ElementTree(combined_svg).write(highlighted_path)

    # Create no-overlay version
    create_combined_svg_with_black_background(segment_root, original_root, svg_id, selected_folder, segment_file.stem)

    # Create white mask version
    white_svg = create_white_mask_svg(original_root, segment_root)
    white_path = white_dir / f"{segment_file.stem}_highlighted.svg"
    ET.ElementTree(white_svg).write(white_path)

def create_combined_svg_with_overlay(original_root, segment_root):
    svg_ns = 'http://www.w3.org/2000/svg'
    combined_svg = ET.Element(original_root.tag, original_root.attrib)
    for defs in original_root.findall(f'.//{{{svg_ns}}}defs'):
        combined_svg.append(defs)
    for child in list(original_root):
        if not child.tag.endswith('defs'):
            combined_svg.append(child)

    highlighted_group = ET.Element(f'{{{svg_ns}}}g', {'id': 'highlighted-segment'})
    visible_elements = extract_visible_elements(segment_root)
    
    for elem in visible_elements:
        outer = ET.Element(elem.tag, elem.attrib.copy())
        style = elem.attrib.get('style', '')
        clean_style = ';'.join(kv for kv in style.split(';') if not kv.strip().startswith('stroke')).strip(';')
        elem.attrib['style'] = clean_style
        highlighted_group.append(outer)
        highlighted_group.append(elem)

    add_black_overlay(combined_svg, highlighted_group)
    return combined_svg

def create_combined_svg_with_black_background(
    segment_root: ET.Element,
    original_root: ET.Element,
    svg_id: str,
    selected_folder: str,
    segment_file_stem: str
):
    """
    Save a highlighted segment with solid black background (no transparency or overlay).
    Saved under: outputs/<svg_id>/highlighted_svgs_no_overlay/
    """
    output_dir = OUTPUT_ROOT / svg_id / "highlighted_svgs_no_overlay"
    output_dir.mkdir(parents=True, exist_ok=True)

    svg_ns = 'http://www.w3.org/2000/svg'
    new_svg = ET.Element(original_root.tag, original_root.attrib)

    for defs in original_root.findall(f'.//{{{svg_ns}}}defs'):
        new_svg.append(defs)

    black_rect = ET.Element(f'{{{svg_ns}}}rect', {
        'x': '0',
        'y': '0',
        'width': '100%',
        'height': '100%',
        'fill': 'black'
    })
    new_svg.append(black_rect)

    highlight_group = ET.Element(f'{{{svg_ns}}}g', {'id': 'highlighted-segment'})
    visible_elements = extract_visible_elements(segment_root)
    
    for elem in visible_elements:
        outer = ET.Element(elem.tag, elem.attrib.copy())

        original_style = elem.attrib.get('style', '')
        style_parts = [kv for kv in original_style.split(';') if not kv.strip().startswith('stroke')]
        elem.attrib['style'] = ';'.join(style_parts)

        highlight_group.append(outer)
        highlight_group.append(elem)

    new_svg.append(highlight_group)

    output_path = output_dir / f"{segment_file_stem}_highlighted.svg"
    try:
        ET.ElementTree(new_svg).write(output_path)
    except Exception as e:
        tqdm.write(f"⚠️ Failed to write black overlay version: {output_path}: {e}")

def create_white_mask_svg(original_root, segment_root):
    svg_ns = 'http://www.w3.org/2000/svg'
    white_svg = ET.Element(original_root.tag, original_root.attrib)
    bg_rect = ET.Element(f'{{{svg_ns}}}rect', {
        'x': '0', 'y': '0', 'width': '100%', 'height': '100%', 'fill': 'black'
    })
    white_svg.append(bg_rect)

    white_group = ET.Element(f'{{{svg_ns}}}g', {
        'id': 'white-shapes',
        'style': 'display:inline;opacity:1'
    })
    
    visible_elements = extract_visible_elements(segment_root)
    
    # Create white shapes from visible elements
    for elem in visible_elements:
        white_shape = ET.Element(elem.tag, elem.attrib.copy())
        white_shape.attrib.pop('stroke', None)
        white_shape.attrib['fill'] = 'white'
        white_shape.attrib['style'] = 'fill:white;display:inline;opacity:1'
        white_group.append(white_shape)

    white_svg.append(white_group)
    return white_svg

def main():
    originals_root = Path("inputs")

    # Step 1: Select a folder from inputs/
    available_folders = [f.name for f in originals_root.iterdir() if f.is_dir()]
    if not available_folders:
        print("❌ No folders found in 'inputs/'")
        return

    answers = inquirer.prompt([
        inquirer.List(
            'selected_input',
            message="Select the folder from inputs/ to process:",
            choices=available_folders
        )
    ])
    if not answers:
        print("❌ No folder selected. Exiting.")
        return

    selected_folder = answers["selected_input"]
    selected_input_path = originals_root / selected_folder
    svg_files = list(selected_input_path.glob("*.svg"))

    if not svg_files:
        print(f"❌ No .svg files found in: inputs/{selected_folder}")
        return

    print(f"\n📁 Selected input folder: {selected_folder}")
    print(f"🔍 Found {len(svg_files)} SVG files to process.")

    # Process each SVG file in the selected folder
    for svg_path in svg_files:
        svg_id = svg_path.stem
        print(f"\n=== 🧩 Processing '{svg_id}' ===")

        # Check if segmented folders exist
        segment_sources = []

        seg_dir = OUTPUT_ROOT / svg_id / "segmented_svgs"
        if seg_dir.exists() and any(seg_dir.iterdir()):
            segment_sources.append(seg_dir)

        plus_dir = Path("segmented_svgs_plus") / svg_id
        if plus_dir.exists() and any(plus_dir.iterdir()):
            segment_sources.append(plus_dir)
            print(f"✅ Found: segmented_svgs_plus/{svg_id}")

        if not segment_sources:
            print(f"⚠️ No segmented sources found for '{svg_id}'. Skipping.")
            continue

        # Run full pipeline for each svg_id
        highlight_segments(
            originals_dir="inputs",
            selected_folder=selected_folder,
            svg_id=svg_id                     
        )

        base_output = OUTPUT_ROOT / svg_id

        convert_svg_folder(base_output / "highlighted_svgs", base_output / "highlighted_pngs")
        convert_svg_folder(base_output / "highlighted_svgs_no_overlay", base_output / "highlighted_pngs_no_overlay")
        convert_svg_folder(base_output / "white_svgs", base_output / "white_pngs")

        convert_full_svg_to_png(
            originals_dir="inputs",
            selected_folder=selected_folder,
            svg_id=svg_id
        )

if __name__ == "__main__":
    main()
