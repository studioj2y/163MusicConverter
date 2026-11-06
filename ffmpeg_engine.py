# -*- coding: utf-8 -*-
"""
ffmpeg_engine.py - Universal FFmpeg Audio Encoder & Discovery Engine
Automates optimal audio encoding for MP3 and AAC with maximum device compatibility.
"""

import os
import re
import shutil
import subprocess
from typing import Optional, Dict, Any, Callable, Tuple
from mutagen.mp3 import MP3
from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB, ID3NoHeaderError
from mutagen.mp4 import MP4, MP4Cover

# Common installation paths on Windows
KNOWN_FFMPEG_PATHS = [
    r"C:\Tools\Portable\ffmpeg-2021-05-12-git-175f675f7b-essentials_build\bin\ffmpeg.exe",
    r"C:\Program Files\DownloadHelper CoApp\ffmpeg.exe",
    r"C:\Tools\Portable\shotcut-win64-25.12.31\Shotcut\ffmpeg.exe",
    r"C:\ffmpeg\bin\ffmpeg.exe",
    r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools", "ffmpeg.exe"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "ffmpeg.exe"),
]

_CACHED_FFMPEG_PATH: Optional[str] = None


def find_ffmpeg(custom_path: Optional[str] = None) -> Optional[str]:
    """
    Locates ffmpeg.exe using custom path, PATH, environment, or known paths.
    """
    global _CACHED_FFMPEG_PATH

    # 1. Custom path
    if custom_path and os.path.isfile(custom_path):
        _CACHED_FFMPEG_PATH = custom_path
        return custom_path

    # 2. Return cached if still valid
    if _CACHED_FFMPEG_PATH and os.path.isfile(_CACHED_FFMPEG_PATH):
        return _CACHED_FFMPEG_PATH

    # 3. Environment variable
    env_path = os.environ.get("FFMPEG_PATH")
    if env_path and os.path.isfile(env_path):
        _CACHED_FFMPEG_PATH = env_path
        return env_path

    # 4. System PATH
    which_path = shutil.which("ffmpeg")
    if which_path and os.path.isfile(which_path):
        _CACHED_FFMPEG_PATH = which_path
        return which_path

    # 5. Known system locations
    for p in KNOWN_FFMPEG_PATHS:
        if os.path.isfile(p):
            _CACHED_FFMPEG_PATH = p
            return p

    return None


