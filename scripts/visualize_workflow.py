#!/usr/bin/env python3
"""
Visualize QA Workflow Graph

Usage:
    python visualize_workflow.py [output_file.png]
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from qa_agent.workflow import visualize_workflow

if __name__ == "__main__":
    output_file = sys.argv[1] if len(sys.argv) > 1 else "workflow_graph.png"
    
    print("Generating workflow graph visualization...")
    result = visualize_workflow(output_file=output_file)
    
    if result:
        print(f"✅ Graph visualization complete!")
        if isinstance(result, bytes):
            print(f"   Saved to: {output_file}")
        else:
            print(f"   Mermaid diagram generated (PNG generation failed)")
    else:
        print("❌ Failed to generate graph visualization")

