"""Documents page — uploading and managing study notes for RAG."""

from __future__ import annotations

import streamlit as st

from apps.frontend.services.api_client import SocraticAIClientError
from apps.frontend.utils.state import get_client, student_id


def render_documents() -> None:
    st.subheader("📚 Study Notes (RAG)")
    st.caption(
        "Upload lecture notes (PDF, TXT or Markdown). The tutor will retrieve "
        "relevant passages when you ask questions on them."
    )

    uploaded = st.file_uploader(
        "Choose a file", type=["pdf", "txt", "md"], accept_multiple_files=True
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
                        f"✅ {file.name} — {result.get('chunk_count')} chunks indexed"
                    )
                else:
                    st.error(f"{file.name}: {result.get('error', 'unknown error')}")
            except SocraticAIClientError as exc:
                st.error(str(exc))

    try:
        documents = get_client().list_documents(student_id())
    except SocraticAIClientError as exc:
        st.error(str(exc))
        return

    if not documents:
        st.info("No documents uploaded yet.")
        return

    st.markdown("### Your documents")
    for doc in documents:
        col1, col2, col3 = st.columns([4, 2, 1])
        col1.markdown(f"**{doc.get('filename')}**")
        col2.caption(f"{doc.get('status')} · {doc.get('chunk_count', 0)} chunks")
        if col3.button("Delete", key=f"del_{doc.get('doc_id')}"):
            try:
                get_client().delete_document(doc.get("doc_id"))
                st.rerun()
            except SocraticAIClientError as exc:
                st.error(str(exc))

