# YouTube Video Downloader

A minimalist web application for downloading YouTube videos in various formats and qualities.

## Features

- Clean, dark-themed interface
- Support for multiple video qualities and formats
- Real-time download progress tracking
- Format selection with size information
- Responsive design

## Screenshot

![Screenshot of the application](screenshot.png)


## Requirements

- Docker and Docker Compose
- Or Python 3.8+ with pip

## Quick Start with Docker

1. Clone the repository
2. Run the application:
```bash
docker-compose up --build
```
3. Open http://localhost:5000 in your browser

## Manual Installation

1. Create virtual environment:
```bash
python -m venv venv
venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python app/main.py
```

## Usage

1. Paste a YouTube video URL
2. Click **Get Formats** to see available options
3. Select desired quality and click **Download**
4. Wait for download to complete

## License

MIT License

## Notes

- Some videos might be unavailable due to YouTube restrictions
- Download speeds may vary based on your internet connection
