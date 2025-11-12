import os
import re
from datetime import datetime, date
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="🏭 자재일정 협력사 챗봇 v3_fix2", layout="centered")

# ───────────────────── 비밀번호: secrets.toml에서 로드 ─────────────────────
try:
    ADMIN_PW = st.secrets["admin"]["password"]
except Exception:
    ADMIN_PW = None

DATA_DIR = "./data"
os.makedirs(DATA_DIR, exist_ok=True)

# ───────────────────── 날짜 파서 (모든 변형 인식) ─────────────────────
def _make_date_safe(y, m, d):
    try:
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
        r'(?P<y>\d{2,4})\s*[년./\- ]*\s*(?P<m>\d{1,2})\s*[월./\- ]*\s*(?P<d>\d{1,2})\s*[일]?',
        r'(?P<m>\d{1,2})\s*[월./\- ]*\s*(?P<d>\d{1,2})\s*[일]?',
    ]
    for p in patterns:
        m = re.search(p, s)
        if m:
            gd = m.groupdict()
            y = gd.get("y")
            mth = gd.get("m")
            d = gd.get("d")
            if y:
                return _make_date_safe(y, mth, d), None
            else:
                return None, (int(mth), int(d))
    return None, None

# ───────────────────── 자연어 + 키워드 추출 ─────────────────────
def extract_tokens_combined(q: str):
    if not isinstance(q, str):
        return []
    s = q.lower()
    # 날짜 제거
    s = re.sub(r'\d{4}[-./]\d{1,2}[-./]\d{1,2}', ' ', s)
    s = re.sub(r'\d{2}[-./]\d{1,2}[-./]\d{1,2}', ' ', s)
    s = re.sub(r'\d{1,2}\s*월\s*\d{1,2}\s*일', ' ', s)
    # 자연어 불용어 제거 (영문+숫자 키워드는 유지)
    stop = {
        '했어','했나요','했냐','했나여','있나요','있나','있나여','있는지','작업','완료','조회','확인','좀',
        '해주세요','해줘','주세요','있었나','있었나요','되었나','되었나요','되었나여','다','되었어','끝났어',
        '끝나','됐나','되었나','다되었','다됐','되었어','다되었나요','다되었나','되었나요','완성','완료됐',
        '있다','했니','했냐','있어','작업했','작업되었','작업완료','작업다되었','작업됐','했을까','되었을까',
        '있을까'
    }
    raw_tokens = re.split(r'[^0-9a-z가-힣]+', s)
    # 영문+숫자코드(발주번호)는 항상 유지
    tokens = []
    for t in raw_tokens:
        if not t:
            continue
        if re.match(r'[a-z0-9]{5,}', t):  # 영문숫자코드
            tokens.append(t)
        elif t not in stop:
            tokens.append(t)
    return tokens

# ───────────────────── 데이터 로드 ─────────────────────
@st.cache_data(ttl=600, show_spinner=False)
def load_excel_all(path: str) -> pd.DataFrame:
    sheets = pd.read_excel(path, sheet_name=None, engine="openpyxl")
    if not sheets:
        return pd.DataFrame()
    df = pd.concat(sheets.values(), ignore_index=True) if len(sheets) > 1 else list(sheets.values())[0]
    df.columns = [str(c).strip().replace(' ', '').lower() for c in df.columns]
    df = df.astype(str).apply(lambda col: col.str.strip().str.lower())
    for c in ["업체코드","업체명","작업일자","요청일자","인수일자","발주번호","아이템","package","수량","규격","브랜드"]:
        if c not in df.columns:
            df[c] = np.nan
    for c in ["작업일자","요청일자","인수일자"]:
        try:
            df[c] = pd.to_datetime(df[c], errors="coerce").dt.date
        except Exception:
            pass
    return df

def fast_contains_any(df: pd.DataFrame, tokens):
    if isinstance(tokens, str):
        tokens = [tokens]
    tokens = [str(t).strip().lower() for t in tokens if str(t).strip()]
    if not tokens:
        return df.iloc[0:0]
    df_str = df.astype(str).apply(lambda s: s.str.lower())
    mask_total = np.zeros(len(df), dtype=bool)
    for t in tokens:
        mask_t = np.column_stack([df_str[col].str.contains(re.escape(t), na=False) for col in df_str.columns]).any(axis=1)
        mask_total = mask_total | mask_t  # OR 조건으로 변경
    return df.loc[mask_total]

