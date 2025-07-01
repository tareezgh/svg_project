# TO GENERATE HTML
#!/usr/bin/env python3

import os
import argparse
import http.server
import socketserver
import webbrowser
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

def get_svg_title(svg_path):
    """Extract title from SVG file."""
    try:
        tree = ET.parse(svg_path)
        root = tree.getroot()
        # Look for title element
        title_elem = root.find('{http://www.w3.org/2000/svg}title')
        if title_elem is not None and title_elem.text:
            return title_elem.text.strip()
    except Exception:
        pass
    # Return filename without extension if no title found
    return os.path.splitext(os.path.basename(svg_path))[0]

def create_preview_page(svg_dir, output_dir):
    """Create an HTML page to preview SVGs."""
    
    # Create preview directory
    preview_dir = os.path.join(output_dir, 'preview')
    os.makedirs(preview_dir, exist_ok=True)
    
    # Copy all SVG files to preview directory
    for root, _, files in os.walk(svg_dir):
        for file in files:
            if file.endswith('.svg'):
                src_path = os.path.join(root, file)
                rel_path = os.path.relpath(src_path, svg_dir)
                dst_path = os.path.join(preview_dir, rel_path)
                os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                shutil.copy2(src_path, dst_path)
    
    # Generate HTML content
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>SVG Preview</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 20px;
                background: #f0f0f0;
            }
            .container {
                max-width: 1200px;
                margin: 0 auto;
            }
            #navigation {
                position: fixed;
                left: 20px;
                top: 20px;
                width: 250px;
                background: white;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                max-height: calc(100vh - 40px);
                overflow-y: auto;
            }
            #navigation h2 {
                margin-top: 0;
                margin-bottom: 15px;
                font-size: 18px;
            }
            #navigation ul {
                list-style: none;
                padding: 0;
                margin: 0;
            }
            #navigation li a {
                display: block;
                padding: 8px 10px;
                color: #333;
                text-decoration: none;
                border-radius: 4px;
                margin-bottom: 5px;
                cursor: pointer;
            }
            #navigation li a:hover {
                background: #f0f0f0;
            }
            #navigation li a.active {
                background: #e0e0e0;
                font-weight: bold;
            }
            .content {
                margin-left: 290px;
            }
            .svg-group {
                background: white;
                border-radius: 8px;
                padding: 20px;
                margin-bottom: 30px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                display: none;
            }
            .svg-group.active {
                display: block;
            }
            .svg-group h2 {
                margin-top: 0;
                color: #333;
                border-bottom: 2px solid #eee;
                padding-bottom: 10px;
                scroll-margin-top: 20px;
            }
            .svg-container {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
                gap: 20px;
                margin-top: 20px;
            }
            .svg-item {
                background: #f8f8f8;
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 10px;
                text-align: center;
                aspect-ratio: 1;
                display: flex;
                flex-direction: column;
            }
            .svg-item h3 {
                margin: 0 0 10px 0;
                font-size: 14px;
                color: #666;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }
            .preview-wrapper {
                flex: 1;
                position: relative;
                width: 100%;
            }
            .svg-preview {
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                border: none;
                background: white;
            }
            .svg-preview object {
                width: 100%;
                height: 100%;
                object-fit: contain;
            }
            .loading {
                text-align: center;
                padding: 20px;
                font-style: italic;
                color: #666;
            }

            /* Modal styles */
            .modal {
                display: none;
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0, 0, 0, 0.8);
                z-index: 1000;
                opacity: 0;
                transition: opacity 0.3s ease;
            }
            
            .modal.active {
                display: flex;
                opacity: 1;
            }
            
            .modal-content {
                position: relative;
                width: 90%;
                height: 90%;
                margin: auto;
                background: white;
                border-radius: 8px;
                padding: 20px;
                box-shadow: 0 4px 8px rgba(0,0,0,0.2);
            }
            
            .close-button {
                position: absolute;
                top: 10px;
                right: 10px;
                width: 30px;
                height: 30px;
                background: #ff4444;
                border: none;
                border-radius: 50%;
                color: white;
                font-size: 20px;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                transition: background 0.3s ease;
            }
            
            .close-button:hover {
                background: #ff0000;
            }
            
            .modal-svg-container {
                width: 100%;
                height: 100%;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            
            .modal-svg-container svg {
                max-width: 100%;
                max-height: 100%;
                object-fit: contain;
            }

            .svg-item {
                cursor: pointer;
                transition: transform 0.2s ease;
            }

            .svg-item:hover {
                transform: scale(1.02);
            }
        </style>
        <script>
            function loadSVG(path, container) {
                fetch(path)
                    .then(response => response.text())
                    .then(svgContent => {
                        container.innerHTML = svgContent;
                        const svg = container.querySelector('svg');
                        if (svg) {
                            svg.style.width = '100%';
                            svg.style.height = '100%';
                            svg.style.objectFit = 'contain';
                        }
                    });
            }

            function showGroup(groupId) {
                // Hide all groups and deactivate all nav links
                document.querySelectorAll('.svg-group').forEach(group => {
                    group.classList.remove('active');
                });
                document.querySelectorAll('#navigation li a').forEach(link => {
                    link.classList.remove('active');
                });

                // Show selected group and activate nav link
                const group = document.getElementById(groupId);
                const navLink = document.querySelector(`a[data-group="${groupId}"]`);
                
                if (group && navLink) {
                    group.classList.add('active');
                    navLink.classList.add('active');
                    
                    // Load SVGs if not already loaded
                    if (!group.dataset.loaded) {
                        const containers = group.querySelectorAll('.svg-preview[data-path]');
                        containers.forEach(container => {
                            const path = container.dataset.path;
                            if (path) {
                                loadSVG(path, container);
                            }
                        });
                        group.dataset.loaded = 'true';
                    }

                    // Scroll into view with offset for fixed header
                    group.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    window.scrollBy(0, -20); // Add some offset from the top
                }

                // Update URL hash without triggering scroll
                history.replaceState(null, null, `#${groupId}`);
            }

            function showModal(svgPath) {
                const modal = document.getElementById('svg-modal');
                const modalContent = document.getElementById('modal-svg-container');
                
                // Load SVG into modal
                fetch(svgPath)
                    .then(response => response.text())
                    .then(svgContent => {
                        modalContent.innerHTML = svgContent;
                        const svg = modalContent.querySelector('svg');
                        if (svg) {
                            svg.style.width = '100%';
                            svg.style.height = '100%';
                            svg.style.objectFit = 'contain';
                        }
                        modal.classList.add('active');
                    });
            }

            function closeModal() {
                const modal = document.getElementById('svg-modal');
                modal.classList.remove('active');
            }

            // Handle initial load and back/forward navigation
            window.addEventListener('load', () => {
                const hash = window.location.hash.slice(1);
                if (hash) {
                    showGroup(hash);
                } else {
                    // Show first group by default
                    const firstGroupId = document.querySelector('#navigation li a').dataset.group;
                    showGroup(firstGroupId);
                }
            });

            window.addEventListener('hashchange', () => {
                const hash = window.location.hash.slice(1);
                if (hash) {
                    showGroup(hash);
                }
            });

            // Close modal when clicking outside content
            document.addEventListener('DOMContentLoaded', () => {
                const modal = document.getElementById('svg-modal');
                modal.addEventListener('click', (e) => {
                    if (e.target === modal) {
                        closeModal();
                    }
                });

                // Close modal on Escape key
                document.addEventListener('keydown', (e) => {
                    if (e.key === 'Escape') {
                        closeModal();
                    }
                });
            });
        </script>
    </head>
    <body>
        <!-- Modal -->
        <div id="svg-modal" class="modal">
            <div class="modal-content">
                <button class="close-button" onclick="closeModal()">X</button>
                <div id="modal-svg-container" class="modal-svg-container"></div>
            </div>
        </div>

        <nav id="navigation">
            <h2>Groups</h2>
            <ul>
    """
    
    # First pass to collect all groups for navigation
    groups = []
    for root, dirs, files in os.walk(preview_dir):
        svg_files = [f for f in files if f.endswith('.svg')]
        if not svg_files:
            continue
        group_path = os.path.relpath(root, preview_dir)
        if group_path == '.':
            group_name = "Original SVGs"
        else:
            group_name = group_path.replace(os.sep, ' / ')
        groups.append((group_path, group_name))
    
    # Add navigation links
    for group_path, group_name in groups:
        group_id = group_path.replace(os.sep, '_').replace('.', '_')
        html_content += f"""
                <li><a href="javascript:void(0)" data-group="{group_id}">{group_name}</a></li>
        """
    
    html_content += """
            </ul>
        </nav>
        <div class="content">
    """
    
    # Second pass to add the actual content
    for group_path, group_name in groups:
        group_id = group_path.replace(os.sep, '_').replace('.', '_')
        html_content += f"""
            <div class="svg-group" id="{group_id}">
                <h2>{group_name}</h2>
                <div class="svg-container">
        """
        
        # Get SVGs for this group
        group_dir = os.path.join(preview_dir, group_path)
        svg_files = [f for f in os.listdir(group_dir) if f.endswith('.svg')]
        
        for svg_file in sorted(svg_files):
            file_path = os.path.join(group_path, svg_file)
            html_content += f"""
                    <div class="svg-item" onclick="showModal('{file_path}')">
                        <h3 title="{svg_file}">{svg_file}</h3>
                        <div class="preview-wrapper">
                            <div class="svg-preview" id="{file_path.replace('/', '_')}" data-path="{file_path}"></div>
                        </div>
                    </div>
            """
        
        html_content += """
                </div>
            </div>
        """
    
    html_content += """
        </div>
        <script>
            document.addEventListener('DOMContentLoaded', () => {
                document.querySelectorAll('#navigation li a').forEach(link => {
                    link.addEventListener('click', (e) => {
                        e.preventDefault();
                        showGroup(link.dataset.group);
                    });
                });
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

class PreviewHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(Path.cwd()), **kwargs)

def main():
    parser = argparse.ArgumentParser(description='Create preview page for SVGs')
    parser.add_argument(
        '--input-dir',
        default='segmented_svgs',
        help='Directory containing SVG files (default: segmented_svgs)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=8000,
        help='Port for preview server (default: 8000)'
    )
    
    args = parser.parse_args()
    
    try:
        if not os.path.isdir(args.input_dir):
            raise Exception(f"Input directory '{args.input_dir}' does not exist")
        
        # Create preview
        html_path = create_preview_page(args.input_dir, args.input_dir)
        preview_url = f'http://localhost:{args.port}/{os.path.relpath(html_path)}'
        
        print(f"\n🌐 Starting preview server at {preview_url}")
        print("Press Ctrl+C to stop the server")
        
        # Open browser
        webbrowser.open(preview_url)
        
        # Start server
        with socketserver.TCPServer(("", args.port), PreviewHandler) as httpd:
            httpd.serve_forever()
            
    except KeyboardInterrupt:
        print("\n✨ Preview server stopped")
    except Exception as e:
        print(f"Error: {str(e)}")
        return 1
    
    return 0

if __name__ == '__main__':
    exit(main()) 