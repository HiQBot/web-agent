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
    
    system_prompt = """You are an AI assistant that analyzes user tasks and creates a structured todo.md checklist in browser format.

Your task:
1. Analyze the user's task description
2. Create a concise title
3. Extract the main goal
4. Break it down into logical, actionable steps

Format requirements (MUST match browser style exactly):
- Title: One line starting with # (main heading)
- Goal: One line starting with ## Goal: followed by goal description
- Tasks: One line starting with ## Tasks: followed by checklist items
- Checklist items: Each step on a new line with - [ ] prefix (use - [x] for completed items, but initially all should be - [ ])

Example format:
# ArXiv CS.AI Recent Papers Collection Task

## Goal: Collect metadata for 20 most recent papers

## Tasks:
- [ ] Navigate to https://arxiv.org/list/cs.AI/recent
- [ ] Initialize papers.md file for storing paper data
- [ ] Collect paper 1/20: The Automated LLM Speedrunning Benchmark
- [ ] Collect paper 2/20: AI Model Passport

Guidelines:
- Break down the task into clear, actionable steps
- Steps should be specific enough to track progress
- Order steps logically (what comes first, second, etc.)
- Include all important steps mentioned in the task
- Don't create too many steps (aim for 5-15 steps for most tasks)
- If the task is very simple (1-2 actions), create 1-3 steps
- Steps should be written as imperative actions (e.g., "Navigate to website", "Fill form", "Click submit")
- Title should be concise and descriptive
- Goal should summarize the overall objective
"""
    
    user_prompt = f"""Analyze this task and create a structured todo.md checklist in browser format:

TASK:
{task}

Create a title, goal statement, and break down the task into logical steps. Return the structure matching the exact browser format."""
    
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

