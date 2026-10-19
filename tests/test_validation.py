#!/usr/bin/env python3
"""
Project Aid — Comprehensive Validation & Tool Test Suite
Tests validation logic against valid worked examples from the PDF and deliberately invalid cases.
"""

import os
import sys
import unittest
from PIL import Image

# Add tools directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tools")))
from validate_task import (
    validate_domain,
    validate_context_note,
    validate_image_file,
    validate_task_entry,
    VALID_DOMAINS
)
from deduplicate import compute_sha256, compute_dhash, hamming_distance


class TestDomainValidation(unittest.TestCase):
    def test_valid_pdf_domains(self):
        """All 5 exact domain strings from PDF Page 3 must pass."""
        expected_domains = [
            "Wound Triage",
            "Skin Lesion Screening",
            "Burn Classification",
            "Rash Identification",
            "Red-Eye Triage"
        ]
        self.assertEqual(VALID_DOMAINS, expected_domains)
        for domain in expected_domains:
            ok, msg = validate_domain(domain)
            self.assertTrue(ok, f"Domain '{domain}' should be valid, but failed: {msg}")

    def test_invalid_domains(self):
        """Invalid, misspelled, or lowercase domains must fail."""
        invalid = [
            "wound triage",
            "Wound Care",
            "Dermatology",
            "Eye",
            "Red Eye Triage",  # missing hyphen
            "General Health",
            "",
            None
        ]
        for domain in invalid:
            ok, msg = validate_domain(domain)
            self.assertFalse(ok, f"Domain '{domain}' should fail, but passed.")


class TestContextNoteValidation(unittest.TestCase):
    def test_pdf_worked_examples_pass(self):
        """The 10 official worked examples from PDF Pages 9-13 must all pass."""
        pdf_worked_examples = [
            "This is a diabetic foot ulcer.",
            "This is a superficial abrasion.",
            "This is melanoma.",
            "This is a benign mole.",
            "This is a partial-thickness burn on the palm.",
            "This is a sunburn (superficial burn).",
            "This is hand-foot-and-mouth disease.",
            "This is poison ivy (allergic contact dermatitis).",
            "This is bacterial conjunctivitis.",
            "This is a subconjunctival hemorrhage.",
        ]
        for note in pdf_worked_examples:
            ok, flags = validate_context_note(note)
            self.assertTrue(ok, f"Official PDF example '{note}' failed validation: {flags}")

    def test_disposition_and_advice_fails(self):
        """Context notes containing disposition, urgency, or treatment advice must fail."""
        failing_notes = [
            "This is a burn that requires emergency treatment.",
            "This looks like a serious infected wound and needs antibiotics.",
            "This is a wound that needs stitches immediately.",
            "This is a deep burn that should be sent to a burn center.",
            "This is an eye irritation suitable for home care.",
            "Call 911 for this wound."
        ]
        for note in failing_notes:
            ok, flags = validate_context_note(note)
            self.assertFalse(ok, f"Note '{note}' should have failed disposition check.")
            self.assertTrue(any("management/disposition" in f.lower() for f in flags))

    def test_multi_sentence_notes_fail(self):
        """Notes with multiple sentences (the #1 rejection trap) must fail."""
        multi_sentence = (
            "This is a deep partial-thickness burn on the palm that is extremely painful. "
            "It will likely need referral to a burn center for proper treatment."
        )
        ok, flags = validate_context_note(multi_sentence)
        self.assertFalse(ok)
        self.assertTrue(any("multiple sentences" in f.lower() for f in flags))

    def test_vague_notes_flagged(self):
        """Vague descriptions (e.g. 'Red eye') must raise a warning flag for review."""
        vague_examples = ["Red eye.", "Rash", "Wound.", "Burn"]
        for note in vague_examples:
            ok, flags = validate_context_note(note)
            self.assertTrue(any("too vague" in f.lower() for f in flags), f"Vague note '{note}' was not flagged.")


class TestImageValidationAndDeduplication(unittest.TestCase):
    def setUp(self):
        self.test_img_path = "/tmp/test_single_img.png"
        self.test_multi_img_path = "/tmp/test_multi_img.gif"
        
        # Create a valid single test image
        img = Image.new("RGB", (300, 300), color=(120, 150, 180))
        img.save(self.test_img_path)

        # Create an animated/multi-frame GIF
        img1 = Image.new("RGB", (100, 100), color=(255, 0, 0))
        img2 = Image.new("RGB", (100, 100), color=(0, 255, 0))
        img1.save(self.test_multi_img_path, save_all=True, append_images=[img2], duration=100, loop=0)

    def tearDown(self):
        for p in [self.test_img_path, self.test_multi_img_path]:
            if os.path.exists(p):
                os.remove(p)

    def test_valid_image(self):
        ok, flags, info = validate_image_file(self.test_img_path)
        self.assertTrue(ok, f"Valid image failed: {flags}")
        self.assertEqual(info["size"], (300, 300))

    def test_multi_frame_image_fails(self):
        ok, flags, info = validate_image_file(self.test_multi_img_path)
        self.assertFalse(ok)
        self.assertTrue(any("multiple frames" in f.lower() for f in flags))

    def test_missing_image_fails(self):
        ok, flags, info = validate_image_file("/tmp/non_existent_image_12345.jpg")
        self.assertFalse(ok)
        self.assertTrue(any("not found" in f.lower() for f in flags))

    def test_deduplication_exact_and_hamming(self):
        sha1 = compute_sha256(self.test_img_path)
        sha2 = compute_sha256(self.test_img_path)
        self.assertEqual(sha1, sha2)

        dh1 = compute_dhash(self.test_img_path)
        dh2 = compute_dhash(self.test_img_path)
        self.assertEqual(hamming_distance(dh1, dh2), 0)


class TestHumanQAGate(unittest.TestCase):
    def test_task_status_transitions(self):
        """A task cannot be approved unless reviewer_notes are recorded."""
        test_task = {
            "task_id": "TEST-01",
            "domain": "Wound Triage",
            "image_path": "/tmp/test_single_img.png",
            "image_context": "This is a superficial abrasion.",
            "source_url": "https://example.org",
            "qa_status": "pending",
            "reviewer_notes": ""
        }
        img = Image.new("RGB", (300, 300), color=(100, 100, 100))
        img.save("/tmp/test_single_img.png")

        # Before human review, computed status should be needs_review
        res = validate_task_entry(test_task)
        self.assertEqual(res["computed_status"], "needs_review")

        # After human review and notes added, status can be approved
        test_task["qa_status"] = "approved"
        test_task["reviewer_notes"] = "Clinically verified from source case study. No PII."
        res = validate_task_entry(test_task)
        self.assertEqual(res["computed_status"], "approved")

        if os.path.exists("/tmp/test_single_img.png"):
            os.remove("/tmp/test_single_img.png")


if __name__ == "__main__":
    unittest.main()
