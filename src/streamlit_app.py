from openai import OpenAI, AssistantEventHandler
from openai.types.beta.threads import Text, TextDelta
import streamlit as st
from Constants import *
from openai.types.beta.assistant_stream_event import ThreadMessageDelta
from openai.types.beta.threads.text_delta_block import TextDeltaBlock 

client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
assistant_id = st.secrets["ASSISTANT_ID"]

thread = client.beta.threads.create()

if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

for message in st.session_state.chat_history:
        with st.chat_message(message["role"]):
                st.markdown(message["content"])


if user_query := st.chat_input("Escribe aquí tu consulta"):

        with st.chat_message("user"):
                st.markdown(user_query)

        client.beta.threads.messages.create(
                thread_id=thread.id,
                role="user",
                content=user_query
        )

        st.session_state.chat_history.append({
                "role": "user",
                "content": user_query
        })

        with st.chat_message("assistant"):
                stream = client.beta.threads.runs.create(
                        thread_id=thread.id,
                        assistant_id=assistant_id,
                        stream=True
                )
                assistant_reply_box = st.empty()
                assistant_reply = ""

                for event in stream:
                        if isinstance(event, ThreadMessageDelta):
                                if isinstance(event.data.delta.content[0], TextDeltaBlock):
                                        # empty the container
                                        assistant_reply_box.empty()
                                        # add the new text
                                        assistant_reply += event.data.delta.content[0].text.value
                                        # display the new text
                                        assistant_reply_box.markdown(assistant_reply)
                
                st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": assistant_reply
                })
                






