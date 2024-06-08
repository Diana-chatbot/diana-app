from openai import OpenAI, Stream
from pymongo.database import Database
from pymongo.collection import Collection
import streamlit as st
from streamlit.delta_generator import DeltaGenerator
from openai.types.beta.assistant_stream_event import ThreadMessageDelta, AssistantStreamEvent, ThreadRunFailed
from openai.types.beta.threads.text_delta_block import TextDeltaBlock 
from token_counting import ensure_fit_tokens
import pymongo
from uuid import uuid4
from datetime import datetime, timezone

client: OpenAI = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
assistant_id: str = st.secrets["ASSISTANT_ID"]
mongo_client: pymongo.MongoClient = pymongo.MongoClient(st.secrets["MONGODB_CONNECTION_STRING"])
mongo_db: Database = mongo_client.get_database(name = "session_events")
msg_collection: Collection = mongo_db.get_collection(name = "messages")

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

def process_query() -> None:

        for message in st.session_state.chat_history:
                with st.chat_message(message["role"]):
                        st.markdown(message["content"])

        with st.chat_message("user"):
                st.markdown(st.session_state.user_query)

        st.session_state.chat_history.append({
                "role": "user",
                "content": st.session_state.user_query
        })

        st.session_state.memory.append({
                "role": "user",
                "content": st.session_state.user_query
        })

        ensure_fit_tokens(st.session_state.memory)

        with st.chat_message("assistant"):
                stream: Stream = client.beta.threads.create_and_run(
                        thread={
                                "messages": st.session_state.memory
                        },
                        assistant_id=assistant_id,
                        stream=True
                )
                assistant_reply_box: DeltaGenerator = st.empty()
                assistant_reply: str = ""

                for event in stream:
                        if isinstance(event, ThreadMessageDelta):
                                if isinstance(event.data.delta.content[0], TextDeltaBlock):
                                        # empty the container
                                        assistant_reply_box.empty()
                                        # add the new text
                                        assistant_reply += event.data.delta.content[0].text.value
                                        # display the new text
                                        assistant_reply_box.markdown(assistant_reply)
                        if isinstance(event, ThreadRunFailed):
                                raise Exception(f"{event}")
                        

                
                st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": assistant_reply
                })
                st.session_state.memory.append({
                        "role": "assistant",
                        "content": assistant_reply
                })
        insert_messages(st.session_state.chat_history[-2:])
        


def main() -> None:
        if "session_id" not in st.session_state:
                st.session_state.session_id = str(uuid4())
        if "memory" not in st.session_state:
                st.session_state.memory = []
        if "chat_history" not in st.session_state:
                st.session_state.chat_history = []

        st.chat_input(
                "Escribe aquí tu consulta", 
                key="user_query",
                on_submit=process_query
        )

if __name__ == "__main__":
        main()

        
                






