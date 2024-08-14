from typing import Any
from openai import OpenAI
from pinecone import Index
from pinecone_text.sparse import BM25Encoder, SparseVector
from Constants import ASSESSMENT_PROMPT
from openai.types.chat.chat_completion import ChatCompletion

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
                query: str,
                sparse_encoder: BM25Encoder,
                dense_encoder_client: OpenAI,
                document_index: Index,
                n_documents: int,
                convex_combination_parameter: float
) -> list[dict[str, Any]]:
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

def assess_sources_needed(query: str, llm_client: OpenAI) -> bool:
        query = "Question: " + query + "\nAnswer:"
        messages: list[dict[str, str]] = [
                {"role": "system", "content": ASSESSMENT_PROMPT},
                {"role": "user", "content": query}
        ]
        response: str = llm_client.chat.completions.create(
                messages = messages, # type:ignore
                model = "gpt-4o-mini"
        ).choices[0].message.content
        return response == "True"

def add_context_to_query(
                query: str,
                sparse_encoder: BM25Encoder,
                dense_encoder_client: OpenAI,
                llm_client: OpenAI,
                document_index: Index,
                n_relevant_documents: int,
                convex_combination_parameter: float
) -> dict[str, str]:
        if not assess_sources_needed(query, llm_client):
                query += "\n\n####\n\nThis query does not have a source available for answering. If it is asking you to do something unrelated to pregnancy, abortion, reproductive rights, family planning, or emotional support in the context of these topics, only mention that your task is to lend support and information related to these topics."
                return {"role": "user", "content": query}
        
        relevant_documents: list[dict[str, Any]] = get_relevant_documents(
                query, sparse_encoder, dense_encoder_client, document_index,
                n_relevant_documents, convex_combination_parameter
        )

        query += "\n\n####\n\n"

        for index, entry in enumerate(relevant_documents):
                query += f"Documento #{index}:\n{entry['metadata']['text']}\n\n"
        
        query += "####"
        
        return {"role": "user", "content": query}

def generate_message(
                memory: list[dict[str, str]],
                llm_client: OpenAI,
                temperature: float,
                response_tokens: int
) -> tuple[dict[str, Any], float]:
        api_response: ChatCompletion = llm_client.chat.completions.create(
                messages = memory, # type:ignore
                model = "gpt-4o",
                temperature = temperature,
                max_tokens = response_tokens
        )
        response: str = api_response.choices[0].message.content # type:ignore
        cost: float  = api_response.usage.prompt_tokens * 2.5e-6 + api_response.usage.prompt_tokens * 1.25e-6 # type:ignore
        return {"role": "assistant", "content": response}, cost