"""
Image composition module for creating grid layouts with metadata labels.
"""
import os
from PIL import Image, ImageDraw, ImageFont
from typing import List, Tuple, Optional, Dict
from config import ProcessingConfig


def format_file_size(size_bytes: int) -> str:
    """Format file size in bytes to human-readable string."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def format_duration(seconds: float) -> str:
    """Format duration in seconds to human-readable string (HH:MM:SS or MM:SS)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes:02d}:{secs:02d}"


def format_timestamp(seconds: float) -> str:
    """Format timestamp in seconds to MM:SS format."""
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    return f"{minutes:02d}:{secs:02d}"


def load_app_icon(size: int = 24) -> Optional[Image.Image]:
    """
    Load the application icon (icon.ico) and resize it.
    
    Args:
        size: Target size of the icon in pixels
        
    Returns:
        PIL Image with the icon, or None if not found
    """
    import sys
    
    # Try to find icon.ico (same logic as main.py)
    try:
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            # Running from PyInstaller bundle
            base_path = sys._MEIPASS
        else:
            # Running from source
            base_path = os.path.dirname(__file__)
            # Go up one level if needed (when running from source)
            if not os.path.exists(os.path.join(base_path, 'icon.ico')):
                base_path = os.path.dirname(base_path)
        
        icon_path = os.path.join(base_path, 'icon.ico')
        
        if os.path.exists(icon_path):
            # Load the icon
            icon = Image.open(icon_path)
            
            # Convert to RGBA if needed
            if icon.mode != 'RGBA':
                icon = icon.convert('RGBA')
            
            # Resize to target size
            icon = icon.resize((size, size), Image.Resampling.LANCZOS)
            
            return icon
    except Exception as e:
        # If loading fails, return None
        print(f"[Watermark] Failed to load icon: {e}", flush=True)
        return None
    
    return None


def add_watermark(image: Image.Image) -> Image.Image:
    """
    Add watermark ("ScreenMachine" text) to top right corner of image.
    
    Args:
        image: PIL Image to add watermark to
        
    Returns:
        PIL Image with watermark added
    """
    # Create a copy to avoid modifying the original
    watermarked = image.copy()
    draw = ImageDraw.Draw(watermarked)
    
    # Watermark dimensions
    padding = 10
    text_size = 12
    text_color = '#777777'  # Gray color
    
    # Get font for text
    try:
        font = get_font(text_size)
    except:
        font = ImageFont.load_default()
    
    text = "ScreenMachine"
    
    # Get text bounding box to calculate position
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    
    # Position at top right corner
    text_x = watermarked.width - text_width - padding
    text_y = padding
    
    # Draw text in gray color
    draw.text((text_x, text_y), text, fill=text_color, font=font)
    
    return watermarked


def get_font(size: int = 16) -> ImageFont.FreeTypeFont:
    """Get a font for text rendering, falling back to default if needed."""
    try:
        # Try to use a nice default font
        if hasattr(ImageFont, 'truetype'):
            # Try common system fonts
            font_paths = [
                'arial.ttf',
                'Arial.ttf',
                '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',  # Linux
                '/System/Library/Fonts/Helvetica.ttc',  # Mac
            ]
            for path in font_paths:
                try:
                    return ImageFont.truetype(path, size)
                except:
                    continue
    except:
        pass
    
    # Fall back to default font
    try:
        return ImageFont.load_default()
    except:
        return ImageFont.load_default()


