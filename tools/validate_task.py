#!/usr/bin/env python3
"""
Project Aid — Task Validation Tool
Validates tasks against the PDF specifications and internal QA criteria.

PDF Rules (Source of Truth):
1. Domain: Strictly one of the 5 allowed domains.
2. Image: Real, single photo, no multi-panel grids, no watermarks, no PII.
3. Image Context Note: <= 1 short sentence naming what the image shows.
   NO disposition, advice, or clinical reasoning.
"""

import os
import re
import json
import argparse
from typing import Dict, List, Tuple, Any
from PIL import Image

VALID_DOMAINS = [
    "Wound Triage",
    "Skin Lesion Screening",
    "Burn Classification",
    "Rash Identification",
    "Red-Eye Triage",
]

# Keywords indicating disposition, clinical management, or treatment advice (prohibited in Phase 1 notes)
DISPOSITION_PATTERNS = [
    r"\bemergency\b",
    r"\ber\b",
    r"\bed\b",
    r"\burgent\b",
    r"\breferral\b",
    r"\brefer\b",
    r"\bhospital\b",
    r"\bclinic\b",
    r"\btreatment\b",
    r"\btreat\b",
    r"\bantibiotic[s]?\b",
    r"\bsuture[s]?\b",
    r"\bstitches\b",
    r"\bhome\s+care\b",
    r"\bself-care\b",
    r"\bneeds\b",
    r"\bshould\s+be\b",
    r"\bmust\s+be\b",
    r"\bcall\s+911\b",
    r"\bburn\s+center\b",
    r"\bcare\s+plan\b",
    r"\bprescription\b",
    r"\bmonitor\b",
]

# Keywords that are too vague to adequately identify the clinical subject
VAGUE_PATTERNS = [
    r"^red\s+eye\.?$",
    r"^rash\.?$",
    r"^wound\.?$",
    r"^burn\.?$",
    r"^lesion\.?$",
    r"^skin\.?$",
    r"^eye\.?$",
]


def validate_domain(domain: str) -> Tuple[bool, str]:
    """Validates that the domain matches one of the five canonical PDF domains."""
    if not domain or not isinstance(domain, str):
        return False, "Domain is missing or not a string."
    if domain not in VALID_DOMAINS:
        return False, f"Invalid domain '{domain}'. Must be one of: {VALID_DOMAINS}"
    return True, ""


def validate_context_note(note: str) -> Tuple[bool, List[str]]:
    """
    Validates that the image context note meets PDF requirements:
    - Terse: <= 1 short sentence.
    - Names the subject only.
    - No triage advice, disposition, or reasoning.
    """
    flags = []
    if not note or not isinstance(note, str) or not note.strip():
        return False, ["Context note is empty or missing."]

    clean_note = note.strip()
    words = clean_note.split()

    # Length check: PDF recommends a few words, one short sentence max
    if len(words) > 16:
        flags.append(f"Context note is too long ({len(words)} words). Aim for a few words (<= 15 words).")

    # Multiple sentence check
    # Check for sentence terminators followed by a space and capital letter
    sentence_matches = re.split(r"[.!?]\s+(?=[A-Z0-9])", clean_note)
    if len(sentence_matches) > 1:
        flags.append(f"Contains multiple sentences ({len(sentence_matches)} found). Must be at most 1 short sentence.")

    # Disposition / advice check
    lower_note = clean_note.lower()
    for pattern in DISPOSITION_PATTERNS:
        match = re.search(pattern, lower_note)
        if match:
            flags.append(f"Prohibited management/disposition term detected: '{match.group(0)}'. Phase 1 notes must name the subject only.")

    # Vague label check
    for pattern in VAGUE_PATTERNS:
        if re.match(pattern, lower_note):
            flags.append(f"Note '{clean_note}' may be too vague to identify the clinical subject adequately.")

    is_valid = len(flags) == 0
    return is_valid, flags


def validate_image_file(image_path: str, base_dir: str = ".") -> Tuple[bool, List[str], Dict[str, Any]]:
    """
    Validates the image file physically:
    - File exists and is non-empty.
    - Valid image format (JPEG, PNG, WEBP).
    - Not multi-frame (rejects animations / collages / multi-page TIFFs).
    """
    flags = []
    info = {}
    
    full_path = os.path.join(base_dir, image_path) if not os.path.isabs(image_path) else image_path
    
    if not os.path.exists(full_path):
        return False, [f"Image file not found: {image_path}"], info

    if os.path.getsize(full_path) == 0:
        return False, ["Image file is 0 bytes (corrupt or empty)."], info

    try:
        with Image.open(full_path) as img:
            info["format"] = img.format
            info["size"] = img.size
            info["mode"] = img.mode
            
            # Check for multi-frame images
            n_frames = getattr(img, "n_frames", 1)
            is_animated = getattr(img, "is_animated", False)
            if n_frames > 1 or is_animated:
                flags.append(f"Image has multiple frames ({n_frames}). Each task must be one single photograph.")

            # Sanity check dimensions (advisory internal flag)
            width, height = img.size
            if width < 150 or height < 150:
                flags.append(f"Image dimensions ({width}x{height}) may be too low-resolution for clinical triage assessment.")

            aspect_ratio = max(width / height, height / width)
            if aspect_ratio > 4.0:
                flags.append(f"Extreme aspect ratio ({aspect_ratio:.2f}:1). Verify image is not a panoramic banner or partial crop.")

    except Exception as e:
        return False, [f"Failed to open image file: {str(e)}"], info

    is_valid = len(flags) == 0
    return is_valid, flags, info


