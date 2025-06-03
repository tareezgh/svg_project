#!/usr/bin/env python3

import os
import xml.etree.ElementTree as ET
import shutil
from pathlib import Path
import re
import logging
from typing import List, Dict, Set

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class SVGSegmenter:
    """A class to handle SVG segmentation into individual elements."""
    
    # SVG namespace
    SVG_NS = {'svg': 'http://www.w3.org/2000/svg'}
    
    # Elements that can contain paths or shapes
    CONTAINER_ELEMENTS = {'g', 'svg'}
    
    # Elements that represent shapes or paths
    SHAPE_ELEMENTS = {
        'path', 'rect', 'circle', 'ellipse', 'line',
        'polyline', 'polygon', 'text', 'use'
    }

    def __init__(self):
        """Initialize the SVGSegmenter."""
        self.processed_ids: Set[str] = set()
        self.id_counter: Dict[str, int] = {}

    def generate_unique_id(self, base: str) -> str:
        """Generate a unique ID for an element."""
        if base not in self.id_counter:
            self.id_counter[base] = 0
        self.id_counter[base] += 1
        return f"{base}_{self.id_counter[base]}"

    def create_svg_template(self, original_root: ET.Element) -> ET.Element:
        """Create a new SVG element with the same attributes as the original."""
        new_svg = ET.Element('svg')
        for key, value in original_root.attrib.items():
            new_svg.set(key, value)
        return new_svg

    def extract_styles(self, root: ET.Element) -> ET.Element:
        """Extract and copy style elements from the original SVG."""
        style_element = root.find('.//svg:style', self.SVG_NS)
        if style_element is not None:
            return ET.fromstring(ET.tostring(style_element))
        return None

    def process_element(self, element: ET.Element, segment_dir: str, base_filename: str,
                       original_root: ET.Element, style_element: ET.Element = None) -> None:
        """Process an individual SVG element and save it as a separate file."""
        if element.tag.split('}')[-1] not in self.SHAPE_ELEMENTS:
            return

        # Add style if it exists
     # 1️⃣ Skip shapes with fill:url(...) in 'style' attribute
        style_attr = element.get('style', '')
        if 'fill:url(' in style_attr:
            logging.info(f"Skipping element with gradient fill (style attribute): {style_attr}")
            return

        # 2️⃣ Skip shapes with fill:none in 'style' attribute
        if 'fill:none' in style_attr.replace(" ", ""):
            logging.info(f"Skipping element with fill:none in style: {style_attr}")
            return

        # 3️⃣ Skip shapes with fill:url(...) in CSS class
        class_attr = element.get('class', '')
        if style_element is not None and class_attr:
            css_text = ET.tostring(style_element, encoding='unicode')
            # Skip gradient fills in class
            pattern_grad = rf'\.{re.escape(class_attr)}\s*\{{[^}}]*fill\s*:\s*url\(#'
            if re.search(pattern_grad, css_text):
                logging.info(f"Skipping element with gradient fill (CSS class): {class_attr}")
                return

            # Skip fill:none in class
            pattern_none = rf'\.{re.escape(class_attr)}\s*\{{[^}}]*fill\s*:\s*none'
            if re.search(pattern_none, css_text):
                logging.info(f"Skipping element with fill:none (CSS class): {class_attr}")
                return

        # 4️⃣ Skip based on opacity (optional)
        opacity_match = re.search(r'opacity\s*:\s*(\d*\.?\d+)', style_attr)
        if opacity_match and float(opacity_match.group(1)) < 0.5:
            logging.info(f"Skipping element with low opacity: {opacity_match.group(1)}")
            return

        # 5️⃣ Skip based on class name keywords (optional)
        if re.search(r'background|shadow', class_attr, re.IGNORECASE):
            logging.info(f"Skipping background element with class: {class_attr}")
            return
    
        # Create new SVG document for this element
        new_svg = self.create_svg_template(original_root)
        

        if style_element is not None:
            new_svg.append(style_element)
        # --- Generic skip logic ---

        # Copy the element
        new_element = ET.fromstring(ET.tostring(element))
        
        # Generate unique ID if needed
        if 'id' not in new_element.attrib:
            new_element.set('id', self.generate_unique_id('element'))
        
        new_svg.append(new_element)

        # Save to file
        element_type = element.tag.split('}')[-1]
        element_id = element.get('id', self.generate_unique_id(element_type))
        filename = f"{base_filename}_{element_id}.svg"
        
        # Ensure valid filename
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        filepath = os.path.join(segment_dir, filename)
        
        # Save the SVG
        tree = ET.ElementTree(new_svg)
        ET.register_namespace('', self.SVG_NS['svg'])
        tree.write(filepath, encoding='utf-8', xml_declaration=True)

    def process_svg_file(self, svg_path: str, output_dir: str) -> None:
        """Process an SVG file and extract all its segments."""
        try:
            # Parse the SVG file
            tree = ET.parse(svg_path)
            root = tree.getroot()
            
            # Create output directory for this SVG
            base_filename = os.path.splitext(os.path.basename(svg_path))[0]
            segment_dir = os.path.join(output_dir, base_filename)
            os.makedirs(segment_dir, exist_ok=True)
            
            # Extract styles
            style_element = self.extract_styles(root)
            
            # Process all shape elements
            for element in root.findall('.//svg:*', self.SVG_NS):
                self.process_element(element, segment_dir, base_filename, root, style_element)
            
            logging.info(f"Processed {svg_path}")
            
        except Exception as e:
            logging.error(f"Error processing {svg_path}: {str(e)}")

def process_directory(input_dir: str, output_dir: str) -> None:
    """Process all SVG files in a directory."""
    segmenter = SVGSegmenter()
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Process all SVG files in the input directory
    svg_files = list(Path(input_dir).glob('**/*.svg'))
    
    if not svg_files:
        logging.warning(f"No SVG files found in {input_dir}")
        return
    
    for svg_path in svg_files:
        segmenter.process_svg_file(str(svg_path), output_dir)

def main():
    """Main function that processes SVGs from all input directories."""
    input_dirs = ['svgs', 'svgs2','3dColorful', 'repeated'] 
    output_dir = 'segmented_svgs'
    
    logging.info("Starting SVG segmentation process...")
    
    for input_dir in input_dirs:
        if os.path.exists(input_dir):
            logging.info(f"Processing directory: {input_dir}")
            process_directory(input_dir, os.path.join(output_dir, input_dir))
        else:
            logging.warning(f"Directory not found: {input_dir}")
    
    logging.info("SVG segmentation process completed!")


if __name__ == "__main__":
    main() 