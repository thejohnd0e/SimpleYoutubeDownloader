from flask import Flask, render_template, request, send_file, jsonify
import yt_dlp
import os
import re
import logging
import json
from datetime import datetime

def format_filesize(bytes):
    if bytes is None:
        return "Unknown size"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes < 1024:
            return f"{bytes:.1f} {unit}"
        bytes /= 1024
    return f"{bytes:.1f} GB"

def is_valid_youtube_url(url):
    if not url:
        return False
    try:
        # Extract video ID from URL
        if 'youtu.be' in url:
            video_id = url.split('/')[-1].split('?')[0]
        else:
            video_id = url.split('v=')[-1].split('&')[0]
        # Check if video ID is valid (11 characters)
        return bool(re.match(r'^[a-zA-Z0-9_-]{11}$', video_id))
    except:
        return False

# Disable Werkzeug logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'
DOWNLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")

# Logging setup
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Global dictionary for storing download progress
download_progress = {}

def get_video_formats(url):
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'format_sort': ['res:1080', 'res:720', 'res:480', 'res:360'],
        'merge_output_format': 'mp4',
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4'
        }, {
            'key': 'FFmpegMetadata',
            'add_metadata': True,
        }],
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'logtostderr': True,
        'no_color': True,
        'socket_timeout': 30,
        'retries': 3,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'Referer': 'https://www.youtube.com/',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Sec-Ch-Ua': '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Upgrade-Insecure-Requests': '1'
        },
        'extractor_args': {
            'youtube': {
                'player_client': ['web', 'web_embedded', 'android'],
                'player_skip': [],
                'skip': ['translated_subs'],
                'embed_webpage': True,
                'player_params': {
                    'hl': 'en',
                    'clientName': 'ANDROID',
                    'clientVersion': '17.31.35',
                    'clientScreen': 'EMBED',
                    'androidSdkVersion': '30'
                }
            }
        }
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            logger.info(f"Starting info extraction for URL: {url}")
            info = ydl.extract_info(url, download=False)
            formats = []
            seen_resolutions = set()
            
            # Process video formats
            for f in info.get('formats', []):
                # Get resolution
                width = f.get('width', 0)
                height = f.get('height', 0)
                resolution = f"{width}x{height}" if width and height else "unknown"
                
                # Get video quality
                quality = f.get('format_note', '')
                if not quality and height:
                    quality = f"{height}p"
                
                # Create unique resolution key
                res_key = f"{height}p" if height else "unknown"
                
                # Skip duplicate resolutions and formats without video
                if res_key in seen_resolutions or f.get('vcodec') == 'none':
                    continue
                
                seen_resolutions.add(res_key)
                
                format_id = f['format_id']
                ext = f.get('ext', 'unknown')
                filesize = format_filesize(f.get('filesize', f.get('filesize_approx', 0)))
                
                tbr = f.get('tbr', 0)
                vbr = f.get('vbr', 0)
                abr = f.get('abr', 0)
                
                # Add bitrate information
                format_note = []
                if quality:
                    format_note.append(quality)
                if tbr:
                    format_note.append(f"{tbr:.0f}k")
                if vbr and not tbr:
                    format_note.append(f"video@{vbr:.0f}k")
                if abr:
                    format_note.append(f"audio@{abr:.0f}k")
                
                formats.append({
                    'format_id': format_id + '+bestaudio[ext=m4a]',  # Add audio stream
                    'ext': ext,
                    'resolution': resolution,
                    'quality': quality,
                    'filesize': filesize,
                    'format_note': ' - '.join(format_note),
                    'height': height or 0
                })
            
            # Sort formats by video height (descending)
            formats.sort(key=lambda x: x['height'], reverse=True)
            
            return {
                'title': info.get('title', 'Unknown Title'),
                'thumbnail': info.get('thumbnail', ''),
                'duration': info.get('duration', 0),
                'formats': formats
            }
        except Exception as e:
            logger.error(f"Error extracting video info: {str(e)}")
            raise

