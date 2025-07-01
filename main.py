# GET SEGMENTED SVGS
#!/usr/bin/env python3

import os
import re
import logging
import numpy as np
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Optional
from svgpathtools import parse_path
from shapely.geometry import Polygon, MultiPolygon, Point, LineString
from shapely.ops import unary_union
from tqdm import tqdm 
import inquirer

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class SVGSegmenter:
    SVG_NS = {'svg': 'http://www.w3.org/2000/svg'}
    SHAPE_ELEMENTS = {'path', 'rect', 'circle', 'ellipse', 'line', 'polyline', 'polygon', 'text', 'use'}

    def __init__(self):
        self.id_counter: Dict[str, int] = {}

    def generate_unique_id(self, base: str) -> str:
        self.id_counter.setdefault(base, 0)
        self.id_counter[base] += 1
        return f"{base}_{self.id_counter[base]}"

    def create_svg_template(self, original_root: ET.Element) -> ET.Element:
        return ET.Element('svg', original_root.attrib)

    def extract_styles(self, root: ET.Element) -> Optional[ET.Element]:
        style_element = root.find('.//svg:style', self.SVG_NS)
        if style_element is not None:
            return ET.fromstring(ET.tostring(style_element))
        return None

    def parse_element_to_shapely(self, element: ET.Element) -> Optional[Polygon]:
        tag = element.tag.split('}')[-1]
        try:
            if tag == 'path':
                d_attr = element.get('d')
                if not d_attr:
                    return None
                path = parse_path(d_attr)
                points = [seg.point(t) for seg in path for t in np.linspace(0, 1, 100)]
                coords = [(p.real, p.imag) for p in points]
                return Polygon(coords).buffer(0.5)
            elif tag == 'rect':
                x, y = float(element.get('x', '0')), float(element.get('y', '0'))
                w, h = float(element.get('width', '0')), float(element.get('height', '0'))
                return Polygon([(x, y), (x+w, y), (x+w, y+h), (x, y+h)])
            elif tag == 'circle':
                cx, cy, r = float(element.get('cx', '0')), float(element.get('cy', '0')), float(element.get('r', '0'))
                return Point(cx, cy).buffer(r)
            elif tag == 'ellipse':
                cx, cy = float(element.get('cx', '0')), float(element.get('cy', '0'))
                rx, ry = float(element.get('rx', '0')), float(element.get('ry', '0'))
                circle = Point(0, 0).buffer(1)
                coords = [(cx + rx * x, cy + ry * y) for x, y in circle.exterior.coords]
                return Polygon(coords)
            elif tag == 'line':
                x1, y1 = float(element.get('x1', '0')), float(element.get('y1', '0'))
                x2, y2 = float(element.get('x2', '0')), float(element.get('y2', '0'))
                return LineString([(x1, y1), (x2, y2)]).buffer(1.0)
            elif tag in {'polyline', 'polygon'}:
                points_attr = element.get('points', '')
                points = [tuple(map(float, p)) for p in re.findall(r'([\d\.\-eE]+),([\d\.\-eE]+)', points_attr)]

                if tag == 'polygon':
                    return Polygon(points)
                else:
                    return LineString(points).buffer(1.0)
            elif tag in {'text', 'use'}:
                x, y = float(element.get('x', '0')), float(element.get('y', '0'))
                return Point(x, y).buffer(3.0)
        except Exception as e:
            logging.warning(f"Failed to parse {tag}: {e}")
            return None

    def polygon_to_pathdata(self, polygon: Polygon) -> str:
        if isinstance(polygon, MultiPolygon):
            return ' '.join(self.polygon_to_pathdata(p) for p in polygon.geoms)
        coords = list(polygon.exterior.coords)
        d = f"M {coords[0][0]} {coords[0][1]} " + ' '.join(f"L {x} {y}" for x, y in coords[1:]) + " Z"
        return d

    def passes_filters(self, element: ET.Element, style_element: Optional[ET.Element]) -> bool:
        style_attr = element.get('style', '')
        class_attr = element.get('class', '')
        if 'fill:url(' in style_attr or 'fill:none' in style_attr.replace(" ", ""):
            return False
        if style_element is not None and class_attr:
            css_text = ET.tostring(style_element, encoding='unicode')
            if re.search(rf'\.{re.escape(class_attr)}\s*\{{[^}}]*fill\s*:\s*url\(#', css_text):
                return False
            if re.search(rf'\.{re.escape(class_attr)}\s*\{{[^}}]*fill\s*:\s*none', css_text):
                return False
        if re.search(r'background|shadow', class_attr, re.IGNORECASE):
            return False
        opacity_match = re.search(r'opacity\s*:\s*(\d*\.?\d+)', style_attr)
        if opacity_match and float(opacity_match.group(1)) < 0.5:
            return False
        return True

    def process_svg_file(self, svg_path: str, output_dir: str):
        try:
            tree = ET.parse(svg_path)
            root = tree.getroot()
            base_filename = os.path.splitext(os.path.basename(svg_path))[0]
            segment_dir = os.path.join(output_dir, base_filename, "segmented_svgs")
            os.makedirs(segment_dir, exist_ok=True)
            style_element = self.extract_styles(root)

            elements = []
            for element in root.findall('.//svg:*', self.SVG_NS):
                tag = element.tag.split('}')[-1]
                if tag not in self.SHAPE_ELEMENTS:
                    continue
                if not self.passes_filters(element, style_element):
                    continue
                poly = self.parse_element_to_shapely(element)
                if poly and not poly.is_empty:
                    elements.append({'element': element, 'polygon': poly})

            for idx, item in enumerate(elements):
                element = item['element']
                polygon = item['polygon']
                upper_polygons = [e['polygon'] for e in elements[idx+1:] if e['polygon']]
                if upper_polygons:
                    mask = unary_union(upper_polygons)
                    if mask.covers(polygon):
                        # logging.info(f"Skipping fully covered element: {element.get('id', 'unknown')}")
                        continue
                    polygon = polygon.difference(mask)
                if polygon.is_empty or polygon.area < 1e-3:
                    # logging.info(f"Skipping small or empty element: {element.get('id', 'unknown')}")
                    continue
                new_svg = self.create_svg_template(root)
                if style_element is not None:
                    new_svg.append(style_element)
                new_element = ET.fromstring(ET.tostring(element))
                new_element.tag = f"{{{self.SVG_NS['svg']}}}path"
                new_element.set('id', self.generate_unique_id('element'))
                new_element.set('d', self.polygon_to_pathdata(polygon))
                new_svg.append(new_element)
                filename = re.sub(r'[<>:"/\\|?*]', '_', f"{base_filename}_{new_element.get('id')}.svg")
                filepath = os.path.join(segment_dir, filename)
                ET.ElementTree(new_svg).write(filepath, encoding='utf-8', xml_declaration=True)

            # logging.info(f"Processed {svg_path}")

        except Exception as e:
            logging.error(f"Error processing {svg_path}: {e}")

