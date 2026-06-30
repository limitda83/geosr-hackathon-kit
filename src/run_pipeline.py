# -*- coding: utf-8 -*-
"""
run_pipeline.py — 고수온 분석 전체 파이프라인 한 번에 실행 (요구사항 3·4·5 + 지도)

순서:
  0) (선택) 출력 폴더 비우기 — 같은 날짜가 섞여 중복 집계되는 것을 방지
  1) [요구사항3·4] 일별 SST → 튐값 제거 + 28℃ 이상 고수온영역 추출 → NC + 지도 이미지
  2) [요구사항5-①] 누적 빈도 NC + 해안선 배경 지도
  3) [요구사항5-②] 3일 이상 연속 지속 NC + 해안선 배경 지도

사용법 (저장소 루트에서):
  python src/run_pipeline.py [입력폴더] [고수온폴더] [분석출력폴더]
  예) python src/run_pipeline.py data/input/khoa_sst data/results/sst_analysis/sst_over28 data/results/sst_analysis/persistence

모든 지도는 Natural Earth 해안선(육지 폴리곤)을 배경으로 그립니다.
"""

import os
import sys
import glob
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # src 를 import 경로에
import sst_processing
import sst_frequency
import sst_persistence

THRESHOLD = 28.0
PERSIST_MIN = 2     # 누적 빈도: 2일 이상
CONSEC_MIN = 3      # 연속 지속: 3일 이상


def clear_outputs(hot_dir, persist_dir):
    """이전 결과를 지운다(중복 집계 방지). NC·PNG 만 지우고 폴더는 유지."""
    patterns = [
        os.path.join(hot_dir, "*_HOT*.nc"),
        os.path.join(hot_dir, "img", "*.png"),
        os.path.join(persist_dir, "SST_HOT*.nc"),
        os.path.join(persist_dir, "SST_HOT*.png"),
    ]
    n = 0
    for pat in patterns:
        for f in glob.glob(pat):
            os.remove(f); n += 1
    print(f"[0] 이전 출력 {n}개 정리 완료.", flush=True)


def main():
    src_dir = sys.argv[1] if len(sys.argv) > 1 else "data/input/khoa_sst"
    hot_dir = sys.argv[2] if len(sys.argv) > 2 else "data/results/sst_analysis/sst_over28"
    persist_dir = sys.argv[3] if len(sys.argv) > 3 else "data/results/sst_analysis/persistence"
    img_dir = os.path.join(hot_dir, "img")

    n_in = len(glob.glob(os.path.join(src_dir, "*.nc")))
    print("=" * 64, flush=True)
    print(f"고수온 분석 파이프라인 시작  (입력 {n_in}개 .nc @ {src_dir})", flush=True)
    print("=" * 64, flush=True)
    t0 = time.time()

    clear_outputs(hot_dir, persist_dir)

    # 1) 고수온 추출 + 이미지
    print(f"\n[1] 고수온(≥{int(THRESHOLD)}℃) 추출 + 지도 이미지 생성 ...", flush=True)
    res = sst_processing.process_dir(src_dir, out_dir=hot_dir, threshold=THRESHOLD,
                                     make_image=True, img_dir=img_dir, progress=True)
    ok = [r for r in res if not r.get("error")]
    err = [r for r in res if r.get("error")]
    print(f"  → 추출 완료 {len(ok)}개 (실패 {len(err)}개). NC={hot_dir}, 이미지={img_dir}", flush=True)
    for r in err:
        print(f"    [실패] {os.path.basename(r['in_path'])}: {r['error']}", flush=True)

    # 2) 누적 빈도
    print(f"\n[2] 누적 빈도({PERSIST_MIN}일 이상) 지도 생성 ...", flush=True)
    fs = sst_frequency.run(hot_dir, persist_dir, persist_min=PERSIST_MIN)
    print(f"  → {fs['period']} ({fs['n_days']}일), {PERSIST_MIN}일+ 누적 {fs['persist_cells']:,}격자", flush=True)
    print(f"     NC={fs['nc']}", flush=True)
    print(f"     지도={fs.get('png','')}", flush=True)

    # 3) 3일 이상 연속 지속
    print(f"\n[3] {CONSEC_MIN}일 이상 연속 지속 공간분포 지도 생성 ...", flush=True)
    cs = sst_persistence.run(hot_dir, persist_dir, consec_min=CONSEC_MIN)
    print(f"  → {cs['period']} ({cs['n_days']}일), {CONSEC_MIN}일+ 연속 {cs['consec_cells']:,}격자, 최장 {cs['max_consec_observed']}일", flush=True)
    print(f"     NC={cs['nc']}", flush=True)
    print(f"     지도={cs.get('png','')}", flush=True)

    print(f"\nPIPELINE DONE  (총 {time.time()-t0:.0f}s, 고수온 NC {len(ok)}개 + 이미지 {len(ok)}개 + 분석 NC 2개 + 분석 지도 2개)", flush=True)


if __name__ == "__main__":
    main()
