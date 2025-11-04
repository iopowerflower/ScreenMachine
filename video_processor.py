"""
Video processing module for extracting screenshots and metadata from video files.
Uses PyAV (FFmpeg bindings) and FFmpeg subprocess for efficient video decoding.
"""
import os
import time
import subprocess
import signal
import sys

try:
    import av
    PYAV_AVAILABLE = True
except ImportError:
    PYAV_AVAILABLE = False

from typing import List, Tuple, Optional, Dict
from PIL import Image
from config import get_video_extensions
from logger import debug, info, warning, error

# Cache for file sizes to avoid redundant os.path.getsize() calls
_file_size_cache: Dict[str, int] = {}


def _get_ffmpeg_path():
    """Get FFmpeg executable path, checking bundled location first."""
    # Check if we're in a PyInstaller bundle
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # We're in a PyInstaller bundle - check bundled location
        bundle_dir = sys._MEIPASS
        ffmpeg_path = os.path.join(bundle_dir, 'ffmpeg')
        if sys.platform == 'win32':
            ffmpeg_path += '.exe'
        if os.path.exists(ffmpeg_path):
            return ffmpeg_path
    
    # Not bundled or not found - use system PATH
    return 'ffmpeg'


def _get_ffprobe_path():
    """Get ffprobe executable path, checking bundled location first."""
    # Check if we're in a PyInstaller bundle
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # We're in a PyInstaller bundle - check bundled location
        bundle_dir = sys._MEIPASS
        ffprobe_path = os.path.join(bundle_dir, 'ffprobe')
        if sys.platform == 'win32':
            ffprobe_path += '.exe'
        if os.path.exists(ffprobe_path):
            return ffprobe_path
    
    # Not bundled or not found - use system PATH
    return 'ffprobe'


def find_video_files(directory: str) -> List[str]:
    """
    Recursively find all video files in the given directory and subdirectories.
    
    Args:
        directory: Root directory to search
        
    Returns:
        List of full paths to video files
    """
    video_files = []
    extensions = get_video_extensions()
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            _, ext = os.path.splitext(file_path.lower())
            if ext in extensions:
                video_files.append(file_path)
    
    return sorted(video_files)


