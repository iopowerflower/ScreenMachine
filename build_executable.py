"""
Build script for creating a standalone executable using PyInstaller.
Bundles FFmpeg and all dependencies into a single executable.
"""
import subprocess
import sys
import os
import shutil


def find_ffmpeg():
    """Find ffmpeg and ffprobe executables."""
    ffmpeg = shutil.which('ffmpeg')
    ffprobe = shutil.which('ffprobe')
    return ffmpeg, ffprobe




def build_executable():
    """Build the executable using PyInstaller with FFmpeg bundled."""
    print("Building executable with FFmpeg bundled...")
    
    # Find FFmpeg executables
    ffmpeg_path, ffprobe_path = find_ffmpeg()
    
    if not ffmpeg_path or not ffprobe_path:
        print("WARNING: FFmpeg not found in PATH. The executable will still work,")
        print("but FFmpeg extraction will require FFmpeg to be installed separately.")
        print("For best results, install FFmpeg and ensure it's in your PATH.")
        print()
    
    # Determine separator for add-data (Windows uses ;, Unix uses :)
    separator = ';' if sys.platform == 'win32' else ':'
    
    # Determine executable name and extension
    if sys.platform == 'win32':
        exe_name = 'ScreenMachine'
        exe_ext = '.exe'
        console_flag = '--windowed'  # No console window on Windows
    else:
        exe_name = 'ScreenMachine'
        exe_ext = ''  # Linux/Mac don't use extensions
        console_flag = '--noconsole'  # No console window on Linux/Mac
    
    # PyInstaller command
    cmd = [
        'pyinstaller',
        '--onefile',                    # Single executable file
        console_flag,                   # No console window (GUI only)
        f'--name={exe_name}',          # Name of the executable
        'main.py'
    ]
    
    # Add icon if it exists (try .ico for Windows, .png for Linux/Mac)
    icon_path = None
    if sys.platform == 'win32':
        icon_path = os.path.join(os.path.dirname(__file__), 'icon.ico')
    else:
        # Try .png first (common on Linux), fallback to .ico
        icon_path = os.path.join(os.path.dirname(__file__), 'icon.png')
        if not os.path.exists(icon_path):
            icon_path = os.path.join(os.path.dirname(__file__), 'icon.ico')
    
    if icon_path and os.path.exists(icon_path):
        # Use absolute path for icon to avoid issues
        icon_path_abs = os.path.abspath(icon_path)
        cmd.append(f'--icon={icon_path_abs}')
        # Also add icon as a data file so it's accessible at runtime
        cmd.append(f'--add-data={icon_path_abs}{separator}.')
        print(f"Found icon: {icon_path_abs}")
        print("Icon will be included in the executable and bundled as data.")
        print()
    
    # Add FFmpeg binaries if found
    if ffmpeg_path and ffprobe_path:
        cmd.extend([
            f'--add-binary={ffmpeg_path}{separator}ffmpeg',
            f'--add-binary={ffprobe_path}{separator}ffprobe',
        ])
        print(f"Found FFmpeg: {ffmpeg_path}")
        print(f"Found ffprobe: {ffprobe_path}")
        print("FFmpeg will be bundled with the executable.")
        print()
    
    # Additional options for better compatibility
    cmd.extend([
        '--collect-all', 'customtkinter',  # Include all customtkinter data
        '--collect-all', 'av',             # Include all PyAV data
        '--hidden-import', 'PIL._tkinter_finder',  # PIL/tkinter compatibility
        '--hidden-import', 'av',            # Ensure PyAV is included
    ])
    
    try:
        subprocess.run(cmd, check=True)
        print("\nBuild complete!")
        print(f"Executable location: dist/{exe_name}{exe_ext}")
        print("\nNote: The executable may be quite large (~100-200MB) due to bundled dependencies.")
        if ffmpeg_path:
            print("FFmpeg is bundled - no separate installation required!")
        else:
            print("WARNING: FFmpeg was not bundled. Users will need to install FFmpeg separately.")
    except subprocess.CalledProcessError as e:
        print(f"Error building executable: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print("Error: PyInstaller not found. Install it with: pip install pyinstaller")
        sys.exit(1)


if __name__ == "__main__":
    build_executable()

