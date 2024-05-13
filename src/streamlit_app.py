from openai import OpenAI, Stream
import streamlit as st
from streamlit.delta_generator import DeltaGenerator
from openai.types.beta.assistant_stream_event import ThreadMessageDelta, AssistantStreamEvent, ThreadRunFailed
from openai.types.beta.threads.text_delta_block import TextDeltaBlock 
from token_counting import ensure_fit_tokens

client: OpenAI = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
assistant_id: str = st.secrets["ASSISTANT_ID"]

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


def main() -> None:
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

        
                






