"""
Streamlit frontend for the Fact Knowledge Layer.
Calls the FastAPI backend over HTTP.

Tabs:
  1. Upload — drag-and-drop PDF, view fact table, filter by status
  2. Facts Explorer — click fact to see PDF highlight + linked relationships
  3. Four Required Cases — one example of each relationship type from live DB
  4. Reasoning Trace — recent LLM call log for auditability
"""

from __future__ import annotations

import io
import os
from typing import Optional

import requests
import streamlit as st
from PIL import Image

# ── Config ─────────────────────────────────────────────────────────────────────
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(
    page_title="Fact Knowledge Layer",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Shared helpers ─────────────────────────────────────────────────────────────

def api_get(path: str, params: dict = None) -> dict | list | None:
    try:
        r = requests.get(f"{BACKEND_URL}{path}", params=params, timeout=60)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"API error: {e}")
        return None


def api_post_file(path: str, file_bytes: bytes, filename: str) -> dict | None:
    try:
        r = requests.post(
            f"{BACKEND_URL}{path}",
            files={"file": (filename, file_bytes, "application/pdf")},
            timeout=600,
        )
        if r.status_code == 409:
            st.warning(r.json().get("detail", "Document already ingested."))
            return None
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"Upload error: {e}")
        return None


def rel_color(rel_type: str) -> str:
    return {
        "corroboration": "🟢",
        "contradiction": "🔴",
        "reconciled_context": "🟡",
        "uncertain": "⚪",
    }.get(rel_type, "⚫")


def rel_badge(rel_type: str) -> str:
    colors = {
        "corroboration": "#22c55e",
        "contradiction": "#ef4444",
        "reconciled_context": "#f59e0b",
        "uncertain": "#6b7280",
    }
    color = colors.get(rel_type, "#6b7280")
    return f'<span style="background:{color};color:white;padding:2px 8px;border-radius:4px;font-size:0.85em">{rel_type}</span>'


# ── Sidebar: document list ─────────────────────────────────────────────────────

with st.sidebar:
    st.title("📄 Fact Knowledge Layer")
    st.caption("Superjoin VIT 2026 Assignment")
    st.divider()

    docs = api_get("/documents") or []
    if docs:
        st.subheader(f"Ingested Documents ({len(docs)})")
        for d in docs:
            doc_info = d["document"]
            st.markdown(
                f"**{doc_info['filename']}**  \n"
                f"📄 {doc_info['page_count']} pages · "
                f"✅ {d['verified_count']} verified · "
                f"⚠️ {d['unverified_count']} unverified"
            )
    else:
        st.info("No documents ingested yet. Upload a PDF to begin.")

# ── Main tabs ──────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4 = st.tabs([
    "📤 Upload & Ingest",
    "🔎 Facts Explorer",
    "📊 Four Required Cases",
    "🔬 Reasoning Trace",
])

# ══════════════════════════════════════════════════════════════════════════════
# TAB 1: Upload
# ══════════════════════════════════════════════════════════════════════════════

