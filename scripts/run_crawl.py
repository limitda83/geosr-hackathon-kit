"""뉴스 크롤링 파이프라인 CLI (웹앱과 동일 백엔드).

예) python scripts/run_crawl.py --keyword 고수온 --max 100
    python scripts/run_crawl.py --seed
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402
from src.news.crawler import ingest_bigkinds, run_pipeline  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keyword", action="append", help="검색 키워드(여러 번 가능)")
    ap.add_argument("--type", default="고수온", help="재난 유형(DB 분류)")
    ap.add_argument("--since", help="시작일 YYYY-MM-DD")
    ap.add_argument("--until", help="종료일 YYYY-MM-DD")
    ap.add_argument("--max", type=int, default=100, help="키워드당 최대 기사 수")
    ap.add_argument("--top", type=int, default=3, help="AOI 상위 N개")
    ap.add_argument("--seed", action="store_true", help="시드데이터만 사용")
    ap.add_argument("--bigkinds", help="빅카인즈 엑셀/CSV 경로로 적재")
    ap.add_argument("--damage", action="store_true",
                    help="실제 피해 발생 기사만(피해/폐사/양식/적조/경보 등)")
    args = ap.parse_args()

    keywords = args.keyword or [args.type]
    if args.bigkinds:
        print(f"[bigkinds] 적재: {args.bigkinds}  (피해필터={args.damage})")
        rep = ingest_bigkinds(args.bigkinds, disaster_type=args.type,
                              keyword=(args.keyword[0] if args.keyword else None),
                              since=args.since, until=args.until, top_n=args.top,
                              damage_only=args.damage)
    else:
        print(f"[crawl] 네이버 키: {'있음' if config.has_naver() else '없음(→RSS/시드 폴백)'}  (피해필터={args.damage})")
        rep = run_pipeline(disaster_type=args.type, keywords=keywords,
                           max_items=args.max, since=args.since, until=args.until,
                           top_n=args.top, force_seed=args.seed,
                           damage_only=args.damage)
    print(f"[crawl] 소스={rep.source_used}  수집 {rep.n_fetched}건  "
          f"신규 {rep.n_new}건  위치추출 {rep.n_located}건")
    print(f"[AOI] 상위 {len(rep.aois)}개:")
    for a in rep.aois:
        print(f"  #{a.rank} {a.region_name}  ({a.center_lat},{a.center_lon})  "
              f"빈도 {a.event_count}  bbox {a.bbox}")
    print(f"[저장] DB={config.EVENTS_DB}")
    print(f"[저장] AOI={config.AOI_JSON}")


if __name__ == "__main__":
    main()
