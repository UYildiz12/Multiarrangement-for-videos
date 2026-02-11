$sourceDir = "c:\Users\user\Desktop\MA\Multiarrangement-for-videos\58videos"
$videoOut = "c:\Users\user\Desktop\MA\Multiarrangement-for-videos\web\public\videos"
$thumbOut = "c:\Users\user\Desktop\MA\Multiarrangement-for-videos\web\public\thumbnails"

Write-Host "Source: $sourceDir"
Write-Host "Dest Video: $videoOut"

# Create directories
if (-not (Test-Path $videoOut)) { New-Item -ItemType Directory -Force -Path $videoOut | Out-Null }
if (-not (Test-Path $thumbOut)) { New-Item -ItemType Directory -Force -Path $thumbOut | Out-Null }

# Get all video files explicitly
$extensions = "*.avi", "*.mp4"
$videos = Get-ChildItem -Path $sourceDir -Include $extensions -Recurse

Write-Host "Found $($videos.Count) videos."

$count = 0
foreach ($video in $videos) {
    $count++
    $baseName = [System.IO.Path]::GetFileNameWithoutExtension($video.Name)
    $mp4Path = Join-Path $videoOut "$baseName.mp4"
    $thumbPath = Join-Path $thumbOut "$baseName.jpg"
    
    Write-Host "[$count/$($videos.Count)] Processing $baseName..."
    
    # 1. Convert to MP4 if needed
    if (-not (Test-Path $mp4Path)) {
        Write-Host "  Converting to MP4..."
        # Use -y to overwrite, fast preset for speed
        $cmd = "ffmpeg -i `"$($video.FullName)`" -c:v libx264 -preset ultrafast -crf 28 -c:a aac -movflags +faststart -y `"$mp4Path`""
        cmd /c $cmd 2>&1 | Out-Null
    } else {
        Write-Host "  MP4 already exists."
    }
    
    # 2. Generate Thumbnail
    if (-not (Test-Path $thumbPath)) {
        Write-Host "  Generating thumbnail..."
        $cmd = "ffmpeg -i `"$($video.FullName)`" -vf `"select=eq(n\,0)`" -vframes 1 -q:v 2 -y `"$thumbPath`""
        cmd /c $cmd 2>&1 | Out-Null
    } else {
        Write-Host "  Thumbnail already exists."
    }
}

Write-Host "Batch conversion complete."
