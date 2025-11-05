# Screen Machine

A Python application that processes video files, extracts screenshots at evenly spaced intervals, and assembles them into grid images with optional metadata labels.

ScreenMachine functions similarly to AMT Auto Movie Thumbnailer, but is 30x as fast for generating screenshots. This is the result of advanced seeking optimizations allowed by FFmpeg.

ScreenMachine functions optimally over the network, with spinning hard drives, and with NVME/SSD, seeking frames dynamically to reduce read strain and CPU consumption as much as possible.

Adjust the number of worker threads for your use case.

## Features

- Recursively processes all videos in a selected directory and subdirectories
- Extracts screenshots at calculated intervals based on video length
- Assembles screenshots into a customizable grid layout (rows × columns)
- Resizes screenshots to fit within specified maximum dimensions
- Adds optional metadata labels (title, resolution, file size, duration, codec)
- Configurable JPG quality/compression
- Option to overwrite existing images or skip them
- Modern GUI built with customtkinter

## Supported Video Formats

- MP4
- AVI
- WMV
- MKV
- MOV
- M4V
- WEBM

## Requirements

- Python 3.8 or higher
- See `requirements.txt` for dependencies

## Installation

1. Clone or download this repository
2. Install system dependencies:

   **Windows:**
   ```bash
   pip install -r requirements.txt
   ```

   **Linux:**
   ```bash
   # Install system packages
   sudo apt-get install python3-tk python3-dev ffmpeg libavcodec-dev libavformat-dev libavutil-dev libswscale-dev
   
   # Install Python dependencies
   pip3 install -r requirements.txt
   ```

## Usage

### Running from Source

#### Windows

```bash
python main.py
```

#### Linux

```bash
# Install dependencies first (if not already installed)
sudo apt-get install python3-tk python3-dev ffmpeg libavcodec-dev libavformat-dev libavutil-dev libswscale-dev

# Install Python dependencies
pip3 install -r requirements.txt

# Run the application
python3 main.py
```

**Note:** On Linux, you may need additional system packages for video processing:
- `python3-tk` - For GUI support
- `python3-dev` - For building Python extensions
- `ffmpeg` - For video processing
- `libavcodec-dev`, `libavformat-dev`, `libavutil-dev`, `libswscale-dev` - For PyAV library support

### Building an Executable

To create a standalone executable (no Python installation required):

#### Windows

```bash
# Recommended: Use the provided build script (handles everything automatically)
python build_executable.py

# Or manually with pyinstaller (includes FFmpeg if found in PATH):
# Note: Replace C:\ffmpeg\bin\ffmpeg.EXE and C:\ffmpeg\bin\ffprobe.EXE with your FFmpeg paths
pyinstaller --onefile --windowed --icon=icon.ico --add-data="icon.ico;." \
  --add-binary="C:\ffmpeg\bin\ffmpeg.EXE;ffmpeg" --add-binary="C:\ffmpeg\bin\ffprobe.EXE;ffprobe" \
  --name "ScreenMachine" main.py \
  --collect-all customtkinter --collect-all av --hidden-import av --hidden-import PIL._tkinter_finder
```

#### Linux

```bash
# Recommended: Use the provided build script (handles everything automatically)
python3 build_executable.py

# Or manually with pyinstaller (includes FFmpeg if found in PATH):
# Note: Replace /usr/bin/ffmpeg and /usr/bin/ffprobe with your FFmpeg paths (use `which ffmpeg` to find them)
pyinstaller --onefile --noconsole --icon=icon.png --add-data="icon.png:." \
  --add-binary="$(which ffmpeg):ffmpeg" --add-binary="$(which ffprobe):ffprobe" \
  --name "ScreenMachine" main.py \
  --collect-all customtkinter --collect-all av --hidden-import av --hidden-import PIL._tkinter_finder

# Note: On Linux, you may need to install additional dependencies:
# sudo apt-get install python3-tk python3-dev
```

**Note:** The build script automatically creates `ScreenMachine.spec` with all dependencies, including FFmpeg binaries. If you run pyinstaller manually, you must include `--add-binary` flags for FFmpeg, or the executable will be smaller but won't work without FFmpeg installed on the target system. For Linux, the script will look for `icon.png` first, then fall back to `icon.ico` if available.

The executable will be created in the `dist` folder and can be distributed without requiring Python.

#### Running the Linux Executable

After building, run the executable:

```bash
# Make the executable executable (if needed)
chmod +x dist/ScreenMachine

# Run the executable
./dist/ScreenMachine
```

**Note:** On Linux, you may need to make the file executable with `chmod +x` if it doesn't have execute permissions. The executable is a standalone file and doesn't require Python or any dependencies to be installed.

## How It Works

1. Select an input directory containing video files
2. Configure grid layout (rows and columns)
3. Set screenshot size (max width/height)
4. Adjust JPG quality
5. Choose which metadata labels to include
6. Select whether to overwrite existing images
7. Click "Start Processing"

The application will:
- Scan for all video files in the selected directory (recursively)
- For each video, extract screenshots at evenly spaced intervals
- Resize screenshots to fit within specified dimensions
- Assemble screenshots into a grid layout
- Add metadata labels at the top (if enabled)
- Save the result as a JPG file with the same name as the video

Output files are saved as: `[video_name].jpg`

## Configuration Options

- **Grid Layout**: Number of rows and columns for the screenshot grid
- **Screenshot Size**: Maximum width and height for each screenshot
- **JPG Quality**: Compression quality (1-100)
- **Metadata Labels**: Toggle individual labels on/off
- **Overwrite Existing**: Whether to overwrite existing output files

## Logging

The application uses a configurable logging system with four log levels:

- **DEBUG**: Detailed diagnostic information (frame-by-frame extraction details)
- **INFO**: General informational messages (fallback messages, processing status)
- **WARNING**: Warnings that don't stop processing (partial frame extraction, corrupt videos)
- **ERROR**: Serious errors that prevent processing (failed file opens, no video streams)

### Setting Log Level

The log level can be set via the `LOG_LEVEL` environment variable:

```bash
# Windows (Command Prompt)
set LOG_LEVEL=WARNING
python main.py

# Windows (PowerShell)
$env:LOG_LEVEL="WARNING"
python main.py

# Linux/Mac
export LOG_LEVEL=WARNING
python main.py
```

**Default log level**: `WARNING` (only warnings and errors are shown)

### Log Level Examples

- `DEBUG`: Show all messages including detailed frame extraction info
- `INFO`: Show informational messages and above (including fallback messages)
- `WARNING`: Show warnings and errors only (default, recommended for normal use)
- `ERROR`: Show only serious errors
- `NONE`: Disable all logging

## Notes

- The number of screenshots extracted is determined by the grid size (rows × columns)
- Screenshots are evenly distributed throughout the video duration
- Screenshots maintain aspect ratio when resized
- The application processes videos sequentially (one at a time)
- Partial frame extraction warnings are normal for corrupt or incomplete video files