with tab1:
    st.header("Upload a PDF Document")
    st.markdown(
        "Upload any PDF to run the full pipeline: "
        "**parse → chunk → extract facts → verify evidence → canonicalize → reason about relationships**."
    )

    uploaded_file = st.file_uploader(
        "Choose a PDF file", type=["pdf"], key="pdf_upload"
    )

    if uploaded_file:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"**File**: `{uploaded_file.name}`  ({uploaded_file.size:,} bytes)")
        with col2:
            run_btn = st.button("🚀 Ingest & Process", type="primary", use_container_width=True)

        if run_btn:
            with st.spinner("Processing PDF through the full pipeline… this may take a few minutes."):
                result = api_post_file("/documents", uploaded_file.getvalue(), uploaded_file.name)

            if result:
                st.success("✅ Document ingested successfully!")
                col_a, col_b, col_c, col_d, col_e = st.columns(5)
                col_a.metric("Pages", result.get("page_count", 0))
                col_b.metric("Chunks", result.get("chunk_count", 0))
                col_c.metric("Facts", result.get("fact_count", 0))
                col_d.metric("Verified", result.get("verified", 0))
                col_e.metric("Relationships", result.get("new_relationships", 0))

    st.divider()
    st.subheader("Document Fact Tables")

    docs = api_get("/documents") or []
    if not docs:
        st.info("No documents yet.")
    else:
        selected_doc = st.selectbox(
            "Select document",
            options=[d["document"]["id"] for d in docs],
            format_func=lambda did: next(
                (d["document"]["filename"] for d in docs if d["document"]["id"] == did), did
            ),
        )

        status_filter = st.radio(
            "Filter by verification status",
            options=["all", "verified", "unverified", "extraction_failed"],
            horizontal=True,
        )

        params = {} if status_filter == "all" else {"status": status_filter}
        facts = api_get(f"/documents/{selected_doc}/facts", params=params) or []

        if not facts:
            st.info("No facts found for this filter.")
        else:
            import pandas as pd

            df = pd.DataFrame([
                {
                    "Entity": f["entity"],
                    "Attribute": f["attribute"],
                    "Value": f["value"],
                    "Unit": f["unit"] or "",
                    "Scope": str(f["scope"]),
                    "Page": f["page_number"],
                    "Confidence": round(f["confidence"], 3),
                    "Status": f["verification_status"],
                    "ID": f["id"],
                }
                for f in facts
            ])

            # Highlight needs-review rows
            def highlight_status(row):
                if row["Status"] == "extraction_failed":
                    return ["background-color: #fef2f2"] * len(row)
                elif row["Status"] == "unverified":
                    return ["background-color: #fffbeb"] * len(row)
                return [""] * len(row)

            st.dataframe(
                df.style.apply(highlight_status, axis=1),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "ID": st.column_config.TextColumn(width="small"),
                    "Confidence": st.column_config.ProgressColumn(
                        min_value=0, max_value=1, format="%.2f"
                    ),
                },
            )
            st.caption(f"Showing {len(facts)} facts. Red = extraction failed, Yellow = unverified (needs review).")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2: Facts Explorer
# ══════════════════════════════════════════════════════════════════════════════

with tab2:
    st.header("Facts Explorer")
    st.markdown("Select a fact to see its **source page with evidence highlighted** and **linked relationships**.")

    docs = api_get("/documents") or []
    if not docs:
        st.info("No documents yet. Upload a PDF first.")
    else:
        exp_doc = st.selectbox(
            "Document",
            options=[d["document"]["id"] for d in docs],
            format_func=lambda did: next(
                (d["document"]["filename"] for d in docs if d["document"]["id"] == did), did
            ),
            key="explorer_doc",
        )

        exp_facts = api_get(f"/documents/{exp_doc}/facts") or []

        if not exp_facts:
            st.info("No facts for this document.")
        else:
            fact_options = {
                f["id"]: f"{f['entity']} / {f['attribute']} = {f['value']} (p.{f['page_number']})"
                for f in exp_facts
            }
            selected_fact_id = st.selectbox(
                "Select a fact",
                options=list(fact_options.keys()),
                format_func=lambda fid: fact_options[fid],
            )

            selected_fact = next((f for f in exp_facts if f["id"] == selected_fact_id), None)

            if selected_fact:
                col_left, col_right = st.columns([1, 1])

                with col_left:
                    st.subheader("📄 Source Evidence")
                    st.markdown(f"**Entity**: {selected_fact['entity']}")
                    st.markdown(f"**Attribute**: {selected_fact['attribute']}")
                    st.markdown(f"**Value**: `{selected_fact['value']}` {selected_fact['unit'] or ''}")
                    st.markdown(f"**Scope**: `{selected_fact['scope']}`")
                    st.markdown(f"**Page**: {selected_fact['page_number']}")
                    conf = selected_fact['confidence']
                    status = selected_fact['verification_status']
                    status_emoji = {"verified": "✅", "unverified": "⚠️", "extraction_failed": "❌"}.get(status, "❓")
                    st.markdown(f"**Status**: {status_emoji} `{status}` (confidence: {conf:.2f})")

                    st.markdown("**Verbatim Evidence**:")
                    st.info(f'"{selected_fact["verbatim_evidence"]}"')

                    # Render page image
                    bbox = selected_fact.get("bbox")
                    bbox_str = None
                    if bbox and len(bbox) == 4:
                        bbox_str = ",".join(str(x) for x in bbox)

                    img_url = f"{BACKEND_URL}/documents/{exp_doc}/pages/{selected_fact['page_number']}/image"
                    if bbox_str:
                        img_url += f"?highlight_bbox={bbox_str}"

                    try:
                        img_response = requests.get(img_url, timeout=30)
                        img_response.raise_for_status()
                        img = Image.open(io.BytesIO(img_response.content))
                        st.image(img, caption=f"Page {selected_fact['page_number']} — evidence highlighted in yellow", use_column_width=True)
                    except Exception as e:
                        st.warning(f"Could not render page image: {e}")

                with col_right:
                    st.subheader("🔗 Linked Relationships")
                    rels = api_get(f"/facts/{selected_fact_id}/relationships") or []

                    if not rels:
                        st.info("No relationships found yet. Other documents may need to be ingested first.")
                    else:
                        for item in rels:
                            rel = item["relationship"]
                            linked = item.get("linked_fact")
                            rel_type = rel["relationship_type"]

                            with st.expander(
                                f"{rel_color(rel_type)} {rel_type.upper()} (conf: {rel['confidence']:.2f})",
                                expanded=True,
                            ):
                                if linked:
                                    st.markdown(f"**Linked fact**: {linked['entity']} / {linked['attribute']} = `{linked['value']}` {linked['unit'] or ''}")
                                    st.markdown(f"**From**: `{linked['document_id'][:8]}…` · Page {linked['page_number']}")
                                    st.markdown(f"**Evidence B**: _{linked['verbatim_evidence'][:200]}…_")
                                st.markdown(f"**Explanation**: {rel['explanation']}")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3: Four Required Cases