def _kill_process(process):
    """Kill a process and its children (cross-platform)."""
    try:
        if sys.platform == 'win32':
            # Windows: use taskkill to kill the process tree (suppress window)
            subprocess.run(['taskkill', '/F', '/T', '/PID', str(process.pid)], 
                         capture_output=True, timeout=2,
                         creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            # Unix: use process group
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
    except Exception:
        pass
    finally:
        try:
            process.terminate()
            process.wait(timeout=1)
        except Exception:
            try:
                process.kill()
            except Exception:
                pass


def get_metadata_ffprobe(video_path: str) -> Optional[Dict]:
    """
    Get video metadata using ffprobe (fast, no decoding required).
    Uses Popen with proper cleanup to ensure processes are killed.
    
    Args:
        video_path: Path to the video file
        
    Returns:
        Dictionary with resolution, fps, duration, or None if ffprobe fails
    """
    process = None
    try:
        # Get resolution, fps, duration, codec, and frame count in one call
        ffprobe_path = _get_ffprobe_path()
        cmd = [
            ffprobe_path,
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height,r_frame_rate,nb_frames,codec_name,codec_long_name',
            '-show_entries', 'format=duration',
            '-of', 'json',
            video_path
        ]
        # Use Popen so we can properly kill the process if it hangs
        # Suppress console window on Windows
        startupinfo = None
        creation_flags = 0
        if sys.platform == 'win32':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            creation_flags = subprocess.CREATE_NO_WINDOW
        
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                  text=True, startupinfo=startupinfo, 
                                  creationflags=creation_flags)
        try:
            stdout, stderr = process.communicate(timeout=5)
            if process.returncode == 0 and stdout.strip():
                import json
                data = json.loads(stdout)
                
                # Extract stream info
                if 'streams' in data and len(data['streams']) > 0:
                    stream = data['streams'][0]
                    width = stream.get('width')
                    height = stream.get('height')
                    r_frame_rate = stream.get('r_frame_rate', '0/1')
                    nb_frames = stream.get('nb_frames')
                    codec_name = stream.get('codec_name', '').upper()
                    codec_long_name = stream.get('codec_long_name', '')
                    
                    # Calculate FPS from r_frame_rate (e.g., "30000/1001" = 29.97)
                    if r_frame_rate and '/' in r_frame_rate:
                        num, den = map(int, r_frame_rate.split('/'))
                        fps = num / den if den > 0 else 0
                    else:
                        fps = 0
                    
                    # Get duration from format
                    duration = 0
                    if 'format' in data and 'duration' in data['format']:
                        duration = float(data['format']['duration'])
                    elif nb_frames and fps > 0:
                        # Calculate from frame count
                        duration = int(nb_frames) / fps
                    
                    # Format codec name nicely
                    codec = codec_name
                    if codec_name:
                        # Map common codec names to user-friendly format
                        codec_map = {
                            'H264': 'H.264',
                            'H265': 'H.265',
                            'HEVC': 'H.265',
                            'AVC1': 'H.264',
                            'MPEG4': 'MPEG-4',
                            'MPEG2': 'MPEG-2',
                            'VP8': 'VP8',
                            'VP9': 'VP9',
                            'AV1': 'AV1',
                        }
                        codec = codec_map.get(codec_name, codec_name)
                    
                    if width and height:
                        return {
                            'resolution': (int(width), int(height)),
                            'fps': fps,
                            'duration': duration,
                            'codec': codec,
                            'nb_frames': int(nb_frames) if nb_frames else None
                        }
        except subprocess.TimeoutExpired:
            # Process is hanging - kill it
            warning(f"Timeout getting metadata for {os.path.basename(video_path)}, killing process", "ffprobe")
            _kill_process(process)
            return None
    except (FileNotFoundError, ValueError, Exception) as e:
        # ffprobe not available or failed
        if process:
            _kill_process(process)
    finally:
        if process and process.poll() is None:
            _kill_process(process)
    return None


def get_video_metadata(video_path: str, file_size: int = None) -> Optional[Dict]:
    """
    Extract metadata from a video file using ffprobe.
    
    Args:
        video_path: Path to the video file
        file_size: Optional file size in bytes (if already known, avoids os.path.getsize call)
        
    Returns:
        Dictionary containing metadata:
        - resolution: (width, height) tuple
        - duration: Duration in seconds
        - fps: Frames per second
        - codec: Codec string (if available from ffprobe)
        - file_size: File size in bytes
        - filename: Just the filename without path
    """
    global _file_size_cache
    
    # Get metadata using ffprobe (fast, no decoding required)
    ffprobe_metadata = get_metadata_ffprobe(video_path)
    
    if ffprobe_metadata:
        width, height = ffprobe_metadata['resolution']
        fps = ffprobe_metadata['fps']
        duration = ffprobe_metadata['duration']
        codec = ffprobe_metadata.get('codec', 'Unknown')
        
        # Get other metadata (file size, filename)
        # Use provided file_size if available, otherwise check cache, then fetch
        if file_size is None:
            # Check cache first
            if video_path in _file_size_cache:
                file_size = _file_size_cache[video_path]
            else:
                # Fetch file size and cache it
                file_size = os.path.getsize(video_path)
                _file_size_cache[video_path] = file_size  # Cache for future use
        else:
            # File size was provided, cache it for future use
            _file_size_cache[video_path] = file_size
        
        filename = os.path.basename(video_path)
        
        return {
            'resolution': (width, height),
            'duration': duration,
            'fps': fps,
            'codec': codec,
            'file_size': file_size,
            'filename': filename
        }
    
    # ffprobe failed - return None (no fallback)
    return None


def resize_image(image: Image.Image, max_width: int, max_height: int) -> Image.Image:
    """
    Resize an image maintaining aspect ratio, fitting within max dimensions.
    
    Args:
        image: PIL Image to resize
        max_width: Maximum width
        max_height: Maximum height
        
    Returns:
        Resized PIL Image
    """
    original_width, original_height = image.size
    
    # Calculate scaling factor to fit within max dimensions
    width_ratio = max_width / original_width
    height_ratio = max_height / original_height
    ratio = min(width_ratio, height_ratio)
    
    # Only resize if image is larger than max dimensions
    if ratio < 1.0:
        new_width = int(original_width * ratio)
        new_height = int(original_height * ratio)
        image = image.resize((new_width, new_height), Image.Resampling.NEAREST)
    
    return image


