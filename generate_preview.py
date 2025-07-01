# TO GENERATE HTML OFFLINE
#!/usr/bin/env python3

import os
import argparse
from pathlib import Path
import inquirer

def extract_segments_info(segments_dir, originals_dir, folder_name):
    segments_map = {}
    originals_map = {}

    segments_path = Path(segments_dir) / folder_name
    if not segments_path.exists():
        return segments_map, originals_map

    # Search all top-level folders for originals
    originals_base_path = Path(originals_dir).parent

    # Find all segment subfolders (each representing an original SVG)
    for subdir in segments_path.iterdir():
        if not subdir.is_dir():
            continue

        segment_list = []
        for file in subdir.glob('*.svg'):
            segment_list.append(file.resolve())
        if segment_list:
            segments_map[subdir.name] = segment_list

            # Search all top-level folders for the matching original SVG
            found_original = False
            for potential_folder in originals_base_path.iterdir():
                if potential_folder.is_dir():
                    candidate = potential_folder / f"{subdir.name}.svg"
                    if candidate.exists():
                        originals_map[subdir.name] = candidate.resolve()
                        found_original = True
                        break
            if not found_original:
                print(f"⚠️ Original SVG not found for: {subdir.name}")

    return segments_map, originals_map

def create_offline_preview(segments_dir, originals_dir, folder_name, output_html):
    segments_map, originals_map = extract_segments_info(segments_dir, originals_dir, folder_name)

    html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>SVG Segment Highlighter</title>
    <meta charset="UTF-8">
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 0;
            background: #f0f0f0;
        }
        svg {
            width: 90% !important;
            height: auto;
        }
        .container {
            display: flex;
            gap: 20px;
            max-width: 1400px;
            margin: 0 auto;
            padding: 20px;
        }
        .navigation {
            width: 250px;
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            overflow-y: auto;
            height: calc(100vh - 40px);
            position: sticky;
            top: 20px;
        }
        .navigation h2 {
            margin-top: 0;
            margin-bottom: 15px;
        }
        .svg-list {
            list-style: none;
            padding: 0;
            margin: 0;
        }
        .svg-list li {
            margin-bottom: 10px;
        }
        .svg-list button {
            width: 100%;
            padding: 8px;
            background: #f8f8f8;
            border: 1px solid #ddd;
            border-radius: 4px;
            cursor: pointer;
            text-align: left;
        }
        .svg-list button:hover {
            background: #f0f0f0;
        }
        .svg-list button.active {
            background: #e0e0e0;
            font-weight: bold;
        }
        .content {
            flex-grow: 1;
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            display: flex;
            gap: 20px;
            height: calc(100vh - 40px);
        }
        .original-svg {
            flex: 3;
            overflow-y: auto;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .original-svg svg {
            width: 100%;
            max-height: 90vh;
            border: 1px solid #ddd;
            border-radius: 4px;
        }
        .segment-list {
            width: 300px;
            background: #f8f8f8;
            padding: 15px;
            border-radius: 4px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
        }
        .segment-controls {
            display: flex;
            justify-content: space-between;
            margin-bottom: 10px;
        }
        .segment-item {
            padding: 8px;
            margin-bottom: 5px;
            background: white;
            border: 1px solid #ddd;
            border-radius: 4px;
            cursor: pointer;
        }
        .segment-item:hover {
            background: #f0f0f0;
        }
        .segment-item.active {
            background: #e0e0e0;
            font-weight: bold;
        }
        .highlight {
            fill: #ff000050 !important;
            stroke: #ff0000 !important;
            stroke-width: 2px !important;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="navigation">
            <h2>Original SVGs</h2>
            <ul class="svg-list">
    """

    # Add original SVG buttons
    for idx, original_name in enumerate(sorted(segments_map.keys()), 1):
        if original_name in originals_map:
            html_content += f"""
                <li>
                    <button onclick="loadOriginal('{original_name}')">{idx}. {original_name}</button>
                </li>
            """

    html_content += """
            </ul>
        </div>
        <div class="content">
            <div class="original-svg" id="original-svg-container">
                <p style="text-align: center; color: #666;">Select an SVG from the left menu</p>
            </div>
            <div class="segment-list">
                <div class="segment-controls">
                    <button onclick="navigateSegment(-1)">Previous</button>
                    <button onclick="navigateSegment(1)">Next</button>
                </div>
                <div id="segment-items">
                    <p style="text-align: center; color: #666;">Select an SVG to see its segments</p>
                </div>
            </div>
        </div>
    </div>
    <script>
        const originals = {};
        const segments = {};
        const segmentNames = {};
    """

    # Embed originals
    for name, path in originals_map.items():
        try:
            with open(path, 'r', encoding='utf-8') as f:
                svg_content = f.read().replace('\n', '').replace('"', '\\"')
                html_content += f'originals["{name}"] = "{svg_content}";\n'
        except Exception as e:
            print(f"⚠️ Failed to embed original {name}: {e}")

    # Embed segments and their names
    for name, files in segments_map.items():
        html_content += f'segments["{name}"] = [];\n'
        html_content += f'segmentNames["{name}"] = [];\n'
        for file in files:
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    svg_content = f.read().replace('\n', '').replace('"', '\\"')
                    file_name = file.stem
                    html_content += f'segments["{name}"].push("{svg_content}");\n'
                    html_content += f'segmentNames["{name}"].push("{file_name}");\n'
            except Exception as e:
                print(f"⚠️ Failed to embed segment for {name}: {e}")

    html_content += """
        let currentOriginal = null;
        let currentIndex = -1;

        function loadOriginal(name) {
            document.querySelectorAll('.svg-list button').forEach(btn => btn.classList.remove('active'));
            const btn = Array.from(document.querySelectorAll('.svg-list button')).find(b => b.textContent.includes(name));
            if (btn) btn.classList.add('active');
            document.getElementById('original-svg-container').innerHTML = originals[name];
            currentOriginal = name;
            currentIndex = -1;

            // Populate segment list
            const segmentItems = segments[name].map((_, i) => `
                <div class="segment-item" onclick="highlightSegment(${i})">
                    ${segmentNames[name][i]}
                </div>
            `).join('');
            document.getElementById('segment-items').innerHTML = segmentItems;
        }

        function highlightSegment(index) {
            if (!currentOriginal) return;
            const container = document.getElementById('original-svg-container');
            const svgElement = container.querySelector('svg');
            if (!svgElement) {
                console.error('Original SVG not found');
                return;
            }

            // Remove existing highlights
            const oldHighlight = svgElement.querySelector('.highlight');
            if (oldHighlight) oldHighlight.remove();

            const parser = new DOMParser();
            const segmentDoc = parser.parseFromString(segments[currentOriginal][index], 'image/svg+xml');
            const shapes = segmentDoc.querySelectorAll('svg > *:not(style)');
            const highlightGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
            highlightGroup.setAttribute('class', 'highlight');
            shapes.forEach(shape => {
                const clone = shape.cloneNode(true);
                clone.setAttribute('fill', '#ff000050');
                clone.setAttribute('stroke', '#ff0000');
                clone.setAttribute('stroke-width', '2');
                highlightGroup.appendChild(clone);
            });
            svgElement.appendChild(highlightGroup);

            // Highlight the segment item
            document.querySelectorAll('.segment-item').forEach(item => item.classList.remove('active'));
            document.querySelectorAll('.segment-item')[index].classList.add('active');
            currentIndex = index;
        }

        function navigateSegment(direction) {
            if (!currentOriginal || !segments[currentOriginal]) return;
            const total = segments[currentOriginal].length;
            if (total === 0) return;

            if (currentIndex === -1) {
                currentIndex = 0;
            } else {
                currentIndex += direction;
                if (currentIndex < 0) currentIndex = total - 1;
                if (currentIndex >= total) currentIndex = 0;
            }
            highlightSegment(currentIndex);
        }
    </script>
</body>
</html>
    """

    with open(output_html, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"✅ Offline HTML preview created at {output_html}")

def main():
    parser = argparse.ArgumentParser(description='Generate offline HTML preview with highlight navigation')
    parser.add_argument('--originals-dir', default='test', help='Directory with original SVGs')
    parser.add_argument('--segments-dir', default='segmented_svgs', help='Directory with segment folders')
    args = parser.parse_args()

    if not os.path.isdir(args.originals_dir):
        print(f"❌ Originals directory '{args.originals_dir}' does not exist.")
        return

    if not os.path.isdir(args.segments_dir):
        print(f"❌ Segments directory '{args.segments_dir}' does not exist.")
        return

    folders = [f.name for f in Path(args.segments_dir).iterdir() if f.is_dir()]
    if not folders:
        print(f"❌ No folders found in '{args.segments_dir}' to select from.")
        return

    questions = [
        inquirer.List(
            "folder",
            message="Select the folder containing segments:",
            choices=folders,
        )
    ]
    answers = inquirer.prompt(questions)
    if not answers:
        print("❌ No folder selected. Exiting.")
        return

    folder_name = answers["folder"]
    output_html = f"{folder_name}_preview.html"

    create_offline_preview(args.segments_dir, args.originals_dir, folder_name, output_html)

if __name__ == "__main__":
    main()
