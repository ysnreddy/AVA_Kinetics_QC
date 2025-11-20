import os
import shutil
import zipfile
from pathlib import Path
import argparse
from tqdm import tqdm
import logging
import json
import torch
import cv2
import pickle
from typing import List

# Tool Imports
from tools.rename_resize import process_videos as rename_resize_videos
from tools.clip_video import clip_video
from tools.keyframe_selector import KeyframeSelector
from rfdetr import RFDETRMedium
from tools.create_proposals_from_tracks import generate_proposals_from_tracks
from tools.assignment_generator import AssignmentGenerator
from tools.proposals_to_cvat import create_xml_for_subset

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def run_pipeline(zip_file_path: str, output_dir: str, batch_name: str, annotators: List[str]):
    base_output_path = Path(output_dir)
    batch_output_dir = base_output_path / batch_name
    work_dir = batch_output_dir / "temp_processing"

    # Directories
    raw_video_dir = work_dir / "0_raw"
    resized_dir = work_dir / "1_resized"
    clipped_dir = work_dir / "2_clipped"
    json_dir = work_dir / "3_jsons"
    final_keyframes_dir = batch_output_dir / "keyframes"  # Images kept here for QC App

    for d in [work_dir, raw_video_dir, resized_dir, clipped_dir, json_dir, final_keyframes_dir, batch_output_dir]:
        d.mkdir(parents=True, exist_ok=True)

    manifest_data = {}

    # Initialize Models
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Using device: {device}")
    detection_model = RFDETRMedium(device=device)
    # optimization commented out to prevent errors
    # detection_model.optimize_for_inference()
    keyframe_selector = KeyframeSelector(detection_model=detection_model, device=device, person_class_id=1)

    try:
        logger.info("[1/7] Preprocessing Videos...")
        with zipfile.ZipFile(zip_file_path, 'r') as zf:
            zf.extractall(raw_video_dir)
        rename_resize_videos(str(raw_video_dir), str(resized_dir))
        clip_video(str(resized_dir), str(clipped_dir))

        logger.info("[2/7] Selecting Intelligent Keyframes...")
        all_clips = list(Path(clipped_dir).rglob("*.mp4"))
        for clip_path in tqdm(all_clips, desc="Processing"):
            clip_stem = clip_path.stem
            result = keyframe_selector.select_best_keyframe(str(clip_path))
            if result is None: continue

            img, frame_idx, dets = result

            # Save Image
            fname = f"{clip_stem}_frame_{frame_idx:04d}.jpg"
            cv2.imwrite(str(final_keyframes_dir / fname), img)

            # Save Detection JSON
            json_out = json_dir / f"{clip_stem}.json"
            formatted_dets = [{"video_id": clip_stem, "frame": fname, "track_id": d["track_id"], "bbox": d["bbox"]} for
                              d in dets]
            with open(json_out, "w") as f:
                json.dump(formatted_dets, f, indent=2)

            # Update Manifest
            manifest_data[fname] = {"source_video": clip_path.name, "source_frame": int(frame_idx)}

        logger.info("[3/7] Writing Manifest...")
        with open(batch_output_dir / "manifest.json", 'w') as f:
            json.dump(manifest_data, f, indent=2)

        logger.info("[4/7] Aggregating Proposals...")
        proposals_pkl = work_dir / "proposals.pkl"
        generate_proposals_from_tracks(str(json_dir), str(proposals_pkl))
        with open(proposals_pkl, 'rb') as f:
            all_proposals = pickle.load(f)

        logger.info("[5/7] Generating 100% Overlap Assignments...")
        assign_gen = AssignmentGenerator()
        # We pass ALL keyframes. The generator ensures 100% overlap.
        all_frames_list = list(manifest_data.keys())
        assignments = assign_gen.generate_100_percent_overlap(all_frames_list, annotators)

        logger.info("[6/7] Packaging Zips...")
        for user, frames in tqdm(assignments.items(), desc="Zipping"):
            zip_path = batch_output_dir / f"{batch_name}_{user}_keyframes.zip"
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for f in frames:
                    p = final_keyframes_dir / f
                    if p.exists(): zf.write(p, arcname=f)

        logger.info("[7/7] Generating Stripped XMLs...")
        for user, frames in tqdm(assignments.items(), desc="XMLs"):
            xml_path = batch_output_dir / f"{batch_name}_{user}_annotations.xml"
            create_xml_for_subset(f"{batch_name}_{user}", frames, all_proposals, str(final_keyframes_dir),
                                  str(xml_path))

        logger.info(f"🎉 Success! Work packages ready in: {batch_output_dir}")

    finally:
        if work_dir.exists():
            shutil.rmtree(work_dir)  # Only delete temp intermediate files


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip_file_name", required=True)
    parser.add_argument("--batch_name", required=True)
    parser.add_argument("--annotators", required=True, help="Comma-separated list (e.g. 'userA,userB')")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent
    input_path = Path(args.zip_file_name)
    if not input_path.is_file(): input_path = project_root / "uploads" / args.zip_file_name

    annotator_list = [a.strip() for a in args.annotators.split(',') if a.strip()]
    run_pipeline(str(input_path), str(project_root / "outputs"), args.batch_name, annotator_list)