def extract_screenshots_pyav(video_path: str, num_screenshots: int,
                             max_width: int = None, max_height: int = None,
                             preview_callback=None,
                             full_resolution: bool = False,
                             original_resolution: tuple = None,
                             duration: float = None, fps: float = None) -> List[Tuple[Image.Image, float]]:
    """
    Internal function: Extract screenshots using PyAV (FFmpeg Python bindings).
    Called by extract_screenshots() - see that function for full parameter documentation.
    """
    if not PYAV_AVAILABLE:
        raise ImportError("PyAV not available. Install with: pip install av")
    
    # Get metadata if not provided
    if duration is None or fps is None:
        metadata = get_metadata_ffprobe(video_path)
        if metadata:
            duration = metadata.get('duration', 0)
            fps = metadata.get('fps', 0)
            if not original_resolution:
                original_resolution = metadata.get('resolution')
        else:
            metadata = get_video_metadata(video_path)
            if metadata:
                duration = metadata.get('duration', 0)
                fps = metadata.get('fps', 0)
                if not original_resolution:
                    original_resolution = metadata.get('resolution')
    
    if duration == 0 or num_screenshots == 0:
        return []
    
    # Calculate target timestamps (evenly distributed)
    if num_screenshots == 1:
        timestamps = [duration / 2]
    else:
        interval = duration / (num_screenshots + 1)
        timestamps = [interval * (i + 1) for i in range(num_screenshots)]
    
    # Calculate decode resolution if needed
    decode_width = None
    decode_height = None
    
    if max_width and max_height and original_resolution and not full_resolution:
        orig_w, orig_h = original_resolution
        orig_aspect = orig_w / orig_h if orig_h > 0 else 1.0
        
        target_w = max_width
        target_h = max_height
        
        if orig_aspect > (target_w / target_h):
            decode_width = target_w
            decode_height = int(target_w / orig_aspect)
        else:
            decode_height = target_h
            decode_width = int(target_h * orig_aspect)
    
    screenshots = []
    
    # OPTIMIZATION: Don't pre-scan for keyframes - it requires reading the entire file!
    # PyAV can seek efficiently on its own - it automatically finds the nearest keyframe.
    # Sort timestamps to minimize disk head movement on spinning disks
    timestamps_sorted = sorted(timestamps)
    
    # OPTIMIZATION: Open container once and reuse for all frames (much faster on spinning disks)
    # Opening/closing for each frame causes re-reading of headers/index on spinning disks
    container = None
    video_stream = None
    try:
        try:
            container = av.open(video_path)
            if not container or len(container.streams.video) == 0:
                error(f"No video stream found in {os.path.basename(video_path)}", "PyAV")
                return []
            video_stream = container.streams.video[0]
        except Exception as e:
            error(f"Failed to open {os.path.basename(video_path)}: {str(e)}", "PyAV")
            return []
        
        # Extract frames at each timestamp - PyAV will automatically find the nearest keyframe
        frames_found = 0
        frames_skipped = 0
        if len(timestamps_sorted) == 0:
            warning(f"No timestamps to extract for {os.path.basename(video_path)}", "PyAV")
            return []
        
        for i, timestamp in enumerate(timestamps_sorted):
            try:
                # Seek directly to timestamp - PyAV automatically finds nearest keyframe
                # Use any_frame=False to seek to keyframes (more efficient)
                try:
                    container.seek(int(timestamp * 1000000), any_frame=False)
                except Exception as seek_err:
                    if i < 3:  # Log first few seek errors
                        debug(f"Seek failed @ {timestamp:.2f}s: {str(seek_err)}", "PyAV")
                    frames_skipped += 1
                    continue
                
                # Decode frames - only need the first frame after seek
                best_frame = None
                frames_decoded = 0
                max_decode_time = 1.0  # Maximum time to spend decoding (1 second)
                decode_deadline = time.time() + max_decode_time
                
                try:
                    for frame in container.decode(video_stream):
                        if time.time() > decode_deadline:
                            if i < 3:  # Log first few timeouts
                                debug(f"Decode timeout @ {timestamp:.2f}s after {frames_decoded} frames", "PyAV")
                            break
                        frames_decoded += 1
                        best_frame = frame  # Take the first frame after seek
                        # Stop immediately after first frame - we don't need more
                        break
                except Exception as decode_err:
                    if i < 3:  # Log first few decode errors
                        debug(f"Decode error @ {timestamp:.2f}s: {str(decode_err)}", "PyAV")
                
                if best_frame is None:
                    frames_skipped += 1
                    if i < 3:  # Log first few failures
                        debug(f"No frame found @ {timestamp:.2f}s after seek, decoded {frames_decoded} frames", "PyAV")
                    continue
                
                frames_found += 1
                
                # Convert frame to PIL Image
                frame_array = best_frame.to_ndarray(format='rgb24')
                pil_image = Image.fromarray(frame_array)
                
                # Resize if needed
                if not full_resolution and max_width and max_height:
                    if original_resolution:
                        orig_w, orig_h = original_resolution
                        orig_aspect = orig_w / orig_h if orig_h > 0 else 1.0
                        
                        if orig_aspect > (max_width / max_height):
                            final_width = max_width
                            final_height = int(max_width / orig_aspect)
                        else:
                            final_height = max_height
                            final_width = int(max_height * orig_aspect)
                        
                        if pil_image.size != (final_width, final_height):
                            pil_image = pil_image.resize((final_width, final_height), Image.Resampling.NEAREST)
                    else:
                        pil_image = resize_image(pil_image, max_width, max_height)
                
                # Store with original timestamp
                screenshots.append((pil_image, timestamp))
                    
            except Exception as e:
                # Skip this frame if extraction fails
                frames_skipped += 1
                if i < 3:  # Log first few exceptions
                    debug(f"Exception extracting frame @ {timestamp:.2f}s: {str(e)}", "PyAV")
                continue
    finally:
        # Close container once after all frames are extracted
        if container:
            try:
                container.close()
            except:
                pass
    
    # Create mapping from timestamp to screenshots (screenshots already have original timestamps)
    timestamp_to_screenshot = {screenshot[1]: screenshot[0] for screenshot in screenshots}
    
    # Build final screenshots list using original timestamps (preserve order)
    final_screenshots = []
    for original_timestamp in timestamps:
        pil_image = timestamp_to_screenshot.get(original_timestamp)
        
        if pil_image:
            final_screenshots.append((pil_image, original_timestamp))
            
            if preview_callback:
                preview_callback(pil_image, original_timestamp)
    
    # Log summary if we got fewer frames than expected
    if len(final_screenshots) < num_screenshots:
        warning(f"Only extracted {len(final_screenshots)}/{num_screenshots} frames for {os.path.basename(video_path)} "
                f"(found: {frames_found}, skipped: {frames_skipped})", "PyAV")
    
    return final_screenshots


