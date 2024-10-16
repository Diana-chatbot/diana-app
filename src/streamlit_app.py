from uuid import uuid4
import pymongo
from pymongo.database import Database
from pymongo.collection import Collection
from openai import OpenAI
from pinecone import Pinecone, Index
from pinecone_text.sparse import BM25Encoder
import streamlit as st
from token_counting import ensure_fit_tokens
from message_generation import generate_message
from Constants import SYSTEM_PROMPT
import nltk
from datetime import datetime, timezone

openai_client: OpenAI = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
sparse_encoder: BM25Encoder = BM25Encoder(language = "spanish")
sparse_encoder.load("weights/sparse_params.json")
pinecone_client: Pinecone = Pinecone(st.secrets["PINECONE_API_KEY"])
corpus_index: Index = pinecone_client.Index(host = st.secrets["DIANACORPUS_HOST"])
mongo_client: pymongo.MongoClient = pymongo.MongoClient(st.secrets["MONGODB_CONNECTION_STRING"])
mongo_db: Database = mongo_client.get_database(name = "session_events")
msg_collection: Collection = mongo_db.get_collection(name = "messages")

pt_download: int = 0

if pt_download == 0:
        nltk.download("punkt_tab")
        pt_download = 1

def insert_messages(messages: list[dict[str, str]]) -> None:
        insert_time: datetime = datetime.now(timezone.utc)
        messages_with_metadata: list[dict[str, str]] = []
        for message in messages:
                temp: dict[str, str] = {}
                temp.update(message)
                temp.update({
                        "time": f"{insert_time.year}-{insert_time.month}-{insert_time.day} {insert_time.hour}:{insert_time.minute}:{insert_time.second}.{insert_time.microsecond}+00",
                        "session_id": st.session_state.session_id
                })
                messages_with_metadata.append(temp)
        msg_collection.insert_many(messages_with_metadata)

def render_messages() -> None:
        for message in st.session_state.chat_history:
                with st.chat_message(
                        message["role"], avatar = f"assets/avatar_{message['role']}.png"
                ):
                        st.markdown(message["content"])
                
        with st.chat_message("user", avatar = "assets/avatar_user.png"):
                st.markdown(st.session_state.user_query)
        
        return

def respond_to_query() -> None:
        render_messages()
        current_query: str = st.session_state.user_query
        st.session_state.chat_history.append({
                "role": "user",
                "content": current_query
        })
        st.session_state.memory.append({
                "role": "user",
                "content": current_query
        })
        ensure_fit_tokens(st.session_state.memory)
        response: dict[str, str] = generate_message(
                st.session_state.memory, openai_client, sparse_encoder,
                corpus_index, temperature = .7
        )
        st.session_state.chat_history.append(response)
        st.session_state.memory.append(response)
        
        with st.chat_message("assistant", avatar = "assets/avatar_assistant.png"):
                st.markdown(st.session_state.chat_history[-1]["content"])
        
        insert_messages(st.session_state.chat_history.append[-2:])
        
        return

def main() -> None:
        if "memory" not in st.session_state:
                st.session_state.memory = [{
                        "role": "system",
                        "content": SYSTEM_PROMPT
                }]
        
        if "chat_history" not in st.session_state:
                st.session_state.chat_history = []
        
        if "session_id" not in st.session_state:
                st.session_state.session_id = str(uuid4())
        
        st.chat_input(
                "Escribe aquí tu consulta", 
                key = "user_query",
                on_submit = respond_to_query
        )

if __name__ == "__main__":
        main()

        
                






