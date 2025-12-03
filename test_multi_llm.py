"""
Test script to verify multi-LLM integration (OpenAI and Gemini)

This tests that:
1. get_llm() can initialize both providers
2. Both providers support with_structured_output()
3. Basic ainvoke() works for both providers
"""
import asyncio
import os
from pydantic import BaseModel
from web_agent.llm import get_llm
from langchain_core.messages import HumanMessage, SystemMessage


class SimpleResponse(BaseModel):
    """Simple structured response for testing"""
    message: str
    number: int


async def test_provider(provider_name: str, model: str = None):
    """Test a specific LLM provider"""
    print(f"\n{'='*60}")
    print(f"Testing {provider_name.upper()} provider")
    print(f"{'='*60}")

    try:
        # Initialize LLM
        print(f"1. Initializing {provider_name} LLM...")
        llm = get_llm(provider=provider_name, model=model)
        print(f"   ✓ LLM initialized: {type(llm).__name__}")
        print(f"   ✓ Model: {llm.model if hasattr(llm, 'model') else 'N/A'}")

        # Test basic text generation
        print(f"\n2. Testing basic text generation...")
        messages = [
            SystemMessage(content="You are a helpful assistant. Be very brief."),
            HumanMessage(content="Say hello in exactly 3 words.")
        ]
        response = await llm.ainvoke(messages)
        print(f"   ✓ Response: {response.content}")

        # Test structured output
        print(f"\n3. Testing structured output...")
        structured_llm = llm.with_structured_output(SimpleResponse, method="function_calling")
        print(f"   ✓ Structured LLM created: {type(structured_llm).__name__}")

        messages = [
            HumanMessage(content='Respond with JSON: {"message": "test passed", "number": 42}')
        ]
        structured_response = await structured_llm.ainvoke(messages)
        print(f"   ✓ Structured response: {structured_response}")
        print(f"   ✓ Type: {type(structured_response)}")
        print(f"   ✓ Message: {structured_response.message}")
        print(f"   ✓ Number: {structured_response.number}")

        print(f"\n✅ {provider_name.upper()} TEST PASSED")
        return True

    except Exception as e:
        print(f"\n❌ {provider_name.upper()} TEST FAILED:")
        print(f"   Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("MULTI-LLM INTEGRATION TEST")
    print("="*60)

    results = {}

    # Test OpenAI (if API key is available)
    if os.getenv("OPENAI_API_KEY"):
        results["openai"] = await test_provider("openai", model="gpt-4o-mini")
    else:
        print("\n⚠️  OPENAI_API_KEY not set - skipping OpenAI test")
        results["openai"] = None

    # Test Gemini (if API key is available)
    if os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"):
        results["gemini"] = await test_provider("google", model="gemini-2.5-flash")
    else:
        print("\n⚠️  GOOGLE_API_KEY not set - skipping Gemini test")
        results["gemini"] = None

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    for provider, result in results.items():
        if result is None:
            print(f"  {provider.upper()}: SKIPPED (no API key)")
        elif result:
            print(f"  {provider.upper()}: ✅ PASSED")
        else:
            print(f"  {provider.upper()}: ❌ FAILED")

    # Overall result
    tested = [r for r in results.values() if r is not None]
    if not tested:
        print("\n⚠️  NO TESTS RUN - Please set OPENAI_API_KEY or GOOGLE_API_KEY")
        return False
    elif all(tested):
        print("\n🎉 ALL TESTS PASSED!")
        return True
    else:
        print("\n❌ SOME TESTS FAILED")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
