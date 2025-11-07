# LangGraph v1 State & Reducer Pattern - Proper Usage

## ✅ **What We're Doing Correctly**

1. **State Definition (state.py):**
   ```python
   class QAAgentState(TypedDict):
       # Fields WITH reducers (accumulate)
       history: Annotated[List[Dict[str, Any]], operator.add]
       completed_goals: Annotated[List[str], operator.add]
       
       # Fields WITHOUT reducers (replace)
       goals: List[Dict[str, Any]]  # Replaced each update
       step_count: int  # Replaced each update
   ```

2. **Node Returns (THINK, ACT, VERIFY):**
   ```python
   # ✅ CORRECT: Return only NEW items for reducer fields
   return {
       "history": [new_history_entry],  # Only new entry - reducer appends
       "completed_goals": [new_goal_id] if new_goal_id else [],  # Only new items
       "step_count": step_count,  # Full value (no reducer)
   }
   ```

## ❌ **What Was Wrong (FIXED)**

**PLAN Node Bug:**
```python
# ❌ WRONG: Returning existing list causes duplication!
return {
    "completed_goals": state.get("completed_goals", []),  # BUG: Will duplicate!
}

# ✅ CORRECT: Return [] (no new items) or omit field
return {
    # completed_goals: Omit field - no new goals completed
    # OR
    "completed_goals": [],  # Means "no new items to add"
}
```

## 📚 **LangGraph v1 Reducer Rules**

### **Fields WITH Reducers (`Annotated[Type, reducer]`):**
- **Return ONLY new items** to append
- **Return `[]`** means "no new items" (appends nothing)
- **Omit field** means "no update" (preserves existing)
- **NEVER return existing list** - causes duplication!

### **Fields WITHOUT Reducers:**
- **Return FULL value** to replace
- **Omit field** means "no update" (preserves existing)

## 🔧 **Fixed Issues**

1. ✅ PLAN node no longer returns existing `completed_goals` list
2. ✅ PLAN node omits `completed_goals` when preserving existing goals
3. ✅ All nodes return only NEW items for reducer fields
4. ✅ FileSystem state properly preserved across nodes

## 📖 **Reference**

- LangGraph v1 Docs: https://docs.langchain.com/oss/python/langgraph/graph-api
- Key Pattern: `Annotated[List[Type], operator.add]` for accumulation
- Reducer functions must be pure (no side effects)

