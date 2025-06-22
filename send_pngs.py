#!/usr/bin/env python3

import requests
import json
from pathlib import Path
from tqdm import tqdm
import inquirer
import base64
import re
from consts import GEMINI_API_KEY, GEMINI_API_URL, DEFAULT_PROMPT

def send_images_with_prompt(image_paths, prompt):
    """
    Send multiple PNG images and a prompt to Gemini AI and get the response.
    """
    # Read and encode images as base64
    base64_images = []
    for image_path in image_paths:
        with open(image_path, "rb") as f:
            encoded_image = base64.b64encode(f.read()).decode("utf-8")
            base64_images.append(encoded_image)

    file_list = "\n".join(f"{i+1}. {img.name}" for i, img in enumerate(image_paths))
    # full_prompt = (
    #     f"{prompt}\n\n"
    #     f"Below are {len(image_paths)} images. Please provide **one description per image**, using the filenames as anchors.\n"
    #     f"IMPORTANT: Match the description to the correct file name.\n\n"
    #     f"{file_list}"
    # )
    full_prompt = (
        f"{prompt.strip()}\n\n"
        f"You will receive {len(image_paths)} images. After each image, you will be told its filename.\n"
        f"For each image, provide a **short, specific description** of the **highlighted region**.\n"
        f"IMPORTANT: Each image will be immediately followed by its filename like this: **filename.png**.\n"
        f"Please make sure the description matches the correct file.\n"
        f"Only return results in the format:\n"
        f'**filename.png**\n* description\n\n'
    )


    parts = [{"text": full_prompt}]

    for i, image_path in enumerate(image_paths):
        with open(image_path, "rb") as f:
            encoded_image = base64.b64encode(f.read()).decode("utf-8")

        parts.append({
            "inlineData": {
                "mimeType": "image/png",
                "data": encoded_image
            }
        })

        parts.append({ "text": f"The image just above is named: **{image_path.name}**. Only describe what is visible in it." })


    payload = {
        "contents": [
            {"parts": parts}
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
        return response.json()
    except Exception as e:
        print(f"❌ Failed to process group {image_paths[0].parent.name}: {e}")
        return None
        
def parse_and_format_response(image_paths, gemini_response, output_path=None):
    """
    Parses Gemini response with Markdown-like structure and maps descriptions to exact image filenames.
    Each filename header (**filename.png**) is followed by a bullet point (* description).
    If no match is found, logs a warning.
    """
    formatted = []

    print("🔍 Gemini full response:")
    print(json.dumps(gemini_response["candidates"][0]["content"]["parts"][0]["text"], indent=2))

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
    # prompt = (
    #     "You are given a full scene image. Describe the overall content, layout, and visual style. "
    #     "Return the result in JSON format with two fields:\n"
    #     "- global_style: a short description of the scene's artistic style (e.g., 'minimalist', 'realistic cartoon')\n"
    #     "- description: a rich, high-level summary of what the scene depicts overall as text-to-image model\n"
    #     "Example:\n"
    #     "{ \"global_style\": \"minimalist vector art\", \"description\": \"A login screen on a laptop with a person sitting in front.\" }"
    # )

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

def send_grouped_pngs(input_dir, output_json_dir, prompt, chunk_size=8):
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
    highlighted_base_dir = "highlighted_pngs"          # PNG input folder
    output_json_dir = "gemini_responses"    # JSON output folder

    selected_input_dir = select_input_folder(highlighted_base_dir)
    if selected_input_dir is None:
        print("❌ No folder selected. Exiting.")
        return
    
    prompt = DEFAULT_PROMPT

    send_grouped_pngs(selected_input_dir, output_json_dir, prompt)

if __name__ == "__main__":
    main()