def get_ffmpeg_version(ffmpeg_path: str) -> str:
    """Returns the version string of the given FFmpeg binary."""
    try:
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
        proc = subprocess.run(
            [ffmpeg_path, "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            startupinfo=startupinfo,
            encoding='utf-8',
            errors='ignore',
            timeout=5
        )
        first_line = proc.stdout.splitlines()[0] if proc.stdout else "FFmpeg (Unknown version)"
        return first_line
    except Exception as e:
        return f"Error: {e}"


def get_audio_duration_seconds(ffmpeg_path: str, input_file: str) -> float:
    """Extracts total duration in seconds using FFmpeg info output."""
    try:
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        proc = subprocess.run(
            [ffmpeg_path, "-nostdin", "-i", input_file],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            startupinfo=startupinfo,
            encoding='utf-8',
            errors='ignore',
            timeout=5
        )
        match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", proc.stderr)
        if match:
            hours, minutes, seconds = match.groups()
            return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    except Exception:
        pass
    return 0.0


def convert_audio(
    input_file: str,
    output_file: str,
    target_format: str,  # 'mp3' or 'aac'
    bitrate: str,        # e.g. '320k', '256k', '192k', '128k', 'vbr0', 'vbr2'
    meta_dict: Optional[Dict[str, Any]] = None,
    img_data: Optional[bytes] = None,
    custom_ffmpeg_path: Optional[str] = None,
    progress_callback: Optional[Callable[[float], None]] = None,
    should_cancel: Optional[Callable[[], bool]] = None
) -> str:
    """
    Converts audio file to optimal MP3 or AAC using FFmpeg.
    Ensures maximum compatibility across iOS, Android, PC, Mac, and Car Audio systems.
    """
    ffmpeg_exe = find_ffmpeg(custom_ffmpeg_path)
    if not ffmpeg_exe:
        raise FileNotFoundError("未找到 FFmpeg 编码器，请确认 FFmpeg 已安装或指定路径。")

    os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
    total_duration = get_audio_duration_seconds(ffmpeg_exe, input_file)

    # Base FFmpeg command
    cmd = [
        ffmpeg_exe,
        "-nostdin",
        "-y",
        "-i", input_file,
        "-map", "0:a",
        "-map", "0:v?",  # include cover art stream if present
    ]

    fmt_lower = target_format.lower()
    if fmt_lower == 'mp3':
        cmd += ["-c:a", "libmp3lame"]
        b_lower = bitrate.lower()
        if 'vbr0' in b_lower or 'v0' in b_lower:
            cmd += ["-q:a", "0"]  # ~245 kbps VBR
        elif 'vbr2' in b_lower or 'v2' in b_lower:
            cmd += ["-q:a", "2"]  # ~190 kbps VBR
        elif 'vbr5' in b_lower or 'v5' in b_lower:
            cmd += ["-q:a", "5"]  # ~130 kbps VBR
        else:
            clean_b = re.sub(r'[^0-9]', '', b_lower) or '320'
            cmd += ["-b:a", f"{clean_b}k"]

        # Optimal compatibility configuration for MP3:
        # ID3v2.3 is recognized across 100% of car stereos, iOS, Android, and Windows Media Player.
        # ID3v1 is appended at the end of file for vintage players/car head-units.
        cmd += [
            "-c:v", "copy",
            "-id3v2_version", "3",
            "-write_id3v1", "1",
        ]

    elif fmt_lower in ('aac', 'm4a'):
        cmd += ["-c:a", "aac"]
        b_lower = bitrate.lower()
        if 'vbr' in b_lower:
            if '130' in b_lower or 'med' in b_lower or 'compact' in b_lower:
                cmd += ["-q:a", "1"]  # ~120-140 kbps VBR
            else:
                cmd += ["-q:a", "2"]  # ~190-220 kbps VBR
        else:
            clean_b = re.sub(r'[^0-9]', '', b_lower) or '256'
            cmd += ["-b:a", f"{clean_b}k"]

        # Optimal configuration for AAC (.m4a):
        # +faststart places the moov atom at beginning for immediate playback on mobile & streaming.
        cmd += [
            "-c:v", "copy",
            "-disposition:v:0", "attached_pic",
            "-movflags", "+faststart",
        ]
    else:
        raise ValueError(f"不支持的目标格式: {target_format}")

    cmd.append(output_file)

    startupinfo = None
    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    # Execute FFmpeg with real-time stderr parsing
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        encoding='utf-8',
        errors='ignore',
        startupinfo=startupinfo,
        bufsize=1
    )

    time_pattern = re.compile(r"time=(\d+):(\d+):(\d+\.\d+)")

    try:
        while True:
            if should_cancel and should_cancel():
                process.terminate()
                try:
                    process.wait(timeout=2)
                except Exception:
                    process.kill()
                if os.path.exists(output_file):
                    try:
                        os.remove(output_file)
                    except Exception:
                        pass
                raise InterruptedError("转码已被用户取消")

            line = process.stderr.readline()
            if not line and process.poll() is not None:
                break

            if progress_callback and total_duration > 0 and "time=" in line:
                match = time_pattern.search(line)
                if match:
                    h, m, s = match.groups()
                    current_sec = int(h) * 3600 + int(m) * 60 + float(s)
                    ratio = min(0.99, current_sec / total_duration)
                    progress_callback(ratio)

        ret_code = process.wait()
        if ret_code != 0:
            raise RuntimeError(f"FFmpeg 转码失败，退出代码: {ret_code}")

    finally:
        if process.poll() is None:
            process.kill()

    # Post-process: Verify and polish tags/cover art using mutagen
    try:
        apply_post_conversion_tags(output_file, fmt_lower, meta_dict, img_data)
    except Exception:
        pass

    if progress_callback:
        progress_callback(1.0)

    return output_file


def apply_post_conversion_tags(
    output_file: str,
    target_format: str,
    meta_dict: Optional[Dict[str, Any]],
    img_data: Optional[bytes]
) -> None:
    """
    Ensures complete, standard metadata and high-res cover art exist in the output file.
    """
    if not meta_dict and not img_data:
        return

    meta = meta_dict or {}
    title = meta.get('musicName', '')
    if not title:
        title = os.path.splitext(os.path.basename(output_file))[0]

    artists_raw = meta.get('artist', [])
    artist_names = []
    if isinstance(artists_raw, list):
        for item in artists_raw:
            if isinstance(item, list) and len(item) > 0:
                artist_names.append(str(item[0]))
            elif isinstance(item, str):
                artist_names.append(item)
    elif isinstance(artists_raw, str):
        artist_names = [artists_raw]
    artist = '/'.join(artist_names) if artist_names else ''
    album = meta.get('album', '')

    if target_format == 'mp3':
        try:
            try:
                tags = ID3(output_file)
            except ID3NoHeaderError:
                tags = ID3()

            if title and not tags.getall('TIT2'):
                tags.add(TIT2(encoding=3, text=title))
            if artist and not tags.getall('TPE1'):
                tags.add(TPE1(encoding=3, text=artist))
            if album and not tags.getall('TALB'):
                tags.add(TALB(encoding=3, text=album))

            if img_data and not tags.getall('APIC'):
                mime = 'image/png' if img_data.startswith(b'\x89PNG') else 'image/jpeg'
                tags.add(APIC(
                    encoding=0,
                    mime=mime,
                    type=3,
                    desc='Cover',
                    data=img_data
                ))
            tags.save(output_file, v2_version=3)
        except Exception:
            pass

    elif target_format in ('aac', 'm4a'):
        try:
            mp4 = MP4(output_file)
            if title:
                mp4['\xa9nam'] = [title]
            if artist:
                mp4['\xa9ART'] = [artist]
            if album:
                mp4['\xa9alb'] = [album]

            if img_data and 'covr' not in mp4:
                cov_fmt = MP4Cover.FORMAT_PNG if img_data.startswith(b'\x89PNG') else MP4Cover.FORMAT_JPEG
                mp4['covr'] = [MP4Cover(img_data, imageformat=cov_fmt)]
            mp4.save()
        except Exception:
            pass
