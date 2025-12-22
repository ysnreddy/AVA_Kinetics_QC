import os
import pickle
import argparse
import cv2
from typing import List, Dict
import xml.etree.ElementTree as ET
from xml.dom import minidom
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def prettify_xml(elem):
    rough_string = ET.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")


def create_xml_for_subset(task_name, frames, proposals, keyframes_dir, output_path):
    """Generates XML without label defs (Project Schema used instead)."""

    # Dummy attributes to ensure structure exists
    # Values don't matter here, they will be overwritten by annotators
    # Keys MUST match your CVAT Project Schema
    dummy_attrs = {
        'work_activity': 'idle',
        'ppe_helmet': 'helmet_worn',
        # ... add others if default is needed
    }

    root = ET.Element('annotations')
    ET.SubElement(root, 'version').text = '1.1'

    meta = ET.SubElement(root, 'meta')
    task = ET.SubElement(meta, 'task')
    ET.SubElement(task, 'name').text = task_name
    ET.SubElement(task, 'mode').text = 'annotation'

    for i, fname in enumerate(frames):
        path = os.path.join(keyframes_dir, fname)
        if not os.path.exists(path): continue
        try:
            h, w, _ = cv2.imread(path).shape
        except:
            continue

        clip_id = '_'.join(fname.split('_')[:-2])
        dets = proposals.get(clip_id, {}).get(fname, [])

        img_tag = ET.SubElement(root, 'image', {'id': str(i), 'name': fname, 'width': str(w), 'height': str(h)})

        for d in dets:
            bbox = d[0:4]
            box_tag = ET.SubElement(img_tag, 'box', {
                'label': 'person', 'occluded': '0',
                'xtl': str(bbox[0]), 'ytl': str(bbox[1]), 'xbr': str(bbox[2]), 'ybr': str(bbox[3])
            })
            for k, v in dummy_attrs.items():
                ET.SubElement(box_tag, 'attribute', {'name': k}).text = v

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(prettify_xml(root))
    logger.info(f"✓ XML saved: {output_path}")