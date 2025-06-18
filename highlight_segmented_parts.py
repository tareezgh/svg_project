#!/usr/bin/env python3

import os
import xml.etree.ElementTree as ET
from pathlib import Path
import inquirer
from tqdm import tqdm
from convert_svg_highlights_to_png import convert_svg_folder

def apply_transparency(svg_element, opacity):
    """
    Apply opacity to all shape elements within the given SVG element.
    """
    for elem in svg_element.iter():
        if 'style' in elem.attrib:
            style = elem.attrib['style']
            if 'opacity' in style:
                style = ';'.join(
                    f"{k.strip()}:{v.strip()}" if k.strip() != 'opacity' else f"opacity:{opacity}"
                    for k, v in (item.split(':') for item in style.split(';') if item)
                )
            else:
                style += f";opacity:{opacity}"
            elem.attrib['style'] = style
        else:
            elem.attrib['style'] = f"opacity:{opacity}"

def find_original_svg(originals_dir, svg_id):
    """
    Search the parent directory of originals_dir for the original SVG file.
    """
    originals_base_path = Path(originals_dir).parent
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


def highlight_segments(originals_dir, segments_dir, output_dir, selected_folder):
    selected_path = Path(segments_dir) / selected_folder
    output_folder = Path(output_dir) / selected_folder

    for svg_subdir in selected_path.iterdir():
        if not svg_subdir.is_dir():
            continue

        svg_id = svg_subdir.name
        original_path = find_original_svg(originals_dir, svg_id)
        if not original_path:
            print(f"⚠️ Original SVG not found for: {svg_id}")
            continue

        try:
            original_tree = ET.parse(original_path)
            original_root = original_tree.getroot()
        except ET.ParseError as e:
            print(f"⚠️ Error parsing {original_path.name}: {e}")
            continue

        svg_output_dir = output_folder / svg_id
        svg_output_dir.mkdir(parents=True, exist_ok=True)
        
        segment_files = list(svg_subdir.glob("*.svg"))
        if not segment_files:
            print(f"⚠️ No segments found for: {svg_id}")
            continue

        print(f"📦 Processing {svg_id} ({len(segment_files)} segments)")
        for segment_file in tqdm(segment_files, desc=f"🔧 {svg_id}", unit="segment"):
            try:
                segment_tree = ET.parse(segment_file)
                segment_root = segment_tree.getroot()
            except ET.ParseError as e:
                print(f"⚠️ Error parsing {segment_file.name}: {e}")
                continue

            # Create a new SVG root, copy attributes from original
            combined_svg = ET.Element(original_root.tag, original_root.attrib)

            # Copy <defs> from original (if any)
            for defs in original_root.findall('.//{http://www.w3.org/2000/svg}defs'):
                combined_svg.append(defs)

            # Append all children from original to the combined SVG
            for child in list(original_root):
                if child.tag.endswith('defs'):
                    continue
                combined_svg.append(child)

            # Create the highlighted group with red stroke
            highlighted_group = ET.Element('{http://www.w3.org/2000/svg}g', {'id': 'highlighted-segment'})
            for child in list(segment_root):
                if child.tag.endswith('defs'):
                    continue

                # Red stroke clone
                outer = ET.Element(child.tag, child.attrib.copy())
                # outer.attrib['style'] = 'stroke:red;stroke-width:2;fill:none'

                # Clean original shape to show only fill
                original_style = child.attrib.get('style', '')
                new_style_parts = [
                    kv for kv in original_style.split(';')
                    if not kv.strip().startswith('stroke')
                ]
                new_style_parts = [kv for kv in new_style_parts if kv.strip()]
                child.attrib['style'] = ';'.join(new_style_parts)

                highlighted_group.append(outer)
                highlighted_group.append(child)

            # Apply black transparent overlay to the full SVG except highlight
            add_black_overlay(combined_svg, highlighted_group)

            # Write result
            output_name = f"{segment_file.stem}_highlighted.svg"
            output_path = svg_output_dir / output_name

            try:
                ET.ElementTree(combined_svg).write(output_path)
            except Exception as e:
                tqdm.write(f"⚠️ Failed to write {output_path}: {e}")


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


def main():
    originals_dir = 'svgs'
    segments_dir = 'segmented_svgs'
    highlighted_dir = 'highlighted_svgs'
    png_output_dir = 'highlighted_pngs'

    if not os.path.exists(segments_dir):
        print(f"❌ Segments directory '{segments_dir}' not found.")
        return

    segmented_folders = [
        d for d in os.listdir(segments_dir)
        if os.path.isdir(os.path.join(segments_dir, d))
    ]

    if not segmented_folders:
        print(f"❌ No folders found in '{segments_dir}'.")
        return

    questions = [
        inquirer.List(
            'selected_folder',
            message="Select the segmented folder to process:",
            choices=segmented_folders
        )
    ]
    answers = inquirer.prompt(questions)
    if answers is None:
        print("❌ No folder selected. Exiting.")
        return

    selected_folder = answers['selected_folder']
    print(f"🔍 Processing folder: {selected_folder}")

    highlight_segments(originals_dir, segments_dir, highlighted_dir, selected_folder)
    print(f"🎨 Highlighted SVGs saved in: {highlighted_dir}")

    input_highlighted_folder = Path(highlighted_dir) / selected_folder
    output_png_folder = Path(png_output_dir) / selected_folder
    convert_svg_folder(input_highlighted_folder, output_png_folder)
    print(f"🎉 PNGs saved in: {png_output_dir}")

if __name__ == "__main__":
    main()
