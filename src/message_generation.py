from typing import Any
from openai import OpenAI
from pinecone import Index
from pinecone_text.sparse import BM25Encoder, SparseVector
from Constants import ASSESSMENT_PROMPT, CONTEXT_REPHRASE_PROMPT, HOSPITALS_AND_ORGS_PROMPT
from openai.types.chat.chat_completion import ChatCompletion

def rephrase_query(messages: list[dict[str, str]], client: OpenAI) -> str:
        rephrase_messages = [
                {"role": "system", "content": CONTEXT_REPHRASE_PROMPT},
                {"role": "user", "content": str(messages)}
        ]
        response: str = client.chat.completions.create(
                messages = rephrase_messages, #type:ignore
                model = "gpt-4o-mini"
        ).choices[0].message.content
        return response

def get_hybrid_embeddings(
                sparse_embeddings: SparseVector,
                dense_embeddings: list[float],
                alpha: float = .5
) -> tuple[SparseVector, list[float]]:
        if alpha < 0 or alpha > 1:
                raise ValueError(
                        f"parameter 'alpha' must be in the interval [0, 1], got {alpha}"
                )
        
        hybrid_sparse: SparseVector = {
                "indices": sparse_embeddings["indices"], # type: ignore
                "values": [
                        value * (1 - alpha) 
                        for value in sparse_embeddings["values"]
                ]
        }
        hybrid_dense: list[float] = [value * alpha for value in dense_embeddings]
        return hybrid_sparse, hybrid_dense

def get_relevant_documents(
                messages: list[dict[str, str]],
                sparse_encoder: BM25Encoder,
                dense_encoder_client: OpenAI,
                document_index: Index,
                n_documents: int,
                convex_combination_parameter: float
) -> list[dict[str, Any]]:
        query: str = rephrase_query(messages, dense_encoder_client)
        sparse_embeddings: SparseVector
        sparse_embeddings = sparse_encoder.encode_queries(query) # type: ignore
        dense_embeddings: list[float] = dense_encoder_client.embeddings.create(
                input = query, model = "text-embedding-3-small"
        ).data[0].embedding
        hybrid_sparse, hybrid_dense = get_hybrid_embeddings(
                sparse_embeddings, dense_embeddings,
                convex_combination_parameter
        )
        relevant_documents: list[dict[str, Any]] = document_index.query(
                top_k = n_documents, vector = hybrid_dense,
                sparse_vector = hybrid_sparse,
                include_metadata = True
        )["matches"]
        return relevant_documents

def assess_sources_needed(messages: list[dict[str, str]], llm_client: OpenAI) -> bool:
        query: str = rephrase_query(messages, llm_client)
        assessment_messages: list[dict[str, str]] = [
                {"role": "system", "content": ASSESSMENT_PROMPT},
                {"role": "user", "content": query}
        ]
        response: str = llm_client.chat.completions.create(
                messages = assessment_messages, # type:ignore
                model = "gpt-4o-mini"
        ).choices[0].message.content
        flag: bool = (response == "True") or ("True" in response)
        return flag

def add_context_to_query(
                messages: list[dict[str, str]],
                sparse_encoder: BM25Encoder,
                dense_encoder_client: OpenAI,
                document_index: Index,
                n_relevant_documents: int = 3,
                convex_combination_parameter: float = 0.34
) -> list[dict[str, str]]:
        
        relevant_documents: list[dict[str, Any]] = get_relevant_documents(
                messages, sparse_encoder, dense_encoder_client, document_index,
                n_relevant_documents, convex_combination_parameter
        )

        query: str = messages[-1]["content"]

        query += "\n\n####\n\n"

        for index, entry in enumerate(relevant_documents):
                query += f"Documento #{index}:\n{entry['metadata']['text']}\n\n"
        
        query += "####"
        messages_with_context: list[dict[str, str]] = messages.copy()
        messages_with_context[-1]["content"] = query
        
        return messages_with_context

def generate_message(
                messages: list[dict[str, str]],
                llm_client: OpenAI,
                sparse_encoder: BM25Encoder,
                document_index: Index,
                temperature: float = .8
) -> dict[str, str]:
        if assess_sources_needed(messages, llm_client):
                query_with_context: list[dict[str, str]] = add_context_to_query(
                        messages, sparse_encoder, llm_client, document_index
                )
                query_with_context[0]["content"] = HOSPITALS_AND_ORGS_PROMPT
                api_response: ChatCompletion = llm_client.chat.completions.create(
                        messages = query_with_context, # type:ignore
                        model = "gpt-4o-mini",
                        temperature = temperature
                )
                response: str = api_response.choices[0].message.content #type:ignore
                return {"role": "assistant", "content": response}
                
        api_response: ChatCompletion = llm_client.chat.completions.create(
                messages = messages, # type:ignore
                model = "ft:gpt-4o-mini-2024-07-18:chakakuna:diana-finetuning-3:A9xprQbz:ckpt-step-1638",
                temperature = temperature
        )
        response: str = api_response.choices[0].message.content # type:ignore
        return {"role": "assistant", "content": response}