"""Connect to the notebook's existing Pinecone corpus without re-ingesting."""
import os, json, hashlib, re
from pathlib import Path
from dotenv import dotenv_values
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone
from .data import ROOT

class SetupError(ValueError):
    """Safe, actionable configuration error without secret values."""

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 512  # Matches the user's current notebook and index.

def load_markdown(data_dir: Path) -> list[Document]:
    if not data_dir.is_dir():
        raise FileNotFoundError(f"Create {data_dir} and add .md files, or fix PROJECT_DIR.")
    documents = []
    for path in sorted(data_dir.rglob("*")):
        if not path.is_file() or path.suffix.lower() != ".md":
            continue
        text = path.read_text(encoding="utf-8-sig")
        if not text.strip():
            continue
        heading = re.search(r"^# +(.+)$", text, re.MULTILINE)
        metadata = {
            "source": path.relative_to(data_dir.parent).as_posix(),
            "filename": path.name,
            "title": heading.group(1).strip() if heading else path.stem,
            "document_hash": hashlib.sha256(text.encode()).hexdigest(),
        }
        for label in ("Document type", "Version", "Last updated", "Authority", "Status"):
            match = re.search(rf"^\*\*{re.escape(label)}:\*\*\s*([^\n]+)", text, re.MULTILINE)
            if match:
                metadata[label.lower().replace(" ", "_")] = match.group(1).strip()
        documents.append(Document(page_content=text, metadata=metadata))
    if not documents:
        raise ValueError(f"No non-empty Markdown files found in {data_dir}.")
    return documents

def corpus_namespace(root=ROOT):
    documents = load_markdown(Path(root) / "data")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100,
        length_function=len,
        add_start_index=True,
    )
    chunks = []
    for doc in documents:
        for number, chunk in enumerate(splitter.split_documents([doc]), start=1):
            start = chunk.metadata["start_index"]
            if start < 0:
                raise ValueError("Could not locate a chunk in its source document.")
            chunk.metadata.update({
                "chunk_number": number,
                "line_start": doc.page_content.count("\n", 0, start) + 1,
                "line_end": doc.page_content.count("\n", 0, start + len(chunk.page_content)) + 1,
            })
            chunks.append(chunk)

    signature = json.dumps({
        "embedding": EMBEDDING_MODEL,
        "dimensions": EMBEDDING_DIMENSIONS,
        "chunks": [(d.page_content, d.metadata) for d in chunks],
    }, sort_keys=True)
    NAMESPACE = "product-pulse-" + hashlib.sha256(signature.encode()).hexdigest()[:20]
    chunk_ids = [hashlib.sha256(
        f"{d.metadata['source']}:{d.metadata['chunk_number']}:{d.page_content}".encode()
    ).hexdigest() for d in chunks]
    return NAMESPACE

def settings(root=ROOT, require_pinecone=True):
    # Read on each run so edited keys are used; never print secrets or mutate os.environ.
    config = {**os.environ, **{k:v for k,v in dotenv_values(Path(root)/".env").items() if v is not None}}
    for key in (("OPENAI_API_KEY", "PINECONE_API_KEY") if require_pinecone else ("OPENAI_API_KEY",)):
        if not config.get(key, "").strip():
            raise SetupError(f"Add {key} to Product Pulse/.env before investigating.")
    return config

def connect_retriever(config, root=ROOT):
    pc = Pinecone(api_key=config["PINECONE_API_KEY"])
    index_name = config.get("PINECONE_INDEX_NAME", "product-pulse-rag")
    description = pc.describe_index(index_name)
    if description.dimension != EMBEDDING_DIMENSIONS or description.metric != "cosine":
        raise SetupError("The app expects the notebook's 512-dimensional cosine index. Check its configuration.")
    namespace = corpus_namespace(root)
    index = pc.Index(host=description.host)
    namespaces = index.describe_index_stats().get("namespaces", {})
    if namespaces.get(namespace, {}).get("vector_count", 0) == 0:
        raise SetupError("The current document corpus is not indexed. Run notebook sections 2–6, then retry.")
    embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL, dimensions=EMBEDDING_DIMENSIONS,
        api_key=config["OPENAI_API_KEY"], request_timeout=60, max_retries=1)
    store = PineconeVectorStore(index=index, embedding=embeddings, namespace=namespace, text_key="text")
    return store.as_retriever(search_kwargs={"k":4})

def live_agent(root=ROOT):
    from .agent_tools import build_tools
    from .agent import build_investigation_agent
    config = settings(root)
    retriever = connect_retriever(config,root)
    model = ChatOpenAI(model="gpt-4.1-mini", api_key=config["OPENAI_API_KEY"], temperature=0,
                       timeout=60, max_retries=1, model_kwargs={"parallel_tool_calls":False})
    return build_investigation_agent(model, build_tools(retriever,root))


def openai_model(root=ROOT):
    config = settings(root, require_pinecone=False)
    return ChatOpenAI(model="gpt-4.1-mini", api_key=config["OPENAI_API_KEY"], temperature=0,
                      timeout=60, max_retries=1, model_kwargs={"parallel_tool_calls":False})
