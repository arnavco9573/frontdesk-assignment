# Human-in-the-Loop AI Voice Agent

This project is a demonstration of a "Human-in-the-Loop" voice AI system. It features a voice agent (the "receptionist") that can answer customer questions. When it doesn't know an answer, it escalates the question to a human supervisor in real-time, learns the new answer, and immediately provides it to the customer.

This system is built with three core components:
1.  **AI Voice Agent (`agent.py`):** A Python agent using the LiveKit Agents SDK. It handles the live voice call, STT/TTS, and conversational logic.
2.  **Backend API (`main.py`):** A FastAPI server that acts as the bridge. It handles escalation requests from the agent and resolution submissions from the supervisor.
3.  **Supervisor Dashboard (`Dashboard.tsx`):** A React component (for a Next.js app) that provides a real-time dashboard for supervisors to see and respond to pending help requests.

## System Design & Flow (Design Notes)

This project's core is the "Human-in-the-Loop" flow, which ensures the agent can learn and resolve issues it has never seen before.

1.  **Initial Query:** A user calls the LiveKit agent and asks a question.
2.  **KB Search (RAG):** The agent (`agent.py`) first queries its **Firestore `knowledge_base` collection** to see if it already knows the answer (Retrieval-Augmented Generation).
3.  **Escalation:** If the answer is not found (or the confidence is too low), the agent's `request_human_supervisor` tool is triggered.
4.  **Agent -> Backend:** The agent sends the user's query and conversation history to the **FastAPI backend** (`POST /api/help-requests`).
5.  **Backend -> Firestore:** The backend (`main.py`) creates a new document in the **`help_requests` collection** with a `status: 'pending'`.
6.  **Agent -> Firestore (Listen):** After sending the request, the agent (`agent.py`) creates a background task (`_listen_for_resolution`) that opens a real-time `on_snapshot` listener on that *specific* Firestore document.
7.  **Dashboard -> Firestore (Listen):** The **Supervisor Dashboard** (`Dashboard.tsx`) is also listening to the `help_requests` collection and immediately displays the new "pending" request on the UI, along with a 60-second countdown timer.
8.  **The Loop Closes (Two Paths):**
    * **Path A: Supervisor Responds (Resolved)**
        * The supervisor types an answer and clicks "Submit" on the dashboard.
        * The dashboard sends the answer to the **FastAPI backend** (`PUT /api/help-requests/.../resolve`).
        * The backend updates the `help_requests` doc to `status: 'resolved'`.
        * **Crucially, the backend also embeds the new Q&A and saves it to the `knowledge_base` collection.**
        * The agent's Firestore listener (`_listen_for_resolution`) fires instantly.
        * The agent uses `session.say()` to speak the supervisor's answer back to the user on the call, closing the loop.
    * **Path B: No Response (Unresolved)**
        * The 60-second timer on the agent's listener (`_listen_for_resolution`) expires.
        * The agent itself updates the Firestore document, setting its `status: 'unresolved'`.
        * The "Pending" card disappears from the dashboard and now appears in the "History" tab as "Unresolved".

This event-driven design using Firestore as a central state manager allows all three components to communicate asynchronously without direct connections.

## Setup and Running

### Prerequisites

* Python 3.10+
* Node.js (for the supervisor dashboard)
* A **Google Firebase** project with **Firestore** enabled.
* A **LiveKit Cloud** account (or self-hosted instance).

### 1. Initial Setup

1.  **Firebase:**
    * In your Firebase project, go to "Project settings" > "Service accounts".
    * Generate a new private key and download the `service-account.json` file.
    * Place this `service-account.json` file in the root of your project.
2.  **Firestore:**
    * Go to the Firestore Database section and create a database.
    * It will start empty. The collections (`help_requests`, `knowledge_base`) will be created automatically when the app runs.
3.  **Google AI:**
    * Go to Google AI Studio and get an API Key. This is needed for generating the embeddings.
4.  **Environment Variables:**
    * Create a `.env` file in your project's root directory and add your keys:

    ```env
    # LiveKit credentials
    LIVEKIT_URL=wss://YOUR_PROJECT_NAME.livekit.cloud
    LIVEKIT_API_KEY=YOUR_API_KEY
    LIVEKIT_API_SECRET=YOUR_API_SECRET

    # Google API Key for embeddings
    GOOGLE_API_KEY=YOUR_GOOGLE_AI_API_KEY
    ```

### 2. Create `requirements.txt` Files

You'll need two `requirements.txt` files.

**For the Backend (save as `backend-requirements.txt`):**
```txt
fastapi
uvicorn[standard]
firebase-admin
google-generativeai
python-dotenv
```
Markdown

# Human-in-the-Loop AI Voice Agent

This project is a demonstration of a "Human-in-the-Loop" voice AI system. It features a voice agent (the "receptionist") that can answer customer questions. When it doesn't know an answer, it escalates the question to a human supervisor in real-time, learns the new answer, and immediately provides it to the customer.

This system is built with three core components:
1.  **AI Voice Agent (`agent.py`):** A Python agent using the LiveKit Agents SDK. It handles the live voice call, STT/TTS, and conversational logic.
2.  **Backend API (`main.py`):** A FastAPI server that acts as the bridge. It handles escalation requests from the agent and resolution submissions from the supervisor.
3.  **Supervisor Dashboard (`Dashboard.tsx`):** A React component (for a Next.js app) that provides a real-time dashboard for supervisors to see and respond to pending help requests.

