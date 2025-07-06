# SEND PNG TO GEMINI TO GET DESCRIPTIONS
#!/usr/bin/env python3

import requests
import json
from pathlib import Path
from tqdm import tqdm
import inquirer
import base64
import re
from consts import GEMINI_API_KEY, GEMINI_API_URL, DEFAULT_PROMPT
import time

import random

def send_images_with_prompt(image_paths, prompt, max_total_wait_minutes=20):
    group_name = image_paths[0].parent.name
    print(f"\n📤 Sending chunk to Gemini: {[img.name for img in image_paths]} (Group: {group_name})")

    base64_images = []
    for image_path in image_paths:
        with open(image_path, "rb") as f:
            encoded_image = base64.b64encode(f.read()).decode("utf-8")
            base64_images.append(encoded_image)

    full_prompt = (
        f"{prompt.strip()}\n\n"
        f"You will receive {len(image_paths)} images. After each image, you will be told its filename.\n"
        f"For each image, provide a **short, specific description** of the **highlighted region**.\n"
        f"IMPORTANT: Each image will be immediately followed by its filename like this: **filename.png**.\n"
        f"Only return results in the format:\n"
        f'**filename.png**\n* description\n\n'
    )

    parts = [{"text": full_prompt}]
    for image_path in image_paths:
        with open(image_path, "rb") as f:
            encoded_image = base64.b64encode(f.read()).decode("utf-8")
        parts.append({
            "inlineData": {
                "mimeType": "image/png",
                "data": encoded_image
            }
        })
        parts.append({ "text": f"The image just above is named: **{image_path.name}**. Only describe what is visible in it." })

    payload = {"contents": [{"parts": parts}]}
    url = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}"

    delay = 6  # Start with 5 seconds
    total_waited = 0

    while total_waited < max_total_wait_minutes * 60:
        try:
            start_time = time.time()
            response = requests.post(url, headers={"Content-Type": "application/json"}, json=payload)
            duration = time.time() - start_time
            print(f"✅ Gemini response status: {response.status_code} (time: {duration:.2f}s)")

            if response.status_code in [429, 503]:
                raise requests.exceptions.HTTPError(f"{response.status_code} Retryable error")

            response.raise_for_status()
            time.sleep(4)
            return response.json()

        except requests.exceptions.RequestException as e:
            print(f"⚠️ Error ({e}). Retrying in {delay}s...")
            time.sleep(delay)
            total_waited += delay
            delay = min(delay * 2, 300)  # Exponential backoff with max 5min
            delay += random.uniform(0, 3)  # Add jitter

    print(f"❌ Failed to process group {group_name} after waiting {total_waited // 60:.1f} minutes.")
    return None


def parse_and_format_response(image_paths, gemini_response, output_path=None):
    """
    Parses Gemini response with Markdown-like structure and maps descriptions to exact image filenames.
    Each filename header (**filename.png**) is followed by a bullet point (* description).
    If no match is found, logs a warning.
    """
    formatted = []

    try:
        text_block = gemini_response["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        print("⚠️ No response text found in Gemini API response.")
        text_block = ""

    # Parse lines
    lines = [line.strip() for line in text_block.split('\n') if line.strip()]

    # Build mapping
    description_map = {}
    current_filename = None

    for line in lines:
        filename_match = re.match(r"\*\*(.+?)\*\*", line)
        if filename_match:
            current_filename = filename_match.group(1).strip()
            continue

        desc_match = re.match(r"^\*\s+(.*)", line)
        if desc_match and current_filename:
            description = desc_match.group(1).strip()
            description_map[current_filename] = description
            current_filename = None

    # Check for missing matches
    missing_count = 0
    for image_path in image_paths:
        description = description_map.get(image_path.name)
        if not description:
            print(f"⚠️ No description found for: {image_path.name}")
            description = "No description available."
            missing_count += 1

        formatted.append({
            "id": image_path.name,
            "description": description
        })

    # Optionally: stop or warn if too many missing
    if missing_count > 0:
        print(f"⚠️ {missing_count} / {len(image_paths)} images received no valid description.")

    # Save output
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(formatted, f, indent=2)
        print(f"✅ Saved Gemini response to: {output_path}")

    return formatted

def extract_element_number(filename):
    """
    Extracts the element number from a filename like '..._element_55_highlighted.png'.
    """
    match = re.search(r'_element_(\d+)', filename)
    if match:
        return int(match.group(1))
    return float('inf')  # If not found, push to the end

def chunk_list(lst, chunk_size):
    """
    Splits a list into smaller chunks of the given size.
    Example: chunk_list([1,2,3,4,5], 2) => [[1,2], [3,4], [5]]
    """
    for i in range(0, len(lst), chunk_size):
        yield lst[i:i + chunk_size]

def send_full_scene_image(full_png_path):
    """
    Sends the full scene PNG image to Gemini to get a global description and style.
    """

    prompt = (
        "You are given a full scene image. Your job is to analyze its visual style and describe what the scene shows.\n\n"
        "1. Describe the **artistic style** in a short, precise phrase. Be specific, using labels such as:\n"
        "- isometric vector illustration (3D-like with depth and angled walls)\n"
        "- flat 2D illustration (no depth or perspective)\n"
        "- cartoon-style vector\n"
        "- infographic diagram\n"
        "- hand-drawn comic style\n"
        "- pixel art\n"
        "- photorealistic rendering\n"
        "Base this on the layout, depth cues, shadows, angles, and design style — not just color or subject.\n\n"
        "2. Provide a high-level scene description (not too detailed) that tells what is happening or shown.\n\n"
        "Respond strictly in this JSON format:\n"
        "{\n"
        "  \"global_style\": \"...\",\n"
        "  \"description\": \"...\"\n"
        "}"
    )


    with open(full_png_path, "rb") as f:
        encoded_image = base64.b64encode(f.read()).decode("utf-8")

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {
                        "inlineData": {
                            "mimeType": "image/png",
                            "data": encoded_image
                        }
                    }
                ]
            }
        ]
    }

    url = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}"

    try:
        response = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            json=payload
        )
        response.raise_for_status()
        time.sleep(5)
        content = response.json()
        text = content["candidates"][0]["content"]["parts"][0].get("text", "")
        if not text:
            raise ValueError("Empty response text from Gemini.")
        
        text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as e:
            print(f"⚠️ Gemini response is not valid JSON:\n{text}")
            raise e

        return parsed

    except Exception as e:
        print(f"❌ Failed to describe full scene image {full_png_path.name}: {e}")
        return {"global_style": "", "description": ""}

