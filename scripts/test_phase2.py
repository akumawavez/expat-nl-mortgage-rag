"""
Phase 2 completion tests: Knowledge Graph (Neo4j).

Run from project root:
  python scripts/test_phase2.py --check-neo4j       # Neo4j connectivity
  python scripts/test_phase2.py --check-graph-write # Graph extraction + write (when implemented)
  python scripts/test_phase2.py --check-graph-content # Graph content query (when implemented)
  python scripts/test_phase2.py --all               # Run all Phase 2 checks

See PHASES.md for success criteria and sign-off checklist.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
os.chdir(_project_root)

import dotenv
dotenv.load_dotenv(_project_root / ".env")

NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "")


def check_neo4j() -> bool:
    """Test Neo4j connectivity. Returns True if pass."""
    print("=" * 60)
    print("Phase 2 – Test 2.1: Neo4j connectivity")
    print("=" * 60)
    print(f"NEO4J_URI = {NEO4J_URI}")
    print()
    if not NEO4J_PASSWORD:
        print("FAIL – NEO4J_PASSWORD not set in .env")
        return False
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        with driver.session() as session:
            result = session.run("RETURN 1 AS n")
            record = result.single()
            if record and record["n"] == 1:
                print("OK – Neo4j is reachable and credentials work.")
                driver.close()
                return True
        driver.close()
    except ImportError:
        print("FAIL – neo4j package not installed. Add: pip install neo4j")
        return False
    except Exception as e:
        print(f"FAIL – Cannot connect to Neo4j: {e}")
        print("  → Start Neo4j and set NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD in .env")
        return False
    print("FAIL – Unexpected result from Neo4j")
    return False


def check_graph_write() -> bool:
    """Test graph extraction + write to Neo4j. Stub until Phase 2 ingestion exists."""
    print("=" * 60)
    print("Phase 2 – Test 2.2: Graph extraction and write")
    print("=" * 60)
    print("NOT IMPLEMENTED – Phase 2 ingestion (extract entities/relations → Neo4j) not yet built.")
    print("  When implemented: run extraction on sample text, write to Neo4j, assert nodes/edges created.")
    print("  Proves: extraction pipeline and Neo4j writer work.")
    return False  # Fail until implemented


def check_graph_content() -> bool:
    """Test that graph contains expected domain content. Stub until Phase 2 exists."""
    print("=" * 60)
    print("Phase 2 – Test 2.3: Graph content")
    print("=" * 60)
    print("NOT IMPLEMENTED – Query Neo4j for expected entities/relationships from sample docs.")
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Phase 2 completion tests (Knowledge Graph).")
    parser.add_argument("--check-neo4j", action="store_true", help="Test Neo4j connectivity")
    parser.add_argument("--check-graph-write", action="store_true", help="Test graph extraction + write")
    parser.add_argument("--check-graph-content", action="store_true", help="Test graph has expected content")
    parser.add_argument("--all", action="store_true", help="Run all Phase 2 checks")
    args = parser.parse_args()

    if not (args.check_neo4j or args.check_graph_write or args.check_graph_content or args.all):
        parser.print_help()
        return 0

    failed = []
    if args.check_neo4j or args.all:
        if not check_neo4j():
            failed.append("check-neo4j")
        print()
    if args.check_graph_write or args.all:
        if not check_graph_write():
            failed.append("check-graph-write")
        print()
    if args.check_graph_content or args.all:
        if not check_graph_content():
            failed.append("check-graph-content")
        print()

    if failed:
        print("Phase 2 tests failed:", ", ".join(failed))
        print("See PHASES.md for completion criteria.")
        return 1
    print("All run Phase 2 checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
