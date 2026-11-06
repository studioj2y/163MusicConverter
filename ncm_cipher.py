# -*- coding: utf-8 -*-
"""
ncm_cipher.py - High-performance NetEase Cloud Music (.ncm) Decryptor & Tagging Engine
Supports chunked decryption, full metadata extraction, and automatic tag embedding.
"""

import os
import struct
import base64
import json
import binascii
from typing import Optional, Dict, Any, Callable, Tuple
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from Crypto.Util.strxor import strxor
import mutagen
from mutagen.mp3 import MP3, EasyMP3
from mutagen.id3 import ID3, APIC, TIT2, TPE1, TALB, COMM
from mutagen.flac import FLAC, Picture

CORE_KEY = binascii.a2b_hex('687A4852416D736F356B496E62617857')
META_KEY = binascii.a2b_hex('2331346C6A6B5F215C5D2630553C2728')
NCM_MAGIC = b'CTENFDAM'


class NCMError(Exception):
    pass


class NotNCMError(NCMError):
    pass


def is_ncm_file(file_path: str) -> bool:
    """Check if the given file starts with the NCM magic header."""
    if not os.path.isfile(file_path):
        return False
    try:
        with open(file_path, 'rb') as f:
            header = f.read(8)
            return header == NCM_MAGIC
    except Exception:
        return False


def extract_ncm_info(file_path: str) -> Dict[str, Any]:
    """
    Fast extraction of NCM metadata without decrypting the entire audio stream.
    Returns: {
        'format': 'mp3' or 'flac',
        'musicName': str,
        'artist': str,
        'album': str,
        'has_cover': bool,
        'cover_size': int,
        'raw_meta': dict
    }
    """
    if not is_ncm_file(file_path):
        raise NotNCMError(f"文件不是有效的 NCM 格式: {file_path}")

    with open(file_path, 'rb') as f:
        f.seek(8 + 2)  # skip magic + 2-byte gap
        key_len = struct.unpack('<I', f.read(4))[0]
        f.seek(key_len, 1)

        meta_len = struct.unpack('<I', f.read(4))[0]
        meta_dict = {}
        if meta_len > 0:
            meta_raw = bytes([b ^ 0x63 for b in f.read(meta_len)])
            try:
                b64_content = meta_raw[22:]  # skip "163 key(Don't modify):"
                cipher = AES.new(META_KEY, AES.MODE_ECB)
                meta_dec = unpad(cipher.decrypt(base64.b64decode(b64_content)), 16).decode('utf-8')
                meta_dict = json.loads(meta_dec[6:])  # skip "music:"
            except Exception:
                meta_dict = {}

        f.seek(5, 1)  # skip 5 bytes gap
        img_space = struct.unpack('<I', f.read(4))[0]
        img_size = struct.unpack('<I', f.read(4))[0]

    music_name = meta_dict.get('musicName', '')
    if not music_name:
        # Fallback to file name without extension
        music_name = os.path.splitext(os.path.basename(file_path))[0]

    artists_raw = meta_dict.get('artist', [])
    artist_names = []
    if isinstance(artists_raw, list):
        for item in artists_raw:
            if isinstance(item, list) and len(item) > 0:
                artist_names.append(str(item[0]))
            elif isinstance(item, str):
                artist_names.append(item)
    artist_str = '/'.join(artist_names) if artist_names else ''

    album_name = meta_dict.get('album', '')
    fmt = meta_dict.get('format', '')
    if not fmt:
        file_sz = os.path.getsize(file_path)
        fmt = 'flac' if file_sz > 16 * 1024 * 1024 else 'mp3'

    return {
        'format': fmt.lower(),
        'musicName': music_name,
        'artist': artist_str,
        'album': album_name,
        'has_cover': img_size > 0,
        'cover_size': img_size,
        'raw_meta': meta_dict
    }


