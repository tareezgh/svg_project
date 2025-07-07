#!/usr/bin/env python3
"""
Master script to run the complete SVG processing pipeline:
1. SVG Segmentation (main.py)
2. Highlight Segmented Parts (highlight_segmented_parts.py) 
3. Send PNGs to Gemini (send_pngs.py)
4. Build Hierarchy (hierarchy_png.py)
"""

import os
import sys
import logging
import inquirer
from pathlib import Path
from tqdm import tqdm

# Import functions from the individual scripts
from main import process_directory, SVGSegmenter
from highlight_segmented_parts import highlight_segments, convert_full_svg_to_png
from send_pngs import send_grouped_pngs
from hierarchy_png import load_png_segments, build_hierarchy_bbox, export_hierarchy_json
from convert_svg_highlights_to_png import convert_svg_folder
from consts import DEFAULT_PROMPT

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

OUTPUT_ROOT = Path("outputs")

def select_input_folder():
    """Let user select a folder from inputs/"""
    base_input_dir = Path('./inputs')
    
    if not base_input_dir.exists():
        logging.error("'inputs/' directory not found")
        return None
        
    available_dirs = [
        d.name for d in base_input_dir.iterdir()
        if d.is_dir()
    ]
    
    if not available_dirs:
        logging.error("No subdirectories found in 'inputs/'")
        return None

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
        return None

    return answers["selected_dir"]

def step1_svg_segmentation(selected_folder):
    """Step 1: Run SVG segmentation (from main.py)"""
    print("\n" + "="*60)
    print("STEP 1: SVG SEGMENTATION")
    print("="*60)
    
    input_dir = Path("inputs") / selected_folder
    output_dir = OUTPUT_ROOT
    
    if not input_dir.exists():
        logging.error(f"Input directory not found: {input_dir}")
        return False
        
    logging.info(f"Processing SVGs from: {input_dir}")
    logging.info(f"Saving results to: {output_dir}")
    
    try:
        process_directory(str(input_dir), str(output_dir))
        logging.info("✅ SVG segmentation completed successfully!")
        return True
    except Exception as e:
        logging.error(f"❌ SVG segmentation failed: {e}")
        return False

def step2_highlight_segments(selected_folder):
    """Step 2: Highlight segmented parts (from highlight_segmented_parts.py)"""
    print("\n" + "="*60)
    print("STEP 2: HIGHLIGHT SEGMENTED PARTS")
    print("="*60)
    
    inputs_dir = Path("inputs")
    outputs_dir = OUTPUT_ROOT
    
    selected_input_path = inputs_dir / selected_folder
    svg_files = list(selected_input_path.glob("*.svg"))
    
    if not svg_files:
        logging.error(f"No SVG files found in: inputs/{selected_folder}")
        return False
    
    logging.info(f"Processing {len(svg_files)} SVG files for highlighting...")
    
    success_count = 0
    for svg_path in tqdm(svg_files, desc="Highlighting segments"):
        svg_id = svg_path.stem
        
        try:
            # Check if segmented folders exist
            segment_sources = []
            
            seg_dir = OUTPUT_ROOT / svg_id / "segmented_svgs"
            if seg_dir.exists() and any(seg_dir.iterdir()):
                segment_sources.append(seg_dir)
            
            plus_dir = Path("segmented_svgs_plus") / svg_id
            if plus_dir.exists() and any(plus_dir.iterdir()):
                segment_sources.append(plus_dir)
            
            if not segment_sources:
                logging.warning(f"No segmented sources found for '{svg_id}'. Skipping.")
                continue
            
            # Run highlighting for this SVG
            highlight_segments(
                originals_dir="inputs",
                selected_folder=selected_folder,
                svg_id=svg_id
            )
            
            # Convert SVGs to PNGs
            base_output = OUTPUT_ROOT / svg_id
            convert_svg_folder(base_output / "highlighted_svgs", base_output / "highlighted_pngs")
            convert_svg_folder(base_output / "highlighted_svgs_no_overlay", base_output / "highlighted_pngs_no_overlay")
            convert_svg_folder(base_output / "white_svgs", base_output / "white_pngs")
            
            # Convert full SVG to PNG
            convert_full_svg_to_png(
                originals_dir="inputs",
                selected_folder=selected_folder,
                svg_id=svg_id
            )
            
            success_count += 1
            
        except Exception as e:
            logging.error(f"❌ Failed to process {svg_id}: {e}")
    
    logging.info(f"✅ Highlighting completed! Successfully processed {success_count}/{len(svg_files)} SVGs")
    return success_count > 0

