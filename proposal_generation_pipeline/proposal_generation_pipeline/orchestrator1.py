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

# Import all necessary functions from your tool scripts
from tools.rename_resize import process_videos as rename_resize_videos
from tools.clip_video import clip_video
from tools.keyframe_selector import KeyframeSelector
from rfdetr import RFDETRMedium
from tools.create_proposals_from_tracks import generate_proposals_from_tracks
from tools.assignment_generator import AssignmentGenerator
from tools.proposals_to_cvat import create_xml_for_subset

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def run_pipeline(zip_file_path: str, output_dir: str, batch_name: str, annotators: List[str], overlap: int):
    base_output_path = Path(output_dir)
    # Create a specific folder for this batch (e.g., outputs/factory_batch_01)
    batch_output_dir = base_output_path / batch_name

    work_dir = batch_output_dir / "temp_processing"

    # Define directories
    raw_video_dir = work_dir / "0_raw"
    resized_dir = work_dir / "1_resized"
    clipped_dir = work_dir / "2_clipped"
    json_dir = work_dir / "3_jsons"

    # Final destination for keyframes (QC app reads from here)
    final_keyframes_dir = batch_output_dir / "keyframes"

    for d in [work_dir, raw_video_dir, resized_dir, clipped_dir, json_dir, final_keyframes_dir, batch_output_dir]:
        d.mkdir(parents=True, exist_ok=True)
    logger.info(f"✅ Directory structure created at {batch_output_dir}")

    manifest_data = {}

    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Using device: {device}")
    detection_model = RFDETRMedium(device=device)
    keyframe_selector = KeyframeSelector(detection_model=detection_model, device=device, person_class_id=1)

    try:
        # --- Stage 1-3: Unzip, Resize, Clip ---
        logger.info("[Stage 1/7] Preprocessing Videos...")
        with zipfile.ZipFile(zip_file_path, 'r') as zf:
            zf.extractall(raw_video_dir)
        rename_resize_videos(str(raw_video_dir), str(resized_dir))
        clip_video(str(resized_dir), str(clipped_dir))

        # --- Stage 4: Intelligent Keyframe Selection ---
        logger.info("[Stage 4/7] Selecting Keyframes & Generating Proposals...")
        all_clips_to_process = list(Path(clipped_dir).rglob("*.mp4"))
        for clip_path in tqdm(all_clips_to_process, desc="  -> Selecting keyframes"):
            clip_stem = clip_path.stem
            result = keyframe_selector.select_best_keyframe(str(clip_path))
            if result is None: continue
            best_frame_img, best_frame_idx, detections = result

            # Save directly to the FINAL keyframes directory
            keyframe_name = f"{clip_stem}_frame_{best_frame_idx:04d}.jpg"
            cv2.imwrite(str(final_keyframes_dir / keyframe_name), best_frame_img)

            json_output_path = json_dir / f"{clip_stem}.json"
            formatted_dets = [
                {"video_id": clip_stem, "frame": keyframe_name, "track_id": d["track_id"], "bbox": d["bbox"]} for d in
                detections]
            with open(json_output_path, "w") as f:
                json.dump(formatted_dets, f, indent=2)

            manifest_data[keyframe_name] = {"source_video": clip_path.name, "source_frame": int(best_frame_idx)}

        # --- Stage 3: Create Master Manifest ---
        logger.info("[Stage 3/7] Creating Master Manifest...")
        manifest_path = batch_output_dir / "manifest.json"
        with open(manifest_path, 'w') as f:
            json.dump(manifest_data, f, indent=2)

        # --- Stage 4: Aggregate All Proposals ---
        logger.info("[Stage 4/7] Aggregating all proposals...")
        proposals_pkl_path = work_dir / "proposals.pkl"
        generate_proposals_from_tracks(str(json_dir), str(proposals_pkl_path))
        with open(proposals_pkl_path, 'rb') as f:
            all_proposals_data = pickle.load(f)

        # --- Stage 5: Generate Assignments ---
        logger.info("[Stage 5/7] Generating assignments...")
        assignment_generator = AssignmentGenerator()
        all_keyframes = list(manifest_data.keys())
        assignments = assignment_generator.generate_random_assignments(all_keyframes, annotators, overlap)

        # --- Stage 6 & 7: Package Files Per Annotator ---
        logger.info("[Stage 6/7] Packaging keyframe ZIP for each annotator...")
        for annotator, assigned_frames in tqdm(assignments.items(), desc="  -> Creating Packages"):
            # Zip Path: outputs/factory_batch_01/factory_batch_01_annotator1_keyframes.zip
            annotator_zip_path = batch_output_dir / f"{batch_name}_{annotator}_keyframes.zip"
            annotator_xml_path = batch_output_dir / f"{batch_name}_{annotator}_annotations.xml"

            # Create Zip
            with zipfile.ZipFile(annotator_zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for frame_name in assigned_frames:
                    frame_path = final_keyframes_dir / frame_name
                    if frame_path.exists():
                        zf.write(frame_path, arcname=frame_name)

            # Create XML
            task_name = f"{batch_name}_{annotator}"
            create_xml_for_subset(
                task_name=task_name,
                keyframes_for_task=assigned_frames,
                all_proposals_data=all_proposals_data,
                keyframes_dir=str(final_keyframes_dir),
                output_xml_path=str(annotator_xml_path)
            )

        logger.info(f"\n🎉🎉🎉 Pipeline complete! Final outputs are in: {batch_output_dir}")

    finally:
        # Only clean up the temp processing (intermediate videos), NOT the keyframes
        if work_dir.exists():
            logger.info(f"Cleaning up temporary working directory: {work_dir}")
            shutil.rmtree(work_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the full local pre-processing pipeline.")
    PROJECT_ROOT = Path(__file__).resolve().parent
    parser.add_argument("--zip_file_name", required=True, help="Name of the master ZIP file with raw videos.")
    parser.add_argument("--batch_name", required=True, help="A unique name for this processing batch.")
    parser.add_argument("--annotators", required=True, help="Comma-separated list of annotator usernames.")
    parser.add_argument("--overlap", type=int, default=20, help="Overlap percentage for assignments.")

    args = parser.parse_args()

    annotator_list = [a.strip() for a in args.annotators.split(',') if a.strip()]
    if not annotator_list:
        logger.error("Annotator list cannot be empty.")
    else:
        input_zip = Path(args.zip_file_name)
        if not input_zip.is_file():
            input_zip = PROJECT_ROOT / "uploads" / args.zip_file_name

        output_path = PROJECT_ROOT / "outputs"

        if not input_zip.exists():
            logger.error(f"Input file not found: {input_zip}")
        else:
            run_pipeline(str(input_zip), str(output_path), args.batch_name, annotator_list, args.overlap)