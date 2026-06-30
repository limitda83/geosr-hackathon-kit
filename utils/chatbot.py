import os
import pandas as pd
from pathlib import Path
import streamlit as st
from openai import OpenAI

REGION_FREQ = Path("data/results/frequency/region_frequency.csv")
DISASTER_DB = Path("data/processed/disaster_db/disaster_events.csv")


def _load_context() -> str:
    parts = []
    if REGION_FREQ.exists():
        df = pd.read_csv(REGION_FREQ)
        parts.append(f"관심지역 빈도:\n{df.to_string(index=False)}")
    if DISASTER_DB.exists():
        df = pd.read_csv(DISASTER_DB)
        parts.append(f"재난 뉴스 건수: {len(df)}건\n최근 5건:\n{df.tail(5).to_string(index=False)}")
    return "\n\n".join(parts) if parts else "아직 수집된 데이터가 없습니다."


def ask(question: str, history: list) -> str:
    api_key = os.environ.get("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY", "")
    if not api_key:
        return "⚠️ OPENAI_API_KEY가 설정되지 않았습니다. `.streamlit/secrets.toml`에 키를 추가하세요."

    client = OpenAI(api_key=api_key)

    messages = [
        {"role": "system", "content": f"""당신은 고수온 연안재해 모니터링 시스템의 해양 기상 전문 AI입니다.
아래 데이터를 참고해서 사용자 질문에 간결하게 답하세요.

=== 현재 수집 데이터 ===
{_load_context()}
"""}
    ]
    for m in history:
        role = "assistant" if m["role"] == "assistant" else "user"
        messages.append({"role": role, "content": m["content"]})
    messages.append({"role": "user", "content": question})

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        max_tokens=512,
    )
    return resp.choices[0].message.content
