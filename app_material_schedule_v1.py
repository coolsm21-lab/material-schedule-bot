import os
import re
from datetime import datetime
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="🏭 자재일정 협력사 챗봇 v1", layout="centered")

# ───────────────────── 비밀번호: secrets.toml에서 로드 ─────────────────────
# Streamlit Cloud: Settings → Secrets에 아래 형식으로 저장
# [admin]
# password = "KYJ3212!@#"
try:
    ADMIN_PW = st.secrets["admin"]["password"]
except Exception:
    ADMIN_PW = None  # 비번 미설정 시 관리자 로그인 불가 처리

DATA_DIR = "./data"
os.makedirs(DATA_DIR, exist_ok=True)

def _kdate(text: str):
    if not isinstance(text, str):
        return None
    m = re.search(r"(\d{1,2})\s*월\s*(\d{1,2})\s*일", text)
    if m:
        now = datetime.now()
        try:
            return datetime(now.year, int(m.group(1)), int(m.group(2))).date()
        except Exception:
            return None
    return None

@st.cache_data(ttl=600, show_spinner=False)
def load_excel_all(path: str) -> pd.DataFrame:
    sheets = pd.read_excel(path, sheet_name=None, engine="openpyxl")
    if not sheets:
        return pd.DataFrame()
    if len(sheets) == 1:
        df = list(sheets.values())[0]
    else:
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
    mask_total = None
    df_str = df.astype(str).apply(lambda s: s.str.lower())
    for t in tokens:
        mask_t = np.column_stack([df_str[col].str.contains(re.escape(t), na=False) for col in df_str.columns]).any(axis=1)
        mask_total = mask_t if mask_total is None else (mask_total & mask_t)
    return df.loc[mask_total]

def summarize_row(row: pd.Series) -> str:
    parts = []
    if "업체명" in row and pd.notna(row["업체명"]):
        parts.append(f"🏭 {row['업체명']}")
    date_text = None
    for key in ["작업일자","요청일자","인수일자"]:
        if key in row and pd.notna(row[key]):
            date_text = row[key]; break
    if date_text:
        parts.append(f"📅 {date_text} 작업내역")
    if "수량" in row and pd.notna(row["수량"]):
        try:
            qty = int(float(row["수량"]))
        except Exception:
            qty = row["수량"]
        parts.append(f"📦 총 수량: {qty}건")
    if "발주번호" in row and pd.notna(row["발주번호"]):
        parts.append(f"📋 발주번호: {row['발주번호']}")
    return "\n".join(parts)

# ───────────────────── 상태 초기화 ─────────────────────
if "page" not in st.session_state:
    st.session_state["page"] = "home"
if "mode" not in st.session_state:
    st.session_state["mode"] = None

def go_home():
    st.session_state["page"] = "home"

def go_login(mode):
    st.session_state["mode"] = mode
    st.session_state["page"] = "login"

def go_admin():
    st.session_state["page"] = "admin"

def go_partner(code=None):
    if code:
        st.session_state["code"] = code.strip().lower()
    st.session_state["page"] = "partner"

# ───────────────────── 홈 ─────────────────────
if st.session_state["page"] == "home":
    st.markdown("<h1 style='text-align:center;'>🏭 자재일정 협력사 챗봇 v1</h1>", unsafe_allow_html=True)
    st.markdown("<hr>", unsafe_allow_html=True)
    mode = st.radio("모드를 선택하세요", ["협력사용", "관리자용"], horizontal=True)
    st.button("확인", on_click=go_login, args=(mode,))

# ───────────────────── 로그인 ─────────────────────
elif st.session_state["page"] == "login":
    if st.session_state["mode"] == "관리자용":
        if ADMIN_PW is None:
            st.error("관리자 비밀번호가 설정되지 않았습니다. Settings → Secrets 또는 로컬 .streamlit/secrets.toml 에서 [admin].password 를 설정하세요.")
        pw = st.text_input("비밀번호를 입력하세요", type="password")
        def _try_admin():
            if ADMIN_PW is None:
                st.error("비밀번호 미설정: 관리자 모드로 진입할 수 없습니다.")
            elif pw == ADMIN_PW:
                go_admin()
            else:
                st.error("비밀번호가 올바르지 않습니다.")
        st.button("확인", on_click=_try_admin)
        st.button("⬅ 처음으로", on_click=go_home)

    elif st.session_state["mode"] == "협력사용":
        code = st.text_input("협력업체 코드를 입력하세요 (예: A001)")
        st.button("확인", on_click=lambda: go_partner(code) if code.strip() else st.warning("업체코드를 입력하세요."))
        st.button("⬅ 처음으로", on_click=go_home)

# ───────────────────── 관리자 ─────────────────────
elif st.session_state["page"] == "admin":
    st.subheader("👷 관리자용 파일 업로드")
    up = st.file_uploader("📤 엑셀 업로드", type=["xlsx"])
    if up:
        save_path = os.path.join(DATA_DIR, "material_schedule.xlsx")
        with open(save_path, "wb") as f:
            f.write(up.getbuffer())
        st.session_state["last_upload_file"] = os.path.basename(save_path)
        st.session_state["last_upload_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.success(f"✅ 파일 저장 완료: {save_path}")
        st.info(f"📁 현재 파일: {st.session_state['last_upload_file']}  \n⏰ 업로드: {st.session_state['last_upload_time']}")
    elif "last_upload_file" in st.session_state:
        st.info(f"📁 현재 파일: {st.session_state['last_upload_file']}  \n⏰ 업로드: {st.session_state['last_upload_time']}")
    st.button("⬅ 처음으로", on_click=go_home)

# ───────────────────── 협력사용 ─────────────────────
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

    company_name = df_company["업체명"].dropna().astype(str).iloc[0] if "업체명" in df_company.columns and not df_company["업체명"].dropna().empty else code.upper()
    st.subheader(f"🤖 협력사 전용 챗봇 {company_name}")

    q = st.text_input("🔍 질문 또는 키워드 입력", placeholder="예: 10월 20일 작업, MLB Hangtags, 3FTKBA143K003 등")
    if st.button("조회"):
        date_guess = _kdate(q)
        df_filtered = df_company
        if date_guess is not None and "작업일자" in df_company.columns:
            df_filtered = df_filtered[df_filtered["작업일자"] == date_guess]
        tokens = [t for t in re.split(r"\s+", q) if t.strip()]
        tokens = [t for t in tokens if _kdate(t) is None]
        if tokens:
            df_filtered = fast_contains_any(df_filtered, tokens)
        if df_filtered.empty:
            st.info("일치하는 데이터가 없습니다. 키워드를 줄이거나 날짜 표현을 바꿔보세요.")
        else:
            st.markdown("#### 📋 검색결과 요약")
            st.text(summarize_row(df_filtered.iloc[0]))

            # 중요: 협력사용자는 상세 DataFrame 비표시 (보안)
            st.markdown("#### 📊 상세내역")
            st.info("보안 정책: 협력사용자는 상세내역(원본 데이터)을 볼 수 없습니다. 관리자에게 문의하세요.")
    st.button("⬅ 처음으로", on_click=go_home)
