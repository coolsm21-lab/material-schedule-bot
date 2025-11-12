import os
import re
from datetime import datetime, date
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="🏭 자재일정 협력사 챗봇 v2", layout="centered")

# ───────────────────── 비밀번호: secrets.toml에서 로드 ─────────────────────
try:
    ADMIN_PW = st.secrets["admin"]["password"]
except Exception:
    ADMIN_PW = None

DATA_DIR = "./data"
os.makedirs(DATA_DIR, exist_ok=True)

# ───────────────────── 날짜 파서 (다양한 변형 인식) ─────────────────────
def _try_make_date(y, m, d):
    try:
        if y is None:
            return None
        y = int(y)
        if y < 100:  # 2자리 연도 -> 2000년대 가정
            y += 2000
        return date(y, int(m), int(d))
    except Exception:
        return None

def parse_date_any(text: str):
    if not isinstance(text, str):
        return None, None  # (정확일자, (월,일)만 있는 경우)

    s = text.strip()

    # 1) yyyy-mm-dd / yyyy.mm.dd / yyyy/mm/dd
    m = re.search(r'(?P<y>\d{4})\s*[-./]\s*(?P<m>\d{1,2})\s*[-./]\s*(?P<d>\d{1,2})', s)
    if m:
        return _try_make_date(m.group("y"), m.group("m"), m.group("d")), None

    # 2) yy-mm-dd / yy.mm.dd
    m = re.search(r'(?P<y>\d{2})\s*[-./]\s*(?P<m>\d{1,2})\s*[-./]\s*(?P<d>\d{1,2})', s)
    if m:
        return _try_make_date(m.group("y"), m.group("m"), m.group("d")), None

    # 3) 25.9.5일 / 25.09.5일 / 25.09.05일
    m = re.search(r'(?P<y>\d{2,4})\s*\.\s*(?P<m>\d{1,2})\s*\.\s*(?P<d>\d{1,2})(?:\s*일)?', s)
    if m:
        return _try_make_date(m.group("y"), m.group("m"), m.group("d")), None

    # 4) 25년 10월 27일 (연도 포함, 공백/띄어쓰기 유연)
    m = re.search(r'(?P<y>\d{2,4})\s*년\s*(?P<m>\d{1,2})\s*월\s*(?P<d>\d{1,2})\s*일', s)
    if m:
        return _try_make_date(m.group("y"), m.group("m"), m.group("d")), None

    # 5) 10월27일 / 10월 27일 / 9월8일 / 9월 8일 (연도 미포함 → 월/일만 반환)
    m = re.search(r'(?P<m>\d{1,2})\s*월\s*(?P<d>\d{1,2})\s*일', s)
    if m:
        return None, (int(m.group("m")), int(m.group("d")))

    return None, None

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

def extract_tokens_natural(q: str):
    if not isinstance(q, str):
        return []
    s = q.lower()
    # 날짜 패턴 제거 후 남은 키워드 사용
    patterns = [
        r'\d{4}\s*[-./]\s*\d{1,2}\s*[-./]\s*\d{1,2}',
        r'\d{2}\s*[-./]\s*\d{1,2}\s*[-./]\s*\d{1,2}',
        r'\d{2,4}\s*\.\s*\d{1,2}\s*\.\s*\d{1,2}(?:\s*일)?',
        r'\d{2,4}\s*년\s*\d{1,2}\s*월\s*\d{1,2}\s*일',
        r'\d{1,2}\s*월\s*\d{1,2}\s*일',
    ]
    for p in patterns:
        s = re.sub(p, ' ', s)
    # 불용어 제거 (한국어 간단)
    stop = {'했어','했나요','했냐','했나여','있나요','있나','있나여','있는지','작업','완료','조회','확인','좀','해주세요','해줘','주세요','있었나','있었나요','되었나','되었나요','되었나여'}
    tokens = [t for t in re.split(r'[^0-9a-z가-힣]+', s) if t and t not in stop]
    return tokens

def summarize_row(row: pd.Series) -> str:
    parts = []
    if "업체명" in row and pd.notna(row["업체명"]):
        parts.append(f"🏭 {row['업체명']}")
    # 대표 날짜: 작업일자 → 요청일자 → 인수일자
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
    st.markdown("<h1 style='text-align:center;'>🏭 자재일정 협력사 챗봇 v2</h1>", unsafe_allow_html=True)
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

    q = st.text_input("🔍 질문 또는 키워드 입력", placeholder="예: 25년 10월 27일 작업, 3ATSN7363C0001 완료 여부 등")
    if st.button("조회"):
        # 1) 날짜 파싱 (정확일자 또는 월/일만)
        exact_date, monthday = parse_date_any(q)

        # 2) 자연어 키워드 추출
        tokens = extract_tokens_natural(q)

        df_filtered = df_company

        # 날짜 필터 적용
        if exact_date is not None and "작업일자" in df_filtered.columns:
            df_filtered = df_filtered[df_filtered["작업일자"] == exact_date]
        elif monthday is not None and "작업일자" in df_filtered.columns:
            m, d = monthday
            md_mask = df_filtered["작업일자"].apply(lambda x: isinstance(x, date) and x.month == m and x.day == d)
            df_filtered = df_filtered[md_mask]

        # 키워드(발주번호 등) 필터
        if tokens:
            df_filtered = fast_contains_any(df_filtered, tokens)

        if df_filtered.empty:
            st.info("일치하는 데이터가 없습니다. 날짜·키워드를 바꿔보세요. (예: 25년 10월 27일 / 3ATSN7363C0001)")
        else:
            st.markdown("#### 📋 검색결과 요약")
            st.text(summarize_row(df_filtered.iloc[0]))

            st.markdown("#### 📊 상세내역 (해당 협력사 데이터)")
            st.dataframe(df_filtered, use_container_width=True)

    st.button("⬅ 처음으로", on_click=go_home)
