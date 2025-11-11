import os
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta

st.set_page_config(page_title="🏷️ 자재일정 멀티시트 챗봇 (B열 업체코드 연동)", layout="centered")
st.title("🏷️ 자재일정 멀티시트 챗봇 (B열 업체코드 연동)")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

def _lower_map(cols):
    return {str(c).strip().lower(): c for c in cols}

def _pick_col_by_names(df, candidates):
    m = _lower_map(df.columns)
    for c in candidates:
        key = str(c).strip().lower()
        if key in m:
            return m[key]
    for col in df.columns:
        lc = str(col).strip().lower()
        for c in candidates:
            if str(c).strip().lower() in lc:
                return col
    return None

@st.cache_data(show_spinner=False)
def load_all_excel_merged(data_dir=DATA_DIR) -> pd.DataFrame:
    if not os.path.isdir(data_dir):
        raise FileNotFoundError(f"데이터 폴더가 없습니다: {data_dir}")
    xfiles = [f for f in os.listdir(data_dir) if f.lower().endswith(".xlsx")]
    if not xfiles:
        raise FileNotFoundError("엑셀 파일이 없습니다. /data 폴더에 .xlsx 파일을 업로드하세요.")
    latest = max([os.path.join(data_dir, f) for f in xfiles], key=os.path.getmtime)
    st.info(f"📂 불러온 파일: **{os.path.basename(latest)}**")
    all_sheets = pd.read_excel(latest, sheet_name=None, engine="openpyxl")
    merged = []
    for sname, sdf in all_sheets.items():
        sdf = sdf.copy()
        code_col = _pick_col_by_names(sdf, ["업체코드", "협력사코드", "거래처코드", "코드"])
        if code_col is None and sdf.shape[1] >= 2:
            code_col = sdf.columns[1]
        if code_col is not None and str(code_col) != "업체코드":
            if "업체코드" in sdf.columns:
                sdf.drop(columns=["업체코드"], inplace=True, errors="ignore")
            sdf.rename(columns={code_col: "업체코드"}, inplace=True)
        qty_col = _pick_col_by_names(sdf, ["수량", "qty", "수량합계"])
        if qty_col is None:
            sdf["수량"] = 0
        elif str(qty_col) != "수량":
            if "수량" in sdf.columns:
                sdf.drop(columns=["수량"], inplace=True, errors="ignore")
            sdf.rename(columns={qty_col: "수량"}, inplace=True)
        type_col = _pick_col_by_names(sdf, ["구분", "유형", "type", "작업유형"])
        if type_col is not None and str(type_col) != "구분":
            if "구분" in sdf.columns:
                sdf.drop(columns=["구분"], inplace=True, errors="ignore")
            sdf.rename(columns={type_col: "구분"}, inplace=True)
        date_col = _pick_col_by_names(sdf, ["날짜", "일자", "date"])
        if date_col is not None and str(date_col) != "날짜":
            if "날짜" in sdf.columns:
                sdf.drop(columns=["날짜"], inplace=True, errors="ignore")
            sdf.rename(columns={date_col: "날짜"}, inplace=True)
        if "업체코드" in sdf.columns:
            sdf["업체코드"] = sdf["업체코드"].astype(str).str.strip().str.lower()
        if "수량" in sdf.columns:
            sdf["수량"] = pd.to_numeric(sdf["수량"], errors="coerce").fillna(0)
        if "구분" in sdf.columns:
            sdf["구분"] = sdf["구분"].astype(str).str.strip().str.lower()
        if "날짜" in sdf.columns:
            sdf["날짜"] = pd.to_datetime(sdf["날짜"], errors="coerce")
        sdf["시트명"] = sname
        merged.append(sdf)
    df = pd.concat(merged, ignore_index=True)
    if "업체코드" not in df.columns:
        if df.shape[1] >= 2:
            fallback_col = df.columns[1]
            df.rename(columns={fallback_col: "업체코드"}, inplace=True)
            df["업체코드"] = df["업체코드"].astype(str).str.strip().str.lower()
        else:
            raise ValueError("업체코드 컬럼을 식별할 수 없습니다. (B열 감지 실패)")
    return df

def filter_company(df, code):
    return df[df["업체코드"] == str(code).strip().lower()]

def summarize(df):
    lines = []
    if "시트명" in df.columns:
        counts = df["시트명"].value_counts().to_dict()
        lines.append("📑 시트별 데이터 건수")
        for s, n in counts.items():
            lines.append(f"- {s}: {n}건")
    if "수량" in df.columns:
        total = int(df["수량"].sum())
        lines.append(f"📦 전체 수량 합계: {total:,}")
    if not lines:
        lines.append("표시할 요약이 없습니다.")
    return "\n".join(lines)

def answer(df, q):
    q = (q or "").lower()
    def sum_by_keyword(keyword):
        if "구분" not in df.columns:
            return 0
        m = df["구분"].astype(str).str.contains(keyword, na=False)
        return int(df.loc[m, "수량"].sum()) if "수량" in df.columns else 0
    if "입고" in q:
        return f"입고 총합은 {sum_by_keyword('입고'):,}건입니다."
    if "출고" in q:
        return f"출고 총합은 {sum_by_keyword('출고'):,}건입니다."
    if "반품" in q:
        return f"반품 총합은 {sum_by_keyword('반품'):,}건입니다."
    if "시트" in q or "sheet" in q:
        sheets = ", ".join(sorted(df.get('시트명', pd.Series()).dropna().unique().tolist()))
        return f"포함된 시트: {sheets if sheets else '시트 정보를 확인할 수 없습니다.'}"
    if "합계" in q or "전체" in q or "총" in q:
        total = int(df.get("수량", pd.Series()).sum()) if "수량" in df.columns else 0
        return f"전체 수량 합계는 {total:,}건입니다."
    return "질문을 이해하지 못했어요. 예) '입고', '출고', '반품', '시트', '합계' 등으로 물어봐 주세요."

if "page" not in st.session_state:
    st.session_state["page"] = "start"
if "company_df" not in st.session_state:
    st.session_state["company_df"] = None
if "chat" not in st.session_state:
    st.session_state["chat"] = []

if st.session_state["page"] == "start":
    st.subheader("🔹 협력업체 코드 입력 (B열 연동)")
    code = st.text_input("🏭 협력업체 코드", placeholder="예: A001 / B002 ...")
    if st.button("조회하기") and code:
        try:
            df_all = load_all_excel_merged()
            comp = filter_company(df_all, code)
            if comp.empty:
                st.error("해당 협력업체 코드 데이터가 없습니다.")
            else:
                st.session_state["company_df"] = comp
                st.session_state["page"] = "chat"
                st.experimental_rerun()
        except Exception as e:
            st.error(f"데이터 로드 오류: {e}")
elif st.session_state["page"] == "chat":
    st.markdown("### 🤖 협력사 전용 챗봇")
    dfc = st.session_state["company_df"]
    st.markdown(summarize(dfc))
    for m in st.session_state["chat"]:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
    user_q = st.chat_input("질문을 입력하세요 (예: 입고/출고/반품/시트/합계)")
    if user_q:
        st.session_state["chat"].append({"role": "user", "content": user_q})
        with st.chat_message("user"):
            st.markdown(user_q)
        try:
            ans = answer(dfc, user_q)
        except Exception as e:
            ans = f"오류 발생: {e}"
        st.session_state["chat"].append({"role": "assistant", "content": ans})
        with st.chat_message("assistant"):
            st.markdown(ans)
    if st.button("🔙 처음으로"):
        st.session_state["page"] = "start"
        st.experimental_rerun()