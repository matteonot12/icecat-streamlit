# app.py
"""
Icecat → Smyths data helper
Streamlit one-file app: fetch an Icecat LIVE product sheet, show basic info,
images, a spec table and let the team download assets.
"""

import io, zipfile, requests, pandas as pd, streamlit as st
from pathlib import Path

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------
ICECAT_USER = "openIcecat-live"
ICECAT_API  = "https://live.icecat.biz/api"
LANGUAGES   = {"DE": "de", "NL": "nl", "EN": "en", "FR": "fr"}
TIMEOUT     = 20            # Icecat call timeout (s)
MAX_GALLERY = 20            # thumbnails to keep UI light

st.set_page_config(page_title="Icecat Fetcher", layout="wide")
st.title("📦 Icecat fetch → Smyths helper")

# ---------------------------------------------------------------------------
# INPUT BAR
# ---------------------------------------------------------------------------
col1, col2, col3 = st.columns([1, 2, 1])
with col1:
    lang = st.selectbox("Language", LANGUAGES.keys(), index=2)
with col2:
    gtin = st.text_input("GTIN / EAN", placeholder="0882780751682")
with col3:
    if st.button("Fetch"):
        st.session_state["do_fetch"] = True

if not st.session_state.get("do_fetch"):
    st.stop()

# ---------------------------------------------------------------------------
# FETCH FROM ICECAT
# ---------------------------------------------------------------------------
if not gtin:
    st.warning("Enter a GTIN first.")
    st.stop()

url = (
    f"{ICECAT_API}?UserName={ICECAT_USER}"
    f"&Language={LANGUAGES[lang].upper()}&GTIN={gtin}"
)
try:
    resp = requests.get(url, timeout=TIMEOUT)
    resp.raise_for_status()
    payload = resp.json()
    assert payload.get("msg") == "OK", payload.get("msg")
    data = payload["data"]
except Exception as exc:
    st.error(f"Icecat error → {exc}")
    st.stop()

info       = data["GeneralInfo"]
image_data = data.get("Image", {})
gallery    = data.get("Gallery", [])[:MAX_GALLERY]
media      = data.get("Multimedia", [])

def short_or_long_summary() -> str:
    desc = info.get("SummaryDescription", {})
    return desc.get("LongSummaryDescription") or desc.get("ShortSummaryDescription", "")

# ---------------------------------------------------------------------------
# 1. BASIC INFO  (ONLY Icecat-supplied fields)
# ---------------------------------------------------------------------------
with st.expander("📝 Basic info", expanded=True):
    st.text_input("Product name",  info["ProductName"], disabled=True)
    st.text_input("Vendor article no.", info.get("BrandPartCode", ""), disabled=True)
    st.text_input("Brand", info["Brand"], disabled=True)
    st.text_area("Description", short_or_long_summary(), height=160, disabled=True)

# ---------------------------------------------------------------------------
# 2. SPECIFICATION TABLE  (FeaturesGroups)
# ---------------------------------------------------------------------------
with st.expander("📑 Specification table"):
    rows = [
        (
            grp["FeatureGroup"]["Name"]["Value"],
            feat["Feature"]["Name"]["Value"],
            feat["PresentationValue"],
        )
        for grp in data.get("FeaturesGroups", [])
        for feat in grp["Features"]
    ]
    if rows:
        spec_df = (
            pd.DataFrame(rows, columns=["Group", "Feature", "Value"])
              .set_index(["Group", "Feature"])
        )
        st.dataframe(spec_df, height=min(500, 35 + 26 * len(spec_df)))

# ---------------------------------------------------------------------------
# 3. MEDIA (images • videos • PDFs)
# ---------------------------------------------------------------------------
with st.expander("🖼️ Media", expanded=True):
    hero = image_data.get("Pic500x500") or image_data.get("HighPic")
    if hero:
        st.image(hero, caption="Main image", use_container_width=True)

    if gallery:
        st.markdown("#### Gallery")
        col_grid = st.columns(4)
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w") as zf:
            for idx, pic in enumerate(gallery):
                thumb = pic["ThumbPic"]
                full  = pic["Pic"]
                name  = Path(full).name

                with col_grid[idx % 4]:
                    st.image(thumb, width=130)
                    if st.button("🔍", key=f"pv{idx}"):
                        st.image(full, caption=name, use_container_width=True)
                    st.download_button(
                        "⬇ Full",
                        data=requests.get(full).content,
                        file_name=name,
                        mime="image/jpeg",
                        key=f"dl{idx}"
                    )
                    zf.writestr(name, requests.get(full).content)

        st.download_button(
            "📦 Download all images (ZIP)",
            data=zip_buf.getvalue(),
            file_name=f"{gtin}_images.zip",
            mime="application/zip",
        )

    videos = [m for m in media if m["IsVideo"]]
    pdfs   = [m for m in media if not m["IsVideo"]]
    if videos:
        st.markdown("#### Videos")
        for v in videos:
            st.video(v["URL"])
    if pdfs:
        st.markdown("#### PDFs")
        for p in pdfs:
            st.download_button(
                label=f"⬇ {p.get('Description','PDF') or Path(p['URL']).name}",
                data=requests.get(p["URL"]).content,
                file_name=Path(p["URL"]).name,
            )

# ---------------------------------------------------------------------------
# FOOTER
# ---------------------------------------------------------------------------
st.caption("Icecat ➜ Smyths helper • Streamlit demo")
