#!/usr/bin/env python3
"""
Project Aid — Image & Task Inspection Tool
Allows human reviewers to inspect image properties, verify clinical notes,
and manage the human QA approval gate for tasks.
"""

import os
import json
import argparse
from typing import Dict, Any, List
from PIL import Image


def load_tasks(tasks_path: str = "metadata/tasks.json") -> List[Dict[str, Any]]:
    if not os.path.exists(tasks_path):
        return []
    with open(tasks_path, "r") as f:
        return json.load(f)


def save_tasks(tasks: List[Dict[str, Any]], tasks_path: str = "metadata/tasks.json"):
    with open(tasks_path, "w") as f:
        json.dump(tasks, f, indent=2)


def inspect_task(task_id: str, tasks_path: str = "metadata/tasks.json"):
    tasks = load_tasks(tasks_path)
    target = None
    for t in tasks:
        if t.get("task_id") == task_id:
            target = t
            break

    if not target:
        print(f"Task '{task_id}' not found in {tasks_path}")
        return

    print("\n========================================================")
    print(f"       Task Inspection: {task_id}")
    print("========================================================")
    print(f"Domain:          {target.get('domain')}")
    print(f"Context Note:    \"{target.get('image_context')}\"")
    print(f"Image Path:      {target.get('image_path')}")
    print(f"Source URL:      {target.get('source_url', 'N/A')}")
    print(f"License:         {target.get('license', 'N/A')}")
    print(f"QA Status:       {target.get('qa_status', 'pending').upper()}")
    print(f"Reviewer Notes:  {target.get('reviewer_notes', 'None')}")

    img_path = target.get("image_path", "")
    if os.path.exists(img_path):
        try:
            with Image.open(img_path) as img:
                w, h = img.size
                print("\nImage Technical Details:")
                print(f"  Dimensions:    {w} x {h} px")
                print(f"  Format:        {img.format}")
                print(f"  Color Mode:    {img.mode}")
                print(f"  Aspect Ratio:  {(w/h):.2f}:1")
                print(f"  File Size:     {os.path.getsize(img_path) / 1024:.1f} KB")
        except Exception as e:
            print(f"\nImage Error: {e}")
    else:
        print(f"\n⚠️ Image file missing: {img_path}")

    print("========================================================\n")


def update_task_qa(task_id: str, new_status: str, notes: str, tasks_path: str = "metadata/tasks.json"):
    tasks = load_tasks(tasks_path)
    found = False
    for t in tasks:
        if t.get("task_id") == task_id:
            t["qa_status"] = new_status
            t["reviewer_notes"] = notes
            found = True
            break

    if not found:
        print(f"Task '{task_id}' not found.")
        return

    save_tasks(tasks, tasks_path)
    print(f"✅ Successfully updated Task '{task_id}': status='{new_status}', notes='{notes}'")


def list_summary(tasks_path: str = "metadata/tasks.json"):
    tasks = load_tasks(tasks_path)
    print(f"\nTotal Tasks: {len(tasks)}")
    counts = {}
    for t in tasks:
        if t.get("_schema_note"):
            continue
        status = t.get("qa_status", "pending")
        counts[status] = counts.get(status, 0) + 1

    print("Status Breakdown:")
    for status, count in counts.items():
        print(f"  {status.upper():15}: {count}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Inspect task and manage human QA approval status.")
    parser.add_argument("--task", help="Task ID to inspect")
    parser.add_argument("--approve", action="store_true", help="Approve task after human inspection")
    parser.add_argument("--reject", action="store_true", help="Reject task")
    parser.add_argument("--notes", help="Reviewer notes (required when approving/rejecting)")
    parser.add_argument("--summary", action="store_true", help="Display summary status of all tasks")
    parser.add_argument("--tasks-file", default="metadata/tasks.json", help="Path to tasks.json")
    args = parser.parse_args()

    if args.summary:
        list_summary(args.tasks_file)
        return 0

    if not args.task:
        parser.print_help()
        return 1

    if args.approve:
        if not args.notes:
            print("Error: --notes must be provided when approving a task.")
            return 1
        update_task_qa(args.task, "approved", args.notes, args.tasks_file)
    elif args.reject:
        if not args.notes:
            print("Error: --notes must be provided when rejecting a task.")
            return 1
        update_task_qa(args.task, "rejected", args.notes, args.tasks_file)
    else:
        inspect_task(args.task, args.tasks_file)

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
