# Batch Image Cropper

A simple desktop tool that applies the same crop region to multiple images at once.

---

## Features

- Load multiple images and batch crop them with a single selection
- Export as PNG, JPEG, or WEBP
- Mouse wheel zoom and middle-click drag to pan
- Real-time crop coordinates and size display in the status bar
- Original filenames preserved on save (`filename_cropped.png`)
- Auto-numbering when output filenames conflict

---

## Usage

### 1. Load Images
Click **Load Images** and select one or more image files.
Supported formats: `jpg` `jpeg` `png` `bmp` `gif` `webp`

### 2. Select Crop Area
Click and drag on the canvas to draw a crop region.
The area outside the selection is dimmed.

### 3. Crop All
Click **Crop All** to apply the same region to every loaded image.

### 4. Save Results
Click **Save Results**, choose an output folder, and all cropped images will be saved there.

---

## Controls

| Action | Input |
|--------|-------|
| Draw crop region | Left-click drag |
| Zoom in / out | Mouse wheel |
| Pan | Middle-click drag |
| Clear selection | **Clear** button |

---

## Installation

### Executable (recommended)
Download the latest `.exe` from the [Releases](https://github.com/hwahyeon/batch-image-cropper/releases) page and run it — no Python required.

> **Windows SmartScreen warning:** click "More info → Run anyway".
> The executable is unsigned, so Windows may flag it on first launch.

### Run from source
```bash
git clone https://github.com/hwahyeon/batch-image-cropper.git
cd batch-image-cropper
pip install -r requirements.txt
python main.py
```

---

## Requirements

- Python 3.9+
- Pillow >= 11.0.0

---

## License

MIT
