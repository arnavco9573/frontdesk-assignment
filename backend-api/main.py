# main.py (Updated with Embedding Logic)
import os
import datetime
import firebase_admin
from firebase_admin import credentials, firestore
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv() #.env file se GOOGLE_API_KEY lene ke liye

# --- Initializations ---
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
EMBEDDING_MODEL = "models/text-embedding-004"

if not firebase_admin._apps:
    cred = credentials.Certificate("service-account.json")
    firebase_admin.initialize_app(cred)
db = firestore.client()
app = FastAPI()


def extract_embedding(result):
    if result is None:
        return None

    embedding = None
    if isinstance(result, dict):
        embedding = result.get("embedding")
    elif isinstance(result, list):
        embedding = result
    else:
        return None

    if isinstance(embedding, dict):
        values = embedding.get("values")
        if isinstance(values, list):
            return values
    elif isinstance(embedding, list):
        if embedding and isinstance(embedding[0], dict):
            values = embedding[0].get("values")
            if isinstance(values, list):
                return values
        elif all(isinstance(item, (int, float)) for item in embedding):
            return embedding

    return None

# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Models ---
class ChatMessage(BaseModel):
    role: str
    content: str

class HelpRequestPayload(BaseModel):
    originalQuery: str
    conversationHistory: List[ChatMessage]
    livekitRoomId: str
    livekitParticipantId: Optional[str] = None

class ResolvePayload(BaseModel):
    answer: str

# --- API Endpoints ---
@app.post("/api/help-requests")
async def create_help_request(payload: HelpRequestPayload):
    try:
        # Create a new help request document in Firestore
        doc_ref = db.collection('help_requests').document()
        doc_ref.set({
            'originalQuery': payload.originalQuery,
            'conversationHistory': [m.dict() for m in payload.conversationHistory],
            'livekitRoomId': payload.livekitRoomId,
            'livekitParticipantId': payload.livekitParticipantId,
            'status': 'pending',
            'createdAt': datetime.datetime.now(datetime.timezone.utc)
        })
        request_id = doc_ref.id
        print(f"Created help request {request_id}")
        return {"requestId": request_id}
    except Exception as e:
        print(f"Error creating help request: {e}")
        return {"error": str(e)}

@app.put("/api/help-requests/{request_id}/resolve")
async def resolve_help_request(request_id: str, payload: ResolvePayload):
    try:
        doc_ref = db.collection('help_requests').document(request_id)
        request_doc = doc_ref.get()
        if not request_doc.exists:
            return {"error": "Request not found"}, 404

        original_query = request_doc.to_dict().get('originalQuery')

        doc_ref.update({
            'status': 'resolved',
            'supervisorResponse': payload.answer,
            'resolvedAt': datetime.datetime.now(datetime.timezone.utc)
        })

        if original_query and payload.answer:
            try:
                question_embedding_result = genai.embed_content(
                    model=EMBEDDING_MODEL,
                    content=original_query,
                )
                question_embedding = extract_embedding(question_embedding_result)

                combined_text = f"Question: {original_query}\nAnswer: {payload.answer}"
                content_embedding_result = genai.embed_content(
                    model=EMBEDDING_MODEL,
                    content=combined_text,
                )
                content_embedding = extract_embedding(content_embedding_result)
            except Exception as embed_error:
                print(f"Embedding generation failed for request {request_id}: {embed_error}")
                question_embedding = None
                content_embedding = None

            # Knowledge Base me embedding ke saath save karo
            kb_ref = db.collection('knowledge_base').document()
            kb_ref.set({
                'question': original_query,
                'answer': payload.answer,
                'question_embedding': question_embedding,
                'content_embedding': content_embedding,
                'sourceRequestId': request_id,
                'createdAt': datetime.datetime.now(datetime.timezone.utc)
            })
            print(f"Added new fact with embedding to knowledge base for request {request_id}")

        return {"message": f"Request {request_id} resolved successfully"}
    except Exception as e:
        print(f"An Error Occurred while resolving {request_id}: {e}")
        return {"error": str(e)}