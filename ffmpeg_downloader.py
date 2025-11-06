"""
Download FFmpeg binaries at runtime if not found.
Downloads static builds that don't require external dependencies.
"""
import os
import sys
import urllib.request
import zipfile
import shutil
import tempfile
from pathlib import Path

# Try to import logger for better logging
try:
    from logger import info, warning, error, debug
except ImportError:
    # Fallback if logger not available
    def info(msg, prefix=""): print(f"[INFO] {prefix}: {msg}" if prefix else f"[INFO] {msg}")
    def warning(msg, prefix=""): print(f"[WARN] {prefix}: {msg}" if prefix else f"[WARN] {msg}")
    def error(msg, prefix=""): print(f"[ERROR] {prefix}: {msg}" if prefix else f"[ERROR] {msg}")
    def debug(msg, prefix=""): pass


def download_ffmpeg_windows(exe_dir: str, show_progress_callback=None):
    """
    Download FFmpeg static binaries for Windows.
    
    Args:
        exe_dir: Directory where the executable is located (where to place binaries)
        show_progress_callback: Optional callback function(percent) to show progress
        
    Returns:
        Tuple of (ffmpeg_path, ffprobe_path) or (None, None) if failed
    """
    # Use BtbN FFmpeg builds - reliable, well-maintained static builds
    # Using the latest GPL build (fully featured)
    url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
    
    info("Downloading FFmpeg binaries...", prefix="FFMPEG_DOWNLOAD")
    info(f"Source: {url}", prefix="FFMPEG_DOWNLOAD")
    info(f"Destination: {exe_dir}", prefix="FFMPEG_DOWNLOAD")
    
    # Create temp directory for download
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, "ffmpeg.zip")
    
    try:
        # Download
        info("Downloading... (this may take a minute)", prefix="FFMPEG_DOWNLOAD")
        
        def progress_hook(block_num, block_size, total_size):
            if total_size > 0:
                percent = min(100, (block_num * block_size * 100) // total_size)
                if show_progress_callback:
                    show_progress_callback(percent)
                else:
                    # Fallback to logging
                    if block_num % 10 == 0:  # Log every 10 blocks to avoid spam
                        debug(f"Download progress: {percent}%", prefix="FFMPEG_DOWNLOAD")
        
        urllib.request.urlretrieve(url, zip_path, reporthook=progress_hook)
        info("Download complete!", prefix="FFMPEG_DOWNLOAD")
        
        # Extract
        info("Extracting...", prefix="FFMPEG_DOWNLOAD")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # Find bin directory in zip
            members = zip_ref.namelist()
            bin_members = [m for m in members if '/bin/' in m and (m.endswith('ffmpeg.exe') or m.endswith('ffprobe.exe'))]
            
            if not bin_members:
                raise ValueError("Could not find ffmpeg.exe or ffprobe.exe in downloaded zip")
            
            # Extract to temp directory first
            extract_temp = os.path.join(temp_dir, "extract")
            os.makedirs(extract_temp, exist_ok=True)
            
            for member in bin_members:
                zip_ref.extract(member, extract_temp)
            
            # Find the actual exe files in the extracted structure
            for root, dirs, files in os.walk(extract_temp):
                for file in files:
                    if file in ('ffmpeg.exe', 'ffprobe.exe'):
                        src_path = os.path.join(root, file)
                        dst_path = os.path.join(exe_dir, file)
                        shutil.move(src_path, dst_path)
                        info(f"Extracted: {file}", prefix="FFMPEG_DOWNLOAD")
        
        # Verify files exist
        ffmpeg_path = os.path.join(exe_dir, 'ffmpeg.exe')
        ffprobe_path = os.path.join(exe_dir, 'ffprobe.exe')
        
        if os.path.exists(ffmpeg_path) and os.path.exists(ffprobe_path):
            info("FFmpeg binaries downloaded successfully!", prefix="FFMPEG_DOWNLOAD")
            return ffmpeg_path, ffprobe_path
        else:
            raise ValueError("Downloaded files not found")
            
    except Exception as e:
        error(f"Error downloading FFmpeg: {e}", prefix="FFMPEG_DOWNLOAD")
        warning("You can manually download FFmpeg from:", prefix="FFMPEG_DOWNLOAD")
        warning("https://github.com/BtbN/FFmpeg-Builds/releases", prefix="FFMPEG_DOWNLOAD")
        warning("Extract ffmpeg.exe and ffprobe.exe to the same directory as the executable.", prefix="FFMPEG_DOWNLOAD")
        return None, None
    finally:
        # Clean up temp directory
        try:
            shutil.rmtree(temp_dir)
        except:
            pass


if __name__ == "__main__":
    # Test download
    if sys.platform == 'win32':
        test_dir = os.path.dirname(__file__)
        download_ffmpeg_windows(test_dir)
    else:
        print("This script currently only supports Windows.")
