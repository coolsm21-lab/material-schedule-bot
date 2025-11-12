import os
import re
from datetime import datetime, date
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="🏭 자재일정 협력사 챗봇 v3", layout="centered")

try:
    ADMIN_PW = st.secrets["admin"]["password"]
except Exception:
    ADMIN_PW = None

DATA_DIR = "./data"
os.makedirs(DATA_DIR, exist_ok=True)

def _try_make_date(y, m, d):
    try:
        if y is None:
            return None
        y = int(y)
        if y < 100:
            y += 2000
        return date(y, int(m), int(d))
    except Exception:
        return None

def parse_date_any(text: str):
    if not isinstance(text, str):
        return None, None
    s = text.strip()
    patterns = [
        (r'(?P<y>\d{4})[-./](?P<m>\d{1,2})[-./](?P<d>\d{1,2})', True),
        (r'(?P<y>\d{2})[-./](?P<m>\d{1,2})[-./](?P<d>\d{1,2})', True),
        (r'(?P<y>\d{2,4})\.\s*(?P<m>\d{1,2})\.\s*(?P<d>\d{1,2})', True),
        (r'(?P<y>\d{2,4})\s*년\s*(?P<m>\d{1,2})\s*월\s*(?P<d>\d{1,2})\s*일', True),
        (r'(?P<m>\d{1,2})\s*월\s*(?P<d>\d{1,2})\s*일', False),
    ]
    for p, has_y in patterns:
        m = re.search(p, s)
        if m:
            if has_y:
                return _try_make_date(m.group("y"), m.group("m"), m.group("d")), None
            else:
                return None, (int(m.group("m")), int(m.group("d")))
    return None, None

@st.cache_data(ttl=600, show_spinner=False)
def load_excel_all(path: str) -> pd.DataFrame:
    sheets = pd.read_excel(path, sheet_name=None, engine="openpyxl")
    if not sheets:
        return pd.DataFrame()
    df = pd.concat(sheets.values(), ignore_index=True)
    df.columns = [str(c).strip() for c in df.columns]
    for c in ["업체코드","업체명","작업일자","요청일자","인수일자","발주번호","아이템","PACKAGE","수량"]:
        if c not in df.columns:
            df[c] = np.nan
    for c in ["작업일자","요청일자","인수일자"]:
        df[c] = pd.to_datetime(df[c], errors="coerce").dt.date
    df["업체코드"] = df["업체코드"].astype(str).str.lower().str.strip()
    return df

def fast_contains_any(df: pd.DataFrame, tokens):
    if isinstance(tokens, str):
        tokens = [tokens]
    tokens = [str(t).strip().lower() for t in tokens if str(t).strip()]
    if not tokens:
        return df.iloc[0:0]
    df_str = df.astype(str).apply(lambda s: s.str.lower())
    mask_total = np.column_stack([
        df_str[col].str.contains('|'.join(map(re.escape, tokens)), na=False)
        for col in df_str.columns
    ]).any(axis=1)
    return df.loc[mask_total]

def extract_tokens_natural(q: str):
    if not isinstance(q, str):
        return []
    s = q.lower()
    s = re.sub(r'\d{2,4}[년\.\-/]\s*\d{1,2}[월\.\-/]\s*\d{1,2}(일)?', ' ', s)
    stop = {'했어','됐어','언제','있나','있나요','있어','지금','가면','가도','돼','되나','되었','확인','조회','좀','해줘','주세요'}
    tokens = [t for t in re.split(r'[^0-9a-z가-힣]+', s) if t and t not in stop]
    return tokens

def summarize_row(row: pd.Series) -> str:
    parts = []
    if "업체명" in row and pd.notna(row["업체명"]):
        parts.append(f"🏭 {row['업체명']}")
    for key in ["작업일자","요청일자","인수일자"]:
        if key in row and pd.notna(row[key]):
            parts.append(f"📅 {row[key]} 작업내역")
            break
    if "수량" in row and pd.notna(row["수량"]):
        try:
            qty = int(float(row["수량"]))
        except Exception:
            qty = row["수량"]
        parts.append(f"📦 총 수량: {qty}건")
    if "발주번호" in row and pd.notna(row["발주번호"]):
        parts.append(f"📋 발주번호: {row['발주번호']}")
    return "\n".join(parts)

