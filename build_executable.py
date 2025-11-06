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
    # First, check for bundled binaries in project directory
    ffmpeg_bin_dir = os.path.join(os.path.dirname(__file__), 'ffmpeg_bin')
    bundled_ffmpeg = os.path.join(ffmpeg_bin_dir, 'ffmpeg.exe' if sys.platform == 'win32' else 'ffmpeg')
    bundled_ffprobe = os.path.join(ffmpeg_bin_dir, 'ffprobe.exe' if sys.platform == 'win32' else 'ffprobe')
    
    if os.path.exists(bundled_ffmpeg) and os.path.exists(bundled_ffprobe):
        print(f"Found bundled FFmpeg binaries in: {ffmpeg_bin_dir}")
        return bundled_ffmpeg, bundled_ffprobe
    
    # Fall back to system PATH
    ffmpeg = shutil.which('ffmpeg')
    ffprobe = shutil.which('ffprobe')
    return ffmpeg, ffprobe




def build_executable():
    
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
    # Use --onefile for a single executable (smaller distribution)
    # Users must have FFmpeg installed separately anyway
    cmd = [
        'pyinstaller',
        '--onefile',                    # Single executable file
        console_flag,                   # No console window (GUI only)
        f'--name={exe_name}',          # Name of the executable
        'main.py'
    ]
    
    # Try UPX compression if available (can reduce size by 30-50%)
    # This is optional - if UPX isn't installed, PyInstaller will skip it
    try:
        import shutil
        if shutil.which('upx'):
            cmd.append('--upx-dir=upx')  # Use UPX if available
            print("ℹ️  UPX compression will be used if available")
    except:
        pass  # UPX is optional
    
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
    
    # Don't bundle FFmpeg binaries - they're huge and users should install separately
    # The executable will look for FFmpeg in system PATH at runtime
    
    # Additional options for better compatibility
    cmd.extend([
        '--collect-all', 'customtkinter',  # Include all customtkinter data
        '--collect-all', 'av',             # Include all PyAV data
        '--hidden-import', 'PIL._tkinter_finder',  # PIL/tkinter compatibility
        '--hidden-import', 'av',            # Ensure PyAV is included
        '--hidden-import', 'logger',       # Ensure logger module is included
        '--hidden-import', 'config',       # Ensure config module is included
        '--hidden-import', 'video_processor',  # Ensure video_processor is included
        '--hidden-import', 'image_composer',    # Ensure image_composer is included
        '--hidden-import', 'utils',        # Ensure utils module is included
        '--hidden-import', 'ffmpeg_downloader',  # Include FFmpeg downloader
    ])
    
    try:
        subprocess.run(cmd, check=True)
        print("\nBuild complete!")
        
        dist_dir = 'dist'
        exe_path = os.path.join(dist_dir, f"{exe_name}{exe_ext}")
        
        print(f"Executable location: {exe_path}")
        
        # Check file size
        if os.path.exists(exe_path):
            size_mb = os.path.getsize(exe_path) / (1024 * 1024)
            print(f"Executable size: {size_mb:.1f} MB")

    except subprocess.CalledProcessError as e:
        print(f"Error building executable: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print("Error: PyInstaller not found. Install it with: pip install pyinstaller")
        sys.exit(1)


if __name__ == "__main__":
    build_executable()

