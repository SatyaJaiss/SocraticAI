"""Documents page — uploading and managing study notes for RAG."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure repository root is on sys.path
root_dir = Path(__file__).resolve().parents[3]
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import streamlit as st
from apps.frontend.services.api_client import SocraticAIClientError
from apps.frontend.utils.state import get_client, student_id

st.header("Study Notes (RAG)", icon=":material/menu_book:")
st.caption(
    "Upload lecture notes or textbooks (PDF, TXT, or Markdown). The AI tutor retrieves "
    "contextual passages when answering your questions."
)

with st.container(border=True):
    uploaded = st.file_uploader(
        "Upload notes",
        type=["pdf", "txt", "md"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )
    if uploaded:
        for file in uploaded:
            try:
                with st.spinner(f"Indexing {file.name}…"):
                    result = get_client().upload_document(
                        student_id(), file.name, file.getvalue()
                    )
                if result.get("status") == "ingested":
                    st.success(
                        f"Indexed {file.name} ({result.get('chunk_count', 0)} chunks)"
                    )
                else:
                    st.error(f"{file.name}: {result.get('error', 'unknown error')}")
            except SocraticAIClientError as exc:
                st.error(str(exc))

try:
    documents = get_client().list_documents(student_id())
except SocraticAIClientError as exc:
    st.error(str(exc))
    documents = []

st.subheader("Your Ingested Documents", icon=":material/folder:")
if not documents:
    st.info("No documents uploaded yet.")
else:
    for doc in documents:
        with st.container(border=True):
            col1, col2, col3 = st.columns([5, 3, 1], vertical_alignment="center")
            col1.markdown(f"**{doc.get('filename')}**")
            col2.caption(f"{doc.get('status', 'active')} · {doc.get('chunk_count', 0)} chunks")
            if col3.button("Delete", key=f"del_{doc.get('doc_id')}", icon=":material/delete:"):
                try:
                    get_client().delete_document(doc.get("doc_id"))
                    st.rerun()
                except SocraticAIClientError as exc:
                    st.error(str(exc))