if "page" not in st.session_state:
    st.session_state["page"] = "home"
if "mode" not in st.session_state:
    st.session_state["mode"] = None

def go_home(): st.session_state["page"] = "home"
def go_login(mode): st.session_state.update({"mode": mode, "page": "login"})
def go_admin(): st.session_state["page"] = "admin"
def go_partner(code=None):
    if code: st.session_state["code"] = code.strip().lower()
    st.session_state["page"] = "partner"

if st.session_state["page"] == "home":
    st.markdown("<h1 style='text-align:center;'>🏭 자재일정 협력사 챗봇 v3</h1>", unsafe_allow_html=True)
    mode = st.radio("모드를 선택하세요", ["협력사용", "관리자용"], horizontal=True)
    st.button("확인", on_click=go_login, args=(mode,))

elif st.session_state["page"] == "login":
    if st.session_state["mode"] == "관리자용":
        pw = st.text_input("비밀번호 입력", type="password")
        def _try_admin():
            if ADMIN_PW and pw == ADMIN_PW:
                go_admin()
            else:
                st.error("비밀번호가 틀렸습니다.")
        st.button("확인", on_click=_try_admin)
        st.button("⬅ 처음으로", on_click=go_home)
    elif st.session_state["mode"] == "협력사용":
        code = st.text_input("협력업체 코드 입력 (예: A001)")
        st.button("확인", on_click=lambda: go_partner(code) if code.strip() else st.warning("코드를 입력하세요."))
        st.button("⬅ 처음으로", on_click=go_home)

elif st.session_state["page"] == "admin":
    st.subheader("👷 관리자용 파일 업로드")
    up = st.file_uploader("📤 엑셀 업로드", type=["xlsx"])
    if up:
        save_path = os.path.join(DATA_DIR, "material_schedule.xlsx")
        with open(save_path, "wb") as f: f.write(up.getbuffer())
        st.success(f"✅ 파일 저장 완료: {save_path}")
    st.button("⬅ 처음으로", on_click=go_home)

elif st.session_state["page"] == "partner":
    path = os.path.join(DATA_DIR, "material_schedule.xlsx")
    if not os.path.exists(path):
        st.error("📄 관리자용에서 엑셀 파일을 업로드하세요.")
        st.button("⬅ 처음으로", on_click=go_home)
        st.stop()

    df_all = load_excel_all(path)
    code = st.session_state.get("code", "").lower()
    df_company = df_all[df_all["업체코드"] == code]
    if df_company.empty:
        st.subheader(f"🤖 협력사 전용 챗봇 ({code.upper()})")
        st.warning("해당 업체코드의 데이터가 없습니다.")
        st.button("⬅ 처음으로", on_click=go_home)
        st.stop()

    company_name = df_company["업체명"].dropna().astype(str).iloc[0]
    st.subheader(f"🤖 협력사 전용 챗봇 {company_name}")

    q = st.text_input("🔍 질문 또는 키워드 입력", placeholder="예: 25년10월27일 작업됐어?, 발주번호 알려줘 등")
    if q:
        exact_date, monthday = parse_date_any(q)
        tokens = extract_tokens_natural(q)

        df_filtered = df_company
        if exact_date is not None:
            df_filtered = df_filtered[df_filtered["작업일자"] == exact_date]
        elif monthday is not None:
            m, d = monthday
            df_filtered = df_filtered[df_filtered["작업일자"].apply(lambda x: isinstance(x, date) and x.month == m and x.day == d)]
        if tokens:
            df_filtered = fast_contains_any(df_filtered, tokens)

        if df_filtered.empty:
            st.info("일치하는 데이터가 없습니다. (예: 25년10월27일 / 3ATSN7363C0001 등)")
        else:
            row = df_filtered.iloc[0]
            st.markdown("#### 📋 검색결과 요약")
            st.text(summarize_row(row))
            st.markdown("#### 📊 상세내역")
            for c, v in row.items():
                st.write(f"**{c}**: {v}")
            st.markdown("---")
            st.dataframe(df_filtered, use_container_width=True)

    st.button("⬅ 처음으로", on_click=go_home)