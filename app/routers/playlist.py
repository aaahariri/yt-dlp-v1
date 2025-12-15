"""
Playlist router for extracting playlist metadata.

This module provides endpoints for:
- Extracting playlist metadata and video lists without downloading
- Filtering playlists by date and item range
- Supporting both playlists and single videos
"""

from fastapi import APIRouter, Query, Depends, HTTPException
import yt_dlp

from app.dependencies import verify_api_key
from app.config import YTDLP_EXTRACTOR_ARGS

router = APIRouter(tags=["Playlist"])


@router.get("/playlist/info")
async def get_playlist_info(
    url: str = Query(...),
    dateafter: str = Query(None, description="Filter videos uploaded after this date (YYYYMMDD or relative like 'today-1week')"),
    datebefore: str = Query(None, description="Filter videos uploaded before this date"),
    max_items: int = Query(None, description="Maximum number of videos to return"),
    items: str = Query(None, description="Select specific videos by index (e.g., '1:5' for videos 1-5, '1,3,5' for specific videos)"),
    _: bool = Depends(verify_api_key)
):
    """Extract playlist metadata without downloading videos."""
    try:
        # Configure yt-dlp for playlist extraction
        ydl_opts = {
            'extract_flat': 'in_playlist',  # Extract playlist metadata without individual video details
            'quiet': True,
            'no_warnings': True,
            'extractor_args': YTDLP_EXTRACTOR_ARGS,
        }

        # Add date filters if provided
        if dateafter:
            ydl_opts['dateafter'] = dateafter
        if datebefore:
            ydl_opts['datebefore'] = datebefore

        # Add playlist item selection if provided
        if items:
            ydl_opts['playlist_items'] = items
        elif max_items:
            ydl_opts['playlist_items'] = f'1:{max_items}'

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            # Check if it's actually a playlist
            if info.get('_type') != 'playlist':
                # Single video, wrap it as a playlist
                video_url = info.get('webpage_url') or url
                return {
                    'playlist_title': info.get('title', 'Single Video'),
                    'playlist_url': url,
                    'channel': info.get('uploader', 'Unknown'),
                    'channel_id': info.get('uploader_id'),
                    'channel_url': info.get('uploader_url'),
                    'video_count': 1,
                    'videos': [{
                        'url': video_url,
                        'title': info.get('title', 'Unknown'),
                        'duration': info.get('duration'),
                        'upload_date': info.get('upload_date'),
                        'index': 1,
                        'id': info.get('id')
                    }]
                }

            # Extract playlist metadata
            playlist_title = info.get('title', 'Unknown Playlist')
            playlist_url = info.get('webpage_url', url)
            channel = info.get('uploader', 'Unknown')
            channel_id = info.get('uploader_id')
            channel_url = info.get('uploader_url')

            # Process video entries
            entries = info.get('entries', [])
            videos = []

            for idx, entry in enumerate(entries, 1):
                if entry is None:  # Skip unavailable videos
                    continue

                # Build video URL
                video_id = entry.get('id')
                video_url = entry.get('url') or entry.get('webpage_url')

                # If we only have ID, construct YouTube URL
                if not video_url and video_id:
                    video_url = f'https://www.youtube.com/watch?v={video_id}'

                # Format duration from seconds to MM:SS or HH:MM:SS
                duration_seconds = entry.get('duration')
                duration_str = None
                if duration_seconds:
                    hours = duration_seconds // 3600
                    minutes = (duration_seconds % 3600) // 60
                    seconds = duration_seconds % 60
                    if hours > 0:
                        duration_str = f"{hours}:{minutes:02d}:{seconds:02d}"
                    else:
                        duration_str = f"{minutes}:{seconds:02d}"

                # Format upload date
                upload_date = entry.get('upload_date')
                if upload_date and len(upload_date) == 8:
                    # Convert YYYYMMDD to YYYY-MM-DD
                    upload_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}"

                video_info = {
                    'url': video_url,
                    'title': entry.get('title', 'Unknown'),
                    'duration': duration_str,
                    'duration_seconds': duration_seconds,
                    'upload_date': upload_date,
                    'index': idx,
                    'id': video_id
                }

                # Add additional metadata if available
                if entry.get('view_count'):
                    video_info['views'] = entry.get('view_count')
                if entry.get('description'):
                    video_info['description'] = entry.get('description')[:200] + '...' if len(entry.get('description', '')) > 200 else entry.get('description')

                videos.append(video_info)

            # Calculate total playlist count (might be different from filtered count)
            total_count = info.get('playlist_count') or len(entries)

            return {
                'playlist_title': playlist_title,
                'playlist_url': playlist_url,
                'channel': channel,
                'channel_id': channel_id,
                'channel_url': channel_url,
                'video_count': len(videos),
                'total_count': total_count,
                'videos': videos,
                'filters_applied': {
                    'dateafter': dateafter,
                    'datebefore': datebefore,
                    'max_items': max_items,
                    'items': items
                }
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error extracting playlist info: {str(e)}")