def create_grid(images: List[Tuple[Image.Image, float]], 
                config: ProcessingConfig,
                metadata: Optional[Dict] = None,
                resize_after_compose: bool = False) -> Image.Image:
    """
    Create a grid image from screenshots with optional metadata labels.
    
    Args:
        images: List of tuples (PIL Image, timestamp)
        config: ProcessingConfig with grid layout and label settings
        metadata: Optional metadata dictionary from get_video_metadata
        resize_after_compose: If True, create grid with full-res images and resize entire grid once
        
    Returns:
        PIL Image containing the grid with labels
    """
    if not images:
        raise ValueError("No images provided for grid creation")
    
    rows = config.rows
    cols = config.columns
    
    # Ensure we have enough images or pad with blank images
    total_needed = rows * cols
    while len(images) < total_needed:
        # Create a blank image with the same size as the first image
        if images:
            blank = Image.new('RGB', images[0][0].size, color='black')
            images.append((blank, 0.0))
    
    # Take only the number we need
    images = images[:total_needed]
    
    # Get dimensions of first screenshot
    first_image = images[0][0]
    screenshot_width, screenshot_height = first_image.size
    
    # OPTIMIZATION 2: If resize_after_compose, create grid with full-res images, resize once at end
    if resize_after_compose:
        # All screenshots should have same dimensions (from same video)
        # Create grid with full-resolution frames
        grid_width = cols * screenshot_width
        grid_height = rows * screenshot_height
        
        # Create full-res grid
        full_res_grid = Image.new('RGB', (grid_width, grid_height), color='black')
        images_only = [img for img, ts in images]
        
        for idx, image in enumerate(images_only):
            row = idx // cols
            col = idx % cols
            x = col * screenshot_width
            y = row * screenshot_height
            full_res_grid.paste(image, (x, y))
        
        # Calculate scale factor to fit within max dimensions per screenshot
        max_total_width = cols * config.max_screenshot_width
        max_total_height = rows * config.max_screenshot_height
        
        width_ratio = max_total_width / grid_width
        height_ratio = max_total_height / grid_height
        scale_factor = min(width_ratio, height_ratio, 1.0)  # Don't upscale
        
        if scale_factor < 1.0:
            # Resize the entire grid once
            new_grid_width = int(grid_width * scale_factor)
            new_grid_height = int(grid_height * scale_factor)
            # Use NEAREST for speed (grid resizing is just for size reduction)
            grid_image = full_res_grid.resize((new_grid_width, new_grid_height), Image.Resampling.NEAREST)
        else:
            grid_image = full_res_grid
        
        # Update screenshot dimensions for header calculation
        screenshot_width = grid_image.width // cols
        screenshot_height = grid_image.height // rows
        grid_width = cols * screenshot_width
        grid_height = rows * screenshot_height
    else:
        # Original approach: screenshots already resized to fit max dimensions
        grid_width = cols * screenshot_width
        grid_height = rows * screenshot_height
        grid_image = None  # Will be created below
    
    # Calculate header height if labels are needed
    header_height = 0
    label_lines = []
    
    if metadata and (config.show_title or config.show_resolution or 
                     config.show_file_size or config.show_duration or config.show_codec):
        font_size = 18
        font = get_font(font_size)
        line_height = font_size + 10
        padding = 10
        
        if config.show_title:
            filename = metadata.get('filename', 'Unknown')
            label_lines.append(f"Title: {filename}")
        if config.show_resolution:
            resolution = metadata.get('resolution')
            if resolution and isinstance(resolution, (tuple, list)) and len(resolution) >= 2:
                width, height = resolution[0], resolution[1]
                label_lines.append(f"Resolution: {width} × {height}")
            elif 'width' in metadata and 'height' in metadata:
                label_lines.append(f"Resolution: {metadata['width']} × {metadata['height']}")
        if config.show_file_size:
            file_size = metadata.get('file_size', 0)
            if file_size > 0:
                size_str = format_file_size(file_size)
                label_lines.append(f"File Size: {size_str}")
        if config.show_duration:
            duration = metadata.get('duration', 0.0)
            if duration > 0:
                duration_str = format_duration(duration)
                label_lines.append(f"Duration: {duration_str}")
        if config.show_codec:
            codec = metadata.get('codec', 'Unknown')
            label_lines.append(f"Codec: {codec}")
        
        header_height = len(label_lines) * line_height + (padding * 2)
    
    # Create the final image
    if resize_after_compose and grid_image is not None:
        # Already have the grid image from resize_after_compose path
        final_image = Image.new('RGB', (grid_width, grid_height + header_height), color='black')
        # Paste the resized grid
        final_image.paste(grid_image, (0, header_height))
    else:
        # Create new grid (original approach)
        final_width = grid_width
        final_height = grid_height + header_height
        final_image = Image.new('RGB', (final_width, final_height), color='black')
        
        # Paste screenshots into grid (optimized batch paste for CPU efficiency)
        images_only = [img for img, ts in images]
        
        for idx, image in enumerate(images_only):
            row = idx // cols
            col = idx % cols
            
            x = col * screenshot_width
            y = header_height + (row * screenshot_height)
            
            # Paste directly without extra processing
            final_image.paste(image, (x, y))
    
    # Draw header with labels if needed (dark theme with white text)
    if header_height > 0 and label_lines:
        # Draw dark header background
        header_rect = Image.new('RGB', (final_image.width, header_height), color='#1a1a1a')
        final_image.paste(header_rect, (0, 0))
        
        draw = ImageDraw.Draw(final_image)
        font = get_font(18)
        padding = 10
        y_offset = padding
        
        for line in label_lines:
            draw.text((padding, y_offset), line, fill='white', font=font)
            y_offset += 28  # line height
    
    # Draw timestamps on each frame if enabled
    if config.show_timestamps:
        draw = ImageDraw.Draw(final_image)
        timestamp_font = get_font(14)
        timestamp_padding = 5
        
        for idx, (image, timestamp) in enumerate(images):
            row = idx // cols
            col = idx % cols
            
            # Calculate position of this frame in the grid
            frame_x = col * screenshot_width
            frame_y = header_height + (row * screenshot_height)
            
            # Format timestamp (MM:SS)
            timestamp_str = format_timestamp(timestamp)
            
            # Position at bottom left of frame
            timestamp_x = frame_x + timestamp_padding
            timestamp_y = frame_y + screenshot_height - timestamp_padding
            
            # Get text height to position from bottom
            bbox = draw.textbbox((0, 0), timestamp_str, font=timestamp_font)
            text_height = bbox[3] - bbox[1]
            timestamp_y = timestamp_y - text_height
            
            # Draw text in white
            draw.text((timestamp_x, timestamp_y), timestamp_str, fill='white', font=timestamp_font)
    
    # Add watermark to top right corner
    final_image = add_watermark(final_image)
    
    return final_image


def save_grid_image(image: Image.Image, output_path: str, quality: Optional[int] = None, format: str = 'JPG') -> None:
    """
    Save the grid image as a JPG or PNG file.
    
    Args:
        image: PIL Image to save
        output_path: Full path where to save the image
        quality: JPG quality (1-100), ignored for PNG
        format: Output format ('JPG' or 'PNG')
    """
    # Force format - explicitly pass format parameter
    format_upper = str(format).upper().strip()
    
    # Ensure extension matches format BEFORE saving
    base_path = os.path.splitext(output_path)[0]
    if format_upper == 'PNG':
        output_path = base_path + '.png'
        # PNG with minimal compression for speed (compress_level=1 is fastest, default is 6)
        image.save(output_path, 'PNG', compress_level=1, optimize=False)
    else:
        output_path = base_path + '.jpg'
        # JPG with quality setting (JPEG compression is CPU-intensive)
        quality = quality or 75
        image.save(output_path, 'JPEG', quality=quality, optimize=False, progressive=False)

