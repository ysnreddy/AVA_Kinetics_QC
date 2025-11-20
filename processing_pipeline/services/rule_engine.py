import yaml
import logging
from typing import List, Dict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RuleEngine:
    def __init__(self, config_path: str = r"D:\Compressed\pycharm projects\AVA_kinetics_multiannotator\processing_pipeline\config\rules.yaml"):
        try:
            with open(config_path, 'r') as f:
                self.config = yaml.safe_load(f)
            logger.info(f"✓ Loaded rules version {self.config.get('version')}")
        except Exception as e:
            logger.error(f"Failed to load rules: {e}")
            self.config = {}

    def validate_annotation(self, attributes: Dict[str, str], box_area: float) -> List[Dict]:
        """
        Checks a single annotation against semantic rules defined in YAML.
        """
        flags = []

        # Get the list of "null" values from config (default to empty list if missing)
        ignore_list = self.config.get('ignore_values', [])

        # Filter out attributes that are None, empty, or in the ignore list
        active_labels = [
            v for k, v in attributes.items()
            if v and v not in ignore_list
        ]

        # 1. Check Limits
        limit = self.config.get('limits', {}).get('max_active_labels', 5)
        if len(active_labels) > limit:
            flags.append({
                "issue": "OVERLABEL",
                "severity": self.config['flags']['OVERLABEL'],
                "details": f"Found {len(active_labels)} active labels (Max {limit})"
            })

        min_area = self.config.get('limits', {}).get('min_box_area', 0)
        if box_area < min_area:
            flags.append({
                "issue": "TINY_BOX",
                "severity": self.config['flags']['TINY_BOX'],
                "details": f"Area {int(box_area)} < {min_area}"
            })

        # 2. Check Mutual Exclusivity
        # (Checks if >1 label from a defined exclusive group is present in the active list)
        me_groups = self.config.get('mutual_exclusivity', {})
        if me_groups:
            for group_name, mutually_exclusive_labels in me_groups.items():
                present = [lbl for lbl in active_labels if lbl in mutually_exclusive_labels]
                if len(present) > 1:
                    flags.append({
                        "issue": "ME_CONFLICT",
                        "severity": self.config['flags']['ME_CONFLICT'],
                        "details": f"Conflicting labels in group '{group_name}': {present}"
                    })

        return flags


# Example Usage for Testing
if __name__ == "__main__":
    engine = RuleEngine()

    # Test Case 1: Safe (Should pass)
    test_safe = {
        "work_activity": "idle",  # Ignored
        "ppe_helmet": "helmet_worn",  # Active
        "team_interaction": "working_alone"  # Ignored
    }
    print("Safe Test:", engine.validate_annotation(test_safe, box_area=5000))

    # Test Case 2: Overlabel (Should flag)
    test_busy = {
        "work_activity": "welding",
        "ppe_helmet": "helmet_incorrect",
        "ppe_vest": "no_vest",  # Ignored
        "ppe_gloves": "gloves_worn",
        "posture_safety": "bending",
        "hazard_proximity": "near_hot_surface",
        "team_interaction": "pair_work"
    }
    # Active count: welding, helmet_incorrect, gloves_worn, bending, near_hot_surface, pair_work = 6
    print("Busy Test:", engine.validate_annotation(test_busy, box_area=5000))