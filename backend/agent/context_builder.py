"""构建紧凑且有边界的 Agent 上下文。"""

from backend.agent.memory import ConversationContext


def build_context(context: ConversationContext) -> dict:
    return {
        "conversation_id": context.conversation_id,
        "video_id": context.video_id,
        "person_id": context.person_id,
        "action": context.action,
        "last_intent": context.last_intent,
        "time_range": list(context.time_range) if context.time_range else None,
        "recent_results": context.recent_results,
        "recent_turns": context.turns,
    }
