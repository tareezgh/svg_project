#!/usr/bin/env python3

import os
import xml.etree.ElementTree as ET
from pathlib import Path
import inquirer
from tqdm import tqdm
from convert_svg_highlights_to_png import convert_svg_folder
from collections import defaultdict


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

def save_highlight_on_black_background(
    segment_root: ET.Element,
    original_root: ET.Element,
    svg_id: str,
    selected_folder: str,
    segment_file_stem: str
):
    """
    Create a version of the highlighted SVG with a solid black background (no transparency or spotlight).
    This creates a visual like: black background + white/red segment on top.
    """
    output_dir = Path("highlighted_svgs_no_overlay") / selected_folder / svg_id
    output_dir.mkdir(parents=True, exist_ok=True)

    svg_ns = 'http://www.w3.org/2000/svg'
    new_svg = ET.Element(original_root.tag, original_root.attrib)

    # Copy <defs> if any
    for defs in original_root.findall(f'.//{{{svg_ns}}}defs'):
        new_svg.append(defs)

    # Add black rectangle covering the whole canvas
    black_rect = ET.Element(f'{{{svg_ns}}}rect', {
        'x': '0',
        'y': '0',
        'width': '100%',
        'height': '100%',
        'fill': 'black'
    })
    new_svg.append(black_rect)

    # Create highlight group
    highlight_group = ET.Element(f'{{{svg_ns}}}g', {'id': 'highlighted-segment'})
    for child in list(segment_root):
        if child.tag.endswith('defs'):
            continue

        # Optional red stroke
        outer = ET.Element(child.tag, child.attrib.copy())

        # Clean fill (remove stroke from child)
        original_style = child.attrib.get('style', '')
        style_parts = [
            kv for kv in original_style.split(';') if not kv.strip().startswith('stroke')
        ]
        child.attrib['style'] = ';'.join(style_parts)

        highlight_group.append(outer)
        highlight_group.append(child)

    new_svg.append(highlight_group)

    # Save SVG
    output_path = output_dir / f"{segment_file_stem}_highlighted.svg"
    try:
        ET.ElementTree(new_svg).write(output_path)
    except Exception as e:
        tqdm.write(f"⚠️ Failed to write black overlay version: {output_path}: {e}")

def highlight_segments(originals_dir, segments_dir, output_dir, selected_folder):
    selected_path = Path(segments_dir) / selected_folder
    plus_path = Path("segmented_svgs_plus")
    highlighted_output_folder = Path("highlighted_svgs") / selected_folder
    white_output_folder = Path("white_svgs") / selected_folder

    svg_id_dirs = defaultdict(list)

    # From segmented_svgs/<selected_folder>/
    if selected_path.exists():
        for d in selected_path.iterdir():
            if d.is_dir():
                svg_id_dirs[d.name].append(d)
                print(f"✅ Found in segmented_svgs: {d.name}")

    # From segmented_svg_plus/
    for svg_id in svg_id_dirs:
        plus_dir = plus_path / svg_id
        if plus_dir.exists() and plus_dir.is_dir():
            svg_id_dirs[svg_id].append(plus_dir)
            print(f"✅ Also found in segmented_svg_plus: {svg_id}")

    if not svg_id_dirs:
        print("❌ No SVG segment folders found.")
        return

    for svg_id, sources in svg_id_dirs.items():
        print(f"\n🔍 Processing svg_id: {svg_id}")
        for src in sources:
            print(f"   └─ Source folder: {src}")

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

        highlighted_dir = highlighted_output_folder / svg_id
        white_dir = white_output_folder / svg_id
        highlighted_dir.mkdir(parents=True, exist_ok=True)
        white_dir.mkdir(parents=True, exist_ok=True)


        # Collect segment files from all sources
        segment_files = []
        for source in sources:
            found_files = list(source.glob("*.svg"))
            if source.name in plus_path.name:
                print(f"   🔹 {len(found_files)} segment(s) from segmented_svg_plus/{source.name}")
            segment_files += found_files

        if not segment_files:
            print(f"⚠️ No segments found for: {svg_id}")
            continue

        print(f"📦 Processing {svg_id} ({len(segment_files)} segments from multiple folders)")
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
            output_path = highlighted_dir / output_name

            try:
                ET.ElementTree(combined_svg).write(output_path)
            except Exception as e:
                tqdm.write(f"⚠️ Failed to write {output_path}: {e}")

            save_highlight_on_black_background(
                segment_root=segment_root,
                original_root=original_root,
                svg_id=svg_id,
                selected_folder=selected_folder,
                segment_file_stem=segment_file.stem
            )

            white_svg = ET.Element(original_root.tag, original_root.attrib)

            bg_rect = ET.Element('{http://www.w3.org/2000/svg}rect', {
                'x': '0', 'y': '0', 'width': '100%', 'height': '100%',
                'fill': 'black'
            })
            white_svg.append(bg_rect)

            white_group = ET.Element('{http://www.w3.org/2000/svg}g', {'id': 'white-shapes'})
            for child in list(segment_root):
                if child.tag.endswith('defs'):
                    continue

                white_shape = ET.Element(child.tag, child.attrib.copy())
                # white_shape.attrib.pop('stroke', None)
                # white_shape.attrib['fill'] = 'white'
                # white_shape.attrib['style'] = 'fill:white'
                white_shape.attrib.pop('stroke', None)
                white_shape.attrib['fill'] = 'white'

                # Override style completely to ensure visibility and fill
                white_shape.attrib['style'] = 'fill:white;display:inline;opacity:1'


                white_group.append(white_shape)
                white_group.attrib['style'] = 'display:inline;opacity:1'

                for elem in white_svg.iter():
                    style = elem.attrib.get('style', '')
                    if 'display:none' in style:
                        new_style = style.replace('display:none', 'display:inline')
                        elem.attrib['style'] = new_style



            white_svg.append(white_group)

            white_output_name = f"{segment_file.stem}_highlighted.svg"
            white_output_path = white_dir / white_output_name

            try:
                ET.ElementTree(white_svg).write(white_output_path)
            except Exception as e:
                tqdm.write(f"⚠️ Failed to write {white_output_path}: {e}")



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

