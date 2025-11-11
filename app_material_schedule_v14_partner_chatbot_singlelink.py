# 🏷️ 자재일정 협력사 챗봇 v14 (단일링크형)
import os, re
import pandas as pd
import streamlit as st
from datetime import datetime

st.set_page_config(page_title="🏷️ 자재일정 협력사 챗봇", layout="centered")
st.markdown("## 🏭 자재일정 협력사 전용 챗봇")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

def pick_col(df, keys):
    low = {str(c).strip().lower(): c for c in df.columns}
    for k in keys:
        key = str(k).strip().lower()
        if key in low:
            return low[key]
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
    files = [f for f in os.listdir(DATA_DIR) if f.endswith('.xlsx')]
    if not files:
        raise FileNotFoundError("xlsx 파일이 없습니다.")
    latest = max([os.path.join(DATA_DIR,f) for f in files], key=os.path.getmtime)
    all_sheets = pd.read_excel(latest, sheet_name=None, engine='openpyxl')
    merged=[]
    for sn, df in all_sheets.items():
        if df.empty: continue
        df = df.copy()
        code_col = pick_col(df, ['업체코드','협력사코드','거래처코드'])
        name_col = pick_col(df, ['업체명','협력사명','거래처명'])
        if code_col: df.rename(columns={code_col:'업체코드'}, inplace=True)
        if name_col: df.rename(columns={name_col:'업체명'}, inplace=True)
        for c in ['작업일자','요청일자','인수일자']:
            if c in df.columns:
                df[c] = pd.to_datetime(df[c], errors='coerce').dt.date
        if '수량' in df.columns:
            df['수량'] = pd.to_numeric(df['수량'].astype(str).str.replace(',','').str.strip(), errors='coerce').fillna(0).astype(int)
        df['시트명']=sn
        merged.append(df)
    return pd.concat(merged, ignore_index=True)

def parse_date_kor(text):
    m = re.search(r'(\d{4})[./-](\d{1,2})[./-](\d{1,2})', text)
    if m:
        y,mth,d=map(int,m.groups()); return datetime(y,mth,d).date()
    m = re.search(r'(\d{1,2})월\s*(\d{1,2})일', text)
    if m:
        now=datetime.now(); mth,d=map(int,m.groups()); return datetime(now.year,mth,d).date()
    return None

def answer(df, q):
    q=q.lower()
    date=parse_date_kor(q)
    df2=df.copy()
    if date:
        for c in ['작업일자','요청일자','인수일자']:
            if c in df2.columns and date in df2[c].values:
                df2=df2[df2[c]==date]; break
    res=""
    if '작업' in q and ('완료' in q or '되었' in q):
        cnt=df2['수량'].sum() if '수량' in df2.columns else len(df2)
        res=f"작업 {'완료' if not df2.empty else '미완료'} / 수량 {cnt:,}건"
    elif '인수' in q:
        cnt=df2['수량'].sum() if '수량' in df2.columns else len(df2)
        res=f"인수 {'완료' if not df2.empty else '미완료'} / 수량 {cnt:,}건"
    elif '요청' in q:
        last=df['요청일자'].dropna().max() if '요청일자' in df.columns else None
        res=f"최근 요청일자: {last}" if last else '요청일자 없음'
    elif '수량' in q:
        res=f"총 수량 {df2['수량'].sum():,}건" if '수량' in df2.columns else '수량정보 없음'
    else:
        res="예) '10월 10일 작업완료?', '인수완료?', '수량 보여줘'"
    if not df2.empty:
        st.dataframe(df2[[c for c in ['작업일자','요청일자','인수일자','발주번호','아이템','규격','수량','PACKAGE','브랜드'] if c in df2.columns]])
    return res

# --- UI ---
if 'page' not in st.session_state: st.session_state['page']='start'
if 'df' not in st.session_state: st.session_state['df']=None

st.markdown('<style>.block-container{padding-top:1rem;padding-bottom:0rem;}input[type=text]{font-size:18px;}button[kind="primary"]{width:100%;height:48px;font-size:18px;}</style>', unsafe_allow_html=True)

if st.session_state['page']=='start':
    code=st.text_input('🔹 협력업체 코드 입력', placeholder='예: A001')
    if st.button('조회하기') and code:
        try:
            df_all=load_all_data()
            df_all['업체코드']=df_all['업체코드'].astype(str).str.strip().str.lower()
            code=code.strip().lower()
            df=df_all[df_all['업체코드']==code]
            if df.empty:
                st.error('해당 코드가 존재하지 않습니다.')
            else:
                st.session_state['df']=df
                st.session_state['page']='chat'
                st.rerun()
        except Exception as e:
            st.error(f'데이터 로드 오류: {e}')

elif st.session_state['page']=='chat':
    df=st.session_state['df']
    nm=df['업체명'].dropna().iloc[0] if '업체명' in df.columns else '(업체명없음)'
    st.markdown(f"### 🏭 {nm} 협력사 전용 챗봇")
    user_q=st.chat_input('질문을 입력하세요 (예: 10월 10일 작업완료?)')
    if 'chat_history' not in st.session_state: st.session_state['chat_history']=[]
    for m in st.session_state['chat_history']:
        with st.chat_message(m['role']): st.markdown(m['content'])
    if user_q:
        st.session_state['chat_history'].append({'role':'user','content':user_q})
        with st.chat_message('user'): st.markdown(user_q)
        try: ans=answer(df,user_q)
        except Exception as e: ans=f'오류: {e}'
        st.session_state['chat_history'].append({'role':'assistant','content':ans})
        with st.chat_message('assistant'): st.markdown(ans)
    if st.button('🔙 처음으로'):
        st.session_state['page']='start'; st.rerun()