def process_directory(input_dir: str, output_dir: str):
    segmenter = SVGSegmenter()
    os.makedirs(output_dir, exist_ok=True)
    svg_files = list(Path(input_dir).glob('**/*.svg'))
    if not svg_files:
        logging.warning(f"No SVG files found in {input_dir}")
        return
    logging.info(f"Processing {len(svg_files)} SVG files from '{input_dir}'...")
    for svg_path in tqdm(svg_files, desc=f"Segmenting SVGs in {input_dir}"):
        segmenter.process_svg_file(str(svg_path), output_dir)

def main():
    base_input_dir = './inputs'

    available_dirs = [
        d for d in os.listdir(base_input_dir)
        if os.path.isdir(os.path.join(base_input_dir, d))
    ]
    if not available_dirs:
        logging.error("No subdirectories found in 'inputs/'")
        return

    questions = [
        inquirer.List(
            "selected_dir",
            message="Select an input folder to process",
            choices=available_dirs,
        )
    ]
    answers = inquirer.prompt(questions)
    if not answers:
        logging.warning("No folder selected. Exiting.")
        return

    selected_folder = answers["selected_dir"]
    input_dir = os.path.join(base_input_dir, selected_folder)
    output_dir = os.path.join("outputs")

    logging.info("Starting SVG segmentation process...")
    logging.info(f"Processing from: {input_dir}")
    logging.info(f"Saving results to: {output_dir}")

    if os.path.exists(input_dir):
        process_directory(input_dir, output_dir)
    else:
        logging.warning(f"Directory not found: {input_dir}")

    logging.info("SVG segmentation process completed!")

if __name__ == "__main__":
    main()


