"""Scroll targets: invisible DOM anchors + parent-frame scroll via components.html.

``window.parent.document`` reaches the Streamlit host page from the components iframe.
If your deployment blocks parent access, scrolling will no-op silently.
"""
from __future__ import annotations

import json

import streamlit as st
import streamlit.components.v1 as components


def inject_anchor(anchor_id: str) -> None:
    """Render a zero-footprint element with a stable ``id`` for ``scrollIntoView``."""
    if not anchor_id or not anchor_id.startswith("mmf-anchor-"):
        raise ValueError("anchor_id must start with mmf-anchor-")
    st.markdown(
        f'<div id="{anchor_id}" class="mmf-scroll-target" '
        'style="height:1px;width:1px;margin:0;padding:0;'
        "scroll-margin-top:5.5rem;overflow:hidden;position:relative;"
        '"></div>',
        unsafe_allow_html=True,
    )


def try_consume_pending_scroll(*, inputs_collapsed: bool) -> None:
    """If session queued a target id, scroll it into view after the current run paints."""
    aid = st.session_state.pop("mmf_scroll_to_id", None)
    if not isinstance(aid, str) or not aid.startswith("mmf-anchor-"):
        return
    if inputs_collapsed and aid.startswith("mmf-anchor-sb-"):
        return
    aid_json = json.dumps(aid)
    components.html(
        f"""<!DOCTYPE html><html><body><script>
const id = {aid_json};
setTimeout(function () {{
  try {{
    const doc = window.parent.document;
    const el = doc.getElementById(id);
    if (el) {{
      el.scrollIntoView({{behavior: "smooth", block: "center"}});
    }}
  }} catch (e) {{}}
}}, 450);
</script></body></html>""",
        height=0,
        width=0,
    )
