# -*- coding: utf-8 -*-
"""
test_suite.py - Comprehensive Unit & Integration Test Suite for CloudMusicConverter
"""

import os
import sys
import unittest
import tempfile
import shutil

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from config import DEFAULT_CONFIG, load_config, save_config
from ncm_cipher import is_ncm_file, extract_ncm_info, decrypt_ncm, NotNCMError
from ffmpeg_engine import find_ffmpeg, get_ffmpeg_version
from task_manager import ConversionTaskManager, TaskStatus


class TestConfig(unittest.TestCase):
    def test_default_config_keys(self):
        self.assertIn("target_format", DEFAULT_CONFIG)
        self.assertIn("mp3_bitrate", DEFAULT_CONFIG)
        self.assertIn("aac_bitrate", DEFAULT_CONFIG)
        self.assertIn("auto_filter_existing", DEFAULT_CONFIG)
        self.assertIn("skip_existing", DEFAULT_CONFIG)

    def test_load_and_save(self):
        cfg = load_config()
        self.assertIsInstance(cfg, dict)
        cfg["test_key"] = "test_val"
        save_config(cfg)
        loaded = load_config()
        self.assertEqual(loaded.get("test_key"), "test_val")


class TestFFmpegEngine(unittest.TestCase):
    def test_find_ffmpeg(self):
        p = find_ffmpeg()
        self.assertIsNotNone(p, "FFmpeg should be detected on the system")
        self.assertTrue(os.path.isfile(p))

    def test_ffmpeg_version(self):
        p = find_ffmpeg()
        if p:
            v = get_ffmpeg_version(p)
            self.assertIn("ffmpeg", v.lower())


class TestTaskManagerComparison(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_output_map_and_conversion_check(self):
        # Create dummy completed audio files
        mp3_file = os.path.join(self.temp_dir, "Song One.mp3")
        m4a_file = os.path.join(self.temp_dir, "Song Two.m4a")
        with open(mp3_file, 'wb') as f:
            f.write(b"data" * 500)
        with open(m4a_file, 'wb') as f:
            f.write(b"data" * 500)

        existing_map = ConversionTaskManager.get_existing_output_map(self.temp_dir)
        self.assertIn("song one", existing_map)
        self.assertIn("song two", existing_map)

        # Check MP3 conversion
        self.assertTrue(ConversionTaskManager.is_item_already_converted("Song One.ncm", existing_map, "mp3"))
        self.assertFalse(ConversionTaskManager.is_item_already_converted("Song Two.ncm", existing_map, "mp3"))

        # Check AAC conversion
        self.assertTrue(ConversionTaskManager.is_item_already_converted("Song Two.ncm", existing_map, "aac"))
        self.assertFalse(ConversionTaskManager.is_item_already_converted("Song One.ncm", existing_map, "aac"))

        # Check non-existent song
        self.assertFalse(ConversionTaskManager.is_item_already_converted("Song Three.ncm", existing_map, "mp3"))


class TestNcmCipher(unittest.TestCase):
    def test_non_ncm_file(self):
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            tf.write(b"NOT_A_NCM_HEADER")
            tf_path = tf.name
        try:
            self.assertFalse(is_ncm_file(tf_path))
            with self.assertRaises(NotNCMError):
                extract_ncm_info(tf_path)
        finally:
            if os.path.exists(tf_path):
                os.remove(tf_path)

    def test_real_ncm_decryption(self):
        vip_dir = r"D:\CloudMusic\VipSongsDownload"
        ncm_files = [os.path.join(vip_dir, f) for f in os.listdir(vip_dir) if f.endswith(".ncm")]
        if not ncm_files:
            self.skipTest("No NCM files found in VIP download directory")

        sample_ncm = ncm_files[0]
        self.assertTrue(is_ncm_file(sample_ncm))

        info = extract_ncm_info(sample_ncm)
        self.assertIn(info['format'], ['mp3', 'flac'])
        self.assertTrue(len(info['musicName']) > 0)

        with tempfile.NamedTemporaryFile(suffix=f".{info['format']}", delete=False) as tf:
            out_tmp = tf.name

        try:
            out_path, meta, img = decrypt_ncm(sample_ncm, out_tmp)
            self.assertTrue(os.path.isfile(out_path))
            self.assertGreater(os.path.getsize(out_path), 1024 * 1024)
        finally:
            if os.path.exists(out_tmp):
                os.remove(out_tmp)


if __name__ == '__main__':
    unittest.main()