## System Design & Flow (Design Notes)

This project's core is the "Human-in-the-Loop" flow, which ensures the agent can learn and resolve issues it has never seen before.

1.  **Initial Query:** A user calls the LiveKit agent and asks a question.
2.  **KB Search (RAG):** The agent (`agent.py`) first queries its **Firestore `knowledge_base` collection** to see if it already knows the answer (Retrieval-Augmented Generation).
3.  **Escalation:** If the answer is not found (or the confidence is too low), the agent's `request_human_supervisor` tool is triggered.
4.  **Agent -> Backend:** The agent sends the user's query and conversation history to the **FastAPI backend** (`POST /api/help-requests`).
5.  **Backend -> Firestore:** The backend (`main.py`) creates a new document in the **`help_requests` collection** with a `status: 'pending'`.
6.  **Agent -> Firestore (Listen):** After sending the request, the agent (`agent.py`) creates a background task (`_listen_for_resolution`) that opens a real-time `on_snapshot` listener on that *specific* Firestore document.
7.  **Dashboard -> Firestore (Listen):** The **Supervisor Dashboard** (`Dashboard.tsx`) is also listening to the `help_requests` collection and immediately displays the new "pending" request on the UI, along with a 60-second countdown timer.
8.  **The Loop Closes (Two Paths):**
    * **Path A: Supervisor Responds (Resolved)**
        * The supervisor types an answer and clicks "Submit" on the dashboard.
        * The dashboard sends the answer to the **FastAPI backend** (`PUT /api/help-requests/.../resolve`).
        * The backend updates the `help_requests` doc to `status: 'resolved'`.
        * **Crucially, the backend also embeds the new Q&A and saves it to the `knowledge_base` collection.**
        * The agent's Firestore listener (`_listen_for_resolution`) fires instantly.
        * The agent uses `session.say()` to speak the supervisor's answer back to the user on the call, closing the loop.
    * **Path B: No Response (Unresolved)**
        * The 60-second timer on the agent's listener (`_listen_for_resolution`) expires.
        * The agent itself updates the Firestore document, setting its `status: 'unresolved'`.
        * The "Pending" card disappears from the dashboard and now appears in the "History" tab as "Unresolved".

This event-driven design using Firestore as a central state manager allows all three components to communicate asynchronously without direct connections.

## Setup and Running

### Prerequisites

* Python 3.10+
* Node.js (for the supervisor dashboard)
* A **Google Firebase** project with **Firestore** enabled.
* A **LiveKit Cloud** account (or self-hosted instance).

### 1. Initial Setup

1.  **Firebase:**
    * In your Firebase project, go to "Project settings" > "Service accounts".
    * Generate a new private key and download the `service-account.json` file.
    * Place this `service-account.json` file in the root of your project.
2.  **Firestore:**
    * Go to the Firestore Database section and create a database.
    * It will start empty. The collections (`help_requests`, `knowledge_base`) will be created automatically when the app runs.
3.  **Google AI:**
    * Go to Google AI Studio and get an API Key. This is needed for generating the embeddings.
4.  **Environment Variables:**
    * Create a `.env` file in your project's root directory and add your keys:

    ```env
    # LiveKit credentials
    LIVEKIT_URL=wss://YOUR_PROJECT_NAME.livekit.cloud
    LIVEKIT_API_KEY=YOUR_API_KEY
    LIVEKIT_API_SECRET=YOUR_API_SECRET

    # Google API Key for embeddings
    GOOGLE_API_KEY=YOUR_GOOGLE_AI_API_KEY
    ```

### 2. Create `requirements.txt` Files

You'll need two `requirements.txt` files.

**For the Backend (save as `backend-requirements.txt`):**
```txt
fastapi
uvicorn[standard]
firebase-admin
google-generativeai
python-dotenv
For the Agent (save as agent-requirements.txt):
livekit-agents
firebase-admin
google-generativeai
requests
numpy
python-dotenv
```

### 3. Run the System

You will need three separate terminals.

Terminal 1: Run the Backend API

# Create and activate a virtual environment
```bash
python -m venv venv_backend
source venv_backend/bin/activate  # (or venv_backend\Scripts\activate on Windows)

# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn main:app --reload 
```

Terminal 2: Run the LiveKit Agent
```bash
# 1. Sync base dependencies (assumes a requirements.txt or pyproject.toml
# for base agent dependencies like livekit-agents, requests, etc.)
uv sync

# 2. Install specific dependencies
uv pip install google-generativeai numpy

# 3. Run the agent worker
# (This command assumes your agent file is at 'src/agent.py')
uv run python src/agent.py console
```

Terminal 3: Run the Supervisor Frontend

# cd into your Next.js/React project directory
``` bash
cd /path/to/your/frontend-project

# Install dependencies (if you haven't)
npm install

# Run the dev server
npm run dev

```

Your system is now live. You can go to http://localhost:3000 to see the dashboard and join a LiveKit room to talk to your agent.

Security Note
Do not commit your .env, .env.local, or service-account.json files to GitHub. Add them to your .gitignore file.