# ───────────────────── 요약 표시 ─────────────────────
def summarize_row(row: pd.Series) -> str:
    parts = []
    add = lambda label, col: parts.append(f"{label} {row[col]}") if col in row and pd.notna(row[col]) else None
    add("🏭", "업체명")
    add("📅", "작업일자")
    add("🏷️ 브랜드:", "브랜드")
    add("📦 아이템:", "아이템")
    add("📏 규격:", "규격")
    add("🔢 수량:", "수량")
    add("📋 발주번호:", "발주번호")
    return "\\n".join(parts)

# ───────────────────── 상태 초기화 ─────────────────────
if "page" not in st.session_state:
    st.session_state["page"] = "home"
if "mode" not in st.session_state:
    st.session_state["mode"] = None

def go_home(): st.session_state["page"] = "home"
def go_login(mode): st.session_state["mode"], st.session_state["page"] = mode, "login"
def go_admin(): st.session_state["page"] = "admin"
def go_partner(code=None):
    if code: st.session_state["code"] = code.strip().lower()
    st.session_state["page"] = "partner"

# ───────────────────── 홈 ─────────────────────
if st.session_state["page"] == "home":
    st.markdown("<h1 style='text-align:center;'>🏭 자재일정 협력사 챗봇 v3_fix2</h1>", unsafe_allow_html=True)
    st.markdown("<hr>", unsafe_allow_html=True)
    mode = st.radio("모드를 선택하세요", ["협력사용", "관리자용"], horizontal=True)
    st.button("확인", on_click=go_login, args=(mode,))

# ───────────────────── 로그인 ─────────────────────
elif st.session_state["page"] == "login":
    if st.session_state["mode"] == "관리자용":
        pw = st.text_input("비밀번호를 입력하세요", type="password")
        def _try_admin():
            if ADMIN_PW and pw == ADMIN_PW:
                go_admin()
            else:
                st.error("비밀번호가 올바르지 않습니다.")
        st.button("확인", on_click=_try_admin)
        st.button("⬅ 처음으로", on_click=go_home)
    else:
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
        st.info(f"📁 현재 파일: {st.session_state['last_upload_file']}  \\n⏰ 업로드: {st.session_state['last_upload_time']}")
    elif "last_upload_file" in st.session_state:
        st.info(f"📁 현재 파일: {st.session_state['last_upload_file']}  \\n⏰ 업로드: {st.session_state['last_upload_time']}")
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
    df_company = df_all[df_all["업체코드"].str.lower() == code]

    if df_company.empty:
        st.subheader(f"🤖 협력사 전용 챗봇 ({code.upper()})")
        st.warning("해당 업체코드의 데이터가 없습니다.")
        st.button("⬅ 처음으로", on_click=go_home)
        st.stop()

    company_name = df_company["업체명"].dropna().astype(str).iloc[0] if "업체명" in df_company.columns and not df_company["업체명"].dropna().empty else code.upper()
    st.subheader(f"🤖 협력사 전용 챗봇 ({company_name})")

    q = st.text_input("🔍 질문 또는 키워드 입력", placeholder="예: 25년 10월 27일 작업되었나요, 3ATSN7363C0001, MLB Hangtags 등")
    if st.button("조회"):
        exact_date, monthday = parse_date_any(q)
        tokens = extract_tokens_combined(q)
        df_filtered = df_company

        if exact_date is not None and "작업일자" in df_filtered.columns:
            df_filtered = df_filtered[df_filtered["작업일자"] == exact_date]
        elif monthday is not None and "작업일자" in df_filtered.columns:
            m, d = monthday
            df_filtered = df_filtered[df_filtered["작업일자"].apply(lambda x: isinstance(x, date) and x.month == m and x.day == d)]

        if tokens:
            df_filtered = fast_contains_any(df_filtered, tokens)

        if df_filtered.empty:
            st.info("일치하는 데이터가 없습니다. 날짜·키워드를 바꿔보세요. (예: 25년 10월 27일 / 3ATSN7363C0001 / MLB Hangtags)")
        else:
            st.markdown("#### 📋 검색결과 요약")
            st.text(summarize_row(df_filtered.iloc[0]))
            st.markdown("#### 📊 상세내역 (해당 협력사 데이터)")
            st.dataframe(df_filtered, use_container_width=True)

    st.button("⬅ 처음으로", on_click=go_home)
