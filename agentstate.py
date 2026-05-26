from typing import List, Optional
from typing_extensions import TypedDict, NotRequired

class UserState:
    user_id: str
    preferences: dict
    expertise_level: str
    goals: list
    personality: str
    permissions: list

class ConversationState:
    current_topic: str
    previous_messages: list
    active_intent: str
    unresolved_questions: list

class TaskState(TypedDict):
    task_id: str
    objective: str
    subtasks: List[dict]  # List of { "agent": "research", "query": "...", "status": "pending", "result": "..." }
    completed_steps: List[str]
    status: str
    priority: int
    last_response: NotRequired[str]
    error: NotRequired[str]


class ToolState:
    available_tools: list
    tool_usage_history: list
    failed_tools: list

class EnvironmentState:
    current_files: list
    open_tabs: list
    active_apps: list
    system_metrics: dict


class PlanningState:
    current_plan: list
    next_action: str
    reasoning_chain: list
    confidence_score: float

class StyleState:
    tone: str
    verbosity: str
    creativity_level: int


class LearningState:
    successful_patterns: list
    failed_patterns: list
    feedback_history: list

class SafetyState:
    blocked_actions: list
    permission_level: str
    risk_score: float

class MemoryState:
    short_term_memory: list
    long_term_memory: list



class AgentState(TypedDict):
    user_input:str
    user_state: UserState
    conversation_state: ConversationState
    task_state: TaskState
    memory_state: MemoryState
    tool_state: ToolState
    environment_state: EnvironmentState
    planning_state: PlanningState
    learning_state: LearningState
    safety_state: SafetyState
    next: list[str]