def send_grouped_pngs(input_dir, output_json_dir, prompt, chunk_size=10):
    """
    Sends the full scene image FIRST, then sends grouped segmented PNGs to Gemini.
    Saves full scene metadata and chunked responses separately for each group.
    """
    input_dir = Path(input_dir)
    output_json_dir = Path(output_json_dir)

    # Group PNGs by their immediate parent folder name
    grouped_pngs = {}
    for png_file in input_dir.rglob("*.png"):
        parent_folder = png_file.parent.relative_to(input_dir)
        grouped_pngs.setdefault(parent_folder, []).append(png_file)

    if not grouped_pngs:
        print(f"⚠️ No PNG files found in {input_dir}")
        return

    print(f"🚀 Sending {len(grouped_pngs)} groups of PNGs from {input_dir} to Gemini AI...")

    for group_name, png_files in tqdm(grouped_pngs.items(), desc="Sending groups", unit="group"):
        full_png_path = next((f for f in png_files if f.name.endswith("-full.png")), None)
        response_dir = output_json_dir / group_name
        response_dir.mkdir(parents=True, exist_ok=True)

        # 1. Send full PNG first
        full_info = {"global_style": "", "description": ""}
        if full_png_path and full_png_path.exists():
            full_info = send_full_scene_image(full_png_path)
            metadata_path = response_dir / "scene_metadata.json"
            with open(metadata_path, "w") as f:
                json.dump(full_info, f, indent=2)
            tqdm.write(f"📝 Saved scene metadata: {metadata_path}")
        else:
            tqdm.write(f"⚠️ No full PNG found for {group_name}, skipping full scene description.")

        # 2. Send segmented PNGs (excluding the full PNG)
        segmented_pngs = sorted(
            [f for f in png_files if not f.name.endswith("-full.png")],
            key=lambda x: extract_element_number(x.name)
        )

        all_formatted_responses = []
        for i, image_chunk in enumerate(chunk_list(segmented_pngs, chunk_size)):
            response = send_images_with_prompt(image_chunk, prompt)
            if response is not None:
                formatted_chunk = parse_and_format_response(image_chunk, response)
                all_formatted_responses.extend(formatted_chunk)
            else:
                fallback_chunk = [
                    {"id": img.name, "description": "No description available."}
                    for img in image_chunk
                ]
                all_formatted_responses.extend(fallback_chunk)
                print(f"⚠️ Skipped chunk {group_name}/{i} due to an error.")

        # 3. Save segmented descriptions
        response_path = response_dir / "response.json"
        with open(response_path, "w") as f:
            json.dump(all_formatted_responses, f, indent=2)
        tqdm.write(f"✅ Saved combined response: {response_path}")

    print(f"🎉 Completed sending all PNG groups. Responses saved in {output_json_dir}")

def select_input_folder(base_dir):
    """
    Prompt the user to select a subfolder from the base_dir.
    """
    base_path = Path(base_dir)
    subfolders = [f.name for f in base_path.iterdir() if f.is_dir()]
    if not subfolders:
        print(f"❌ No subfolders found in '{base_dir}'.")
        return None

    question = [
        inquirer.List(
            'selected_folder',
            message="Select the input folder to process:",
            choices=subfolders
        )
    ]
    answers = inquirer.prompt(question)
    if answers:
        return base_path / answers['selected_folder']
    return None

def main():
    inputs_dir = Path("inputs")
    outputs_dir = Path("outputs")

    # Step 1: Let user pick a folder from inputs/
    input_folders = [f.name for f in inputs_dir.iterdir() if f.is_dir()]
    if not input_folders:
        print("❌ No folders found in 'inputs/'.")
        return

    answers = inquirer.prompt([
        inquirer.List(
            'selected_folder',
            message="Select a folder from inputs/ to process all its SVGs:",
            choices=input_folders
        )
    ])
    if not answers:
        print("❌ No folder selected. Exiting.")
        return

    selected_input_folder = answers['selected_folder']
    selected_input_path = inputs_dir / selected_input_folder
    svg_files = list(selected_input_path.glob("*.svg"))

    if not svg_files:
        print(f"❌ No SVG files found in: inputs/{selected_input_folder}")
        return

    print(f"\n📁 Selected input folder: {selected_input_folder}")
    print(f"🔍 Found {len(svg_files)} SVG files to process.")

    prompt = DEFAULT_PROMPT

    for svg_path in svg_files:
        svg_id = svg_path.stem
        print(f"\n=== 🧠 Sending for: {svg_id} ===")

        highlighted_png_dir = outputs_dir / svg_id / "highlighted_pngs"
        output_json_dir = outputs_dir / svg_id / "gemini_responses"

        if not highlighted_png_dir.exists():
            print(f"⚠️ Skipping {svg_id} — folder not found: {highlighted_png_dir}")
            continue

        send_grouped_pngs(highlighted_png_dir, output_json_dir, prompt)


if __name__ == "__main__":
    main()