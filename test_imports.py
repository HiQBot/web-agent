#!/usr/bin/env python3
"""
Test script to verify all imports compile correctly
"""
import sys

def test_import(module_name, description):
    """Test importing a module"""
    try:
        __import__(module_name)
        print(f"✓ {description}")
        return True
    except ImportError as e:
        print(f"✗ {description}: {e}")
        return False
    except Exception as e:
        print(f"✗ {description}: {e}")
        return False

if __name__ == "__main__":
    print("Testing imports...\n")
    
    results = []
    
    # Test the renamed module
    results.append(test_import("web_agent.prompts.browser_prompts", "browser_prompts module"))
    
    # Test classes from browser_prompts
    try:
        from web_agent.prompts.browser_prompts import SystemPrompt, AgentMessagePrompt
        print("✓ SystemPrompt and AgentMessagePrompt classes")
        results.append(True)
    except Exception as e:
        print(f"✗ SystemPrompt and AgentMessagePrompt classes: {e}")
        results.append(False)
    
    # Test act_wrapper
    results.append(test_import("web_agent.nodes.act_wrapper", "act_wrapper module"))
    
    # Test message_manager service
    results.append(test_import("web_agent.agent.message_manager.service", "message_manager.service module"))
    
    # Test workflow
    results.append(test_import("web_agent.workflow", "workflow module"))
    
    # Test nodes __init__
    results.append(test_import("web_agent.nodes", "nodes __init__ module"))
    
    # Test API main
    results.append(test_import("api.main", "API main module"))
    
    print(f"\n{'='*50}")
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("✓ All imports successful!")
        sys.exit(0)
    else:
        print("✗ Some imports failed")
        sys.exit(1)

