# QA Agent Fixes Summary - DOM Stability & State Communication

## ✅ Implemented Fixes

### 1. **DOM Stability After Actions** ✅
**Problem**: After actions (click, hover, input), DOM changes (dropdowns, modals) but LLM doesn't see them immediately.

**Solution**: 
- Created `qa_agent/utils/dom_stability.py` with `wait_for_dom_stability()` function
- Follows browser-use pattern: Check pending network requests, wait 1-3s if found
- Act node now waits for DOM stability after ALL actions before passing state to Think

**Files Changed**:
- `qa_agent/utils/dom_stability.py` (NEW)
- `qa_agent/nodes/act.py` - Added DOM stability wait after actions

### 2. **Backend 1 Step Ahead Pattern** ✅
**Problem**: LLM sees stale state - doesn't know about dropdowns/modals that appeared after actions.

**Solution**:
- Act node fetches fresh browser state AFTER actions and DOM stability wait
- Passes fresh state to Think node via `fresh_state_available` flag
- Think node uses pre-fetched state (avoids duplicate work)
- Ensures LLM always sees CURRENT page structure

**Files Changed**:
- `qa_agent/nodes/act.py` - Fetch fresh state after actions
- `qa_agent/nodes/think.py` - Use pre-fetched state from Act node
- `qa_agent/state.py` - Added `fresh_state_available` and `page_changed` flags

### 3. **Cache Clearing After Actions** ✅
**Problem**: Browser state cache might contain stale DOM after actions.

**Solution**:
- Created `clear_cache_if_needed()` function in `dom_stability.py`
- Clears cache after page-changing actions (navigate, switch, go_back)
- Clears cache after DOM-changing actions (click, input, scroll) if URL changed
- Follows browser-use pattern from `session.py` line 926

**Files Changed**:
- `qa_agent/utils/dom_stability.py` - Added cache clearing logic
- `qa_agent/nodes/act.py` - Call cache clearing before fetching fresh state

### 4. **Tab Switch Validation** ✅ (Already Fixed)
- `SwitchTabAction` supports `min_length=3` to allow "new" keyword
- `switch()` function handles "new" keyword properly

### 5. **Graph Visualization** ✅
**Added**: `visualize_workflow()` function to generate Mermaid/PNG diagrams

**Files Changed**:
- `qa_agent/workflow.py` - Added visualization function
- `scripts/visualize_workflow.py` (NEW) - Standalone script

### 6. **State Model Updates** ✅
**Added fields**:
- `fresh_state_available`: Flag for Act → Think communication
- `page_changed`: Indicates if page changed
- `previous_url`, `previous_element_count`: For change detection
- `dom_selector_map`: Cached selector map
- Tab management fields: `new_tab_id`, `just_switched_tab`, etc.

**Files Changed**:
- `qa_agent/state.py` - Added new state fields

## 🔄 New Workflow Flow

**Before**:
```
Think → Act → Verify → Think
         ↓
    (no fresh state)
```

**After**:
```
Think → Act → [Wait DOM Stability] → [Fetch Fresh State] → Verify → Think
         ↓                                    ↓
    (actions executed)              (fresh state passed to Think)
```

## 🎯 Key Improvements

1. **DOM Stability**: Waits for network idle and DOM to settle after actions
2. **Fresh State**: Act node proactively fetches fresh state (backend 1 step ahead)
3. **Cache Management**: Clears cache when needed to avoid stale data
4. **State Communication**: Clear flags for Act → Think state passing
5. **Graph Visualization**: Can visualize workflow structure

## 📋 Remaining Tasks

- [ ] Fix extraction action param model issues (if any)
- [ ] Test with hover dropdown scenarios
- [ ] Test with tab switch scenarios
- [ ] Verify graph visualization works

## 🧪 Testing Scenarios

1. **Hover Dropdown**: Click button → dropdown appears → LLM sees dropdown items
2. **Tab Switch**: Click link → new tab opens → LLM sees new tab's content
3. **Dynamic Content**: Input text → autocomplete appears → LLM sees suggestions
4. **Modal**: Click button → modal opens → LLM sees modal content

All scenarios should now work because:
- Act node waits for DOM stability
- Act node fetches fresh state
- Think node uses fresh state
- LLM sees CURRENT page structure