def decrypt_ncm(
    input_path: str,
    output_path: str,
    progress_callback: Optional[Callable[[float], None]] = None,
    should_cancel: Optional[Callable[[], bool]] = None
) -> Tuple[str, Dict[str, Any], Optional[bytes]]:
    """
    Decrypts an NCM file into the output_path in chunks.
    Automatically applies ID3v2 / FLAC tags and embeds album cover.
    
    Returns:
        (final_output_path, metadata_dict, cover_image_bytes)
    """
    if not is_ncm_file(input_path):
        raise NotNCMError(f"文件不是有效的 NCM 格式: {input_path}")

    with open(input_path, 'rb') as f:
        header = f.read(8)
        if header != NCM_MAGIC:
            raise NotNCMError("Header magic 不匹配")
        f.seek(2, 1)

        # 1. Decrypt key data
        key_len = struct.unpack('<I', f.read(4))[0]
        raw_key = bytes([b ^ 0x64 for b in f.read(key_len)])
        cipher_core = AES.new(CORE_KEY, AES.MODE_ECB)
        key_data = unpad(cipher_core.decrypt(raw_key), 16)[17:]

        # 2. Key scheduling algorithm (RC4 S-box)
        key_l = len(key_data)
        S = list(range(256))
        j = 0
        for i in range(256):
            j = (j + S[i] + key_data[i % key_l]) & 0xFF
            S[i], S[j] = S[j], S[i]

        # 3. Precompute keystream lookup table
        stream = bytes([S[(S[i] + S[(i + S[i]) & 0xFF]) & 0xFF] for i in range(256)])
        key_box = stream[1:] + stream[:1]  # 256-byte aligned table

        # 4. Decrypt metadata
        meta_len = struct.unpack('<I', f.read(4))[0]
        meta_dict = {}
        if meta_len > 0:
            meta_raw = bytes([b ^ 0x63 for b in f.read(meta_len)])
            try:
                b64_content = meta_raw[22:]
                cipher_meta = AES.new(META_KEY, AES.MODE_ECB)
                meta_dec = unpad(cipher_meta.decrypt(base64.b64decode(b64_content)), 16).decode('utf-8')
                meta_dict = json.loads(meta_dec[6:])
            except Exception:
                meta_dict = {}

        # 5. Read cover image
        f.seek(5, 1)
        img_space = struct.unpack('<I', f.read(4))[0]
        img_size = struct.unpack('<I', f.read(4))[0]
        img_data = f.read(img_size) if img_size > 0 else None
        f.seek(img_space - img_size, 1)

        # 6. Stream decrypt audio data in chunks to output_path
        total_audio_size = os.path.getsize(input_path) - f.tell()
        processed = 0
        chunk_size = 128 * 1024  # 128 KB buffer

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, 'wb') as out_f:
            offset = 0
            while True:
                if should_cancel and should_cancel():
                    raise InterruptedError("操作已被用户取消")

                chunk = f.read(chunk_size)
                if not chunk:
                    break

                mask = (key_box * (len(chunk) // 256 + 2))[offset % 256 : offset % 256 + len(chunk)]
                dec_chunk = strxor(chunk, mask)
                out_f.write(dec_chunk)

                offset += len(chunk)
                processed += len(chunk)
                if progress_callback and total_audio_size > 0:
                    progress_callback(min(1.0, processed / total_audio_size))

    # 7. Apply tags to the decrypted file
    detected_format = meta_dict.get('format', '').lower()
    if not detected_format:
        # Check by sniffing output file header
        with open(output_path, 'rb') as chk:
            head_bytes = chk.read(4)
            if head_bytes.startswith(b'fLaC'):
                detected_format = 'flac'
            else:
                detected_format = 'mp3'
        meta_dict['format'] = detected_format

    try:
        embed_tags_and_cover(output_path, detected_format, meta_dict, img_data)
    except Exception as e:
        # Tag embedding failure should not destroy the decrypted audio file
        pass

    return output_path, meta_dict, img_data


def embed_tags_and_cover(
    file_path: str,
    audio_format: str,
    meta_dict: Dict[str, Any],
    img_data: Optional[bytes]
) -> None:
    """Embeds ID3v2.3 tags (for MP3) or Vorbis Comments + Picture (for FLAC)."""
    title = meta_dict.get('musicName', '')
    if not title:
        title = os.path.splitext(os.path.basename(file_path))[0]

    artists_raw = meta_dict.get('artist', [])
    artist_names = []
    if isinstance(artists_raw, list):
        for item in artists_raw:
            if isinstance(item, list) and len(item) > 0:
                artist_names.append(str(item[0]))
            elif isinstance(item, str):
                artist_names.append(item)
    artist = '/'.join(artist_names) if artist_names else ''
    album = meta_dict.get('album', '')

    if audio_format == 'flac':
        try:
            audio = FLAC(file_path)
            if title:
                audio['title'] = [title]
            if artist:
                audio['artist'] = [artist]
            if album:
                audio['album'] = [album]

            if img_data:
                pic = Picture()
                pic.type = 3  # front cover
                pic.mime = 'image/png' if img_data.startswith(b'\x89PNG') else 'image/jpeg'
                pic.data = img_data
                audio.clear_pictures()
                audio.add_picture(pic)
            audio.save()
        except Exception:
            pass

    elif audio_format == 'mp3':
        try:
            # First ensure ID3 tag exists
            try:
                tags = ID3(file_path)
            except mutagen.id3.ID3NoHeaderError:
                tags = ID3()

            if title:
                tags.add(TIT2(encoding=3, text=title))  # UTF-8
            if artist:
                tags.add(TPE1(encoding=3, text=artist))
            if album:
                tags.add(TALB(encoding=3, text=album))

            if img_data:
                mime = 'image/png' if img_data.startswith(b'\x89PNG') else 'image/jpeg'
                tags.add(APIC(
                    encoding=0,
                    mime=mime,
                    type=3,  # cover front
                    desc='Cover',
                    data=img_data
                ))

            # Save as ID3v2.3 for maximum compatibility across car audio and portable players
            tags.save(file_path, v2_version=3)
        except Exception:
            pass
