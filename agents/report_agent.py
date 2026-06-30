"""
보고서 생성 서브에이전트
분석 결과 → Claude API → docx 저장
"""
import os
import anthropic
import pandas as pd
from pathlib import Path
from datetime import datetime

try:
    from docx import Document
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False

SUMMARY_DIR = Path("data/results/summary")


def run(regions: list[dict], results: list[dict]) -> str:
    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)

    summary_rows = []
    for r, res in zip(regions, results):
        if res.get("success") and res.get("data"):
            df = pd.DataFrame(res["data"])
            summary_rows.append({
                "region": r["location"],
                "news_count": r.get("count", 0),
                "sst_avg": round(df["sst"].mean(), 1) if "sst" in df.columns else None,
                "sst_max": round(df["sst"].max(), 1) if "sst" in df.columns else None,
                "hot28_days": int((df["sst"] > 28).sum()) if "sst" in df.columns else 0,
            })

    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(SUMMARY_DIR / "summary.csv", index=False, encoding="utf-8-sig")

    context = summary_df.to_string(index=False) if not summary_df.empty else "데이터 없음"
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        messages=[{"role": "user", "content": f"""
다음 데이터를 바탕으로 2025년 6~8월 고수온 연안재해 분석 보고서를 작성하세요.

{context}

형식: 개요 / 주요 결과 / 지역별 분석 / 권고사항 순서로 작성
"""}],
    )
    report_text = resp.content[0].text

    output_path = SUMMARY_DIR / f"report_{datetime.now().strftime('%Y%m%d')}.docx"
    if HAS_DOCX:
        doc = Document()
        doc.add_heading("고수온 연안재해 분석 보고서", 0)
        doc.add_paragraph(f"생성일: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        for line in report_text.split("\n"):
            doc.add_paragraph(line)
        doc.save(str(output_path))
    else:
        txt_path = output_path.with_suffix(".txt")
        txt_path.write_text(report_text, encoding="utf-8")
        return str(txt_path)

    return str(output_path)
