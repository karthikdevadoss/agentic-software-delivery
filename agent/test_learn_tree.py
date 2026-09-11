"""
Focused tests for agent/learn_tree.py and the canonical learn-tree.json it
loads (built by agent/build_learn_tree.py) — the recursive Learn Wikipedia
data model (P0-A).

Run: python agent/test_learn_tree.py
"""

import unittest

import learn_tree


class TreeStructureTestCase(unittest.TestCase):
    def test_tree_has_required_top_level_fields(self):
        tree = learn_tree.load_tree()
        self.assertIn("domains", tree)
        self.assertIn("metrics", tree)
        self.assertIn("generated_at_utc", tree)
        self.assertIn("git_commit", tree)
        self.assertGreater(len(tree["domains"]), 0)

    def test_system_design_domain_exists_with_required_subdomains(self):
        tree = learn_tree.load_tree()
        sd = next(d for d in tree["domains"] if d["slug"] == "system-design")
        child_slugs = {c["slug"] for c in sd["children"]}
        required = {"requirements", "apis", "networking", "compute", "databases",
                    "caching", "distributed-systems", "security", "reliability",
                    "observability", "cloud-deployment", "performance"}
        self.assertTrue(required.issubset(child_slugs), f"missing: {required - child_slugs}")

    def test_ai_assisted_engineering_domain_exists(self):
        tree = learn_tree.load_tree()
        slugs = {d["slug"] for d in tree["domains"]}
        self.assertIn("ai-assisted-software-engineering", slugs)

    def test_existing_reference_catalog_preserved(self):
        """The original 127-topic/15-section catalog must still exist
        somewhere in the tree, never deleted during migration."""
        tree = learn_tree.load_tree()
        slugs = {d["slug"] for d in tree["domains"]}
        # A sample of original section ids from learn-data.json.
        for original_id in ("ai-foundations", "llms", "rag", "mcp", "agents"):
            self.assertIn(original_id, slugs)

    def test_deep_dive_topics_preserved_with_full_sections(self):
        node = learn_tree.find_node_by_slug("production-verification")
        self.assertIsNotNone(node)
        self.assertIn("what", node["sections"])
        self.assertIn("development_steps", node["sections"])
        self.assertIn("interview", node["sections"])

    def test_deep_recursion_reaches_a_leaf_topic(self):
        """Learn -> System Design -> Databases -> Connection Pooling —
        the exact example from P0_PROMPT.txt Section 5."""
        node, breadcrumb = learn_tree.resolve_path(["system-design", "databases", "connection-pooling"])
        self.assertIsNotNone(node)
        self.assertEqual(node["title"], "Connection Pooling")
        self.assertEqual(len(breadcrumb), 3)
        self.assertEqual(breadcrumb[-1]["title"], "Connection Pooling")

    def test_unknown_path_resolves_to_none(self):
        node, breadcrumb = learn_tree.resolve_path(["system-design", "does-not-exist"])
        self.assertIsNone(node)
        self.assertIsNone(breadcrumb)

    def test_no_experience_classification_is_fabricated_as_professional(self):
        """This repo has no docs/EXPERIENCE_EVIDENCE.md entry for AWS/
        Cognito/FusionAuth/Jenkins/Oracle/Kafka/Redis/Spring Security —
        none of them may ever be marked as professional experience."""
        for slug in ("aws", "cognito", "fusionauth", "jenkins", "oracle", "kafka", "redis", "jwt"):
            node = learn_tree.find_node_by_slug(slug)
            if node is None:
                continue
            self.assertNotEqual(node.get("experience_classification"), "REAL_PROFESSIONAL_EXPERIENCE")

    def test_current_project_experience_used_only_for_evidenced_tech(self):
        node = learn_tree.find_node_by_slug("connection-pooling")
        self.assertEqual(node["experience_classification"], "CURRENT_PROJECT_EXPERIENCE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
