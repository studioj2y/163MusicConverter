# -*- coding: utf-8 -*-
"""
task_manager.py - Multi-threaded Batch Processing Pipeline for Decryption & Conversion
Handles file scanning, queuing, concurrency, progress calculation, and cancellation.
"""

import os
import time
import uuid
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Event
from typing import List, Dict, Set, Any, Optional, Callable
from ncm_cipher import is_ncm_file, extract_ncm_info, decrypt_ncm
from ffmpeg_engine import convert_audio, find_ffmpeg

AUDIO_EXTENSIONS = {'.ncm', '.flac', '.mp3', '.m4a', '.aac', '.wav', '.ogg', '.ape'}


class TaskStatus:
    PENDING = "pending"
    DECRYPTING = "decrypting"
    CONVERTING = "converting"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ConversionTaskManager:
    def __init__(self):
        self._cancel_event = Event()
        self._is_running = False
        self._executor: Optional[ThreadPoolExecutor] = None

    @property
    def is_running(self) -> bool:
        return self._is_running

    def cancel(self):
        self._cancel_event.set()

    @staticmethod
    def get_existing_output_map(output_dir: str) -> Dict[str, Set[str]]:
        """
        Fast scan of output_dir returning {lower_stem: {ext1, ext2, ...}}
        for non-empty audio files (>1024 bytes).
        """
        if not os.path.isdir(output_dir):
            return {}
        res = {}
        try:
            with os.scandir(output_dir) as entries:
                for entry in entries:
                    if entry.is_file() and entry.stat().st_size > 1024:
                        stem, ext = os.path.splitext(entry.name)
                        stem_l = stem.lower()
                        if stem_l not in res:
                            res[stem_l] = set()
                        res[stem_l].add(ext.lower())
        except Exception:
            pass
        return res

    @staticmethod
    def is_item_already_converted(
        filename: str,
        existing_map: Dict[str, Set[str]],
        target_format: str
    ) -> bool:
        """
        Checks if an output file corresponding to filename already exists in existing_map.
        """
        stem_l = os.path.splitext(filename)[0].lower()
        exts = existing_map.get(stem_l)
        if not exts:
            return False

        fmt = target_format.lower()
        if fmt == 'source':
            return bool(exts.intersection({'.flac', '.mp3', '.m4a', '.wav', '.ogg'}))
        elif fmt == 'mp3':
            return '.mp3' in exts
        elif fmt in ('aac', 'm4a'):
            return bool(exts.intersection({'.m4a', '.aac'}))
        return bool(exts)

    def scan_files(self, paths: List[str], recursive: bool = True) -> List[Dict[str, Any]]:
        """
        Scans given paths (files or directories) and returns a list of candidate items.
        """
        file_list: List[Dict[str, Any]] = []
        seen = set()

        def add_file(fpath: str):
            fpath = os.path.abspath(fpath)
            if fpath in seen:
                return
            ext = os.path.splitext(fpath)[1].lower()
            if ext in AUDIO_EXTENSIONS and os.path.isfile(fpath):
                seen.add(fpath)
                is_ncm = (ext == '.ncm')
                sz = os.path.getsize(fpath)
                file_list.append({
                    'id': str(uuid.uuid4()),
                    'path': fpath,
                    'filename': os.path.basename(fpath),
                    'size': sz,
                    'size_str': f"{sz / 1024 / 1024:.2f} MB",
                    'is_ncm': is_ncm,
                    'status': TaskStatus.PENDING,
                    'status_text': "等待中",
                    'progress': 0.0,
                    'error': None,
                    'output_path': None
                })

        for p in paths:
            if os.path.isfile(p):
                add_file(p)
            elif os.path.isdir(p):
                if recursive:
                    for root, _, files in os.walk(p):
                        for f in files:
                            add_file(os.path.join(root, f))
                else:
                    for f in os.listdir(p):
                        add_file(os.path.join(p, f))

        return file_list

    def run_batch(
        self,
        items: List[Dict[str, Any]],
        target_format: str,      # 'source', 'mp3', or 'aac'
        bitrate: str,            # '320k', '256k', '192k', '128k', 'vbr0', 'vbr2'
        output_dir: str,
        skip_existing: bool = True,
        max_workers: int = 3,
        custom_ffmpeg_path: Optional[str] = None,
        on_item_update: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_total_progress: Optional[Callable[[int, int, float], None]] = None,
        on_finished: Optional[Callable[[Dict[str, Any]], None]] = None
    ):
        """
        Executes batch conversion in a worker thread pool.
        """
        self._cancel_event.clear()
        self._is_running = True

        total_items = len(items)
        completed_count = 0
        success_count = 0
        skipped_count = 0
        failed_count = 0
        start_time = time.time()

        os.makedirs(output_dir, exist_ok=True)
        ffmpeg_exe = find_ffmpeg(custom_ffmpeg_path)

        def should_cancel() -> bool:
            return self._cancel_event.is_set()

        def process_single_item(item: Dict[str, Any]):
            nonlocal completed_count, success_count, skipped_count, failed_count

            if should_cancel():
                item['status'] = TaskStatus.CANCELLED
                item['status_text'] = "⏹️ 已取消"
                if on_item_update:
                    on_item_update(item)
                return

            in_path = item['path']
            base_name = os.path.splitext(item['filename'])[0]

            try:
                # 1. Inspect format & metadata if NCM
                ncm_meta = None
                ncm_format = None
                if item['is_ncm']:
                    try:
                        ncm_info = extract_ncm_info(in_path)
                        ncm_format = ncm_info['format']
                        ncm_meta = ncm_info.get('raw_meta')
                    except Exception:
                        ncm_format = 'mp3'

                # 2. Determine target extension & output path
                if target_format == 'source':
                    ext = ncm_format if item['is_ncm'] else os.path.splitext(in_path)[1].lstrip('.').lower()
                    if not ext:
                        ext = 'mp3'
                elif target_format == 'mp3':
                    ext = 'mp3'
                elif target_format in ('aac', 'm4a'):
                    ext = 'm4a'
                else:
                    ext = 'mp3'

                out_path = os.path.join(output_dir, f"{base_name}.{ext}")
                item['output_path'] = out_path

                # 3. Check skip existing
                if skip_existing and os.path.exists(out_path) and os.path.getsize(out_path) > 1024:
                    item['status'] = TaskStatus.SKIPPED
                    item['status_text'] = "⏭️ 已跳过 (已存在)"
                    item['progress'] = 1.0
                    skipped_count += 1
                    completed_count += 1
                    if on_item_update:
                        on_item_update(item)
                    if on_total_progress:
                        on_total_progress(completed_count, total_items, completed_count / total_items)
                    return

                # 4. Conversion logic
                if item['is_ncm']:
                    # Case A: Source format (decrypt only)
                    if target_format == 'source':
                        item['status'] = TaskStatus.DECRYPTING
                        item['status_text'] = "⚡ 正在解密..."
                        if on_item_update:
                            on_item_update(item)

                        decrypt_ncm(
                            in_path,
                            out_path,
                            progress_callback=lambda p: self._update_item_progress(item, p, on_item_update),
                            should_cancel=should_cancel
                        )

                    # Case B: Target MP3 and source was already MP3 (no lossy re-encoding if 320k)
                    elif target_format == 'mp3' and ncm_format == 'mp3' and bitrate.lower() in ('320k', '320'):
                        item['status'] = TaskStatus.DECRYPTING
                        item['status_text'] = "⚡ 解密并封装 (原曲320k)..."
                        if on_item_update:
                            on_item_update(item)

                        decrypt_ncm(
                            in_path,
                            out_path,
                            progress_callback=lambda p: self._update_item_progress(item, p, on_item_update),
                            should_cancel=should_cancel
                        )

                    # Case C: Re-encoding required (e.g. FLAC -> MP3, or to AAC, or downsample MP3)
                    else:
                        item['status'] = TaskStatus.DECRYPTING
                        item['status_text'] = "⚡ 正在解密临时音频..."
                        if on_item_update:
                            on_item_update(item)

                        # Decrypt to temp file first
                        with tempfile.NamedTemporaryFile(suffix=f".{ncm_format}", delete=False) as tf:
                            temp_audio_path = tf.name

                        try:
                            _, raw_meta, cover_bytes = decrypt_ncm(
                                in_path,
                                temp_audio_path,
                                progress_callback=lambda p: self._update_item_progress(item, p * 0.4, on_item_update),
                                should_cancel=should_cancel
                            )

                            item['status'] = TaskStatus.CONVERTING
                            item['status_text'] = f"🔄 正在转码为 {target_format.upper()}..."
                            if on_item_update:
                                on_item_update(item)

                            def transcode_progress(p: float):
                                self._update_item_progress(item, 0.4 + p * 0.6, on_item_update)

                            convert_audio(
                                input_file=temp_audio_path,
                                output_file=out_path,
                                target_format=target_format,
                                bitrate=bitrate,
                                meta_dict=raw_meta,
                                img_data=cover_bytes,
                                custom_ffmpeg_path=custom_ffmpeg_path,
                                progress_callback=transcode_progress,
                                should_cancel=should_cancel
                            )
                        finally:
                            if os.path.exists(temp_audio_path):
                                try:
                                    os.remove(temp_audio_path)
                                except Exception:
                                    pass

                else:
                    # Regular audio file (not NCM)
                    if target_format == 'source':
                        # Already audio, skip or copy
                        item['status'] = TaskStatus.COMPLETED
                        item['status_text'] = "ℹ️ 原文件已是标准音频"
                        item['progress'] = 1.0
                        success_count += 1
                        completed_count += 1
                        if on_item_update:
                            on_item_update(item)
                        if on_total_progress:
                            on_total_progress(completed_count, total_items, completed_count / total_items)
                        return
                    else:
                        item['status'] = TaskStatus.CONVERTING
                        item['status_text'] = f"🔄 正在转码为 {target_format.upper()}..."
                        if on_item_update:
                            on_item_update(item)

                        convert_audio(
                            input_file=in_path,
                            output_file=out_path,
                            target_format=target_format,
                            bitrate=bitrate,
                            custom_ffmpeg_path=custom_ffmpeg_path,
                            progress_callback=lambda p: self._update_item_progress(item, p, on_item_update),
                            should_cancel=should_cancel
                        )

                item['status'] = TaskStatus.COMPLETED
                item['status_text'] = "✅ 转换完成"
                item['progress'] = 1.0
                success_count += 1

            except InterruptedError:
                item['status'] = TaskStatus.CANCELLED
                item['status_text'] = "⏹️ 已取消"
            except Exception as e:
                item['status'] = TaskStatus.FAILED
                item['status_text'] = f"❌ 失败: {str(e)}"
                item['error'] = str(e)
                failed_count += 1
            finally:
                completed_count += 1
                if on_item_update:
                    on_item_update(item)
                if on_total_progress:
                    on_total_progress(completed_count, total_items, completed_count / total_items)

        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        futures = [self._executor.submit(process_single_item, it) for it in items]

        for _ in as_completed(futures):
            pass

        self._executor.shutdown(wait=True)
        self._is_running = False

        elapsed = time.time() - start_time
        summary = {
            'total': total_items,
            'completed': completed_count,
            'success': success_count,
            'skipped': skipped_count,
            'failed': failed_count,
            'cancelled': self._cancel_event.is_set(),
            'elapsed_sec': round(elapsed, 1),
            'output_dir': output_dir
        }

        if on_finished:
            on_finished(summary)

    def _update_item_progress(
        self,
        item: Dict[str, Any],
        progress: float,
        callback: Optional[Callable[[Dict[str, Any]], None]]
    ):
        item['progress'] = max(0.0, min(1.0, progress))
        if callback:
            callback(item)
