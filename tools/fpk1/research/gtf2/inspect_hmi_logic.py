#!/usr/bin/env python3
"""Curated GTF2-owned control-flow log anchors, without extracting firmware assets.

Usage: python3 tools/fpk1/research/gtf2/inspect_hmi_logic.py /path/to/gtf2
Offsets are file offsets; use ELF PT_LOAD to convert them to virtual addresses.
"""
import argparse
import hashlib
import json
from pathlib import Path

ANCHORS = {
    "activation": [
        "GssMan2HMIReplyImpl::activate()",
        "GssMan2HMIReplyImpl::deactivate()",
        "GssMan2HMIReplyImpl::enterColdCrank()",
        "GssMan2HMIReplyImpl::leaveColdCrank()",
        "GssMan2HMIReplyImpl::switchDisplayBacklight(), no proxy?",
        "GssMan2HMIReplyImpl::persistentData()",
    ],
    "loading": [
        "handleLoadingKZBs()",
        "handleLoadingKZBs(), EarlyTubes loaded",
        "handleLoadingKZBs(), ClusterFull loaded",
        "handleLoadingKZBs(), 3D Car Loaded",
        "handleLoadingKZBs(), Requesting Early Tubes",
        "handleLoadingKZBs(), Waiting %i frames",
        "handleLoadingKZBs(), Done waiting -> Requesting Cluster Full",
        "handleLoadingKZBs(), 3D Car Requested",
        "Delay the HMI start by %u ms.",
        "Non-ECL Mode Enabled. Starting HMI immediately.",
    ],
    "assets": [
        "CHMIGTFAssetManager::KZBListener::process, eventId = %lld",
        "CHMIGTFAssetManager::KZBListener::process, mergeEvent NULL",
        "CHMIGTFAssetManager::registerMergeId, batch finished",
    ],
    "views": [
        "ViewManager::handleViewSwitchCenter",
        "ViewManager::doSwitch",
        "ViewManager::aboutToShow()",
        "ViewManager::justHidden()",
        "BaseViewManager::processEvent(DP)",
        "BaseViewManager::processEvent(StateMachine)",
        "BaseViewManager::processEvent(Application)",
    ],
}

def inspect(data):
    found = {}
    for category, strings in ANCHORS.items():
        rows = []
        for value in strings:
            needle = value.encode("ascii") + b"\0"
            pos = data.find(needle)
            rows.append({"string": value, "file_offset": hex(pos) if pos >= 0 else None,
                         "found": pos >= 0})
        found[category] = rows
    return {"sha256": hashlib.sha256(data).hexdigest(),
            "size": len(data), "anchors": found,
            "caution": "String presence does not prove execution, call order, or owning function."}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("elf", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = json.dumps(inspect(args.elf.read_bytes()), indent=2) + "\n"
    if args.output:
        args.output.write_text(result)
    else:
        print(result, end="")

if __name__ == "__main__":
    main()
