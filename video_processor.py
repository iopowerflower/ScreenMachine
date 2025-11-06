"""
Video processing module for extracting screenshots and metadata from video files.
Uses PyAV (FFmpeg bindings) and FFmpeg subprocess for efficient video decoding.
"""
import os
import time
import subprocess
import signal
import sys
import threading

# Windows-specific subprocess flag to suppress console windows
if sys.platform == 'win32':
    CREATE_NO_WINDOW = subprocess.CREATE_NO_WINDOW
else:
    CREATE_NO_WINDOW = 0

try:
    import av
    PYAV_AVAILABLE = True
except ImportError:
    PYAV_AVAILABLE = False

from typing import List, Tuple, Optional, Dict
from PIL import Image
from config import get_video_extensions
from logger import debug, info, warning, error, critical_error

# Cache for file sizes to avoid redundant os.path.getsize() calls
_file_size_cache: Dict[str, int] = {}

# Lock for FFmpeg download to prevent concurrent downloads
_ffmpeg_download_lock = threading.Lock()
_ffmpeg_downloading = False


def check_ffmpeg_available():
    """
    Check if FFmpeg and ffprobe are available, downloading if needed.
    Returns tuple (ffmpeg_path, ffprobe_path) or (None, None) if unavailable.
    """
    global _ffmpeg_download_lock, _ffmpeg_downloading
    
    ffmpeg_path = None
    ffprobe_path = None
    
    # Check if binaries exist next to executable (downloaded at runtime)
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
    else:
        exe_dir = os.path.dirname(__file__)
    
    exe_dir_ffmpeg = os.path.join(exe_dir, 'ffmpeg.exe' if sys.platform == 'win32' else 'ffmpeg')
    exe_dir_ffprobe = os.path.join(exe_dir, 'ffprobe.exe' if sys.platform == 'win32' else 'ffprobe')
    
    # Check local files first
    if os.path.exists(exe_dir_ffmpeg) and os.path.exists(exe_dir_ffprobe):
        try:
            # Test both binaries
            test_ffmpeg = subprocess.run(
                [exe_dir_ffmpeg, '-version'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=2,
                creationflags=CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            test_ffprobe = subprocess.run(
                [exe_dir_ffprobe, '-version'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=2,
                creationflags=CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            if (test_ffmpeg.returncode in (0, 1) and test_ffprobe.returncode in (0, 1)):
                info(f"Found FFmpeg binaries next to executable", prefix="FFMPEG_CHECK")
                return exe_dir_ffmpeg, exe_dir_ffprobe
        except Exception as e:
            debug(f"Cannot execute FFmpeg from exe directory: {e}", prefix="FFMPEG_CHECK")
    
    # Check system PATH
    from shutil import which
    system_ffmpeg = which('ffmpeg')
    system_ffprobe = which('ffprobe')
    if system_ffmpeg and system_ffprobe:
        info(f"Found FFmpeg in system PATH", prefix="FFMPEG_CHECK")
        return system_ffmpeg, system_ffprobe
    
    # Try to download if running as frozen executable on Windows
    if getattr(sys, 'frozen', False) and sys.platform == 'win32':
        with _ffmpeg_download_lock:
            # Check again after acquiring lock (another thread might have downloaded)
            if os.path.exists(exe_dir_ffmpeg) and os.path.exists(exe_dir_ffprobe):
                info(f"FFmpeg binaries already downloaded", prefix="FFMPEG_CHECK")
                return exe_dir_ffmpeg, exe_dir_ffprobe
            
            if _ffmpeg_downloading:
                # Another thread is downloading, wait a bit and check again
                time.sleep(2)
                if os.path.exists(exe_dir_ffmpeg) and os.path.exists(exe_dir_ffprobe):
                    info(f"FFmpeg binaries downloaded by another thread", prefix="FFMPEG_CHECK")
                    return exe_dir_ffmpeg, exe_dir_ffprobe
            
            try:
                _ffmpeg_downloading = True
                info("FFmpeg not found. Attempting to download at runtime...", prefix="FFMPEG_CHECK")
                from ffmpeg_downloader import download_ffmpeg_windows
                
                # Show message to user
                try:
                    import tkinter.messagebox as mb
                    mb.showinfo(
                        "Downloading FFmpeg",
                        "FFmpeg not found. Downloading it now (this may take a minute)...\n\n"
                        "This is a one-time download. FFmpeg will be saved next to the executable."
                    )
                except:
                    pass  # GUI not available, continue anyway
                
                downloaded_ffmpeg, downloaded_ffprobe = download_ffmpeg_windows(exe_dir)
                
                if downloaded_ffmpeg and downloaded_ffprobe and \
                   os.path.exists(downloaded_ffmpeg) and os.path.exists(downloaded_ffprobe):
                    info(f"Successfully downloaded FFmpeg binaries", prefix="FFMPEG_CHECK")
                    return downloaded_ffmpeg, downloaded_ffprobe
            except ImportError:
                error("ffmpeg_downloader module not available", prefix="FFMPEG_CHECK")
            except Exception as e:
                error(f"Failed to download FFmpeg: {e}", prefix="FFMPEG_CHECK")
            finally:
                _ffmpeg_downloading = False
    
    warning("FFmpeg not found. Please install FFmpeg.", prefix="FFMPEG_CHECK")
    return None, None


def _get_ffmpeg_path():
    """Get FFmpeg executable path."""
    # Cache the path to avoid redundant checks
    if hasattr(_get_ffmpeg_path, '_cached_path'):
        return _get_ffmpeg_path._cached_path
    
    # First, check if binaries exist next to the executable (downloaded at runtime)
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
    else:
        exe_dir = os.path.dirname(__file__)
    
    exe_dir_ffmpeg = os.path.join(exe_dir, 'ffmpeg.exe' if sys.platform == 'win32' else 'ffmpeg')
    if os.path.exists(exe_dir_ffmpeg):
        try:
            test_result = subprocess.run(
                [exe_dir_ffmpeg, '-version'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=2,
                creationflags=CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            if test_result.returncode == 0 or test_result.returncode == 1:
                info(f"Found ffmpeg next to executable: {exe_dir_ffmpeg}", prefix="FFMPEG_PATH")
                _get_ffmpeg_path._cached_path = exe_dir_ffmpeg
                return exe_dir_ffmpeg
        except Exception as e:
            debug(f"Cannot execute ffmpeg from exe directory: {e}", prefix="FFMPEG_PATH")
    
    # Try system PATH
    from shutil import which
    system_ffmpeg = which('ffmpeg')
    if system_ffmpeg:
        info(f"Found ffmpeg in system PATH: {system_ffmpeg}", prefix="FFMPEG_PATH")
        _get_ffmpeg_path._cached_path = system_ffmpeg
        return system_ffmpeg
    
    # Final fallback - return 'ffmpeg' and let subprocess handle the error
    warning("FFmpeg not found. Please install FFmpeg.", prefix="FFMPEG_PATH")
    _get_ffmpeg_path._cached_path = 'ffmpeg'
    return 'ffmpeg'


def _get_ffprobe_path():
    """Get ffprobe executable path."""
    # Cache the path to avoid redundant checks
    if hasattr(_get_ffprobe_path, '_cached_path'):
        return _get_ffprobe_path._cached_path
    
    # First, check if binaries exist next to the executable (downloaded at runtime)
    if getattr(sys, 'frozen', False):
        exe_dir = os.path.dirname(sys.executable)
    else:
        exe_dir = os.path.dirname(__file__)
    
    exe_dir_ffprobe = os.path.join(exe_dir, 'ffprobe.exe' if sys.platform == 'win32' else 'ffprobe')
    if os.path.exists(exe_dir_ffprobe):
        try:
            test_result = subprocess.run(
                [exe_dir_ffprobe, '-version'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=2,
                creationflags=CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            if test_result.returncode == 0 or test_result.returncode == 1:
                info(f"Found ffprobe next to executable: {exe_dir_ffprobe}", prefix="FFPROBE_PATH")
                _get_ffprobe_path._cached_path = exe_dir_ffprobe
                return exe_dir_ffprobe
        except Exception as e:
            debug(f"Cannot execute ffprobe from exe directory: {e}", prefix="FFPROBE_PATH")
    
    # Try system PATH
    from shutil import which
    system_ffprobe = which('ffprobe')
    if system_ffprobe:
        info(f"Found ffprobe in system PATH: {system_ffprobe}", prefix="FFPROBE_PATH")
        _get_ffprobe_path._cached_path = system_ffprobe
        return system_ffprobe
    
    # Final fallback - return 'ffprobe' and let subprocess handle the error
    warning("ffprobe not found. Please install FFmpeg.", prefix="FFPROBE_PATH")
    _get_ffprobe_path._cached_path = 'ffprobe'
    return 'ffprobe'


def find_video_files(directory: str) -> List[str]:
    """
    Find all video files in the given directory.
    
    Args:
        directory: Path to directory to search
        
    Returns:
        List of video file paths
    """
    if not os.path.isdir(directory):
        return []
    
    video_extensions = get_video_extensions()
    video_files = []
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            if any(file.lower().endswith(ext) for ext in video_extensions):
                video_files.append(os.path.join(root, file))
    
    return sorted(video_files)


def _kill_process(process):
    """Kill a subprocess and its children."""
    try:
        if sys.platform == 'win32':
            # On Windows, use taskkill to kill the process tree
            subprocess.run(
                ['taskkill', '/F', '/T', '/PID', str(process.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
                creationflags=CREATE_NO_WINDOW
            )
        else:
            # On Unix, kill the process group
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
    except Exception as e:
        debug(f"Error killing process: {e}", prefix="PROCESS")


def get_metadata_ffprobe(video_path: str) -> Optional[Dict]:
    """
    Get video metadata using ffprobe.
    
    Args:
        video_path: Path to video file
        
    Returns:
        Dictionary with metadata or None if failed
    """
    ffprobe_path = _get_ffprobe_path()
    
    try:
        # Get video metadata using ffprobe
        cmd = [
            ffprobe_path,
            '-v', 'error',
            '-show_entries', 'format=duration,size,bit_rate',
            '-show_entries', 'stream=width,height,r_frame_rate,codec_name',
            '-of', 'json',
            video_path
        ]
        
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
            text=True,
            creationflags=CREATE_NO_WINDOW if sys.platform == 'win32' else 0
        )
        
        if result.returncode != 0:
            error(f"ffprobe failed for {os.path.basename(video_path)}: {result.stderr}", prefix="FFPROBE")
            return None
        
        import json
        data = json.loads(result.stdout)
        
        # Extract metadata
        format_info = data.get('format', {})
        streams = data.get('streams', [])
        
        # Find video stream
        video_stream = None
        for stream in streams:
            if stream.get('codec_type') == 'video':
                video_stream = stream
                break
        
        if not video_stream:
            error(f"No video stream found in {os.path.basename(video_path)}", prefix="FFPROBE")
            return None
        
        # Parse duration
        duration_str = format_info.get('duration', '0')
        try:
            duration = float(duration_str)
        except (ValueError, TypeError):
            duration = 0.0
        
        # Parse frame rate
        fps_str = video_stream.get('r_frame_rate', '0/1')
        try:
            num, den = map(int, fps_str.split('/'))
            fps = num / den if den > 0 else 0.0
        except (ValueError, ZeroDivisionError):
            fps = 0.0
        
        # Get resolution
        width = video_stream.get('width', 0)
        height = video_stream.get('height', 0)
        
        metadata = {
            'duration': duration,
            'fps': fps,
            'width': width,
            'height': height,
            'codec': video_stream.get('codec_name', 'unknown')
        }
        
        return metadata
        
    except FileNotFoundError:
        error(f"ffprobe not found. Please install FFmpeg.", prefix="FFPROBE")
        return None
    except subprocess.TimeoutExpired:
        error(f"ffprobe timed out for {os.path.basename(video_path)}", prefix="FFPROBE")
        return None
    except Exception as e:
        error(f"Exception in get_metadata_ffprobe for {os.path.basename(video_path)}: {e}", prefix="FFPROBE")
        return None


def get_video_metadata(video_path: str, file_size: int = None) -> Optional[Dict]:
    """
    Get video metadata from file.
    
    Args:
        video_path: Path to video file
        file_size: Optional file size (to avoid redundant os.path.getsize calls)
        
    Returns:
        Dictionary with metadata or None if failed
    """
    try:
        # Try PyAV first (faster, no subprocess)
        if PYAV_AVAILABLE:
            try:
                import av
                container = av.open(video_path)
                
                # Get video stream
                video_stream = None
                for stream in container.streams.video:
                    video_stream = stream
                    break
                
                if not video_stream:
                    debug(f"No video stream found in {video_path}", prefix="METADATA")
                    container.close()
                    return None
                
                # Get duration
                duration = float(container.duration) / av.time_base if container.duration else 0.0
                
                # Get FPS
                fps = float(video_stream.average_rate) if video_stream.average_rate else 0.0
                
                # Get resolution
                width = video_stream.width
                height = video_stream.height
                
                # Get codec
                codec = video_stream.codec.name if video_stream.codec else 'unknown'
                
                container.close()
                
                metadata = {
                    'duration': duration,
                    'fps': fps,
                    'width': width,
                    'height': height,
                    'codec': codec
                }
                
                return metadata
                
            except Exception as e:
                debug(f"PyAV failed for {os.path.basename(video_path)}, trying ffprobe: {e}", prefix="METADATA")
        
        # Fallback to ffprobe
        return get_metadata_ffprobe(video_path)
        
    except Exception as e:
        error(f"get_video_metadata failed for {os.path.basename(video_path)}: {e}", prefix="VIDEO_METADATA")
        return None


def resize_image(image: Image.Image, max_width: int, max_height: int) -> Image.Image:
    """
    Resize an image maintaining aspect ratio.
    
    Args:
        image: PIL Image to resize
        max_width: Maximum width
        max_height: Maximum height
        
    Returns:
        Resized PIL Image
    """
    if not image:
        return image
    
    width, height = image.size
    
    # Calculate new size maintaining aspect ratio
    if width <= max_width and height <= max_height:
        return image
    
    ratio = min(max_width / width, max_height / height)
    new_width = int(width * ratio)
    new_height = int(height * ratio)
    
    return image.resize((new_width, new_height), Image.Resampling.LANCZOS)


def extract_screenshots_pyav(video_path: str, num_screenshots: int,
                             max_width: int, max_height: int,
                             preview_callback=None, full_resolution: bool = False,
                             original_resolution: bool = False,
                             duration: float = None, fps: float = None) -> Optional[List[Image.Image]]:
    """
    Internal function: Extract screenshots using PyAV (FFmpeg Python bindings).
    
    Args:
        video_path: Path to video file
        num_screenshots: Number of screenshots to extract
        max_width: Maximum width for screenshots
        max_height: Maximum height for screenshots
        preview_callback: Optional callback function(path, frame_index, total) for preview updates
        full_resolution: If True, extract at full resolution (ignores max_width/max_height)
        original_resolution: If True, keep original resolution (ignores max_width/max_height)
        duration: Video duration in seconds (optional, for better frame selection)
        fps: Video FPS (optional, for better frame selection)
        
    Returns:
        List of PIL Images or None if failed
    """
    if not PYAV_AVAILABLE:
        return None
    
    try:
        import av
        
        container = av.open(video_path)
        video_stream = None
        
        for stream in container.streams.video:
            video_stream = stream
            break
        
        if not video_stream:
            container.close()
            return None
        
        # Get actual duration and FPS if not provided
        if duration is None:
            duration = float(container.duration) / av.time_base if container.duration else 0.0
        if fps is None:
            fps = float(video_stream.average_rate) if video_stream.average_rate else 0.0
        
        # Calculate timestamps for screenshots
        if duration > 0 and num_screenshots > 0:
            # Distribute screenshots evenly across the video
            step = duration / (num_screenshots + 1)
            timestamps = [step * (i + 1) for i in range(num_screenshots)]
        else:
            # Fallback: extract from beginning
            timestamps = [0.0] * num_screenshots
        
        screenshots = []
        frames_seen = 0
        
        for timestamp in timestamps:
            # Seek to timestamp
            container.seek(int(timestamp * av.time_base))
            
            # Extract frame
            for frame in container.decode(video_stream):
                if frame.time >= timestamp or frames_seen == 0:
                    # Convert to PIL Image
                    img = frame.to_image()
                    
                    # Resize if needed
                    if not full_resolution and not original_resolution:
                        img = resize_image(img, max_width, max_height)
                    
                    screenshots.append(img)
                    
                    # Call preview callback if provided
                    if preview_callback:
                        try:
                            preview_callback(video_path, len(screenshots), num_screenshots)
                        except:
                            pass
                    
                    break
                frames_seen += 1
        
        container.close()
        return screenshots if screenshots else None
        
    except Exception as e:
        error(f"PyAV extraction failed for {os.path.basename(video_path)}: {e}", prefix="PYAV")
        return None


def extract_screenshots_ffmpeg(video_path: str, num_screenshots: int,
                               max_width: int, max_height: int,
                               preview_callback=None, full_resolution: bool = False,
                               original_resolution: bool = False,
                               duration: float = None, fps: float = None) -> Optional[List[Image.Image]]:
    """
    Internal function: Extract screenshots using ffmpeg subprocess.
    
    Args:
        video_path: Path to video file
        num_screenshots: Number of screenshots to extract
        max_width: Maximum width for screenshots
        max_height: Maximum height for screenshots
        preview_callback: Optional callback function(path, frame_index, total) for preview updates
        full_resolution: If True, extract at full resolution (ignores max_width/max_height)
        original_resolution: If True, keep original resolution (ignores max_width/max_height)
        duration: Video duration in seconds (optional, for better frame selection)
        fps: Video FPS (optional, for better frame selection)
        
    Returns:
        List of PIL Images or None if failed
    """
    ffmpeg_path = _get_ffmpeg_path()
    
    try:
        # Calculate timestamps for screenshots
        if duration and duration > 0 and num_screenshots > 0:
            # Distribute screenshots evenly across the video
            step = duration / (num_screenshots + 1)
            timestamps = [step * (i + 1) for i in range(num_screenshots)]
        else:
            # Fallback: extract from beginning
            timestamps = [0.0] * num_screenshots
        
        screenshots = []
        
        for i, timestamp in enumerate(timestamps):
            try:
                # Build ffmpeg command
                cmd = [
                    ffmpeg_path,
                    '-ss', str(timestamp),
                    '-i', video_path,
                    '-vframes', '1',
                    '-f', 'image2pipe',
                    '-vcodec', 'png',
                    '-'
                ]
                
                # Add scaling if needed
                if not full_resolution and not original_resolution:
                    cmd.insert(-1, '-vf')
                    cmd.insert(-1, f'scale={max_width}:{max_height}:force_original_aspect_ratio=decrease')
                
                # Run ffmpeg
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=30,
                    creationflags=CREATE_NO_WINDOW if sys.platform == 'win32' else 0
                )
                
                if result.returncode != 0:
                    warning(f"ffmpeg failed for frame {i+1} at {timestamp:.2f}s: {result.stderr.decode('utf-8', errors='ignore')[:200]}", prefix="FFmpeg")
                    continue
                
                # Load image from bytes
                from io import BytesIO
                img = Image.open(BytesIO(result.stdout))
                screenshots.append(img)
                
                # Call preview callback if provided
                if preview_callback:
                    try:
                        preview_callback(video_path, len(screenshots), num_screenshots)
                    except:
                        pass
                
            except subprocess.TimeoutExpired:
                warning(f"Timeout extracting frame @ {timestamp:.2f}s for {os.path.basename(video_path)}, killing process", prefix="FFmpeg")
                # Skip this frame if extraction fails
                continue
            except Exception as e:
                warning(f"Error extracting frame @ {timestamp:.2f}s for {os.path.basename(video_path)}: {e}", prefix="FFmpeg")
                # Skip this frame if extraction fails
                continue
        
        return screenshots if screenshots else None
        
    except FileNotFoundError:
        error(f"ffmpeg not found. Please install FFmpeg.", prefix="FFmpeg")
        return None
    except Exception as e:
        error(f"Exception in extract_screenshots_ffmpeg for {os.path.basename(video_path)}: {e}", prefix="FFmpeg")
        return None


def extract_screenshots(video_path: str, num_screenshots: int,
                       max_width: int, max_height: int,
                       preview_callback=None, full_resolution: bool = False,
                       original_resolution: bool = False,
                       duration: float = None, fps: float = None) -> Optional[List[Image.Image]]:
    """
    Extract screenshots from a video file.
    
    Args:
        video_path: Path to video file
        num_screenshots: Number of screenshots to extract
        max_width: Maximum width for screenshots
        max_height: Maximum height for screenshots
        preview_callback: Optional callback function(path, frame_index, total) for preview updates
        full_resolution: If True, extract at full resolution (ignores max_width/max_height)
        original_resolution: If True, keep original resolution (ignores max_width/max_height)
        duration: Video duration in seconds (optional, for better frame selection)
        fps: Video FPS (optional, for better frame selection)
        
    Returns:
        List of PIL Images or None if failed
    """
    
    # Try PyAV first (best performance - network-efficient + no subprocess overhead)
    if PYAV_AVAILABLE:
        try:
            result = extract_screenshots_pyav(
                video_path, num_screenshots, max_width, max_height,
                preview_callback, full_resolution,
                original_resolution, duration, fps
            )
            if result and len(result) > 0:
                return result
        except Exception as e:
            debug(f"PyAV extraction failed, falling back to ffmpeg: {e}", prefix="EXTRACT")
    
    # Fallback to ffmpeg subprocess
    return extract_screenshots_ffmpeg(
        video_path, num_screenshots, max_width, max_height,
        preview_callback, full_resolution,
        original_resolution, duration, fps
    )
