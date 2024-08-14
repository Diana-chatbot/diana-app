from openai import OpenAI
from pinecone import Pinecone, Index
from pinecone_text.sparse import BM25Encoder
import streamlit as st
from token_counting import ensure_fit_tokens
from message_generation import add_context_to_query, generate_message
from Constants import SYSTEM_PROMPT

openai_client: OpenAI = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
sparse_encoder: BM25Encoder = BM25Encoder(language = "spanish")
sparse_encoder.load("weights/sparse_params.json")
pinecone_client: Pinecone = Pinecone(st.secrets["PINECONE_API_KEY"])
corpus_index: Index = pinecone_client.Index(host = st.secrets["DIANACORPUS_HOST"])

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
        st.session_state.chat_history.append({
                "role": "user",
                "content": st.session_state.user_query
        })
        st.session_state.memory.append(
                add_context_to_query(
                        st.session_state.user_query, sparse_encoder, 
                        openai_client, openai_client, corpus_index, 
                        n_relevant_documents = st.session_state.n_relevant_documents,
                        convex_combination_parameter = st.session_state.convex_comb_param
                )
        )
        ensure_fit_tokens(st.session_state.memory)
        response, cost = generate_message(
                st.session_state.memory, openai_client,
                st.session_state.temperature,
                st.session_state.response_tokens
        )
        st.session_state.cost += cost
        st.session_state.chat_history.append(response)
        
        with st.chat_message("assistat", avatar = "assets/avatar_assistant.png"):
                st.markdown(st.session_state.chat_history[-1]["content"])
        
        st.session_state.memory[-2:] = st.session_state.chat_history[-2:]
        return

def update_prompt() -> None:
        st.session_state.memory[0]["content"] = st.session_state.custom_prompt
        return

def clear_chat_history() -> None:
        st.session_state.memory = st.session_state.memory[0:1]
        st.session_state.chat_history = []

def main() -> None:
        if "memory" not in st.session_state:
                st.session_state.memory = [{
                        "role": "system",
                        "content": SYSTEM_PROMPT
                }]
        
        if "chat_history" not in st.session_state:
                st.session_state.chat_history = []
        
        if "n_relevant_documents" not in st.session_state:
                st.session_state.n_relevant_documents = 5

        if "convex_comb_param" not in st.session_state:
                st.session_state.convex_comb_param = 0.5

        if "temperature" not in st.session_state:
                st.session_state.temperature = 0.5
        
        if "response_tokens" not in st.session_state:
                st.session_state.response_tokens = 400
        
        if "cost" not in st.session_state:
                st.session_state.cost = 0.
        
        if "custom_prompt" not in st.session_state:
                st.session_state.custom_prompt = SYSTEM_PROMPT
        
        with st.sidebar:
                st.session_state.n_relevant_documents = st.slider(
                        "Número de documentos relevantes para recuperar:",
                        1, 10, 5, 1
                )
                st.session_state.convex_comb_param = st.slider(
                        "Parámetro para búsqueda híbrida: mayor valor da mayor peso al componente semántico y menor peso al componente morfológico",
                        0., 1., .5, 0.1
                )
                st.session_state.temperature = st.slider(
                        "Temperatura. Un valor mayor provoca respuestas más aleatorias o 'creativas'",
                        0., 2., 1., 0.2
                )
                st.session_state.response_tokens = st.number_input(
                        "Número máximo de tokens. Determina la extensión de la respuesta",
                        min_value = 50,
                        max_value = 8000,
                        value = 400
                )
                st.session_state.custom_prompt = st.text_area(
                        "Prompt del sistema, la instrucción inicial que recibe Diana",
                        value = SYSTEM_PROMPT
                )
                st.button(
                        "Cambiar prompt del sistema",
                        on_click = update_prompt
                )
                st.button(
                        "Borrar historial de conversación",
                        on_click = clear_chat_history,
                        type = "primary"
                )
                st.write(f"Costo de la sesión: {st.session_state.cost}")

        st.chat_input(
                "Escribe aquí tu consulta", 
                key = "user_query",
                on_submit = respond_to_query
        )

if __name__ == "__main__":
        main()

        
                






