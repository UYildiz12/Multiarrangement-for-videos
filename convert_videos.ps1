$sourceDir = "c:\Users\user\Desktop\MA\Multiarrangement-for-videos\58videos"
$videoOut = "c:\Users\user\Desktop\MA\Multiarrangement-for-videos\web\public\videos"
$thumbOut = "c:\Users\user\Desktop\MA\Multiarrangement-for-videos\web\public\thumbnails"

# Create directories
New-Item -ItemType Directory -Force -Path $videoOut | Out-Null
New-Item -ItemType Directory -Force -Path $thumbOut | Out-Null

# Get all video files
$videos = Get-ChildItem -Path $sourceDir -Include *.avi,*.mp4 -File

Write-Host "Converting $($videos.Count) videos..."

foreach ($video in $videos) {
    $baseName = [System.IO.Path]::GetFileNameWithoutExtension($video.Name)
    $mp4Path = Join-Path $videoOut "$baseName.mp4"
    $thumbPath = Join-Path $thumbOut "$baseName.jpg"
    
    # Skip if already converted
    if (Test-Path $mp4Path) {
        Write-Host "Skipping $baseName (already exists)"
    } else {
        Write-Host "Converting $($video.Name) -> $baseName.mp4"
        ffmpeg -i $video.FullName -c:v libx264 -preset fast -crf 23 -c:a aac -movflags +faststart -y $mp4Path 2>$null
    }
    
    # Generate thumbnail
    if (-not (Test-Path $thumbPath)) {
        Write-Host "Generating thumbnail for $baseName"
        ffmpeg -i $video.FullName -vf "select=eq(n\,0)" -vframes 1 -y $thumbPath 2>$null
    }
}

Write-Host "Done! Converted to $videoOut"