class ProgressHook:
    def __init__(self, video_id):
        self.video_id = video_id
        
    def __call__(self, d):
        if d['status'] == 'downloading':
            try:
                total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                downloaded_bytes = d.get('downloaded_bytes', 0)
                speed = d.get('speed', 0)
                eta = d.get('eta', 0)
                
                if total_bytes > 0:
                    progress = (downloaded_bytes / total_bytes) * 100
                else:
                    progress = 0
                    
                download_progress[self.video_id] = {
                    'status': 'downloading',
                    'progress': round(progress, 1),
                    'speed': format_filesize(speed) + '/s' if speed else 'Unknown',
                    'eta': f'{eta} seconds' if eta else 'Unknown',
                    'size': format_filesize(total_bytes),
                    'downloaded': format_filesize(downloaded_bytes)
                }
            except Exception as e:
                logger.error(f"Error updating progress: {str(e)}")
                
        elif d['status'] == 'finished':
            download_progress[self.video_id] = {
                'status': 'finished',
                'progress': 100
            }
        elif d['status'] == 'error':
            download_progress[self.video_id] = {
                'status': 'error',
                'error': str(d.get('error', 'Unknown error'))
            }

def download_video(url, format_id):
    video_id = url.split('v=')[-1].split('&')[0]  # Get clean video ID from URL
    download_progress[video_id] = {'status': 'starting', 'progress': 0}
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Modify filename template and add special character handling
    sanitized_template = '%(title)s_' + timestamp + '.%(ext)s'
    output_template = os.path.join(DOWNLOAD_FOLDER, sanitized_template)
    
    ydl_opts = {
        'format': format_id,
        'outtmpl': output_template,
        'merge_output_format': 'mp4',
        'progress_hooks': [ProgressHook(video_id)],
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4'
        }, {
            'key': 'FFmpegMetadata',
            'add_metadata': True,
        }],
        'restrictfilenames': True,  # Add this for safe filenames
        'windowsfilenames': True,   # Ensure Windows compatibility
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'no_warnings': True,
        'quiet': True,
        'socket_timeout': 30,
        'retries': 3,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'Referer': 'https://www.youtube.com/',
            'Connection': 'keep-alive'
        }
    }
    
    try:
        logger.info(f"Starting download with format_id: {format_id}")
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            # Очищаем имя файла от некорректных символов
            # Заменить на:
            # Clean up invalid characters from filename
            filename = os.path.basename(filename)
            logger.info(f"Download completed: {filename}")
            
            final_path = os.path.join(DOWNLOAD_FOLDER, filename)
            if not os.path.exists(final_path):
                raise Exception(f"Downloaded file not found: {final_path}")
                
            return final_path
            
    except Exception as e:
        logger.error(f"Error during download: {str(e)}")
        download_progress[video_id] = {
            'status': 'error',
            'error': str(e)
        }
        raise

@app.route('/', methods=['GET', 'POST'])
def index():
    return render_template('index.html')

@app.route('/get_formats', methods=['POST'])
def get_formats():
    try:
        url = request.form['url']
        logger.info(f"Processing URL: {url}")
        
        if not is_valid_youtube_url(url):
            return jsonify({'error': "Please enter a valid YouTube video URL"})
        
        video_info = get_video_formats(url)
        return jsonify(video_info)
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return jsonify({'error': f"Error getting video information: {str(e)}"})

@app.route('/download', methods=['POST'])
def download():
    try:
        url = request.form['url']
        format_id = request.form['format']
        
        if not is_valid_youtube_url(url):
            return "Invalid video URL", 400
            
        file_path = download_video(url, format_id)
        
        if not os.path.exists(file_path):
            raise Exception(f"File not found: {file_path}")
            
        # Get filename from full path
        filename = os.path.basename(file_path)
        
        # Send file with correct headers
        response = send_file(
            file_path,
            as_attachment=True,
            download_name=filename,
            mimetype='video/mp4'
        )
        
        # Add CORS headers
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        
        # Delete file after sending
        @response.call_on_close
        def cleanup():
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"Cleaned up file: {file_path}")
            except Exception as e:
                logger.error(f"Error cleaning up file: {str(e)}")
        
        return response
        
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        return str(e), 400

@app.route('/progress/<video_id>')
def get_progress(video_id):
    progress = download_progress.get(video_id, {'status': 'not_found'})
    return jsonify(progress)

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=False)