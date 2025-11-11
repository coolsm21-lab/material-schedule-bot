# 🏷️ 자재일정 협력사 챗봇 (v13 - 업체코드 + 발주번호 통합검색)
import os, re
import pandas as pd
import streamlit as st
from datetime import datetime

st.set_page_config(page_title="🏷️ 자재일정 협력사 챗봇", layout="centered")
st.title("🏷️ 자재일정 협력사 챗봇 (업체코드 + 발주번호 통합)")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

def parse_date_kor(text):
    text = (text or "").strip()
    m = re.search(r"(\d{4})[./-](\d{1,2})[./-](\d{1,2})", text)
    if m:
        y, mth, d = map(int, m.groups())
        return datetime(y, mth, d).date()
    m = re.search(r"(\d{1,2})\s*월\s*(\d{1,2})\s*일", text)
    if m:
        now = datetime.now()
        mth, d = map(int, m.groups())
        return datetime(now.year, mth, d).date()
    m = re.search(r"(\d{1,2})[./-](\d{1,2})", text)
    if m:
        now = datetime.now()
        mth, d = map(int, m.groups())
        return datetime(now.year, mth, d).date()
    return None

def pick_col(df, keys):
    low = {str(c).strip().lower(): c for c in df.columns}
    for k in keys:
        key = str(k).strip().lower()
        if key in low: return low[key]
    for c in df.columns:
        lc = str(c).strip().lower()
        for k in keys:
            if str(k).strip().lower() in lc:
                return c
    return None

@st.cache_data
def load_all_data():
    if not os.path.isdir(DATA_DIR):
        raise FileNotFoundError("data 폴더가 없습니다.")
    files = [f for f in os.listdir(DATA_DIR) if f.endswith(".xlsx")]
    if not files:
        raise FileNotFoundError("xlsx 파일이 없습니다.")
    latest = max([os.path.join(DATA_DIR,f) for f in files], key=os.path.getmtime)
    all_sheets = pd.read_excel(latest, sheet_name=None, engine="openpyxl")
    merged = []
    for sn, df in all_sheets.items():
        df = df.copy()
        if df.empty: continue
        code_col = pick_col(df, ["업체코드","협력사코드","거래처코드"])
        name_col = pick_col(df, ["업체명","협력사명","거래처명"])
        po_col = pick_col(df, ["발주번호","주문번호","po"])
        qty_col = pick_col(df, ["수량","qty"])
        work_col = pick_col(df, ["작업일자","작업일","완료일"])
        req_col = pick_col(df, ["요청일자","요청일"])
        recv_col = pick_col(df, ["인수일자","인계","수령일자"])
        pkg_col = pick_col(df, ["PACKAGE","포장","패키지"])
        item_col = pick_col(df, ["아이템","품목","제품명"])
        if code_col: df.rename(columns={code_col:"업체코드"}, inplace=True)
        if name_col: df.rename(columns={name_col:"업체명"}, inplace=True)
        if po_col: df.rename(columns={po_col:"발주번호"}, inplace=True)
        if qty_col: df.rename(columns={qty_col:"수량"}, inplace=True)
        if work_col: df.rename(columns={work_col:"작업일자"}, inplace=True)
        if req_col: df.rename(columns={req_col:"요청일자"}, inplace=True)
        if recv_col: df.rename(columns={recv_col:"인수일자"}, inplace=True)
        if pkg_col: df.rename(columns={pkg_col:"PACKAGE"}, inplace=True)
        if item_col: df.rename(columns={item_col:"아이템"}, inplace=True)
        for c in ["작업일자","요청일자","인수일자"]:
            if c in df.columns:
                df[c] = pd.to_datetime(df[c], errors="coerce").dt.date
        if "수량" in df.columns:
            df["수량"] = pd.to_numeric(df["수량"].astype(str).str.replace(",","").str.strip(), errors="coerce").fillna(0).astype(int)
        if "업체코드" in df.columns:
            df["업체코드"] = df["업체코드"].astype(str).str.strip().str.lower()
        df["시트명"] = sn
        merged.append(df)
    df = pd.concat(merged, ignore_index=True)
    return df

def filter_code(df, code):
    c = str(code).strip().lower()
    if "업체코드" in df.columns and c in df["업체코드"].values:
        return df[df["업체코드"]==c], "업체"
    elif "발주번호" in df.columns and c in df["발주번호"].astype(str).values:
        return df[df["발주번호"].astype(str)==c], "발주"
    return pd.DataFrame(), None

