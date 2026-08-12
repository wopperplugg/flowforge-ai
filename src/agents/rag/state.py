from langchain_core.documents import Document
from langgraph.graph import MessagesState


class RAGState(MessagesState):
    query: str
    documents: list[Document]
    documents_relevant: bool
    answer: str
    rewrite_count: int