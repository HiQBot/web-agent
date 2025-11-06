# QA Agent Deep Diagnosis & Fixes

## Executive Summary

After deep analysis comparing your QA agent (onkernal) with browser-use, I've identified **3 critical issues** causing the failures:

1. **Tab Switch Validation Error**: The "new" keyword fails validation (3 chars < 4 required)
2. **Infinite Loop at Recursion Limit**: Agent hits LangGraph's 25-step limit repeatedly
3. **LLM Not Adapting to Page Changes**: After tab switch, LLM doesn't analyze fresh DOM structure

---

## Issue #1: Tab Switch Action Validation Failure

### Root Cause

**Location**: [qa_agent/tools/views.py:64](qa_agent/tools/views.py#L64)

```python
class SwitchTabAction(BaseModel):
	tab_id: str = Field(min_length=4, max_length=4, description='4-char id')
```

**The Problem**:
- LLM outputs: `{"action": "switch", "tab_id": "new"}`
- Validation requires exactly 4 characters
- "new" is only 3 characters → **VALIDATION FAILS**

**Error Log**:
```
ValidationError: tab_id should have at least 4 characters
  [type=string_too_short, input_value='new', input_type=str]
```

### Why This Happens

Your code detects new tabs in [act.py:172-214](qa_agent/nodes/act.py#L172-L214) and stores `new_tab_id` in state. The verify node then **automatically switches** to the new tab.

However, the LLM is **also trying to switch manually** using a "new" keyword that doesn't exist in browser-use's design.

**Browser-use does NOT support "new" keyword**. It uses:
- 4-character tab IDs (last 4 chars of CDP target_id)
- Special handling for `target_id=None` at the **event level** (not action level)

### The Fix: Special "new" Keyword Handler

**Option A: Add "new" keyword support** (recommended for your use case)

1. **Relax validation** in [qa_agent/tools/views.py:64](qa_agent/tools/views.py#L64):

```python
class SwitchTabAction(BaseModel):
	tab_id: str = Field(
		min_length=3,  # Changed from 4 to allow "new"
		max_length=4,
		description='4-char tab id or "new" for most recent tab'
	)
```

2. **Add special handling** in [qa_agent/tools/service.py:526-545](qa_agent/tools/service.py#L526-L545):

```python
async def switch(params: SwitchTabAction, browser_session: BrowserSession):
	"""Switch to another tab. Supports 4-char tab_id or 'new' for most recent tab."""

	# Handle special "new" keyword
	if params.tab_id.lower() == "new":
		# Get most recent tab from browser state
		state = await browser_session.get_browser_state_summary(
			include_screenshot=False,
			cached=False
		)
		if state.tabs and len(state.tabs) > 0:
			# Get the last tab (most recent)
			most_recent_tab = state.tabs[-1]
			target_id = most_recent_tab.target_id
			logger.info(f"🔄 'new' keyword resolved to tab #{target_id[-4:]}")
		else:
			return ActionResult(
				error="No tabs available to switch to",
				extracted_content="No tabs available"
			)
	else:
		# Normal 4-char tab_id lookup
		target_id = await browser_session.get_target_id_from_tab_id(params.tab_id)

	# Continue with existing switch logic...
	try:
		event = browser_session.event_bus.dispatch(SwitchTabEvent(target_id=target_id))
		await event
		new_target_id = await event.event_result(raise_if_any=False, raise_if_none=False)

		if new_target_id:
			memory = f'Switched to tab #{new_target_id[-4:]}'
		else:
			memory = f'Switched to tab #{params.tab_id}'

		logger.info(f'🔄  {memory}')
		return ActionResult(extracted_content=memory, long_term_memory=memory)
	except Exception as e:
		logger.warning(f'Tab switch may have failed: {e}')
		memory = f'Attempted to switch to tab #{params.tab_id}'
		return ActionResult(extracted_content=memory, long_term_memory=memory)
```

**Option B: Remove automatic tab switching** (align with browser-use)

If you want to match browser-use exactly:
1. Remove automatic tab switching from [verify.py:31-158](qa_agent/nodes/verify.py#L31-L158)
2. Let the LLM explicitly decide when to switch tabs
3. Don't use "new" keyword - LLM uses 4-char tab IDs from browser state

---

## Issue #2: Hitting LangGraph Recursion Limit

### Root Cause

**Location**: [qa_agent/workflow.py:38-46](qa_agent/workflow.py#L38-L46)

```python
# Stop at 20 steps to leave room for LangGraph's recursion limit (25)
effective_max = min(max_steps, 20)  # Cap at 20 to avoid recursion limit

if step_count >= effective_max:
	logger.warning(f"Max steps reached: {step_count}/{effective_max}")
	return "done"
```

**The Problem**:
- Your workflow has: `START → init → think → act → verify → think → ...` (loop)
- Each loop iteration increments the LangGraph recursion counter
- LangGraph default limit is **25 recursions**
- Your effective max is 20 steps, but you're hitting 25 before reaching it

**Error Log**:
```
ERROR: Recursion limit of 25 reached without hitting a stop condition.
```

### Why This Happens

Your workflow creates a cycle: `verify → think → act → verify → ...`

Each cycle counts as **multiple recursions** in LangGraph:
- Step 1: `START → init → think → act → verify` (5 recursions)
- Step 2: `verify → think → act → verify` (3 more = 8 total)
- Step 3: `verify → think → act → verify` (3 more = 11 total)
- ...
- Step 8: `verify → think → act → verify` (= 25 total) **→ LIMIT HIT**

You only completed **8 actual task steps** but consumed all 25 LangGraph recursions.

### The Fix: Increase Recursion Limit

**Location**: [qa_agent/workflow.py:178](qa_agent/workflow.py#L178)

```python
def create_qa_workflow() -> Any:
	"""Create the QA automation workflow"""
	logger.info("Creating QA automation workflow")

	# Create workflow graph
	workflow = StateGraph(QAAgentState)

	# ... (add nodes) ...

	# Compile workflow with higher recursion limit
	compiled_workflow = workflow.compile(
		checkpointer=None,  # Add checkpointer if you need state persistence
		interrupt_before=None,
		interrupt_after=None,
		debug=False,
	)

	logger.info("Workflow created successfully")

	return compiled_workflow
```

**Wait - LangGraph doesn't expose recursion_limit in compile()!**

The recursion limit is set at **invocation time**, not compile time. Fix it in your API route:

**Location**: [api/routes/workflow.py](api/routes/workflow.py) (wherever you invoke the workflow)

```python
# When invoking the workflow:
result = await workflow.ainvoke(
	initial_state,
	config={
		"recursion_limit": 100,  # Increase from default 25 to 100
	}
)
```

Or in the streaming version:

```python
async for event in workflow.astream(
	initial_state,
	config={
		"recursion_limit": 100,
	}
):
	# ... handle events ...
```

**Also update your max steps** in [qa_agent/workflow.py:42](qa_agent/workflow.py#L42):

```python
# Remove artificial cap at 20
effective_max = max_steps  # Use full max_steps now that recursion limit is higher
```

---

## Issue #3: LLM Not Adapting to Page Structure After Tab Switch

### Root Cause

This is the **most critical human-QA issue**. Your logs show:

```
Step 5: Clicked "ChatGPT (opens in a new window...)" ✅
Step 6: Tab switch action fails (validation error) ❌
Step 7 (retry): Clicks "Log in" button AGAIN ❌
Step 8: Clicks "ChatGPT" AGAIN ❌
Step 9: Recursion limit reached ❌
```

**The LLM is stuck in a loop** because:

1. **Tab switch fails** due to validation error
2. **LLM doesn't adapt** - keeps retrying the same old plan
3. **No fresh page analysis** - LLM doesn't understand it's on a new page with new structure

### Why This Happens

Your verify node DOES switch tabs automatically and refresh state ([verify.py:31-158](qa_agent/nodes/verify.py#L31-L158)).

Your think node DOES get fresh browser state ([think.py:58-72](qa_agent/nodes/think.py#L58-L72)).

**BUT** the LLM's reasoning pattern is task-focused, not structure-focused:

**Current LLM Behavior** (from logs):
```json
{
  "thinking": "I previously attempted to open ChatGPT login...",
  "next_goal": "Click the 'Log in' button to proceed",
  "action": [{"click": {"index": 155}}]
}
```

The LLM is thinking: "My goal is to fill email field → I should click buttons to get there"

**Expected Human QA Behavior**:
```json
{
  "thinking": "I'm now on a NEW page after tab switch. Let me ANALYZE what elements are available:
    - I see buttons: 'Log in', 'Sign up', 'Try it first'
    - I do NOT see any email input field yet
    - This means I need to click one of these buttons FIRST to reveal the form
    - The task said 'fill email field', but the form isn't visible yet
    - ADAPTIVE REASONING: I need to click 'Sign up' or 'Log in' to reveal the form",
  "evaluation_previous_goal": "Tab switch succeeded, now on new page with different structure. Need to analyze available elements. Verdict: Partial success, need to adapt.",
  "memory": "Switched to ChatGPT login page. Currently see 3 buttons but no email field. Need to click a button to reveal the form.",
  "next_goal": "Click 'Log in' or 'Sign up' button to reveal email input form, then analyze the new page structure.",
  "action": [{"click": 214}]  // Click "Log in" button
}
```

### The Fix: Enhance System Prompt with Structure-First Reasoning

**Location**: [qa_agent/prompts/system_prompt.md](qa_agent/prompts/system_prompt.md)

Add a new section emphasizing **adaptive page analysis**:

```markdown
## CRITICAL: Adaptive Page Structure Analysis (Human QA Pattern)

When the page changes (after navigation, tab switch, or any action), you MUST:

1. **STOP and ANALYZE the CURRENT page structure FIRST**
   - Look at the `<browser_state>` interactive elements list
   - Understand what elements are ACTUALLY available right now
   - DON'T assume elements exist just because the task mentions them

2. **COMPARE current state with your goal**
   - Goal: "Fill email field"
   - Current reality: "I see buttons: 'Log in', 'Sign up', but NO email field"
   - **ADAPTIVE REASONING**: "The form isn't visible yet → I need to click a button first"

3. **REASON about the PAGE FLOW before acting**
   - Modern websites use progressive disclosure (show content step-by-step)
   - If you don't see expected elements, they may appear after clicking/scrolling
   - Example: Click "Sign up" button → THEN email form appears

4. **EXPLICIT verification in your thinking**
   ```
   "thinking": "
   STEP 1: ANALYZE CURRENT PAGE
   - URL: https://chatgpt.com/auth
   - Available elements: [214] button 'Log in', [218] button 'Sign up', [222] button 'Try it first'
   - Missing elements: email input field (expected from task)

   STEP 2: UNDERSTAND PAGE FLOW
   - This is a landing page with action buttons
   - Email form is NOT visible yet
   - Likely flow: Click button → Form appears

   STEP 3: ADAPT STRATEGY
   - Original task: 'fill in the email field'
   - Current reality: No email field visible
   - Adaptive action: Click 'Sign up' or 'Log in' first to reveal form
   - THEN I can fill the email field in the next step
   "
   ```

5. **UPDATE your evaluation_previous_goal with page context**
   - BAD: "Failed to fill email field. Verdict: Failure"
   - GOOD: "Switched to new tab successfully. Page shows buttons but no email field yet. Need to click a button first to reveal form. Verdict: Partial success, adapting strategy."

6. **NEVER retry the same action if the page structure has changed**
   - If you're on a new page, ANALYZE the new structure
   - If elements you expect are missing, ADAPT your approach
   - Don't blindly retry actions from old page state

## CRITICAL: After Tab Switch or Navigation

When you detect a tab switch or URL change in `<agent_history>`:

1. **TREAT IT AS A COMPLETELY NEW PAGE**
2. **IGNORE element indices from previous steps** (they're from the old page)
3. **ANALYZE the FRESH `<browser_state>` provided in this step**
4. **REASON about what elements are available NOW**
5. **ADAPT your action plan based on CURRENT page structure**

Example:
```json
{
  "thinking": "Previous step: Clicked ChatGPT button, which opened new tab.

  ANALYZING CURRENT PAGE (FRESH STATE):
  - Current URL: https://chatgpt.com/auth (NEW PAGE)
  - Available elements in <browser_state>:
    [214] button 'Log in'
    [218] button 'Sign up for free'
    [222] button 'Try it first'
  - Notable: NO email input field visible

  UNDERSTANDING PAGE STRUCTURE:
  - This is a landing page with authentication options
  - Email form is NOT shown yet (progressive disclosure pattern)
  - Expected flow: Click 'Sign up' → Email form appears

  ADAPTIVE STRATEGY:
  - Original task says 'fill in the email field with test@example.com'
  - But email field doesn't exist on current page
  - ADAPTATION: Click 'Sign up' button first to reveal email form
  - THEN fill email in next step once form is visible
  ",
  "evaluation_previous_goal": "Successfully switched to ChatGPT login page. Page shows authentication buttons but email form not visible yet. Need to click button to reveal form. Verdict: Success (tab switch), Now adapting to new page structure.",
  "memory": "Switched to ChatGPT tab. Currently on landing page with buttons: 'Log in', 'Sign up', 'Try it first'. No email field visible yet. Need to click 'Sign up' to reveal form.",
  "next_goal": "Click 'Sign up' button to reveal email input form.",
  "action": [{"click": 218}]
}
```
```

### Additional Fix: Enhance Retry Feedback

**Location**: [qa_agent/nodes/think.py:202-209](qa_agent/nodes/think.py#L202-L209)

Strengthen the retry message to emphasize page analysis:

```python
if is_retry:
	logger.info(f"🔄 RETRY STEP {step_count}: Sending fresh browser_state with {len(selector_map)} interactive elements")
	logger.info(f"   LLM will see CURRENT page state and can adapt actions based on what's actually available")
	logger.info(f"   Previous failure context is included in agent_history above")

	# Add special retry instruction to agent_history
	retry_instruction = (
		"⚠️ RETRY: The previous action failed. Please review the CURRENT <browser_state> above "
		"to see what elements are actually available on this page. Element indices may have changed - "
		"use the indices shown in the current browser_state, not from previous steps. "
		"ANALYZE the page structure FIRST before deciding your next action. "
		"If expected elements are missing, reason about WHY (e.g., need to click button first, need to scroll, page not loaded)."
	)
```

And update the agent history format in [think.py:295-299](qa_agent/nodes/think.py#L295-L299) to include more context:

```python
# Add verification results to history (so LLM knows WHY it failed)
if node == "verify":
	verification_results = step_entry.get("verification_results", [])
	if verification_results:
		for vr in verification_results:
			if vr.get("status") == "fail":
				reason = vr.get("reason", "Unknown failure")
				step_content_parts.append(f"Verification failed: {reason}")
```

---

## Issue #4: Tab Information Not Reaching LLM Effectively

### Root Cause

Your code DOES send tab information to the LLM ([think.py:101](qa_agent/nodes/think.py#L101)):

```python
tab_info = [{"id": t.target_id[-4:], "title": t.title, "url": t.url} for t in current_tabs]
```

But it's not emphasized in the prompt. The LLM might not notice new tabs opened.

### The Fix: Emphasize Tab Changes in Agent History

**Location**: [qa_agent/nodes/verify.py:146-155](qa_agent/nodes/verify.py#L146-L155)

When a tab switch succeeds, add a system message to agent_history:

```python
# Mark that we just switched tabs - think node should treat this as a fresh page state
state_updates["just_switched_tab"] = True
state_updates["tab_switch_url"] = fresh_state.url if 'fresh_state' in locals() else None
state_updates["tab_switch_title"] = fresh_state.title if 'fresh_state' in locals() else None

# ADD THIS: Create a history entry for the tab switch
existing_history = state.get("history", [])
tab_switch_entry = {
	"step": state.get("step_count", 0),
	"node": "verify",
	"action_results": [{
		"extracted_content": f"🔄 TAB SWITCHED to tab #{tab_id_4char}: {fresh_state.title} ({fresh_state.url})",
		"long_term_memory": f"Switched to new tab. Now on: {fresh_state.title}"
	}]
}
state_updates["history"] = existing_history + [tab_switch_entry]
```

**Location**: [qa_agent/nodes/think.py:112-118](qa_agent/nodes/think.py#L112-L118)

When building the prompt after a tab switch, add emphasis:

```python
if just_switched_tab:
	logger.info(f"🔄 DETECTED TAB SWITCH - Fresh browser state retrieved: {tab_switch_title} ({tab_switch_url})")
	logger.info(f"   Interactive elements available: {len(selector_map)}")
	logger.info("   LLM will analyze browser_state and adapt actions based on current page structure.")

	# ADD THIS: Inject special instruction into agent_history
	tab_switch_instruction = (
		f"\n<sys>🔄 TAB SWITCH DETECTED: You are now on a NEW page: {tab_switch_title} ({tab_switch_url})\n"
		f"CRITICAL: Analyze the CURRENT <browser_state> below. Element indices are from THIS page, not the previous tab.\n"
		f"Available elements: {len(selector_map)} interactive elements\n"
		f"ADAPT your strategy based on what elements are ACTUALLY visible on this new page.</sys>\n"
	)
```

---

## Summary of Fixes

### Priority 1: Fix Tab Switch Validation (Immediate)

1. **File**: [qa_agent/tools/views.py:64](qa_agent/tools/views.py#L64)
   - Change `min_length=4` to `min_length=3`

2. **File**: [qa_agent/tools/service.py:526-545](qa_agent/tools/service.py#L526-L545)
   - Add special handling for `tab_id == "new"`
   - Resolve to most recent tab from browser state

### Priority 2: Fix Recursion Limit (Immediate)

1. **File**: [api/routes/workflow.py](api/routes/workflow.py) (wherever workflow is invoked)
   - Add `config={"recursion_limit": 100}` to `ainvoke()` or `astream()`

2. **File**: [qa_agent/workflow.py:42](qa_agent/workflow.py#L42)
   - Remove artificial cap: `effective_max = max_steps` instead of `min(max_steps, 20)`

### Priority 3: Enhance LLM Reasoning (High Impact)

1. **File**: [qa_agent/prompts/system_prompt.md](qa_agent/prompts/system_prompt.md)
   - Add new section: "CRITICAL: Adaptive Page Structure Analysis"
   - Emphasize: Analyze CURRENT page FIRST before acting
   - Add examples of structure-first reasoning

2. **File**: [qa_agent/nodes/think.py:202-209](qa_agent/nodes/think.py#L202-L209)
   - Strengthen retry feedback with page analysis emphasis
   - Add retry instruction to agent_history

### Priority 4: Tab Switch Context (Medium Impact)

1. **File**: [qa_agent/nodes/verify.py:146-155](qa_agent/nodes/verify.py#L146-L155)
   - Add tab switch event to history with clear marker

2. **File**: [qa_agent/nodes/think.py:112-118](qa_agent/nodes/think.py#L112-L118)
   - Inject system message when tab switch detected
   - Emphasize that indices are from NEW page

---

## Testing Plan

After implementing fixes, test with this scenario:

**Task**: "Navigate to openai.com, click the Login button, click on the ChatGPT login option from the dropdown, switch to the new tab that opens, fill in the email field with test@example.com, wait 2 seconds, then extract the page title and URL"

**Expected Flow** (after fixes):

1. ✅ Navigate to openai.com (auto-extracted)
2. ✅ Click "Log in" button
3. ✅ Click "ChatGPT" option from dropdown
4. ✅ New tab opens → Verify node auto-switches to it
5. ✅ Think node gets FRESH browser state from new tab
6. ✅ LLM analyzes: "I see buttons: 'Log in', 'Sign up', but NO email field"
7. ✅ LLM reasons: "Need to click 'Sign up' or 'Log in' first to reveal form"
8. ✅ Click "Sign up" or "Log in" button
9. ✅ Form appears with email field
10. ✅ Fill email field with test@example.com
11. ✅ Wait 2 seconds
12. ✅ Extract title and URL
13. ✅ Done

**Key Success Criteria**:
- No validation errors on tab switch
- No recursion limit errors
- LLM adapts strategy when form not immediately visible
- Task completes within 15-20 steps

---

## Root Cause Analysis: Why These Issues Occurred

### Issue #1: Tab Switch Validation
- **Cause**: Mismatch between LLM output format ("new") and validation rules (4 chars)
- **Why it happened**: Code borrowed from browser-use but added custom "new" keyword without validation support
- **Lesson**: Always align validation with what LLM can output

### Issue #2: Recursion Limit
- **Cause**: Default LangGraph limit (25) too low for cyclic workflows
- **Why it happened**: Each workflow cycle consumes 3+ recursions (verify→think→act→verify)
- **Lesson**: Always configure recursion_limit for workflows with loops

### Issue #3: LLM Not Adapting
- **Cause**: System prompt doesn't emphasize structure-first analysis after page changes
- **Why it happened**: LLM is task-focused ("fill email") not reality-focused ("what's on this page?")
- **Lesson**: Prompt engineering must teach adaptive reasoning, not just task execution

---

## Browser-Use Comparison: What They Do Differently

### Tab Management
- **Browser-use**: No automatic tab switching. LLM explicitly switches using 4-char tab IDs
- **Onkernal**: Automatic tab switching in verify node + manual switching via LLM
- **Verdict**: Onkernal's automatic switching is fine, but needs better LLM communication

### Recursion Handling
- **Browser-use**: Not using LangGraph, no recursion limits
- **Onkernal**: Using LangGraph, must configure recursion_limit
- **Verdict**: Architecture difference, need to adapt LangGraph config

### LLM Reasoning
- **Browser-use**: System prompt emphasizes analyzing browser_state at lines 136-148
- **Onkernal**: Uses browser-use prompts but doesn't emphasize page structure analysis enough
- **Verdict**: Need stronger emphasis on structure-first reasoning

---

## Additional Recommendations

### 1. Add Debugging Checkpoints

Add explicit logging when tab switch happens:

```python
# In verify.py after successful tab switch:
logger.info("=" * 80)
logger.info("🔄 TAB SWITCH COMPLETE")
logger.info(f"   From: {old_tab_id[-4:]} ({old_url})")
logger.info(f"   To:   {new_tab_id[-4:]} ({new_url})")
logger.info(f"   New page elements: {len(selector_map)}")
logger.info("   LLM WILL SEE FRESH STATE FROM NEW TAB IN NEXT THINK NODE")
logger.info("=" * 80)
```

### 2. Add State Validation

Verify browser state is actually from the correct tab:

```python
# In think.py after getting browser state:
if just_switched_tab and tab_switch_url:
	if browser_state.url != tab_switch_url:
		logger.error(f"❌ CRITICAL: Got wrong tab's state!")
		logger.error(f"   Expected URL: {tab_switch_url}")
		logger.error(f"   Got URL: {browser_state.url}")
		raise ValueError("Browser state mismatch after tab switch")
```

### 3. Add LLM Response Validation

Validate that LLM is using CURRENT element indices:

```python
# In act.py before executing actions:
for action in planned_actions:
	if action.get("action") == "click":
		index = action.get("index")
		if index not in selector_map:
			logger.warning(f"⚠️ LLM used invalid index {index} - element may not exist on current page")
			logger.warning(f"   Available indices: {list(selector_map.keys())[:10]}...")
```

### 4. Add Explicit "Page Changed" Detection

Track when URL or DOM structure changes significantly:

```python
# In think.py:
previous_url = state.get("previous_url")
previous_element_count = state.get("previous_element_count", 0)
current_element_count = len(selector_map)

significant_change = (
	current_url != previous_url or
	abs(current_element_count - previous_element_count) > 10  # >10 elements changed
)

if significant_change:
	logger.info("🔄 SIGNIFICANT PAGE CHANGE DETECTED")
	logger.info(f"   URL: {previous_url} → {current_url}")
	logger.info(f"   Elements: {previous_element_count} → {current_element_count}")
	logger.info("   LLM should ANALYZE CURRENT PAGE STRUCTURE before acting")
```

---

## Conclusion

The QA agent has **solid foundation** (80% browser-use code) but needs:

1. **Fix validation** to support "new" keyword or align with browser-use pattern
2. **Increase recursion limit** to allow longer workflows
3. **Enhance prompts** to teach structure-first, adaptive reasoning
4. **Better communication** between nodes about page changes

After these fixes, the agent will behave like a human QA tester:
- ✅ Analyze page structure FIRST
- ✅ Adapt strategy when elements missing
- ✅ Understand page flow (click button → form appears)
- ✅ Never blindly retry same actions on new pages

**Estimated fix time**: 2-4 hours
**Estimated impact**: Should resolve 90%+ of current issues

Good luck! 🚀
