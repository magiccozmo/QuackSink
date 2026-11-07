@echo off
setlocal

rem Convert kartlotta_meet.mp4 to a WAV, removing leading silence
rem while preserving 0.5 seconds before the first detected speech/audio.

set "INPUT=%~dp0kartlotta_meet.mp4"
set "OUTPUT=%~dp0kartlotta_meet.wav"

where ffmpeg >nul 2>&1
if errorlevel 1 (
    echo ERROR: FFmpeg was not found.
    echo Install FFmpeg and make sure ffmpeg.exe is in your PATH.
    pause
    exit /b 1
)

if not exist "%INPUT%" (
    echo ERROR: Could not find:
    echo "%INPUT%"
    echo Put this BAT file in the same folder as kartlotta_meet.mp4.
    pause
    exit /b 1
)

if exist "%OUTPUT%" (
    echo ERROR: Output already exists:
    echo "%OUTPUT%"
    echo Rename or move the existing WAV before running this again.
    pause
    exit /b 1
)

echo Converting video audio to WAV...
echo Removing leading silence but keeping 0.5 seconds before speech.

ffmpeg -hide_banner -i "%INPUT%" -map 0:a:0 -vn -af "silenceremove=start_periods=1:start_duration=0.10:start_threshold=-45dB:start_silence=0.5" -c:a pcm_s16le "%OUTPUT%"

if errorlevel 1 (
    echo.
    echo ERROR: FFmpeg could not create the WAV file.
    pause
    exit /b 1
)

echo.
echo SUCCESS: Created:
echo "%OUTPUT%"
pause
exit /b 0
