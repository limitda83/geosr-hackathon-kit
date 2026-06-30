# earthquake_model_setting 10단계 분석 (자동화 설계 근거 · 재사용 자산)

> teamH / 작성: Jin. 원본 스크립트는 수정하지 않고 **읽기 분석**만 수행. (에이전트 서브에이전트 3개 병렬 조사)
> 핵심 결론: 모든 단계가 **Python `Config`(경로·파라미터) 하드코딩** 구조 → 자동화 = "파라미터로 Config 생성 + 10단계 순차 오케스트레이션".

## 전체 데이터 흐름
```
01 Deform_plane.xlsx ─(Deform_plane.py)→ *_deform_plane.in        [단층→Okada 입력]
02 *_deform_plane.in + base fort.14 ─(Tsu_xyz*.py)→ *_tsu.xyz     [해저 수직변위]
03 *_tsu.xyz + base fort.14 ─(01_Fort14*.py)→ *_fort.14           [케이스별 격자]  ─(02/03 image)→ PNG 검증
03b fort.14_CASE(CASE1~9) ─(Case_sum_edit*.py)→ *_TOTAL_fort.14   [방향/케이스 합성]
04 raw fort.14 + Only_MSL_lonlat.dat ─(MSL_to_AHHW*.py)→ fort_AHHW.14   [MSL→AHHW 조위보정]
05 fort_AHHW.14 + 케이스 fort.14 ─(Fort13_manning*.py)→ *_fort.13  [Manning/tau0 노드속성]
06 *_fort.13 + 공통실행파일 ─(Transport*.py)→ Run_CASE/<case>/     [지진해일 실행폴더]
── (별도 SLR 라인) ──
07 SSP NetCDF ─(01_SLR_Scenario.py→02_..Global.py)→ Total_Avg_total_slr_{near|far}.dat
08 fort_AHHW.14 + SLR.dat ─(fort14_Create*.py)→ SSP*_SLR.14        [SLR 분포를 격자에 보간]
09 AHHW.14 + SSP*_SLR.14 ─(fort14_Change_Elevation*.py)→ fort.14   [new_z = AHHW수심 + SLR]
10 케이스 fort.13 + 09 fort.14 + 공통파일 ─(Tsunami_SLR_RLT_CASE*.py)→ SLR_RUN/<case>/  [SLR 실행폴더]
   → (ADCIRC+SWAN 실행) → 케이스별 최대침수고/범람 결과(fort.6x 계열)
```

## 시나리오 변형 축 (자동화로 파라미터화할 대상)
| 축 | 값 | 코드에서의 표현 |
|---|---|---|
| 지역(권역) | Ulsan / Jeju_north / Jeju_south / Jindo_Wando | 스크립트 사본 `_2/_3/_4` = 경로·base fort.14·대표MSL 변형 |
| SSP 시나리오 | 2.6 / 4.5 / 7.0 / 8.5 (= ssp126/245/370/585) | 경로 문자열·NetCDF 파일명으로만 구분 |
| 기간 | near(2021–40) / mid / long / far(2081–2100) | 07 `export/avg year` + 폴더명 |
| 거리 | near / far | 08~10 출력 파일·폴더 분기 |
| 지진해일 case | CASE 1~9, 방향시트 EAST/WEST/SOUTH | 01 엑셀 행·시트, 03b `target_case_numbers=range(1,10)` |

## 단계별 핵심 파라미터(사용자가 가장 자주 바꾸는 값)
- **01**: 단층 물리값은 **코드가 아니라 `Deform_plane.xlsx` 셀**에 있음(Lon/Lat, L/W/D, Strike(TH)/Dip(DL)/Depth(HH)/Rake(RD)). `sheets=["SOUTH"]`(방향 선택), `template_title`.
- **02**: `indir`(deform_plane_CASE), `fort14_path`(base 격자). 물리상수(지구반경 등)는 고정. 변위 마스크 `r<=L*2.0`.
- **03**: `fort14_path`, `tsu_dir`, `out_dir`, `xy_round=10`. (이미지: `display_min=-5.0, display_max=10.0`, `tile_zoom`, `case_order`)
- **03b**: `target_case_numbers=range(1,10)`(합산 케이스 필터), 합성규칙(0무시/음수=min/양수=max).
- **04**: `representative_msls`(지역별 검조소 좌표·MSL ← 보정 결과 좌우), `search_radius_km=10.0`, `forced_wet_depth=-0.1`, `msl_sign`.
- **05**: `manning_from_h(h)` 룩업테이블(육상 h<0: Ulsan=0.15 일괄 / 타 권역=0.10~0.04 차등; 수역=0.035~0.017), `tsu_abs_cut=0.001`, `fort.13.tau0base*` 베이스 선택.
- **06**: `common_files`(adcirc,adcprep,aswip,fort.15,padcirc,padcswan,swaninit), `mode=copy`, `overwrite`.
- **07**: `input_nc`(SSP·해상도 015/060/250), `target_var="total_slr"`, `export/avg_start/end_year`(기간), `use_ocean_mask`. 02_Global: 250>060>015 우선순위 병합.
- **08**: `raw_fort14_path`(AHHW), `slr_dat_path`(07 출력), `out_path`, `display_min/max(0~1m)`, `use_nearest_fallback`.
- **09**: `raw_fort14_path`(AHHW), `slr_fort14_path`(08 출력), `out_path`. 규칙 `new_z = raw_z + slr_z`, `coord_tol=1e-9`.
- **10**: `src_dir`(케이스 fort.13), `ahhw_fort14_path`(09 출력), `dst_root`, `common_files`, `overwrite`.

## 자동화 설계 함의
1. **경로 파라미터화가 1차 가치** — 리눅스 절대경로 하드코딩을 `{지역,SSP,기간,거리,case}` 기반 자동 생성으로 대체.
2. **단계 의존 그래프가 명확** — 01→02→03→(03b)→04→05→06 / 07→08→09→10. 파이프라인 엔진이 이 순서를 강제.
3. **데모는 Mock** — 본 ADCIRC/SWAN 실행은 불가하므로, 파라미터→Config→실행준비(폴더/파일 생성)까지는 실제 동작, 최종 결과는 기존 결과/Mock으로 시각화.