def step3_send_to_gemini(selected_folder):
    """Step 3: Send PNGs to Gemini API (from send_pngs.py)"""
    print("\n" + "="*60)
    print("STEP 3: SEND TO GEMINI API")
    print("="*60)
    
    inputs_dir = Path("inputs")
    outputs_dir = OUTPUT_ROOT
    
    selected_input_path = inputs_dir / selected_folder
    svg_files = list(selected_input_path.glob("*.svg"))
    
    if not svg_files:
        logging.error(f"No SVG files found in: inputs/{selected_folder}")
        return False
    
    logging.info(f"Processing {len(svg_files)} SVG files for Gemini API...")
    
    success_count = 0
    for svg_path in tqdm(svg_files, desc="Sending to Gemini"):
        svg_id = svg_path.stem
        
        try:
            highlighted_png_dir = outputs_dir / svg_id / "highlighted_pngs"
            output_json_dir = outputs_dir / svg_id / "gemini_responses"
            
            if not highlighted_png_dir.exists():
                logging.warning(f"Skipping {svg_id} — highlighted_pngs folder not found")
                continue
            
            send_grouped_pngs(highlighted_png_dir, output_json_dir, DEFAULT_PROMPT)
            success_count += 1
            
        except Exception as e:
            logging.error(f"❌ Failed to send {svg_id} to Gemini: {e}")
    
    logging.info(f"✅ Gemini API processing completed! Successfully processed {success_count}/{len(svg_files)} SVGs")
    return success_count > 0

def step4_build_hierarchy(selected_folder):
    """Step 4: Build hierarchy (from hierarchy_png.py)"""
    print("\n" + "="*60)
    print("STEP 4: BUILD HIERARCHY")
    print("="*60)
    
    inputs_dir = Path("inputs")
    outputs_dir = OUTPUT_ROOT
    
    selected_input_path = inputs_dir / selected_folder
    svg_files = list(selected_input_path.glob("*.svg"))
    
    if not svg_files:
        logging.error(f"No SVG files found in: inputs/{selected_folder}")
        return False
    
    logging.info(f"Processing {len(svg_files)} SVG files for hierarchy building...")
    
    success_count = 0
    for svg_file in tqdm(svg_files, desc="Building hierarchy"):
        svg_id = svg_file.stem
        
        try:
            base_output = outputs_dir / svg_id
            png_dir = base_output / "highlighted_pngs_no_overlay"
            regular_svg_dir = base_output / "segmented_svgs"
            plus_svg_dir = Path("segmented_svgs_plus") / svg_id
            
            if not png_dir.exists():
                logging.warning(f"Skipping {svg_id}: highlighted_pngs_no_overlay not found")
                continue
            
            segments = load_png_segments(png_dir, regular_svg_dir, plus_svg_dir, selected_folder)
            
            if not segments:
                logging.warning(f"No valid segments found for {svg_id}")
                continue
            
            segments_with_parents = build_hierarchy_bbox(segments)
            output_path = base_output / "hierarchy_output" / f"{svg_id}_hierarchy.json"
            export_hierarchy_json(segments_with_parents, output_path, svg_id)
            
            success_count += 1
            
        except Exception as e:
            logging.error(f"❌ Failed to build hierarchy for {svg_id}: {e}")
    
    logging.info(f"✅ Hierarchy building completed! Successfully processed {success_count}/{len(svg_files)} SVGs")
    return success_count > 0

def check_prerequisites():
    """Check if all required dependencies and directories exist"""
    print("🔍 Checking prerequisites...")
    
    # Check required directories
    required_dirs = ["inputs", "outputs"]
    for dir_name in required_dirs:
        if not Path(dir_name).exists():
            logging.error(f"Required directory '{dir_name}/' not found")
            return False
    
    # Check if inputs directory has subdirectories
    inputs_dir = Path("inputs")
    if not any(inputs_dir.iterdir()):
        logging.error("'inputs/' directory is empty")
        return False
    
    # Check for optional directories
    optional_dirs = ["segmented_svgs_plus"]
    for dir_name in optional_dirs:
        if not Path(dir_name).exists():
            logging.warning(f"Optional directory '{dir_name}/' not found - some features may be limited")
    
    print("✅ Prerequisites check completed")
    return True

def main():
    """Run the complete pipeline"""
    print("🚀 SVG PROCESSING PIPELINE")
    print("="*60)
    print("This script will run the complete pipeline:")
    print("1. SVG Segmentation")
    print("2. Highlight Segmented Parts") 
    print("3. Send PNGs to Gemini API")
    print("4. Build Hierarchy")
    print("="*60)
    
    # Check prerequisites
    if not check_prerequisites():
        logging.error("❌ Prerequisites check failed. Please fix the issues above.")
        return
    
    # Step 0: Select input folder
    selected_folder = select_input_folder()
    if not selected_folder:
        return
    
    print(f"\n📁 Selected folder: {selected_folder}")
    print("🔄 Running all steps in sequence...")
    
    # Run all steps in order
    steps = [
        ("Step 1: SVG Segmentation", step1_svg_segmentation),
        ("Step 2: Highlight Segmented Parts", step2_highlight_segments),
        ("Step 3: Send to Gemini API", step3_send_to_gemini),
        ("Step 4: Build Hierarchy", step4_build_hierarchy)
    ]
    
    for step_name, step_func in steps:
        if not step_func(selected_folder):
            logging.error(f"❌ Pipeline failed at {step_name}. Stopping.")
            return
    
    print("\n" + "="*60)
    print("🎉 PIPELINE COMPLETED SUCCESSFULLY!")
    print("="*60)
    print(f"All processing completed for folder: {selected_folder}")
    print("Check the 'outputs/' directory for results.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ Pipeline interrupted by user.")
        sys.exit(1)
    except Exception as e:
        logging.error(f"❌ Unexpected error: {e}")
        sys.exit(1) 