# ══════════════════════════════════════════════════════════════════════════════

with tab3:
    st.header("📊 Four Required Relationship Cases")
    st.markdown(
        "These examples are pulled **live from the database** by relationship type — "
        "not hardcoded. They appear after the demo dataset has been seeded."
    )

    cases = api_get("/relationships/cases") or {}

    case_defs = {
        "corroboration": ("🟢 Corroboration", "Two facts from different documents stating the same value."),
        "contradiction": ("🔴 Contradiction", "Two facts from different documents with materially different values for the same scope."),
        "reconciled_context": ("🟡 Reconciled Context", "Apparent contradiction explained by scope differences (period, basis, geography…)."),
        "uncertain": ("⚪ Uncertain", "Insufficient context to classify — a real and expected outcome."),
    }

    for rel_type, (label, description) in case_defs.items():
        with st.expander(label, expanded=True):
            st.caption(description)
            case = cases.get(rel_type)
            if not case:
                st.info(f"No {rel_type} relationship found yet. Seed more documents to populate this.")
                continue

            rel = case["relationship"]
            fa = case["fact_a"]
            fb = case["fact_b"]

            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown("**Fact A**")
                if fa:
                    st.markdown(f"- **Entity**: {fa['entity']}")
                    st.markdown(f"- **Attribute**: {fa['attribute']}")
                    st.markdown(f"- **Value**: `{fa['value']}` {fa['unit'] or ''}")
                    st.markdown(f"- **Scope**: `{fa['scope']}`")
                    st.markdown(f"- **Evidence**: _{fa['verbatim_evidence'][:250]}_")

            with col_b:
                st.markdown("**Fact B**")
                if fb:
                    st.markdown(f"- **Entity**: {fb['entity']}")
                    st.markdown(f"- **Attribute**: {fb['attribute']}")
                    st.markdown(f"- **Value**: `{fb['value']}` {fb['unit'] or ''}")
                    st.markdown(f"- **Scope**: `{fb['scope']}`")
                    st.markdown(f"- **Evidence**: _{fb['verbatim_evidence'][:250]}_")

            st.markdown(f"**Reasoning**: {rel['explanation']}")
            st.markdown(f"**Confidence**: {rel['confidence']:.2f}")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4: Reasoning Trace
# ══════════════════════════════════════════════════════════════════════════════

with tab4:
    st.header("🔬 Reasoning Trace")
    st.markdown(
        "Every LLM call is logged locally to `data/traces.jsonl`. "
        "This tab shows the most recent entries — providing full auditability of the pipeline."
    )

    n_traces = st.slider("Number of entries to show", min_value=10, max_value=200, value=50, step=10)
    traces = api_get("/trace", params={"n": n_traces}) or []

    if not traces:
        st.info("No trace entries yet. Ingest a document to generate LLM calls.")
    else:
        import pandas as pd

        df = pd.DataFrame([
            {
                "Time": t.get("timestamp", "")[:19].replace("T", " "),
                "Type": t.get("call_type", ""),
                "Model": t.get("model", ""),
                "Input": t.get("input_summary", "")[:80],
                "Output": t.get("output_summary", "")[:80],
                "Latency (ms)": round(t.get("latency_ms", 0)),
                "✓": "✅" if t.get("success") else "❌",
            }
            for t in reversed(traces)
        ])

        st.dataframe(df, use_container_width=True, hide_index=True)
        st.caption(f"Showing {len(traces)} most recent LLM calls.")
