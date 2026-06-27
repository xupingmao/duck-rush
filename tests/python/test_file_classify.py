#!/usr/bin/env python3
"""只读测试 — file-classify，不真实移动文件"""

import os
import sys
import unittest
import tempfile
import importlib.util

PROJECT_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
MODULE_PATH = os.path.join(PROJECT_ROOT, "duck_rush", "fs", "file-classify.py")

spec = importlib.util.spec_from_file_location("file_classify", MODULE_PATH)
fc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fc)


class TestConvertConfigToSet(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(fc.convert_config_to_set(""), set())

    def test_single(self):
        self.assertEqual(fc.convert_config_to_set("txt"), {".txt"})

    def test_multiple(self):
        result = fc.convert_config_to_set("txt|jpg|png")
        self.assertEqual(result, {".txt", ".jpg", ".png"})

    def test_leading_dot_preserved(self):
        result = fc.convert_config_to_set(".txt|.jpg")
        self.assertEqual(result, {".txt", ".jpg"})

    def test_mixed_dots(self):
        result = fc.convert_config_to_set("txt|.jpg|png")
        self.assertEqual(result, {".txt", ".jpg", ".png"})

    def test_empty_items_skipped(self):
        result = fc.convert_config_to_set("txt||jpg")
        self.assertEqual(result, {".txt", ".jpg"})


class TestHasDatePrefix(unittest.TestCase):
    def test_matches(self):
        self.assertTrue(fc.has_date_prefix("20260627_test"))
        self.assertTrue(fc.has_date_prefix("20260627_测试"))
        self.assertTrue(fc.has_date_prefix("20260627_123"))

    def test_too_short(self):
        self.assertFalse(fc.has_date_prefix("2026"))

    def test_no_underscore(self):
        self.assertFalse(fc.has_date_prefix("20260627test"))

    def test_non_digit_prefix(self):
        self.assertFalse(fc.has_date_prefix("abc_test"))


class TestBuildTargetPath(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.tmpfile = os.path.join(self.tmpdir.name, "test.txt")
        with open(self.tmpfile, "w") as f:
            f.write("hello")

    def tearDown(self):
        self.tmpdir.cleanup()

    def assert_path_components(self, target, dest, fname):
        self.assertIn(dest, target)
        self.assertTrue(target.endswith(fname), "%s does not end with %s" % (target, fname))
        # between dest and filename there should be a year dir
        suffix = target[len(dest):]
        self.assertRegex(suffix, r"[/\\]\d{4}[/\\].+")

    def test_normal_file(self):
        dest = os.path.join("", "dest")
        target = fc.build_target_path(dest, self.tmpfile)
        self.assert_path_components(target, dest, "_test.txt")
        self.assertRegex(target, r"\d{8}_test\.txt$")

    def test_file_with_date_prefix(self):
        fpath = os.path.join(self.tmpdir.name, "20260627_test.txt")
        with open(fpath, "w") as f:
            f.write("data")
        dest = os.path.join("", "dest")
        target = fc.build_target_path(dest, fpath)
        self.assert_path_components(target, dest, "20260627_test.txt")

    def test_file_with_dup_date_prefix(self):
        fpath = os.path.join(self.tmpdir.name, "20260627_20260627_test.txt")
        with open(fpath, "w") as f:
            f.write("data")
        dest = os.path.join("", "dest")
        target = fc.build_target_path(dest, fpath)
        self.assert_path_components(target, dest, "20260627_test.txt")


class TestCheckFileByExt(unittest.TestCase):
    def test_match(self):
        self.assertTrue(fc.check_file_by_ext("foo.txt", {".txt"}))

    def test_no_match(self):
        self.assertFalse(fc.check_file_by_ext("foo.jpg", {".txt"}))

    def test_case_insensitive(self):
        self.assertTrue(fc.check_file_by_ext("foo.TXT", {".txt"}))

    def test_empty_set(self):
        self.assertFalse(fc.check_file_by_ext("foo.txt", set()))


class TestIsHiddenFile(unittest.TestCase):
    def test_dot_prefix(self):
        self.assertTrue(fc.is_hidden_file(".bashrc"))

    def test_ds_store(self):
        self.assertTrue(fc.is_hidden_file(".DS_Store"))

    def test_normal_file(self):
        self.assertFalse(fc.is_hidden_file("test.txt"))


class TestGetHome(unittest.TestCase):
    def test_returns_string(self):
        home = fc.get_home()
        self.assertIsInstance(home, str)
        self.assertTrue(os.path.isabs(home))


class TestGetDirs(unittest.TestCase):
    def test_get_download_dir(self):
        d = fc.get_download_dir()
        self.assertTrue(d.endswith("Downloads"))

    def test_get_document_dir(self):
        d = fc.get_document_dir()
        self.assertTrue(d.endswith("Documents"))

    def test_get_music_dir(self):
        d = fc.get_music_dir()
        self.assertTrue(d.endswith("Music"))

    def test_get_image_dir(self):
        d = fc.get_image_dir()
        self.assertTrue(d.endswith("Pictures"))

    def test_get_archive_dir(self):
        d = fc.get_archive_dir()
        self.assertTrue(d.endswith("Archives"))
        self.assertTrue("Downloads" in d)

    def test_get_program_dir(self):
        d = fc.get_program_dir()
        self.assertTrue(d.endswith("Programs"))
        self.assertTrue("Downloads" in d)


class TestResolveTargetPath(unittest.TestCase):
    def test_non_existing_returns_same(self):
        result = fc.resolve_target_path("/nonexistent/path/file.txt")
        self.assertEqual(result, "/nonexistent/path/file.txt")

    def test_existing_appends_counter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = os.path.join(tmpdir, "test.txt")
            with open(fpath, "w") as f:
                f.write("data")
            result = fc.resolve_target_path(fpath)
            self.assertNotEqual(result, fpath)
            self.assertRegex(result, r"test_\d+\.txt$")

    def test_multiple_existing_increments_counter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = os.path.join(tmpdir, "test.txt")
            with open(base, "w") as f:
                f.write("0")
            with open(os.path.join(tmpdir, "test_1.txt"), "w") as f:
                f.write("1")
            result = fc.resolve_target_path(base)
            self.assertRegex(result, r"test_2\.txt$")


class TestClassifierCheck(unittest.TestCase):
    def test_document_classifier(self):
        c = fc.DocumentClassifier()
        self.assertTrue(c.check("report.pdf"))
        self.assertTrue(c.check("doc.docx"))
        self.assertTrue(c.check("notes.txt"))
        self.assertFalse(c.check("song.mp3"))

    def test_music_classifier(self):
        c = fc.MusicClassifier()
        self.assertTrue(c.check("song.mp3"))
        self.assertTrue(c.check("track.wav"))
        self.assertFalse(c.check("doc.pdf"))

    def test_image_classifier(self):
        c = fc.ImageClassifier()
        self.assertTrue(c.check("photo.jpg"))
        self.assertTrue(c.check("image.png"))
        self.assertFalse(c.check("doc.pdf"))

    def test_video_classifier(self):
        c = fc.VideoClassifier()
        self.assertTrue(c.check("video.mp4"))
        self.assertTrue(c.check("movie.mkv"))
        self.assertFalse(c.check("doc.pdf"))

    def test_archive_classifier(self):
        c = fc.ArchiveClassifier()
        self.assertTrue(c.check("archive.zip"))
        self.assertTrue(c.check("data.rar"))
        self.assertTrue(c.check("disk.iso"))
        self.assertFalse(c.check("installer.exe"))

    def test_program_classifier(self):
        c = fc.ProgramClassifier()
        self.assertTrue(c.check("installer.exe"))
        self.assertTrue(c.check("package.dmg"))
        self.assertTrue(c.check("app.msi"))
        self.assertTrue(c.check("app.apk"))
        self.assertFalse(c.check("archive.zip"))


class TestGetTargetPath(unittest.TestCase):
    def test_pdf_goes_to_documents(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = os.path.join(tmpdir, "report.pdf")
            with open(fpath, "w") as f:
                f.write("pdf")
            result = fc.get_target_path(fpath)
            self.assertIsNotNone(result)
            self.assertIn("Documents", result)
            self.assertRegex(result, r"\d{8}_report\.pdf$")

    def test_mp3_goes_to_music(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = os.path.join(tmpdir, "song.mp3")
            with open(fpath, "w") as f:
                f.write("mp3")
            result = fc.get_target_path(fpath)
            self.assertIsNotNone(result)
            self.assertIn("Music", result)

    def test_exe_goes_to_programs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = os.path.join(tmpdir, "setup.exe")
            with open(fpath, "w") as f:
                f.write("exe")
            result = fc.get_target_path(fpath)
            self.assertIsNotNone(result)
            self.assertIn("Programs", result)

    def test_unknown_extension_returns_none(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = os.path.join(tmpdir, "unknown.xyz")
            with open(fpath, "w") as f:
                f.write("data")
            result = fc.get_target_path(fpath)
            self.assertIsNone(result)


class TestClassifyPreview(unittest.TestCase):
    def test_classify0_dry_run_does_not_move(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = os.path.join(tmpdir, "test.txt")
            with open(fpath, "w") as f:
                f.write("data")
            result = fc.classify0(tmpdir, confirmed=False)
            self.assertTrue(result)
            self.assertTrue(os.path.exists(fpath))

    def test_classify0_returns_false_when_no_matches(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = os.path.join(tmpdir, "test.xyz")
            with open(fpath, "w") as f:
                f.write("data")
            result = fc.classify0(tmpdir, confirmed=False)
            self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
