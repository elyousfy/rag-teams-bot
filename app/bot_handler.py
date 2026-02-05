"""
Microsoft Teams bot message handler.

Processes incoming messages from Teams, validates users,
and routes questions to the RAG engine.
"""

import structlog
from botbuilder.core import (
    ActivityHandler,
    TurnContext,
    BotFrameworkAdapter,
    BotFrameworkAdapterSettings,
)
from botbuilder.schema import Activity, ActivityTypes

from app import config
from app.auth import is_user_authorized
from app.queue_worker import get_request_queue

logger = structlog.get_logger()


# Unauthorized user message
UNAUTHORIZED_MESSAGE = """Sorry, you don't have access to this bot.

Please contact your administrator to request access to the company documents bot."""

# Processing message for long waits
PROCESSING_MESSAGE = "Looking through the documents for you..."


class CompanyDocsBot(ActivityHandler):
    """
    Teams bot that answers questions about company documents.
    """

    async def on_message_activity(self, turn_context: TurnContext):
        """Handle incoming messages."""
        # Get user info
        user_id = turn_context.activity.from_property.id
        user_name = turn_context.activity.from_property.name
        user_aad_id = turn_context.activity.from_property.aad_object_id
        message_text = turn_context.activity.text.strip() if turn_context.activity.text else ""

        logger.info(
            "Received message",
            user_id=user_id,
            user_name=user_name,
            message_length=len(message_text),
        )

        # Check if user is authorized
        if not await is_user_authorized(user_aad_id):
            logger.warning(
                "Unauthorized user attempted access",
                user_id=user_id,
                user_name=user_name,
            )
            await turn_context.send_activity(UNAUTHORIZED_MESSAGE)
            return

        # Handle empty messages
        if not message_text:
            await turn_context.send_activity(
                "Please send me a question about company documents."
            )
            return

        # Handle special commands
        if message_text.lower() in ["/clear", "/reset"]:
            from app.rag_engine import get_rag_engine
            get_rag_engine().clear_conversation(user_id)
            await turn_context.send_activity(
                "Conversation history cleared. Feel free to ask a new question!"
            )
            return

        if message_text.lower() in ["/help", "help"]:
            await turn_context.send_activity(
                "**Company Documents Bot**\n\n"
                "Ask me questions about company documents and I'll find relevant information.\n\n"
                "**Commands:**\n"
                "- `/clear` - Clear conversation history\n"
                "- `/help` - Show this help message\n\n"
                "**Tips:**\n"
                "- Be specific in your questions\n"
                "- I'll cite the source documents in my answers\n"
                "- I can handle follow-up questions about the same topic"
            )
            return

        # Queue the request for processing
        queue = get_request_queue()

        # If there are other requests queued, let user know
        if queue.queue_size > 0 or queue.is_processing:
            await turn_context.send_activity(
                f"Your question is queued (position: {queue.queue_size + 1}). Please wait..."
            )

        try:
            # Process through queue
            result = await queue.enqueue(message_text, user_id)

            # Format response with citations
            response = self._format_response(result)

            await turn_context.send_activity(response)

            logger.info(
                "Sent response",
                user_id=user_id,
                sources_count=len(result.get("sources", [])),
            )

        except Exception as e:
            logger.error(
                "Error processing question",
                user_id=user_id,
                error=str(e),
            )
            await turn_context.send_activity(
                "Sorry, I encountered an error processing your question. Please try again."
            )

    def _format_response(self, result: dict) -> str:
        """Format the RAG response with citations."""
        answer = result.get("answer", "I couldn't find an answer.")
        sources = result.get("sources", [])

        response = answer

        # Add sources section if available
        if sources:
            response += "\n\n---\n**Sources:**\n"
            for source in sources[:5]:  # Limit to 5 sources
                response += f"- {source}\n"

        return response

    async def on_members_added_activity(self, members_added, turn_context: TurnContext):
        """Welcome new members."""
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                await turn_context.send_activity(
                    "Welcome to the Company Documents Bot! 📚\n\n"
                    "Ask me questions about company documents and I'll help you find the information you need.\n\n"
                    "Type `/help` for more information."
                )


def create_adapter() -> BotFrameworkAdapter:
    """Create the Bot Framework adapter with settings."""
    settings = BotFrameworkAdapterSettings(
        app_id=config.AZURE_APP_ID,
        app_password=config.AZURE_APP_SECRET,
    )
    return BotFrameworkAdapter(settings)


# Global bot and adapter instances
_bot: CompanyDocsBot | None = None
_adapter: BotFrameworkAdapter | None = None


def get_bot() -> CompanyDocsBot:
    """Get the global bot instance."""
    global _bot
    if _bot is None:
        _bot = CompanyDocsBot()
    return _bot


def get_adapter() -> BotFrameworkAdapter:
    """Get the global adapter instance."""
    global _adapter
    if _adapter is None:
        _adapter = create_adapter()
    return _adapter
