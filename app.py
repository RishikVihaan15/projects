import tempfile
import streamlit as st
from ingest import ingest_pdf
from qa_chain import load_qa_chain

st.set_page_config(page_title="Document Q&A", page_icon="📄")
st.title("📄 Document Q&A")
st.caption("Upload a PDF and ask questions about it")

if "ingested" not in st.session_state:
    st.session_state.ingested = False
if "chain" not in st.session_state:
    st.session_state.chain = None  # type: ignore

uploaded_file = st.file_uploader("Upload a PDF", type=["pdf"])

if uploaded_file and not st.session_state.ingested:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = tmp.name

    with st.spinner("Reading and indexing your document..."):
        num_chunks = ingest_pdf(tmp_path)
        st.session_state.chain = load_qa_chain()
        st.session_state.ingested = True

    st.success(f"Done! Indexed {num_chunks} chunks. Ask away.")

if st.session_state.ingested:
    if st.button("Upload a different document"):
        st.session_state.ingested = False
        st.session_state.chain = None
        st.rerun()

if st.session_state.ingested:
    question = st.text_input("Ask a question about your document")

    if question:
        with st.spinner("Searching and generating answer..."):
            result = st.session_state.chain.invoke(question)  # type: ignore

        st.markdown("### Answer")
        st.write(result)
else:
    st.info("Upload a PDF above to get started.")