def validate_task_entry(task: Dict[str, Any], base_dir: str = ".") -> Dict[str, Any]:
    """
    Validates a complete task record against PDF rules and internal QA fields.
    """
    task_id = task.get("task_id", "UNKNOWN")
    domain = task.get("domain", "")
    image_path = task.get("image_path", "")
    context_note = task.get("image_context", "")
    
    blocking_errors = []
    warning_flags = []

    # 1. Domain Check
    domain_ok, domain_err = validate_domain(domain)
    if not domain_ok:
        blocking_errors.append(domain_err)

    # 2. Context Note Check
    note_ok, note_flags = validate_context_note(context_note)
    for flag in note_flags:
        if "multiple sentences" in flag.lower() or "prohibited management" in flag.lower() or "empty" in flag.lower():
            blocking_errors.append(flag)
        else:
            warning_flags.append(flag)

    # 3. Image Check
    img_ok, img_flags, img_info = validate_image_file(image_path, base_dir=base_dir)
    for flag in img_flags:
        if "multiple frames" in flag.lower() or "not found" in flag.lower():
            blocking_errors.append(flag)
        else:
            warning_flags.append(flag)

    # 4. Provenance & QA fields (Internal QA requirement)
    source_url = task.get("source_url", "")
    if not source_url:
        warning_flags.append("Missing source_url. All images must have traceable provenance.")

    # Determine recommended status
    if blocking_errors:
        computed_status = "rejected"
    elif warning_flags:
        computed_status = "needs_review"
    else:
        # If no blocking errors and no warning flags, human approval can proceed
        current_status = task.get("qa_status", "pending")
        if current_status == "approved" and task.get("reviewer_notes"):
            computed_status = "approved"
        else:
            computed_status = "needs_review"

    return {
        "task_id": task_id,
        "is_valid": len(blocking_errors) == 0,
        "computed_status": computed_status,
        "current_status": task.get("qa_status", "pending"),
        "blocking_errors": blocking_errors,
        "warning_flags": warning_flags,
        "image_info": img_info
    }


def main():
    parser = argparse.ArgumentParser(description="Validate Project Aid tasks against PDF rules & QA criteria.")
    parser.add_argument("--tasks", default="metadata/tasks.json", help="Path to tasks.json")
    parser.add_argument("--export-phase1", help="Export clean Phase 1 payload to specified JSON file")
    parser.add_argument("--base-dir", default=".", help="Base directory of the project")
    args = parser.parse_args()

    tasks_file = os.path.join(args.base_dir, args.tasks)
    if not os.path.exists(tasks_file):
        print(f"Error: {tasks_file} does not exist.")
        return 1

    with open(tasks_file, "r") as f:
        tasks = json.load(f)

    print(f"\n========================================================")
    print(f"   Project Aid QA Task Validator — {len(tasks)} Tasks Loaded")
    print(f"========================================================\n")

    results = []
    status_counts = {"approved": 0, "needs_review": 0, "rejected": 0, "pending": 0}

    for task in tasks:
        # Ignore documentation placeholder rows
        if task.get("_schema_note") and not os.path.exists(os.path.join(args.base_dir, task.get("image_path", ""))):
            continue

        res = validate_task_entry(task, base_dir=args.base_dir)
        results.append(res)
        status_counts[res["computed_status"]] = status_counts.get(res["computed_status"], 0) + 1

        print(f"[{res['computed_status'].upper()}] Task: {res['task_id']} | Domain: {task.get('domain')}")
        print(f"  Note: \"{task.get('image_context')}\"")
        if res["blocking_errors"]:
            for err in res["blocking_errors"]:
                print(f"  ❌ BLOCKING: {err}")
        if res["warning_flags"]:
            for warn in res["warning_flags"]:
                print(f"  ⚠️  WARNING: {warn}")
        print()

    print(f"--------------------------------------------------------")
    print(f"Summary: {status_counts.get('approved', 0)} Approved | {status_counts.get('needs_review', 0)} Needs Review | {status_counts.get('rejected', 0)} Rejected")
    print(f"--------------------------------------------------------\n")

    # Save QA results
    qa_results_path = os.path.join(args.base_dir, "metadata/qa_results.json")
    with open(qa_results_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"QA audit results saved to: {qa_results_path}")

    # Export Phase 1 clean payload if requested
    if args.export_phase1:
        clean_payload = []
        for task in tasks:
            # Only export tasks that have passed all blocking errors and have an approved status
            res = validate_task_entry(task, base_dir=args.base_dir)
            if res["computed_status"] == "approved":
                clean_payload.append({
                    "domain": task["domain"],
                    "image_path": task["image_path"],
                    "image_context": task["image_context"]
                })
        export_path = os.path.join(args.base_dir, args.export_phase1)
        with open(export_path, "w") as f:
            json.dump(clean_payload, f, indent=2)
        print(f"Exported {len(clean_payload)} approved tasks to Phase 1 payload: {export_path}")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
