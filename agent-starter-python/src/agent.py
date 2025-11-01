import logging
import requests
import json
import asyncio
from typing import AsyncIterable
import os
from difflib import SequenceMatcher
import numpy as np

from dotenv import load_dotenv
from livekit.agents import (
    Agent, AgentSession, JobContext, JobProcess, MetricsCollectedEvent,
    RoomInputOptions, WorkerOptions, cli, inference, metrics,
    function_tool, RunContext, llm, ModelSettings
)
from livekit.plugins import noise_cancellation, silero

import firebase_admin
from firebase_admin import credentials, firestore
import google.generativeai as genai

load_dotenv()
load_dotenv('.env.local', override=True)

logging.basicConfig(level=logging.INFO)
logging.getLogger("livekit.agents").setLevel(logging.INFO)
logging.getLogger("livekit.agents.voice").setLevel(logging.INFO)
logger = logging.getLogger("agent")

# --- Initializations ---
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
EMBEDDING_MODEL = "models/text-embedding-004"
KB_MATCH_THRESHOLD = float(os.getenv("KB_MATCH_THRESHOLD", "0.55"))
KB_LEXICAL_THRESHOLD = float(os.getenv("KB_LEXICAL_THRESHOLD", "0.6"))

if not firebase_admin._apps:
    cred = credentials.Certificate("service-account.json")
    firebase_admin.initialize_app(cred)
db = firestore.client()

