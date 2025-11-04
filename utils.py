"""
Utility functions for path and file operations.
"""
import os
from typing import Tuple


def calculate_output_path(video_path: str, input_dir: str, output_dir: str, 
                         output_format: str, follow_structure: bool, suffix: str = "") -> str:
    """
    Calculate the output path for a video file based on settings.
    
    Args:
        video_path: Full path to the video file
        input_dir: Root input directory
        output_dir: Root output directory
        output_format: Output format ('JPG' or 'PNG')
        follow_structure: Whether to preserve directory structure
        suffix: Optional suffix to append to filename (before extension)
        
    Returns:
        Full path to the output file
    """
    video_name = os.path.basename(video_path)
    output_ext = '.png' if output_format.upper() == 'PNG' else '.jpg'
    # Add suffix if provided (after original filename, before image extension)
    if suffix:
        output_filename = f"{video_name}{suffix}{output_ext}"
    else:
        output_filename = f"{video_name}{output_ext}"
    
    if follow_structure:
        # Calculate relative path from input_dir to video's directory
        video_dir = os.path.dirname(video_path)
        try:
            rel_path = os.path.relpath(video_dir, input_dir)
            if rel_path == '.':
                # Video is in the root input directory
                return os.path.join(output_dir, output_filename)
            else:
                # Create subdirectory structure in output_dir
                target_dir = os.path.join(output_dir, rel_path)
                os.makedirs(target_dir, exist_ok=True)
                return os.path.join(target_dir, output_filename)
        except ValueError:
            # If paths are on different drives (Windows), place in output_dir root
            return os.path.join(output_dir, output_filename)
    else:
        # Place directly in output directory
        return os.path.join(output_dir, output_filename)

