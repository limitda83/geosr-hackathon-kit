"""산출물 파일의 수정시각을 모아 submit/evidence/timestamps.txt 로 기록(증빙 자동화).

재사용 자산: 언제든 `python scripts/log_evidence.py` 로 타임스탬프 증빙을 갱신.
"""
import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "submit" / "evidence" / "timestamps.txt"
TARGETS = ["app.py", "config.py", "requirements.txt", ".env.example",
           "src", "scripts", "data/news/seed_events.csv"]


def iter_files():
    for t in TARGETS:
        p = ROOT / t
        if p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.is_file() and "__pycache__" not in f.parts:
                    yield f
        elif p.is_file():
            yield p


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().isoformat(timespec="seconds")
    lines = [f"# 산출물 타임스탬프 (자동 생성: {stamp})",
             f"# 기준 경로: {ROOT}", ""]
    n = 0
    for f in iter_files():
        st = f.stat()
        mt = datetime.datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds")
        lines.append(f"{mt}  {st.st_size:>8d}B  {f.relative_to(ROOT)}")
        n += 1
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"기록 완료: {OUT}  ({n} files)")


if __name__ == "__main__":
    main()