class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="""You are a helpful and friendly receptionist for a salon named 'Glamour Cuts'.
            Your goal is to answer customer questions based on the information you have.

            Here is what you know about Glamour Cuts:
            - Services and Prices: Haircut is $50, Hair Coloring is $120.
            - Working Hours: We are open from 10 AM to 8 PM, Tuesday to Sunday. We are closed on Mondays.
            - Location: 123 Style Street, Fashion City.

            IMPORTANT RULES:
            1. If you are provided with 'ADDITIONAL CONTEXT', you MUST use that information to answer the user's question.
            2. If you don't have the information and no 'ADDITIONAL CONTEXT' is provided, you MUST call the request_human_supervisor tool immediately.
            3. NEVER make up answers or guess.
            4. NEVER say "let me check with my supervisor" without actually calling the request_human_supervisor tool.
            5. After calling request_human_supervisor, wait for the response before continuing.
            """,
        )
        self._current_chat_ctx = None
        self.pending_escalations = {}  # Track pending escalations
    
    async def llm_node(
        self, chat_ctx: llm.ChatContext, tools: list, model_settings: ModelSettings
    ) -> AsyncIterable[llm.ChatChunk]:
        self._current_chat_ctx = chat_ctx
        
        last_user_message = None
        for item in reversed(chat_ctx.items):
            role = getattr(item, "role", None)
            if role == 'user':
                last_user_message = item
                break

        if last_user_message:
            user_query = last_user_message.text_content
            logger.info("Searching knowledge base for: '%s'", user_query)

            embedding_result = genai.embed_content(model=EMBEDDING_MODEL, content=user_query)
            query_embedding = np.asarray(embedding_result['embedding'], dtype=np.float32)
            query_norm = np.linalg.norm(query_embedding)
            
            if query_norm == 0:
                logger.warning("Query embedding norm is zero; skipping KB search")
            else:
                kb_docs = db.collection('knowledge_base').stream()

                best_match = None
                highest_similarity = -1.0

                for doc in kb_docs:
                    doc_data = doc.to_dict()
                    doc_embedding_list = (
                        doc_data.get('content_embedding')
                        or doc_data.get('question_embedding')
                    )

                    if not doc_embedding_list or not isinstance(doc_embedding_list, list):
                        fallback_text = None
                        question_text = doc_data.get('question')
                        answer_text = doc_data.get('answer')
                        if question_text and answer_text:
                            fallback_text = f"Question: {question_text}\nAnswer: {answer_text}"
                        elif question_text:
                            fallback_text = question_text
                        elif answer_text:
                            fallback_text = answer_text

                        if fallback_text:
                            try:
                                logger.info("Backfilling missing embedding for KB doc %s", doc.id)
                                backfill_embedding = genai.embed_content(
                                    model=EMBEDDING_MODEL,
                                    content=fallback_text,
                                )["embedding"]
                                if isinstance(backfill_embedding, list):
                                    doc_embedding_list = backfill_embedding
                                    doc.reference.update({
                                        'content_embedding': backfill_embedding,
                                    })
                            except Exception as backfill_error:
                                logger.warning(
                                    "Could not backfill embedding for KB doc %s: %s",
                                    doc.id,
                                    backfill_error,
                                )

                    if not doc_embedding_list or not isinstance(doc_embedding_list, list):
                        continue

                    doc_embedding = np.asarray(doc_embedding_list, dtype=np.float32)
                    doc_norm = np.linalg.norm(doc_embedding)
                    if doc_norm == 0:
                        continue

                    similarity = float(
                        np.dot(query_embedding, doc_embedding)
                        / (query_norm * doc_norm)
                    )

                    if similarity > highest_similarity:
                        highest_similarity = similarity
                        best_match = doc_data

                if best_match:
                    logger.info(
                        "Knowledge base best match similarity %.3f for question '%s'",
                        highest_similarity,
                        best_match.get('question'),
                    )
                    answer = best_match.get('answer')
                    similarity_ok = highest_similarity >= KB_MATCH_THRESHOLD
                    
                    if not similarity_ok:
                        question_text = best_match.get('question', "")
                        normalized_query = " ".join(
                            user_query.lower().strip().rstrip("?.!").split()
                        )
                        normalized_question = " ".join(
                            question_text.lower().strip().rstrip("?.!").split()
                        )
                        if normalized_query and normalized_question:
                            lexical_ratio = SequenceMatcher(
                                None, normalized_query, normalized_question
                            ).ratio()
                            logger.debug(
                                "KB lexical ratio %.3f for '%s' vs '%s'",
                                lexical_ratio,
                                normalized_query,
                                normalized_question,
                            )
                            if lexical_ratio >= KB_LEXICAL_THRESHOLD:
                                similarity_ok = True
                        if not similarity_ok and normalized_query == normalized_question:
                            similarity_ok = True

                    if not similarity_ok:
                        logger.info(
                            "Knowledge base match %.3f below threshold %.2f", 
                            highest_similarity,
                            KB_MATCH_THRESHOLD,
                        )

                    if answer and similarity_ok:
                        rag_context = (
                            f"ADDITIONAL CONTEXT: The user asked '{user_query}'. "
                            f"A similar question was answered before. The trusted answer is: '{answer}' "
                            f"Use this answer to respond to the user."
                        )
                        chat_ctx.add_message(role='system', content=rag_context)
                        logger.info("Added RAG context to chat")

        async for chunk in super().llm_node(chat_ctx, tools, model_settings):
            yield chunk

    async def _listen_for_resolution(self, session: AgentSession, request_id: str):
        """Listen for supervisor response and add it to context"""
        loop = asyncio.get_running_loop()
        doc_ref = db.collection('help_requests').document(request_id)
        response_received = asyncio.Event()
        supervisor_response = None

        def on_snapshot(doc_snapshot, changes, read_time):
            nonlocal supervisor_response
            for doc in doc_snapshot:
                if doc.exists:
                    data = doc.to_dict()
                    if data.get('status') == 'resolved':
                        supervisor_response = data.get('supervisorResponse')
                        logger.info(f"Supervisor response received for {request_id}: {supervisor_response}")
                        response_received.set()

        doc_watch = doc_ref.on_snapshot(on_snapshot)
        
        try:
            await asyncio.wait_for(response_received.wait(), timeout=3600.0)
            
            if supervisor_response:
                # Add supervisor's answer to knowledge base context
                if self._current_chat_ctx:
                    context_msg = (
                        f"ADDITIONAL CONTEXT: The supervisor has provided this answer: '{supervisor_response}'. "
                        f"You must use this information to answer the user's question."
                    )
                    self._current_chat_ctx.add_message(role='system', content=context_msg)
                
                # Speak the response
                await session.say(f"I have an update from my supervisor. {supervisor_response}")
                
                # Remove from pending escalations
                if request_id in self.pending_escalations:
                    del self.pending_escalations[request_id]
                    
        except asyncio.TimeoutError:
            logger.warning(f"Timed out waiting for response for request {request_id}")
        finally:
            logger.info(f"Unsubscribing from request {request_id}")
            doc_watch.unsubscribe()

    @function_tool()
    async def request_human_supervisor(self, context: RunContext, user_query: str):
        """
        Escalate a question to a human supervisor when you don't know the answer.
        
        Args:
            user_query: The exact question from the user that you cannot answer
        """
        logger.info(f"🚨 ESCALATING to human supervisor for query: {user_query}")
        
        # Build conversation history
        chat_history = []
        current_chat_ctx = getattr(self, "_current_chat_ctx", None)
        if current_chat_ctx:
            for msg in current_chat_ctx.items:
                # Skip function calls and only include messages with role/content
                if hasattr(msg, 'role') and hasattr(msg, 'text_content'):
                    role = str(msg.role)
                    content = msg.text_content
                    if content:  # Only add if there's actual content
                        chat_history.append({
                            'role': role, 
                            'content': content
                        })
        
        # Get room and participant info
        room_sid, user_participant_sid = "unknown_room", "unknown_participant"
        try:
            room_sid = await context.session.room.sid()
            for p in context.session.room.remote_participants.values():
                user_participant_sid = p.sid
                break
        except AttributeError:
            logger.warning("Running in a test environment without a real room.")
        
        payload = {
            "originalQuery": user_query,
            "conversationHistory": chat_history,
            "livekitRoomId": room_sid,
            "livekitParticipantId": user_participant_sid
        }
        
        try:
            logger.info(f"📤 Sending help request to backend...")
            logger.debug(f"Payload: {json.dumps(payload, indent=2)}")
            
            response = requests.post(
                "http://127.0.0.1:8000/api/help-requests", 
                json=payload,
                timeout=10
            )
            
            logger.info(f"📥 Backend response status: {response.status_code}")
            logger.debug(f"Response body: {response.text}")
            
            response.raise_for_status()
            response_data = response.json()
            request_id = response_data.get("requestId")
            
            if request_id:
                logger.info(f"✅ Help request created with ID: {request_id}")
                
                # Track this escalation
                self.pending_escalations[request_id] = user_query
                
                # Start listening for resolution in the background
                asyncio.create_task(
                    self._listen_for_resolution(context.session, request_id)
                )
                
                return (
                    "I don't have that information right now. "
                    "I've contacted my supervisor and they'll get back to you shortly with an answer."
                )
            else:
                logger.error("❌ No requestId returned from backend")
                logger.error(f"Response data: {response_data}")
                return "I've tried to reach my supervisor but didn't get a confirmation. Please try again."
                
        except requests.Timeout as e:
            logger.error(f"⏱️ Request timeout: {e}")
            return "My supervisor didn't respond in time. Please try again."
        except requests.ConnectionError as e:
            logger.error(f"🔌 Connection error: {e}")
            return "I can't connect to my supervisor right now. Please make sure the backend server is running."
        except requests.HTTPError as e:
            logger.error(f"🚫 HTTP error {e.response.status_code}: {e.response.text}")
            return "There was an error reaching my supervisor. Please try again."
        except requests.RequestException as e:
            logger.error(f"❌ Request failed: {e}")
            return "I'm having trouble reaching my supervisor right now. Please try again in a moment."
        except Exception as e:
            logger.error(f"💥 Unexpected error: {e}", exc_info=True)
            return "An unexpected error occurred. Please try again."

def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()

async def entrypoint(ctx: JobContext):
    ctx.log_context_fields = {"room": ctx.room.name}
    
    session = AgentSession(
        stt=inference.STT(model="assemblyai/universal-streaming", language="en"),
        llm=inference.LLM(model="openai/gpt-4.1-mini"),
        tts=inference.TTS(model="cartesia/sonic-3", voice="9626c31c-bec5-4cca-baa8-f8ba9e84c8bc"),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )
    
    usage_collector = metrics.UsageCollector()
    
    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)
    
    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")
    
    ctx.add_shutdown_callback(log_usage)
    
    await session.start(
        agent=Assistant(),
        room=ctx.room,
        room_input_options=RoomInputOptions(noise_cancellation=noise_cancellation.BVC()),
    )
    
    await ctx.connect()

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))