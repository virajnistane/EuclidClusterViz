"""
Guided-tour step definitions must point at elements that exist in the layout.

Every ``#id`` used in a TOUR_STEPS selector has to be an id in the built app
layout, every section tour must open a real sidebar section, and every tour
entry point (menu items, "?" buttons) must exist. A renamed or removed control
otherwise silently drops out of the tour.
"""

import re
import unittest

from cluster_visualization.ui.layout import AppLayout
from cluster_visualization.ui.tour_steps import SECTION_ORDER, SECTION_TITLES, TOUR_STEPS


def layout_ids(component):
    ids = set()

    def walk(node):
        if isinstance(node, (list, tuple)):
            for child in node:
                walk(child)
            return
        if not hasattr(node, "to_plotly_json"):
            return
        node_id = getattr(node, "id", None)
        if isinstance(node_id, str):
            ids.add(node_id)
        walk(getattr(node, "children", None))
        # DropdownMenu labels and similar props can hold components too
        walk(getattr(node, "label", None))

    walk(component)
    return ids


class TestTourSteps(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ids = layout_ids(AppLayout.create_layout())

    def test_every_selector_id_exists(self):
        missing = []
        for tour, steps in TOUR_STEPS.items():
            for step in steps:
                for element_id in re.findall(r"#([\w-]+)", step["element"]):
                    if element_id not in self.ids:
                        missing.append((tour, step["title"], element_id))
        self.assertEqual(missing, [])

    def test_section_tours_cover_every_section(self):
        self.assertEqual(set(SECTION_ORDER), set(SECTION_TITLES))
        for section in SECTION_ORDER:
            self.assertIn(section, TOUR_STEPS)
            self.assertTrue(TOUR_STEPS[section], f"{section} tour has no steps")
            for step in TOUR_STEPS[section]:
                self.assertEqual(step["section"], section)

    def test_entry_points_exist(self):
        expected = {"tour-quick", "tour-full", "tutorial-tour-menu", "tour-init-dummy", "tour-analysis"}
        for section in SECTION_ORDER:
            expected |= {
                f"tour-section-{section}",
                f"{section}-tour",
                f"{section}-toggle",
                f"{section}-collapse",
                f"{section}-header",
            }
        self.assertEqual(expected - self.ids, set())

    def test_steps_are_complete(self):
        for tour, steps in TOUR_STEPS.items():
            for step in steps:
                for key in ("element", "title", "body"):
                    self.assertTrue(step.get(key), f"{tour}: step missing {key}")


if __name__ == "__main__":
    unittest.main()
