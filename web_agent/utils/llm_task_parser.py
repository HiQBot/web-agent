"""
LLM-Driven Task Parser - Use LLM to dynamically create todo.md structure

This uses LLM intelligence to parse tasks and create todo.md structure,
matching browser's exact format and style. Compulsory in INIT node.
"""
import logging
from typing import List
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class TodoStructureResponse(BaseModel):
    """LLM response with todo.md structure matching browser format"""
    title: str = Field(description="Task title (used as main heading)")
    goal: str = Field(description="The main goal/objective of the task")
    steps: List[str] = Field(description="List of step descriptions for the todo checklist")


async def llm_create_todo_structure(task: str, llm) -> str:
    """
    Use LLM to dynamically parse task and create todo.md structure.
    
    Matches browser's exact format:
    # Task Title
    
    ## Goal: Goal description
    
    ## Tasks:
    - [ ] Step 1
    - [ ] Step 2
    
    Args:
        task: Task string from user
        llm: LLM instance for analysis
        
    Returns:
        Markdown content for todo.md file in browser format
    """
    if not task or not task.strip():
        # Fallback: create simple todo.md
        return "# Task\n\n## Goal: Complete the task\n\n## Tasks:\n- [ ] Complete the task\n"
    
    # Create LLM prompt matching browser style
    from langchain_core.messages import SystemMessage, HumanMessage
    
    system_prompt = """You are a QA Engineer breaking down a test scenario into actionable test steps.

Think like a QA professional conducting manual testing:
- What needs to be navigated/accessed?
- What forms need to be filled?
- What buttons/actions trigger the flow?
- How do you verify each step worked?
- What error scenarios should be handled?

Your task:
1. Analyze the user's goal/query
2. Create a concise test scenario title
3. Extract the main objective
4. Break it down into logical, sequential test steps (the way QA would execute manually)

CRITICAL RULES FOR QA-STYLE BREAKDOWN:
================================

1. **Navigation Phase**: Start with accessing the right page/URL
   - Step: Navigate to the website/page
   - Step: Verify you're on the correct page

2. **Form/Data Entry Phase**: Fill in required information
   - For each form or input: Create ONE step per form section or logical group
   - Include field names and what data to enter
   - Example: "Fill account information (email: X, password: Y, name: Z)"
   - NOT: "Fill email", "Fill password", "Fill name" (combine related fields)

3. **Action/Submission Phase**: Click buttons, submit forms
   - Step: Click the relevant button
   - Step: Wait for response/next page

4. **Verification Phase**: Check results
   - Step: Verify success (look for confirmation message, new page, etc.)
   - Step: Handle error scenarios (email exists, invalid input, etc.)

5. **Recovery/Continuation**: If error, handle it
   - Step: If error X occurred, do Y (switch to login, retry, etc.)
   - Step: Continue with next phase

GROUPING STRATEGY:
==================
- **Group related inputs together**: Don't create separate steps for each form field
  - Bad: "Fill email", "Fill password", "Fill name"
  - Good: "Fill signup form with: Email: X, Password: Y, Name: Z"

- **One action per step**: Each button click or submission is one step
- **Include verification**: After each major action, verify it worked
- **Handle errors proactively**: Include steps for "if X error, then do Y"

STEP NAMING:
============
- Use clear, specific language
- Include what data is being entered (not generic "fill form")
- Include expected outcomes when relevant
- Be concise but complete

Example for "Register account and add hostel":
- Navigate to hostelx.pk homepage
- Click signup/login button
- Fill signup form with provided email and password
- Verify account creation or handle "email already exists" error
- Login if needed
- Navigate to dashboard
- Click "Add hostel" button
- Fill hostel details form (name, category, price, location)
- Verify hostel was created successfully

Format requirements (MUST match browser style exactly):
- Title: One line starting with # (main heading)
- Goal: One line starting with ## Goal: followed by goal description
- Tasks: One line starting with ## Tasks: followed by checklist items
- Checklist items: Each step on a new line with - [ ] prefix
"""
    
    user_prompt = f"""You are a QA Engineer. Analyze this test scenario and break it down into actionable test steps.

TASK/SCENARIO:
{task}

INSTRUCTIONS:
1. Create a concise test scenario title
2. Extract the main objective (what needs to be verified/completed)
3. Break down into sequential test steps following QA best practices:
   - Start with navigation
   - Group related form inputs together (not individual field steps)
   - Include button clicks and submissions
   - Add verification steps for each major action
   - Include error handling steps if relevant
   - Make steps specific and actionable

OUTPUT FORMAT:
Title: The test scenario name
Goal: The main objective
Steps: 5-20 actionable test steps (combine related inputs, one action per step)

Create steps the way a QA engineer would execute them manually on the website."""
    
    try:
        logger.info(f"llm_create_todo_structure: Starting LLM call for task (length: {len(task)} chars)")
        logger.debug(f"llm_create_todo_structure: Task preview: {task[:200]}...")
        
        # Call LLM with structured output (with timeout to prevent hanging)
        logger.info(f"llm_create_todo_structure: Creating structured LLM with TodoStructureResponse")
        structured_llm = llm.with_structured_output(TodoStructureResponse)
        logger.info(f"llm_create_todo_structure: Structured LLM created, calling ainvoke with 60s timeout...")
        
        import asyncio
        response = await asyncio.wait_for(
            structured_llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]),
            timeout=60.0  # 60 second timeout for todo creation (should be fast)
        )
        
        logger.info(f"llm_create_todo_structure: LLM response received: title='{response.title}', goal='{response.goal[:50]}...', steps={len(response.steps)}")
        
        # Build todo.md content matching browser format exactly
        content = f"# {response.title}\n\n"
        content += f"## Goal: {response.goal}\n\n"
        content += "## Tasks:\n"
        
        for step in response.steps:
            content += f"- [ ] {step}\n"
        
        logger.info(f"llm_create_todo_structure: ✅ LLM created todo.md structure (browser format): {len(response.steps)} steps - Title: {response.title[:50]}")
        logger.debug(f"llm_create_todo_structure: Generated content length: {len(content)} chars")
        return content
        
    except asyncio.TimeoutError:
        logger.error(f"llm_create_todo_structure: ❌ LLM call timed out after 60 seconds")
        # Fallback: create simple todo.md in browser format
        fallback_content = f"# Task\n\n## Goal: {task}\n\n## Tasks:\n- [ ] Complete the task\n"
        logger.warning(f"llm_create_todo_structure: Returning fallback content due to timeout (length: {len(fallback_content)} chars)")
        return fallback_content
    except Exception as e:
        logger.error(f"llm_create_todo_structure: ❌ Failed to use LLM for todo structure creation: {e}", exc_info=True)
        logger.error(f"llm_create_todo_structure: Exception type: {type(e).__name__}, message: {str(e)}")
        # Fallback: create simple todo.md in browser format
        fallback_content = f"# Task\n\n## Goal: {task}\n\n## Tasks:\n- [ ] Complete the task\n"
        logger.warning(f"llm_create_todo_structure: Returning fallback content (length: {len(fallback_content)} chars)")
        return fallback_content

