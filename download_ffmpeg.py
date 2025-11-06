"""
Download FFmpeg static binaries for bundling with the executable.
Uses static builds that don't require external dependencies.
"""
import os
import sys
import urllib.request
import zipfile
import shutil
from pathlib import Path


def download_ffmpeg_windows():
    """Download FFmpeg static binaries for Windows."""
    # Using BtbN FFmpeg builds (commonly used, reliable)
    # Direct download from GitHub releases
    url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
    
    print("Downloading FFmpeg static binaries for Windows...")
    print(f"URL: {url}")
    
    ffmpeg_dir = Path("ffmpeg_bin")
    ffmpeg_dir.mkdir(exist_ok=True)
    
    zip_path = ffmpeg_dir / "ffmpeg.zip"
    
    try:
        # Download
        print("Downloading... (this may take a minute)")
        urllib.request.urlretrieve(url, zip_path)
        print(f"Downloaded to: {zip_path}")
        
        # Extract
        print("Extracting...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # Find the bin directory in the zip
            members = zip_ref.namelist()
            bin_members = [m for m in members if '/bin/' in m and (m.endswith('ffmpeg.exe') or m.endswith('ffprobe.exe'))]
            
            if not bin_members:
                raise ValueError("Could not find ffmpeg.exe or ffprobe.exe in downloaded zip")
            
            # Extract only the exe files
            for member in bin_members:
                # Get just the filename
                filename = os.path.basename(member)
                zip_ref.extract(member, ffmpeg_dir)
                # Move to top level of ffmpeg_bin
                extracted_path = ffmpeg_dir / member.replace('ffmpeg-master-latest-win64-gpl/', '')
                if extracted_path.exists():
                    final_path = ffmpeg_dir / filename
                    if final_path.exists():
                        final_path.unlink()
                    shutil.move(str(extracted_path), str(final_path))
        
        # Clean up zip
        zip_path.unlink()
        
        # Clean up extracted directory structure
        for item in ffmpeg_dir.iterdir():
            if item.is_dir() and item.name != 'ffmpeg_bin':
                shutil.rmtree(item)
        
        print(f"✅ FFmpeg binaries extracted to: {ffmpeg_dir}")
        print(f"   - ffmpeg.exe: {(ffmpeg_dir / 'ffmpeg.exe').exists()}")
        print(f"   - ffprobe.exe: {(ffmpeg_dir / 'ffprobe.exe').exists()}")
        
        return ffmpeg_dir / "ffmpeg.exe", ffmpeg_dir / "ffprobe.exe"
        
    except Exception as e:
        print(f"❌ Error downloading FFmpeg: {e}")
        print("\nYou can manually download FFmpeg from:")
        print("https://github.com/BtbN/FFmpeg-Builds/releases")
        print("Extract ffmpeg.exe and ffprobe.exe to a 'ffmpeg_bin' folder in this directory.")
        return None, None


if __name__ == "__main__":
    if sys.platform == 'win32':
        download_ffmpeg_windows()
    else:
        print("This script currently only supports Windows.")
        print("For other platforms, install FFmpeg system-wide or provide static binaries.")
