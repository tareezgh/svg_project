#!/usr/bin/env python3

import os
import argparse
import http.server
import socketserver
import webbrowser
from pathlib import Path
import xml.etree.ElementTree as ET
import shutil
import json
from collections import defaultdict

def extract_segments_info(svg_dir):
    """Extract information about segments and their original SVGs."""
    segments_map = defaultdict(list)
    originals_map = {}
    processed_files = set()  # Track processed files to avoid duplicates

    # First, find all original SVGs in the root directories
    original_dirs = ['hugging-1000',]# 'svgs2', '3dColorful']
    for original_dir in original_dirs:
        original_root = os.path.join(os.path.dirname(svg_dir), original_dir)
        if not os.path.exists(original_root):
            continue
            
        # Look for original SVGs in the root directory
        for file in os.listdir(original_root):
            if file.endswith('.svg'):
                original_name = os.path.splitext(file)[0]
                original_path = os.path.join(original_dir, file)
                originals_map[original_name] = original_path

    # Then process segments
    for parent_dir in ["hugging-1000"]:#'svgs', 'svgs2', '3dColorful']:
        segments_dir = os.path.join(svg_dir, parent_dir)
        if not os.path.exists(segments_dir):
            continue
            
        for item in os.listdir(segments_dir):
            item_path = os.path.join(segments_dir, item)
            if not os.path.isdir(item_path):
                continue
                
            # Process segments in this directory
            for file in os.listdir(item_path):
                if not file.endswith('.svg'):
                    continue
                    
                file_path = os.path.join(item_path, file)
                if file_path in processed_files:
                    continue
                    
                processed_files.add(file_path)
                # Get original name from the directory name
                original_name = item
                relative_path = os.path.join(parent_dir, item, file)
                segments_map[original_name].append(relative_path)

    # Debug information
    print(f"\nFound {len(originals_map)} original SVGs:")
    for name, path in originals_map.items():
        print(f"- {name}: {path}")
    
    print(f"\nFound segments for {len(segments_map)} SVGs:")
    for name in segments_map:
        print(f"- {name}: {len(segments_map[name])} segments")

    return dict(segments_map), originals_map