def extract_screenshots_ffmpeg(video_path: str, num_screenshots: int,
                                max_width: int = None, max_height: int = None,
                                preview_callback=None,
                                full_resolution: bool = False,
                                original_resolution: tuple = None,
                                duration: float = None, fps: float = None) -> List[Tuple[Image.Image, float]]:
    """
    Internal function: Extract screenshots using ffmpeg subprocess.
    Called by extract_screenshots() - see that function for full parameter documentation.
    """
    # Get metadata if not provided
    if duration is None or fps is None:
        metadata = get_metadata_ffprobe(video_path)
        if metadata:
            duration = metadata.get('duration', 0)
            fps = metadata.get('fps', 0)
            if not original_resolution:
                original_resolution = metadata.get('resolution')
        else:
            # Fallback: try to get from get_video_metadata (uses ffprobe)
            metadata = get_video_metadata(video_path)
            if metadata:
                duration = metadata.get('duration', 0)
                fps = metadata.get('fps', 0)
                if not original_resolution:
                    original_resolution = metadata.get('resolution')
    
    if duration == 0 or num_screenshots == 0:
        return []
    
    # Calculate target timestamps (evenly distributed)
    if num_screenshots == 1:
        timestamps = [duration / 2]
    else:
        interval = duration / (num_screenshots + 1)
        timestamps = [interval * (i + 1) for i in range(num_screenshots)]
    
    # Calculate decode resolution if needed
    decode_width = None
    decode_height = None
    scale_filter = None
    
    if max_width and max_height and original_resolution and not full_resolution:
        orig_w, orig_h = original_resolution
        orig_aspect = orig_w / orig_h if orig_h > 0 else 1.0
        
        target_w = max_width
        target_h = max_height
        
        # Calculate dimensions that fit within target while maintaining aspect ratio
        if orig_aspect > (target_w / target_h):
            decode_width = target_w
            decode_height = int(target_w / orig_aspect)
        else:
            decode_height = target_h
            decode_width = int(target_h * orig_aspect)
        
        scale_filter = f"scale={decode_width}:{decode_height}"
    
    screenshots = []
    
    # OPTIMIZATION: Sort timestamps to minimize disk head movement on spinning disks
    # This significantly improves performance when reading from spinning disks
    timestamps_sorted = sorted(timestamps)
    
    # Extract frames one at a time using -ss seeking (network-efficient, seeks directly to timestamps)
    for timestamp in timestamps_sorted:
        try:
            # Build ffmpeg command
            # -ss before -i enables input seeking (much faster, reads less data!)
            ffmpeg_path = _get_ffmpeg_path()
            cmd = [ffmpeg_path, '-v', 'error', '-ss', str(timestamp), '-i', video_path]
            
            # Add scale filter if decoding at lower resolution
            if scale_filter:
                cmd.extend(['-vf', scale_filter])
            
            # Output single frame as PNG to stdout
            cmd.extend(['-vframes', '1', '-f', 'image2pipe', '-vcodec', 'png', '-'])
            
            # Run ffmpeg with proper cleanup
            # Suppress console window on Windows
            startupinfo = None
            creation_flags = 0
            if sys.platform == 'win32':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                creation_flags = subprocess.CREATE_NO_WINDOW
            
            process = None
            stdout = None
            try:
                process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                          startupinfo=startupinfo, creationflags=creation_flags)
                # Use longer timeout for large videos (30 seconds should be enough for most)
                stdout, stderr = process.communicate(timeout=30)
                
                # Always ensure process is terminated, even after successful completion
                if process.poll() is None:
                    # Process still running somehow - kill it
                    _kill_process(process)
                
                if process.returncode != 0:
                    continue
            except subprocess.TimeoutExpired:
                warning(f"Timeout extracting frame @ {timestamp:.2f}s for {os.path.basename(video_path)}, killing process", "FFmpeg")
                if process:
                    _kill_process(process)
                continue
            except Exception as e:
                # Ensure process is killed on any exception
                if process:
                    _kill_process(process)
                continue
            finally:
                # Double-check: ensure process is always terminated
                if process:
                    try:
                        if process.poll() is None:
                            # Process still running - kill it aggressively
                            _kill_process(process)
                        # Ensure process handle is closed
                        process.wait(timeout=0.1)
                    except:
                        # If wait fails, process is already dead - that's fine
                        pass
            
            if stdout is None:
                continue
            
            # Load image from stdout
            from io import BytesIO
            image_data = BytesIO(stdout)
            pil_image = Image.open(image_data)
            
            # Convert to RGB if needed (video frames are typically RGB, but handle other modes)
            if pil_image.mode != 'RGB':
                pil_image = pil_image.convert('RGB')
            
            # Resize if needed (if we decoded at lower resolution, we may need to resize to exact target)
            if not full_resolution and max_width and max_height:
                if original_resolution:
                    orig_w, orig_h = original_resolution
                    orig_aspect = orig_w / orig_h if orig_h > 0 else 1.0
                    
                    # Calculate final dimensions maintaining aspect ratio
                    if orig_aspect > (max_width / max_height):
                        final_width = max_width
                        final_height = int(max_width / orig_aspect)
                    else:
                        final_height = max_height
                        final_width = int(max_height * orig_aspect)
                    
                    # Resize if different from decode size
                    if pil_image.size != (final_width, final_height):
                        pil_image = pil_image.resize((final_width, final_height), Image.Resampling.NEAREST)
                else:
                    # Standard resize
                    pil_image = resize_image(pil_image, max_width, max_height)
            
            screenshots.append((pil_image, timestamp))
                
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
            # Skip this frame if extraction fails
            continue
    
    # Create mapping from timestamp to screenshots (we extracted in sorted order)
    timestamp_to_screenshot = {screenshot[1]: screenshot[0] for screenshot in screenshots}
    
    # Build final screenshots list using original timestamps (preserve order)
    final_screenshots = []
    for original_timestamp in timestamps:
        pil_image = timestamp_to_screenshot.get(original_timestamp)
        
        if pil_image:
            final_screenshots.append((pil_image, original_timestamp))
            
            # Call preview callback if provided
            if preview_callback:
                preview_callback(pil_image, original_timestamp)
    
    return final_screenshots


