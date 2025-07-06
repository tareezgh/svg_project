# SVG Processing Pipeline

This project contains a complete pipeline for processing SVG files through segmentation, highlighting, AI analysis, and hierarchy building.

## Quick Start

Run the complete pipeline with a single command:

```bash
python run_full_pipeline.py
```

## Pipeline Steps

The pipeline consists of 4 main steps:

1. **SVG Segmentation** (`main.py`)
   - Segments SVG files into individual components
   - Output: `outputs/<svg_id>/segmented_svgs/`

2. **Highlight Segmented Parts** (`highlight_segmented_parts.py`)
   - Creates highlighted versions of segments
   - Converts SVGs to PNGs
   - Output: `outputs/<svg_id>/highlighted_pngs/`, `white_pngs/`, etc.

3. **Send PNGs to Gemini API** (`send_pngs.py`)
   - Sends highlighted PNGs to Google Gemini for AI analysis
   - Gets descriptions of each segment
   - Output: `outputs/<svg_id>/gemini_responses/`

4. **Build Hierarchy** (`hierarchy_png.py`)
   - Analyzes spatial relationships between segments
   - Creates hierarchical structure
   - Output: `outputs/<svg_id>/hierarchy_output/`

## Usage

### Run Complete Pipeline
```bash
python run_full_pipeline.py
```

The script will:
1. Let you select an input folder from `inputs/`
2. Let you choose which steps to run
3. Execute the selected steps in sequence
4. Show progress and results

### Run Individual Steps

If you prefer to run steps individually:

```bash
# Step 1: SVG Segmentation
python main.py

# Step 2: Highlight Segmented Parts  
python highlight_segmented_parts.py

# Step 3: Send to Gemini API
python send_pngs.py

# Step 4: Build Hierarchy
python hierarchy_png.py
```

## Directory Structure

```
svg_project/
├── inputs/                    # Input SVG folders
│   ├── folder1/
│   │   ├── image1.svg
│   │   └── image2.svg
│   └── folder2/
├── outputs/                   # All processing results
│   ├── image1/
│   │   ├── segmented_svgs/    # Step 1 output
│   │   ├── highlighted_pngs/  # Step 2 output
│   │   ├── gemini_responses/  # Step 3 output
│   │   └── hierarchy_output/  # Step 4 output
│   └── image2/
├── segmented_svgs_plus/       # Additional segment data (optional)
├── run_full_pipeline.py       # Master script
├── main.py                    # Step 1: SVG segmentation
├── highlight_segmented_parts.py # Step 2: Highlighting
├── send_pngs.py              # Step 3: Gemini API
└── hierarchy_png.py          # Step 4: Hierarchy building
```

## Prerequisites

- Python 3.7+
- Required packages (install with `pip`):
  - `svgpathtools`
  - `shapely`
  - `tqdm`
  - `inquirer`
  - `cairosvg`
  - `PIL` (Pillow)
  - `lxml`
  - `opencv-python`
  - `requests`
  - `numpy`

## Configuration

- **Gemini API Key**: Set in `consts.py`
- **Default Prompt**: Customize the AI prompt in `consts.py`
- **Output Resolution**: Modify PNG output size in conversion functions

## Error Handling

The master script includes:
- Prerequisites checking
- Step-by-step error handling
- Progress tracking
- Graceful interruption handling
- Detailed logging

## Troubleshooting

### Common Issues

1. **"No subdirectories found in 'inputs/'"**
   - Make sure you have SVG files in subdirectories of `inputs/`

2. **"Required directory 'outputs/' not found"**
   - Create the `outputs/` directory: `mkdir outputs`

3. **Gemini API errors**
   - Check your API key in `consts.py`
   - Verify internet connection
   - Check API quota limits

4. **Missing dependencies**
   - Install required packages: `pip install -r requirements.txt`

### Resuming Interrupted Pipeline

If the pipeline is interrupted, you can resume from any step:
1. Run `python run_full_pipeline.py`
2. Select the same input folder
3. Uncheck the steps that were already completed
4. Run the remaining steps

## Output Files

### Step 1: Segmented SVGs
- Individual SVG files for each segment
- Located in `outputs/<svg_id>/segmented_svgs/`

### Step 2: Highlighted PNGs
- PNG images with highlighted segments
- Multiple versions: with overlay, without overlay, white masks
- Located in `outputs/<svg_id>/highlighted_pngs/`

### Step 3: Gemini Responses
- JSON files with AI descriptions
- Scene metadata
- Located in `outputs/<svg_id>/gemini_responses/`

### Step 4: Hierarchy
- JSON files with hierarchical structure
- Spatial relationships between segments
- Located in `outputs/<svg_id>/hierarchy_output/` 