def convert_full_svg_to_png(originals_dir, selected_folder, svg_id, output_folder):
    """
    Converts full SVG from svgs/{selected_folder}/{svg_id}.svg to PNG as
    highlighted_pngs/{selected_folder}/{svg_id}/{svg_id}-full.png
    """
    svg_path = Path("./inputs") / selected_folder / f"{svg_id}.svg"
    output_path = Path(output_folder) / selected_folder / svg_id / f"{svg_id}-full.png"

    if not svg_path.exists():
        print(f"⚠️ Full SVG not found at: {svg_path}")
        return

    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        import cairosvg
        cairosvg.svg2png(
            url=str(svg_path),
            write_to=str(output_path),
            output_width=512,
            output_height=512
        )
        print(f"✅ Saved full PNG: {output_path}")
    except Exception as e:
        print(f"❌ Failed to convert full SVG to PNG for {svg_id}: {e}")


def main():
    originals_dir = 'inputs'
    SEGMENTS_DIRS = {
        'segmented_svgs': Path('segmented_svgs'),
        'segmented_svg_plus': Path('segmented_svg_plus')
    }
    highlighted_dir = 'highlighted_svgs'
    png_output_dir = 'highlighted_pngs'

    # Collect all folders from both sources
    folder_choices = []
    folder_source_map = {}
    for label, base_path in SEGMENTS_DIRS.items():
        if not base_path.exists():
            continue
        for folder in base_path.iterdir():
            if folder.is_dir():
                folder_choices.append(f"{label}/{folder.name}")
                folder_source_map[f"{label}/{folder.name}"] = (base_path, folder.name)

    if not folder_choices:
        print("❌ No segmented folders found.")
        return

    questions = [
        inquirer.List(
            'selected_folder',
            message="Select the segmented folder to process:",
            choices=folder_choices
        )
    ]
    answers = inquirer.prompt(questions)
    if answers is None:
        print("❌ No folder selected. Exiting.")
        return

    full_selected = answers['selected_folder']
    base_path, selected_folder = folder_source_map[full_selected]

    print(f"🔍 Processing folder: {selected_folder} from {base_path.name}")

    highlight_segments(originals_dir, str(base_path), highlighted_dir, selected_folder)
    print(f"🎨 Highlighted SVGs saved in: {highlighted_dir}")

    input_highlighted_folder = Path(highlighted_dir) / selected_folder
    output_png_folder = Path(png_output_dir) / selected_folder
    convert_svg_folder(input_highlighted_folder, output_png_folder)
    print(f"🎉 PNGs saved in: {png_output_dir}")

    # Convert no-overlay highlights to PNG
    no_overlay_input_folder = Path("highlighted_svgs_no_overlay") / selected_folder
    no_overlay_png_output_folder = Path("highlighted_pngs_no_overlay") / selected_folder
    convert_svg_folder(no_overlay_input_folder, no_overlay_png_output_folder)
    print(f"🎉 PNGs saved in: highlighted_pngs_no_overlay/{selected_folder}")

    white_input_folder = Path("white_svgs") / selected_folder
    white_png_output_folder = Path("white_pngs") / selected_folder
    convert_svg_folder(white_input_folder, white_png_output_folder)
    print(f"🎉 White-only PNGs saved in: white_pngs/{selected_folder}")

    # Convert full SVGs for each svg_id (i.e. each subfolder)
    segmented_subfolders = base_path / selected_folder
    for svg_subdir in segmented_subfolders.iterdir():
        if not svg_subdir.is_dir():
            continue

        svg_id = svg_subdir.name
        convert_full_svg_to_png(
            originals_dir=originals_dir,
            selected_folder=selected_folder,
            svg_id=svg_id,
            output_folder=png_output_dir
        )


if __name__ == "__main__":
    main()