def summary_block(df, code_type, code):
    if df.empty: return "해당 데이터가 없습니다."
    nm = df["업체명"].dropna().iloc[0] if "업체명" in df.columns else "(업체명 없음)"
    if code_type=="업체":
        header=f"🏭 {nm} 협력사 전용 챗봇"
    else:
        header=f"📋 발주번호 {code} — {nm}"
    cnt=df["수량"].sum() if "수량" in df.columns else len(df)
    latest=df["작업일자"].dropna().max() if "작업일자" in df.columns else None
    text=f"{header}\n📦 총 수량: {cnt:,}건"
    if latest: text+=f"\n📅 최근 작업일자: {latest}"
    return text

def answer(df, q):
    q=q.lower()
    date=parse_date_kor(q)
    res=""
    df2=df.copy()
    if date:
        for c in ["작업일자","요청일자","인수일자"]:
            if c in df2.columns and date in df2[c].values:
                df2=df2[df2[c]==date]; break
    if "작업" in q and ("완료" in q or "되었" in q):
        done=not df2.empty
        cnt=df2["수량"].sum() if "수량" in df2.columns else 0
        res=f"작업 {'완료' if done else '미완료'}입니다. 수량 {cnt:,}건."
    elif "인수" in q:
        ok=not df2.empty
        cnt=df2["수량"].sum() if "수량" in df2.columns else 0
        res=f"인수 {'완료' if ok else '미완료'}입니다. 수량 {cnt:,}건."
    elif "요청" in q:
        last=df["요청일자"].dropna().max() if "요청일자" in df.columns else None
        res=f"최근 요청일자는 {last} 입니다." if last else "요청일자 정보를 찾지 못했습니다."
    elif "수량" in q:
        total=df2["수량"].sum() if "수량" in df2.columns else len(df2)
        res=f"해당 조건의 수량은 {total:,}건입니다."
    elif "아이템" in q:
        if "아이템" in df2.columns: 
            vals=", ".join(df2["아이템"].astype(str).unique()[:10])
            res=f"아이템: {vals}"
        else: res="아이템 정보가 없습니다."
    elif "package" in q or "패키지" in q or "포장" in q:
        if "PACKAGE" in df2.columns:
            vals=", ".join(df2["PACKAGE"].astype(str).unique()[:10])
            res=f"PACKAGE: {vals}"
        else: res="PACKAGE 정보가 없습니다."
    else:
        res="예) '10월 20일 작업완료', '인수완료?', '아이템 보여줘', 'PACKAGE 내역'"
    if not df2.empty:
        st.dataframe(df2[[c for c in ["작업일자","요청일자","인수일자","발주번호","아이템","규격","수량","PACKAGE","브랜드","시트명"] if c in df2.columns]])
    return res

# Streamlit UI
if "page" not in st.session_state: st.session_state["page"]="start"
if "df" not in st.session_state: st.session_state["df"]=None
if "type" not in st.session_state: st.session_state["type"]=None
if "code" not in st.session_state: st.session_state["code"]=""

if st.session_state["page"]=="start":
    code=st.text_input("🔹 조회코드 입력 (업체코드 또는 발주번호)", placeholder="예: A001 또는 3FTKBA143K003")
    if st.button("조회하기") and code:
        try:
            df_all=load_all_data()
            df_filt,typ=filter_code(df_all,code)
            if df_filt.empty:
                st.error("해당 코드가 존재하지 않습니다.")
            else:
                st.session_state["df"]=df_filt
                st.session_state["type"]=typ
                st.session_state["code"]=code
                st.session_state["page"]="chat"
                st.rerun()
        except Exception as e:
            st.error(f"오류: {e}")

elif st.session_state["page"]=="chat":
    df=st.session_state["df"]; typ=st.session_state["type"]; code=st.session_state["code"]
    st.markdown(summary_block(df,typ,code))
    user_q=st.chat_input("질문을 입력하세요 (예: '10월 20일 작업완료?', '인수완료?', '아이템 뭐야?')")
    if "chat_history" not in st.session_state: st.session_state["chat_history"]=[]
    for m in st.session_state["chat_history"]:
        with st.chat_message(m["role"]): st.markdown(m["content"])
    if user_q:
        st.session_state["chat_history"].append({"role":"user","content":user_q})
        with st.chat_message("user"): st.markdown(user_q)
        try: ans=answer(df,user_q)
        except Exception as e: ans=f"오류: {e}"
        st.session_state["chat_history"].append({"role":"assistant","content":ans})
        with st.chat_message("assistant"): st.markdown(ans)
    if st.button("🔙 처음으로"):
        st.session_state["page"]="start"; st.rerun()
