from typing import List, Dict


class AssignmentGenerator:
    def __init__(self):
        pass

    def generate_100_percent_overlap(
            self,
            items: List[str],
            annotators: List[str]
    ) -> Dict[str, List[str]]:
        """
        Assigns EVERY item to EVERY annotator provided.
        This guarantees 100% overlap for the batch.
        """
        if not items or not annotators:
            raise ValueError("Items and annotators lists cannot be empty.")

        # Simple Logic: Everyone does everything in this batch
        assignments = {}
        for annotator in annotators:
            assignments[annotator] = sorted(items)

        return assignments