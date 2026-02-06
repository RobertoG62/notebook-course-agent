#!/usr/bin/env python3
"""
run_pipeline.py — NotebookLM → HTML → GitHub Pages

Usage:
    python run_pipeline.py                    # Run all 3 phases
    python run_pipeline.py extract            # Only extract from NotebookLM
    python run_pipeline.py build              # Only build HTML (uses existing data/raw/)
    python run_pipeline.py deploy             # Only deploy to GitHub Pages
    python run_pipeline.py extract build      # Extract + Build (no deploy)
    python run_pipeline.py --notebook-id ID   # Override notebook ID from config
    python run_pipeline.py --dry-run          # Show plan without executing
"""

import argparse
import io
import sys
import json
from pathlib import Path

# Fix Windows console encoding for Hebrew/emoji output
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Use JSON config to avoid pyyaml dependency
# We convert yaml to json at load time if needed
ROOT = Path(__file__).parent


def load_config(path: Path) -> dict:
    """Load config from YAML or JSON."""
    text = path.read_text(encoding="utf-8")

    # Try JSON first
    if path.suffix == ".json":
        return json.loads(text)

    # YAML — try importing pyyaml, fallback to simple parser
    try:
        import yaml
        return yaml.safe_load(text)
    except ImportError:
        print("ERROR: pyyaml not installed. Install with: pip install pyyaml")
        print("  Or convert config.yaml to config.json")
        sys.exit(1)


def run_extract(config: dict, dry_run: bool = False) -> bool:
    """Phase 1: Extract content from NotebookLM."""
    print("=" * 60)
    print("PHASE 1: EXTRACT")
    print("=" * 60)

    questions = config["questions"]
    max_budget = config["query"]["max_budget"]

    print(f"  Questions: {len(questions)}/{max_budget} budget")
    print(f"  Notebook: {config['notebook']['id']}")

    if len(questions) > max_budget:
        print(f"  ERROR: Questions ({len(questions)}) exceed budget ({max_budget})")
        return False

    raw_dir = ROOT / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    if dry_run:
        print(f"  DRY RUN: Would query {len(questions)} questions")
        for q in questions:
            print(f"    {q['id']}: {q['text'][:60]}...")
        return True

    from src.extractor import NotebookExtractor
    extractor = NotebookExtractor(config)
    results = extractor.extract_all(questions, raw_dir)

    successful = sum(1 for r in results.values() if r.get("success"))
    failed = len(results) - successful
    print(f"\n  Results: {successful} OK, {failed} failed")

    return failed == 0


def run_build(config: dict, dry_run: bool = False) -> bool:
    """Phase 2: Build HTML from extracted content."""
    print("\n" + "=" * 60)
    print("PHASE 2: BUILD")
    print("=" * 60)

    template_path = ROOT / "templates" / "base.html"
    raw_dir = ROOT / "data" / "raw"
    output_path = ROOT / "dist" / "index.html"

    if not template_path.exists():
        print(f"  ERROR: Template not found: {template_path}")
        return False

    # Check for raw data
    raw_files = list(raw_dir.glob("q*.txt"))
    if not raw_files:
        print(f"  ERROR: No raw data in {raw_dir}. Run 'extract' first.")
        return False

    print(f"  Template: {template_path}")
    print(f"  Raw files: {len(raw_files)}")
    print(f"  Output: {output_path}")

    if dry_run:
        print(f"  DRY RUN: Would build from {len(raw_files)} files")
        return True

    from src.builder import HTMLBuilder
    builder = HTMLBuilder(template_path, config)
    size = builder.build(raw_dir, output_path)

    print(f"\n  Output: {output_path}")
    print(f"  Size: {size:,} chars ({size // 1024} KB)")
    return True


def run_deploy(config: dict, dry_run: bool = False) -> bool:
    """Phase 3: Deploy to GitHub Pages."""
    print("\n" + "=" * 60)
    print("PHASE 3: DEPLOY")
    print("=" * 60)

    from src.deployer import GitHubDeployer
    deployer = GitHubDeployer(ROOT)
    return deployer.deploy(dry_run=dry_run)


def main():
    parser = argparse.ArgumentParser(
        description="NotebookLM Course Pipeline: Extract → Build → Deploy"
    )
    parser.add_argument(
        "phases", nargs="*",
        choices=["extract", "build", "deploy"],
        help="Phases to run (default: all)"
    )
    parser.add_argument(
        "--notebook-id",
        help="Override notebook ID from config"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would happen without executing"
    )
    parser.add_argument(
        "--config", default="config.yaml",
        help="Config file path (default: config.yaml)"
    )

    args = parser.parse_args()

    # Load config
    config_path = ROOT / args.config
    if not config_path.exists():
        print(f"ERROR: Config not found: {config_path}")
        sys.exit(1)

    config = load_config(config_path)

    # Override notebook ID if provided
    if args.notebook_id:
        config["notebook"]["id"] = args.notebook_id
        print(f"  Notebook override: {args.notebook_id}")

    # Determine phases
    phases = args.phases if args.phases else ["extract", "build", "deploy"]

    print(f"\nPipeline: {' → '.join(p.upper() for p in phases)}")
    if args.dry_run:
        print("MODE: DRY RUN\n")

    # Run phases
    success = True
    if "extract" in phases:
        if not run_extract(config, args.dry_run):
            success = False

    if success and "build" in phases:
        if not run_build(config, args.dry_run):
            success = False

    if success and "deploy" in phases:
        if not run_deploy(config, args.dry_run):
            success = False

    if success:
        print("\n" + "=" * 60)
        print("PIPELINE COMPLETE")
        print("=" * 60)
    else:
        print("\nPipeline failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
