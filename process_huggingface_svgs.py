# JUST TO GET ALL HUGGIINGFACE SVGS
#!/usr/bin/env python3

import os
import logging
from datasets import load_dataset
from huggingface_hub import login
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def download_huggingface_svgs( output_dir: str, sample_limit: int = None):
    """
    Downloads the MMSVG-Illustration dataset from Hugging Face, saves each SVG locally.

    :param hf_token: Hugging Face authentication token
    :param output_dir: Directory to save SVG files
    :param sample_limit: Optional limit for number of samples (e.g. 1000)
    """


    # Load dataset
    logging.info("Loading MMSVG-Illustration dataset...")
    dataset = load_dataset("OmniSVG/MMSVG-Illustration", split="train")

    if sample_limit:
        dataset = dataset.select(range(sample_limit))

    # Save SVGs
    os.makedirs(output_dir, exist_ok=True)
    for i, item in enumerate(dataset):
        svg_id = item.get("id", f"svg_{i}")
        svg_content = item["svg"]
        file_path = os.path.join(output_dir, f"{svg_id}.svg")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(svg_content)
        if i % 100 == 0:
            logging.info(f"Saved {i + 1}/{len(dataset)} SVG files...")

    logging.info(f"Downloaded and saved {len(dataset)} SVG files to '{output_dir}'.")

def main():
    """
    Main function for downloading and segmenting Hugging Face dataset.
    """
    try:
        login()  # uses stored token
    except Exception as e:
        logging.error(f"Failed to authenticate with Hugging Face: {e}")
        return

    download_dir = "huggingface_svgs"
    segment_output_dir = "segmented_huggingface_svgs"

    # Download and save SVGs
    download_huggingface_svgs(download_dir, sample_limit=None)  # remove sample_limit to fetch all

    # Segment the downloaded SVGs
    logging.info("Starting segmentation process...")
    # process_directory(download_dir, segment_output_dir)
    logging.info("Segmentation process completed!")

if __name__ == "__main__":
    main()