def create_preview_page(svg_dir, output_dir):
    """Create an HTML page to preview SVGs with segment highlighting."""
    
    # Create preview directory
    preview_dir = os.path.join(output_dir, 'highlight_preview')
    os.makedirs(preview_dir, exist_ok=True)
    
    # Get segments information
    segments_map, originals_map = extract_segments_info(svg_dir)
    
    # Only copy necessary files
    files_to_copy = set()
    
    # Add original SVGs
    for original_path in originals_map.values():
        # Get the source path from the workspace root
        src_path = os.path.join(os.path.dirname(svg_dir), original_path)
        if os.path.exists(src_path):
            # Copy to preview directory
            dst_path = os.path.join(preview_dir, original_path)
            os.makedirs(os.path.dirname(dst_path), exist_ok=True)
            shutil.copy2(src_path, dst_path)
    
    # Add segment SVGs
    for segments in segments_map.values():
        for segment_path in segments:
            src_path = os.path.join(svg_dir, segment_path)
            if os.path.exists(src_path):
                dst_path = os.path.join(preview_dir, segment_path)
                os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                shutil.copy2(src_path, dst_path)

    # Generate HTML content
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>SVG Segment Highlighter</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 20px;
                background: #f0f0f0;
            }

            svg {
                width: 700px !important;
                height: 100%;
            }

            .container {
                display: flex;
                gap: 20px;
                max-width: 1400px;
                margin: 0 auto;
            }
            #navigation {
                width: 250px;
                background: white;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                max-height: calc(100vh - 40px);
                position: sticky;
                top: 20px;
                overflow-y: auto;
            }
            #navigation h2 {
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
            }
            .svg-container {
                display: flex;
                gap: 20px;
            }
            .original-svg {
                flex: 2;
                min-width: 0;
                position: relative;
            }
            .original-svg svg {
                width: 100%;
                height: auto;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
            .segment-list {
                width: 250px;
                background: #f8f8f8;
                padding: 15px;
                border-radius: 4px;
                max-height: 600px;
                overflow-y: auto;
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
            <nav id="navigation">
                <h2>Original SVGs</h2>
                <ul class="svg-list">
    """
    
    # Add navigation items
    for idx, original_name in enumerate(sorted(segments_map.keys()), 1):
        if original_name in originals_map:  # Only show SVGs that have originals
            original_path = originals_map[original_name]
            folder_name = Path(original_path).parent.name
            html_content += f"""
                        <li>
                            <button onclick="loadOriginalSVG('{original_name}')">{idx}. {folder_name} / {original_name}</button>
                        </li>
            """
    
    html_content += """
                </ul>
            </nav>
            <main class="content">
                <div class="svg-container">
                    <div class="original-svg" id="original-svg-container">
                        <p style="text-align: center; color: #666;">Select an SVG from the left menu</p>
                    </div>
                    <div class="segment-list" id="segment-list-container">
                        <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                            <button id="prev-segment" onclick="navigateSegment(-1)">Previous</button>
                            <button id="next-segment" onclick="navigateSegment(1)">Next</button>
                        </div>
                        <div id="segment-items">
                            <p style="text-align: center; color: #666;">Select an SVG to see its segments</p>
                        </div>
                    </div>

                </div>
            </main>
        </div>
        <script>
            // Store the segments data
            const segmentsMap = """ + json.dumps(segments_map) + """;
            const originalsMap = """ + json.dumps(originals_map) + """;
            
            let currentSvgContent = null;
            let loadedSegments = new Set();
            let currentSegmentIndex = -1;
            let currentSegments = [];
            
            function loadOriginalSVG(name) {
                // Update navigation
                document.querySelectorAll('.svg-list button').forEach(btn => {
                    btn.classList.remove('active');
                });
                document.querySelector(`button[onclick="loadOriginalSVG('${name}')"]`).classList.add('active');
                
                // Load original SVG
                const originalPath = originalsMap[name];
                if (!originalPath) {
                    document.getElementById('original-svg-container').innerHTML = 
                        '<p style="text-align: center; color: #666;">Original SVG not found</p>';
                    document.getElementById('segment-list').innerHTML = 
                        '<p style="text-align: center; color: #666;">No segments available</p>';
                    return;
                }

                fetch(originalPath)
                    .then(response => {
                        if (!response.ok) {
                            throw new Error(`SVG not found (${response.status})`);
                        }
                        return response.text();
                    })
                    .then(svgContent => {
                        currentSvgContent = svgContent;
                        document.getElementById('original-svg-container').innerHTML = svgContent;
                    

                        // Update segments list
                        const segments = segmentsMap[name] || [];
                        const segmentList = document.getElementById('segment-items');
                        segmentList.innerHTML = segments.map(segment => `
                            <div class="segment-item" onclick="highlightSegment('${segment}')">
                                ${segment.split('/').pop()}
                            </div>
                        `).join('');
                        
                        // Pre-fetch segment SVGs
                        segments.forEach(segment => {
                            if (!loadedSegments.has(segment)) {
                                fetch(segment).catch(() => console.log(`Failed to prefetch: ${segment}`));
                                loadedSegments.add(segment);
                            }
                        });

                        currentSegments = segments;
                        currentSegmentIndex = -1;
                    })
                    .catch(error => {
                        console.error('Error loading SVG:', error);
                        document.getElementById('original-svg-container').innerHTML = 
                            '<p style="text-align: center; color: #666;">Error loading SVG: ' + error.message + '</p>';
                        document.getElementById('segment-list').innerHTML = 
                            '<p style="text-align: center; color: #666;">No segments available</p>';
                    });
            }
            
            function highlightSegment(segmentPath) {
                if (!currentSvgContent) return;

                // Reset segment items
                document.querySelectorAll('.segment-item').forEach(item => {
                    item.classList.remove('active');
                });

                // Highlight the clicked segment
                const segmentItem = document.querySelector(`.segment-item[onclick="highlightSegment('${segmentPath}')"]`);
                if (segmentItem) {
                    segmentItem.classList.add('active');
                }

                // Reset the original SVG
                document.getElementById('original-svg-container').innerHTML = currentSvgContent;

                // Select the newly re-injected original SVG
                const svgElement = document.querySelector('#original-svg-container svg');
                if (!svgElement) {
                    console.error('Original SVG not found');
                    return;
                }

                // Load the segment SVG
                fetch(segmentPath)
                    .then(response => {
                        if (!response.ok) {
                            throw new Error('Segment not found');
                        }
                        return response.text();
                    })
                    .then(segmentContent => {
                        const parser = new DOMParser();
                        const segmentDoc = parser.parseFromString(segmentContent, 'image/svg+xml');
                        const segmentShapes = segmentDoc.querySelectorAll('svg > *:not(style)');

                        if (!segmentShapes.length) {
                            throw new Error('No shape elements found in segment');
                        }

                        // Create a group for highlights
                        const highlightGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
                        highlightGroup.setAttribute('class', 'highlight');

                        segmentShapes.forEach(shape => {
                            const clone = shape.cloneNode(true);
                            clone.setAttribute('fill', '#ff000050');
                            clone.setAttribute('stroke', '#ff0000');
                            clone.setAttribute('stroke-width', '2');
                            highlightGroup.appendChild(clone);
                        });

                        svgElement.appendChild(highlightGroup);
                    })
                    .catch(error => {
                        console.error('Error highlighting segment:', error);
                    });

                // Update currentSegmentIndex
                currentSegmentIndex = currentSegments.indexOf(segmentPath);
            }

            function navigateSegment(direction) {
                if (!currentSegments.length) return;
                if (currentSegmentIndex === -1) {
                    currentSegmentIndex = 0;
                } else {
                    currentSegmentIndex += direction;
                    if (currentSegmentIndex < 0) currentSegmentIndex = 0;
                    if (currentSegmentIndex >= currentSegments.length) currentSegmentIndex = currentSegments.length - 1;
                }
                highlightSegment(currentSegments[currentSegmentIndex]);
            }

            // Load first SVG automatically
            window.addEventListener('DOMContentLoaded', () => {
                const firstButton = document.querySelector('.svg-list button');
                if (firstButton) {
                    const name = firstButton.textContent;
                    loadOriginalSVG(name);
                }
            });
        </script>
    </body>
    </html>
    """
    
    # Write HTML file
    html_path = os.path.join(preview_dir, 'index.html')
    with open(html_path, 'w') as f:
        f.write(html_content)
    
    return html_path

def main():
    parser = argparse.ArgumentParser(description='Create highlight preview for SVG segments')
    parser.add_argument(
        '--input-dir',
        default='segmented_svgs',
        help='Directory containing SVG files (default: segmented_svgs)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=8001,
        help='Port for preview server (default: 8000)'
    )
    
    args = parser.parse_args()
    
    try:
        if not os.path.isdir(args.input_dir):
            raise Exception(f"Input directory '{args.input_dir}' does not exist")
        
        # Create preview
        html_path = create_preview_page(args.input_dir, args.input_dir)
        preview_url = f'http://localhost:{args.port}/{os.path.relpath(html_path)}'
        
        print(f"\n🌐 Starting highlight preview server at {preview_url}")
        print("Press Ctrl+C to stop the server")
        
        # Start server first
        httpd = socketserver.TCPServer(("", args.port), http.server.SimpleHTTPRequestHandler)
        
        # Then open browser
        webbrowser.open(preview_url)
        
        # Start serving
        httpd.serve_forever()
            
    except KeyboardInterrupt:
        print("\n✨ Preview server stopped")
    except Exception as e:
        print(f"Error: {str(e)}")
        return 1
    
    return 0

if __name__ == '__main__':
    exit(main())
