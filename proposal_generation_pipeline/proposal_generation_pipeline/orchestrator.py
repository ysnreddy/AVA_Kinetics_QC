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

from tools.rename_resize import process_videos as rename_resize_videos
from tools.clip_video import clip_video
from tools.keyframe_selector import KeyframeSelector
from rfdetr import RFDETRMedium
from tools.create_proposals_from_tracks import generate_proposals_from_tracks
from tools.assignment_generator import AssignmentGenerator
from tools.proposals_to_cvat import create_xml_for_subset
from tools.s3_uploader import S3Uploader

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# ------------------ JSON SAFETY (CRITICAL FIX) ------------------
def to_python(obj):
    """
    Recursively convert numpy / torch scalars to native Python types
    so json.dump NEVER fails.
    """
    if isinstance(obj, dict):
        return {str(k): to_python(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [to_python(v) for v in obj]
    if hasattr(obj, "item"):
        return obj.item()
    return obj


def run_pipeline(
    zip_file_path: str,
    output_dir: str,
    batch_name: str,
    annotators: List[str],
    s3_bucket: str
):
    base_output_path = Path(output_dir)
    batch_output_dir = base_output_path / batch_name
    work_dir = batch_output_dir / "temp_processing"

    raw_video_dir = work_dir / "0_raw"
    resized_dir = work_dir / "1_resized"
    clipped_dir = work_dir / "2_clipped"
    json_dir = work_dir / "3_jsons"
    final_keyframes_dir = batch_output_dir / "keyframes"

    for d in [
        work_dir,
        raw_video_dir,
        resized_dir,
        clipped_dir,
        json_dir,
        final_keyframes_dir,
        batch_output_dir,
    ]:
        d.mkdir(parents=True, exist_ok=True)

    manifest_data = {}
    presigned_urls = {}

    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Using device: {device}")

    detection_model = RFDETRMedium(device=device)
    keyframe_selector = KeyframeSelector(
        detection_model=detection_model,
        device=device,
        person_class_id=1,
    )

    uploader = S3Uploader(bucket_name=s3_bucket)

    try:
        # ------------------ [1] PREPROCESS ------------------
        logger.info("[1/7] Preprocessing Videos")
        with zipfile.ZipFile(zip_file_path, "r") as zf:
            zf.extractall(raw_video_dir)

        rename_resize_videos(str(raw_video_dir), str(resized_dir))
        clip_video(str(resized_dir), str(clipped_dir))

        # ------------------ [2] KEYFRAME SELECTION ------------------
        logger.info("[2/7] Selecting Keyframes")
        clips = list(Path(clipped_dir).rglob("*.mp4"))

        for clip in tqdm(clips, desc="Keyframe Selection"):
            result = keyframe_selector.select_best_keyframe(str(clip))
            if result is None:
                continue

            img, frame_idx, dets = result
            frame_idx = int(frame_idx)

            fname = f"{clip.stem}_frame_{frame_idx:04d}.jpg"
            cv2.imwrite(str(final_keyframes_dir / fname), img)

            # Detection JSON (SAFE TYPES)
            with open(json_dir / f"{clip.stem}.json", "w") as f:
                json.dump(
                    [
                        {
                            "video_id": str(clip.stem),
                            "frame": str(fname),
                            "track_id": int(d["track_id"]),
                            "bbox": [float(x) for x in d["bbox"]],
                        }
                        for d in dets
                    ],
                    f,
                    indent=2,
                )

            # Manifest entry (SAFE TYPES)
            manifest_data[str(fname)] = {
                "source_video": str(clip.name),
                "source_frame": frame_idx,
            }

        # ------------------ [3] MANIFEST ------------------
        logger.info("[3/7] Writing Manifest")
        manifest_path = batch_output_dir / "manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(to_python(manifest_data), f, indent=2)

        # ------------------ [4] PROPOSALS ------------------
        logger.info("[4/7] Generating Proposals")
        proposals_pkl = work_dir / "proposals.pkl"
        generate_proposals_from_tracks(str(json_dir), str(proposals_pkl))

        with open(proposals_pkl, "rb") as f:
            all_proposals = pickle.load(f)

        # ------------------ [5] ASSIGNMENTS ------------------
        logger.info("[5/7] Generating Assignments (100% overlap)")
        assigner = AssignmentGenerator()
        assignments = assigner.generate_100_percent_overlap(
            list(manifest_data.keys()), annotators
        )

        # ------------------ [6] FRAME ZIPs ------------------
        for user, frames in assignments.items():
            zip_name = f"{batch_name}_{user}_keyframes.zip"
            zip_path = batch_output_dir / zip_name

            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for f in frames:
                    zf.write(final_keyframes_dir / f, arcname=f)

            s3_zip_key = f"{batch_name}/frames_zip/{zip_name}"
            uploader.upload_file(str(zip_path), s3_zip_key)

            presigned_urls.setdefault(user, {})
            presigned_urls[user]["keyframes_zip"] = uploader.generate_presigned_url(s3_zip_key)

        # ------------------ [7] XMLs ------------------
        for user, frames in assignments.items():
            xml_name = f"{batch_name}_{user}_annotations.xml"
            xml_path = batch_output_dir / xml_name

            create_xml_for_subset(
                f"{batch_name}_{user}",
                frames,
                all_proposals,
                str(final_keyframes_dir),
                str(xml_path),
            )

            s3_xml_key = f"{batch_name}/annotations/{xml_name}"
            uploader.upload_file(str(xml_path), s3_xml_key)

            presigned_urls[user]["annotations_xml"] = uploader.generate_presigned_url(s3_xml_key)

        # ------------------ UPLOAD KEYFRAME IMAGES ------------------
        uploader.upload_directory(
            str(final_keyframes_dir),
            f"{batch_name}/keyframes"
        )

        # ------------------ UPLOAD MANIFEST ------------------
        uploader.upload_file(
            str(manifest_path),
            f"{batch_name}/manifest/manifest.json"
        )

        # ------------------ PRESIGNED URL FILE ------------------
        urls_path = batch_output_dir / "presigned_urls.json"
        with open(urls_path, "w") as f:
            json.dump(to_python(presigned_urls), f, indent=2)

        uploader.upload_file(
            str(urls_path),
            f"{batch_name}/presigned_urls.json"
        )

        logger.info("🎉 PIPELINE COMPLETE — ALL FILES UPLOADED SUCCESSFULLY")

    finally:
        if work_dir.exists():
            shutil.rmtree(work_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip_file_name", required=True)
    parser.add_argument("--batch_name", required=True)
    parser.add_argument("--annotators", required=True)
    parser.add_argument("--s3_bucket", required=True)

    args = parser.parse_args()

    annotators = [a.strip() for a in args.annotators.split(",") if a.strip()]
    project_root = Path(__file__).resolve().parent

    input_zip = Path(args.zip_file_name)
    if not input_zip.exists():
        input_zip = project_root / "uploads" / args.zip_file_name

    run_pipeline(
        str(input_zip),
        str(project_root / "outputs"),
        args.batch_name,
        annotators,
        args.s3_bucket,
    )