def extract_screenshots(video_path: str, num_screenshots: int, 
                       max_width: int = None, max_height: int = None,
                       preview_callback=None,
                       full_resolution: bool = False,
                       original_resolution: tuple = None,
                       duration: float = None,
                       fps: float = None) -> List[Tuple[Image.Image, float]]:
    """
    Extract screenshots from a video at evenly spaced intervals.
    
    Uses PyAV (FFmpeg bindings) or FFmpeg subprocess for efficient video decoding.
    PyAV is preferred for better performance (no subprocess overhead).
    Falls back to FFmpeg subprocess if PyAV is not available or fails.
    
    Args:
        video_path: Path to the video file
        num_screenshots: Number of screenshots to extract
        max_width: Maximum width for each screenshot (ignored if full_resolution=True)
        max_height: Maximum height for each screenshot (ignored if full_resolution=True)
        preview_callback: Optional callback function(image, timestamp) called for each screenshot
        full_resolution: If True, return full-resolution frames without resizing
        original_resolution: Original video resolution tuple (width, height) for aspect ratio preservation
        duration: Video duration in seconds (if known, avoids extra ffprobe call)
        fps: Video FPS (if known, avoids extra ffprobe call)
        
    Returns:
        List of tuples (PIL Image, timestamp in seconds)
    """
    # Get metadata if not provided (avoid redundant calls)
    if duration is None or fps is None or not original_resolution:
        metadata = get_metadata_ffprobe(video_path)
        if not metadata:
            # If we need to call get_video_metadata, check cache for file_size first
            # This avoids redundant os.path.getsize() calls
            cached_file_size = _file_size_cache.get(video_path)
            metadata = get_video_metadata(video_path, file_size=cached_file_size)
        
        if not metadata:
            raise ValueError(f"Could not read metadata from video file: {video_path}")
        
        if duration is None:
            duration = metadata.get('duration', 0)
        if fps is None:
            fps = metadata.get('fps', 0)
        if not original_resolution:
            original_resolution = metadata.get('resolution')
    
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
            else:
                # PyAV returned empty result - log it
                info(f"Returned empty result for {os.path.basename(video_path)}, falling back to FFmpeg subprocess", "PyAV")
        except Exception as e:
            # Log why PyAV failed (helps debug why FFmpeg subprocess is being used)
            info(f"Failed for {os.path.basename(video_path)}, falling back to FFmpeg subprocess: {str(e)}", "PyAV")
            # Fall through to FFmpeg subprocess if PyAV fails
            pass
    
    # Fallback to FFmpeg subprocess if PyAV not available or failed
    result = extract_screenshots_ffmpeg(
        video_path, num_screenshots, max_width, max_height,
        preview_callback, full_resolution,
        original_resolution, duration, fps
    )
    
    if result:
        return result
    
    # Both PyAV and FFmpeg failed - raise error
    raise ValueError(f"Could not extract screenshots from video file: {video_path}")

