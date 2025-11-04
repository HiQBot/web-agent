"""
Test script for Phase 1 - Basic Structure Verification

This script tests:
1. Import structure
2. State creation
3. Workflow creation
4. Node imports
"""
import sys
import asyncio
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


async def test_phase_1():
    """Test Phase 1 structure"""
    print("=" * 60)
    print("Phase 1 Structure Test")
    print("=" * 60)
    
    # Test 1: Import config
    print("\n1. Testing config import...")
    try:
        from qa_agent.config import settings
        print(f"   ✓ Config imported successfully")
        print(f"   - API Title: {settings.api_title}")
        print(f"   - Max Steps: {settings.max_steps}")
    except Exception as e:
        print(f"   ✗ Config import failed: {e}")
        return False
    
    # Test 2: Import state
    print("\n2. Testing state import...")
    try:
        from qa_agent.state import QAAgentState, create_initial_state
        print(f"   ✓ State imported successfully")
        
        # Test state creation
        initial_state = create_initial_state(
            task="Test task",
            max_steps=10
        )
        print(f"   ✓ Initial state created")
        print(f"   - Task: {initial_state['task']}")
        print(f"   - Max Steps: {initial_state['max_steps']}")
    except Exception as e:
        print(f"   ✗ State import/creation failed: {e}")
        return False
    
    # Test 3: Import nodes
    print("\n3. Testing node imports...")
    try:
        from qa_agent.nodes import think_node, act_node, verify_node, report_node
        print(f"   ✓ All nodes imported successfully")
        print(f"   - think_node: {think_node}")
        print(f"   - act_node: {act_node}")
        print(f"   - verify_node: {verify_node}")
        print(f"   - report_node: {report_node}")
    except Exception as e:
        print(f"   ✗ Node import failed: {e}")
        return False
    
    # Test 4: Test workflow creation
    print("\n4. Testing workflow creation...")
    try:
        from qa_agent.workflow import create_qa_workflow
        workflow = create_qa_workflow()
        print(f"   ✓ Workflow created successfully")
        print(f"   - Workflow type: {type(workflow)}")
    except Exception as e:
        print(f"   ✗ Workflow creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Test 5: Test API imports
    print("\n5. Testing API imports...")
    try:
        from api.main import app
        print(f"   ✓ FastAPI app imported successfully")
        print(f"   - App title: {app.title}")
    except Exception as e:
        print(f"   ✗ API import failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print("\n" + "=" * 60)
    print("✓ All Phase 1 tests passed!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = asyncio.run(test_phase_1())
    sys.exit(0 if success else 1)

