# PROCESS_LOG — 작업 기록 (과정 70점의 핵심 근거)

> 표준 헤더(CLAUDE.md 등)를 로드했다면 에이전트가 알아서 채워 줍니다. 비면 직접 채우세요.
> 원칙: **실제로 시킨 프롬프트를 그대로 인용**할 것. 요약만 있으면 점수가 깎입니다.

## 작성자 정보 (개인별 로그 — 본인 것만)
- 팀명: team-gvidia
- 본인 이름(작성자): srlee
- 공통과제(우리 팀이 자동화한 반복 수작업): 키워드(예: "고수온") 기반 인터넷 뉴스/기사 수집 → 지역·날짜·현상·지속·피해·대응조치 정리 자동화 (구글 뉴스 RSS → 본문 추출 → CSV/엑셀)
- 내가 맡은 부분: 크롤러 기능 설계·구현 (src/news_crawler.py, src/app.py)
- 자유과제(있으면):

> **이 로그는 본인 것만 작성**합니다. 각자 자기 PC·계정으로 작업해 개인 로그를 남기고, 제출 시 **영문 파일명** `<팀영문명>_<이름로마자>_PROCESS_LOG.md`(예: `teamA_kim_PROCESS_LOG.md`)로 저장하세요. **한글 파일명은 압축 시 깨지므로 금지** — 한글 팀명·이름은 위 '작성자 정보'에 적습니다. 운영자가 팀별로 모아 채점합니다(전원 참여 = 팀별 개인 로그 수).

## 효과 측정 (Before → After, 결과 ⑥ 채점용 — 형식 자유)
> **지표는 자기 업무에 맞게 고름 — 강제 항목 없음.** (예시, 해당되는 것만) 소요 시간 · 반복 횟수 · 다루는 자료/파일 수 · 손 가는 단계 수 · 품질·일관성 · 오류/누락 · 커버리지 등. 정량이 어려우면 정성도 인정.

| 지표(자기 업무에 맞게) | Before(기존 수작업) | After(에이전트화) |
|------|------|------|
|  |  |  |
|  |  |  |

## 사용 기법 (권장·가점, 필수 아님)
- [x] (a) 서브에이전트 / 역할 분담 — 리서치 3종 병렬 + 빌드·검토·마무리, 총 6개 에이전트 워크플로우로 최신 방법 검증→코드 생성→교차검토
- [x] (b) 외부 도구·데이터 연동 (파일/API/MCP/사내데이터) — 구글 뉴스 RSS 피드, trafilatura 본문 추출, 웹 검색으로 2025~2026 최신 방식 검증
- [ ] (c) 재사용 산출물 (스킬 / 프롬프트셋 / CLAUDE.md / 서브에이전트 구성)

---

## 작업 로그 (단계마다 1개씩 누적 / 시간순)

### [#1] 키워드 기반 구글 뉴스 크롤러(본문→CSV) + Streamlit UI 만들기
- 작성자(팀원): srlee
- 목표: 사용자가 입력한 키워드로 인터넷 뉴스/기사를 모아 본문까지 추출하고 CSV로 저장하는 기능 구현
- 에이전트에게 시킨 것(실제 프롬프트 핵심 인용):
  > "인터넷 뉴스 또는 기사를 크롤링하는 기능을 만들려고 해. 우선 키워드는 사용자가 입력할꺼야. 어떻게 해야되는지 알려줘"
- 사용한 기법(있으면): (a) 서브에이전트 — 리서치/빌드/검토/마무리 4단계 워크플로우(에이전트 6개) / (b) 도구연동 — 구글 뉴스 RSS, trafilatura, 웹검색
- 결과: `src/news_crawler.py`(crawl(keyword,limit)→list[dict]), `src/app.py`(Streamlit 화면), `requirements.txt`, `src/README.md` 생성. 파이프라인: 구글 뉴스 RSS(hl=ko&gl=KR&ceid=KR:ko) → 링크 복원(googlenewsdecoder) → 본문 추출(trafilatura, 바이트 전달로 한글 EUC-KR/CP949/UTF-8 자동감지) → CSV(utf-8-sig, 엑셀에서 안 깨짐). 기사별 try/except·예의 sleep(1s)·timeout(15s) 적용. 두 .py 모두 컴파일 통과.
- 막힘 → 해결: ① 구글 뉴스 RSS의 기사 링크가 진짜 주소가 아니라 리다이렉트 링크(2024년 이후 단순 추적 불가) → googlenewsdecoder의 gnewsdecoder(dict 반환, status 확인 후 decoded_url)로 복원, 실패 시 구글 링크 유지+note. ② 검토 에이전트가 "RSS 요청에 timeout 없어 무한 대기 위험" 지적 → requests로 직접 받아 feedparser에 바이트 전달하도록 보완.

### [#2] 라이브 테스트 — "고수온" 실제 수집 검증
- 작성자(팀원): srlee
- 목표: 작성한 크롤러가 검색→링크복원→본문추출→CSV까지 실제로 끝까지 동작하는지 확인
- 에이전트에게 시킨 것(실제 프롬프트 핵심 인용):
  > "먼저 지금 코드로 라이브 테스트" (고수온 키워드로 실제 실행해 동작 확인 요청)
- 사용한 기법(있으면): (b) 도구연동 — 실제 구글 뉴스 RSS·언론사 페이지에 네트워크 요청
- 결과: venv에 feedparser/trafilatura(2.1.0)/googlenewsdecoder(0.1.7) 설치 후 `crawl("고수온", 3)` 실행. **3/3건 모두** 구글 리다이렉트 링크를 진짜 기사 URL로 복원(헤드라인제주·제주환경일보·미디어제주), 본문 823~1567자 추출, **실패 0건**, 한글 정상. 소요 10.8초(건당 약 3.6초). 결과를 `submit/evidence/sample_gosuon.csv`로 저장 — BOM(utf-8-sig) 확인, 7개 컬럼·4행(헤더 포함).
- 막힘 → 해결: 증빙 CSV를 한글 파일명으로 저장 → 압축 시 깨질 위험이라 영문 `sample_gosuon.csv`로 변경.

### [#3] KHOA SST(해수면온도) 자료 자동 다운로더 만들기
- 작성자(팀원): srlee
- 목표: nosc.go.kr OPeNDAP에서 2025년 7~8월 KHOA SST 일자별 자료를 자동으로 받기
- 에이전트에게 시킨 것(실제 프롬프트 핵심 인용):
  > "https://nosc.go.kr/opendap/CONJUGATE/KHOA_SST/contents.html 해당 위치에서 2025년 7월부터 8월까지 khoa sst자료를 받고 싶어"
- 사용한 기법(있으면): (b) 외부 데이터 연동 — OPeNDAP/Hyrax 서버 구조를 실측으로 파악 후 다운로더 구현
- 결과: 서버 구조 파악(연/월 폴더, 파일명 `KHOA_SST_L4_Z003_D01_WGS001K_U{YYYYMMDD}.nc`, NetCDF3 약 42MB/일, 변수 `sst`[°C], 격자 20~53N·117~150E 3301²). 서버가 HEAD는 403이지만 GET은 허용됨을 확인. `src/download_khoa_sst.py` 작성(날짜범위·저장폴더 인자, 1MB 스트리밍 저장, CDF매직+최소크기 검증, 이어받기, 재시도 3회, 실패목록 출력). 2일치(7/1~7/2) 실제 다운로드·검증 통과(각 41.6MB), 재실행 시 건너뜀(이어받기) 확인. 7/1~8/31 전체는 62일 ≈ 2.6GB.
- 막힘 → 해결: HEAD가 403이라 사전 용량확인 불가 → 다운로드 후 파일 앞 3바이트(`b"CDF"`)와 최소크기로 정상 여부를 검증하고 오류 응답(작은 HTML)은 자동 삭제·재시도하도록 처리.

### [#4] KHOA SST 2025년 7~8월 전체 실제 다운로드
- 작성자(팀원): srlee
- 목표: 만든 다운로더로 7/1~8/31 SST 자료를 실제로 내려받아 완전성 검증
- 에이전트에게 시킨 것(실제 프롬프트 핵심 인용):
  > "전체 파일 그대로 받기" (관심해역 subset 대신 62일 전체를 그대로 수신 선택)
- 사용한 기법(있으면): (b) 외부 데이터 연동 — OPeNDAP에서 대용량 자료 일괄 수신
- 결과: `data/khoa_sst/`에 62개 파일 전부 수신(받음 62/건너뜀 0/실패 0). 총 **2.52GB**. 전 파일 `CDF` 매직+크기 검증 통과, `.part` 잔여 0, 기대 62일 중 누락 0. 수신 목록을 `submit/evidence/khoa_sst_files.txt`로 정리. 백그라운드 실행 로그는 `data/khoa_sst_download.log`. (대용량이라 `.gitignore`에 `data/`·`*.nc` 추가 — 제출은 submit/만)
- 막힘 → 해결: 없음(2일치 사전검증 덕분에 본 다운로드는 무사고 완료).

### [#5] dev/srlee 작업 통합 후 main에 반영(충돌 해결·병합 push)
- 작성자(팀원): srlee
- 목표: 이 브랜치 작업물을 충돌 확인 후 main에 올리기
- 에이전트에게 시킨 것(실제 프롬프트 핵심 인용):
  > "이 브랜치에서 작업한 내용을 충돌있는지 확인하고, main에 push해줘"
- 사용한 기법(있으면): (b) 도구연동 — git 충돌 진단·병합
- 결과: 원격 main이 팀원 커밋(`b1c29bb` Streamlit 뼈대+requirements)으로 전진해 add/add 충돌(`requirements.txt`·`.gitignore`) 발생을 확인. 두 파일을 **합집합으로 병합**(팀원 8개 패키지 전부 보존). 코드만 선별 커밋(`76baa67`), 데이터(2.5GB)·`.DS_Store`·`.claude`·`submit/`은 제외(`.gitignore` 보강). dev/srlee를 원격 생성·push 후 `dev/srlee→main` fast-forward push(`b1c29bb..2a66ff1`). 작업 트리의 미커밋 submit 로그·data는 보존.
- 막힘 → 해결: 제출물 `submit/`이 `.gitignore`에 걸려 git 제외 상태 → 사용자 확인 후 '`submit/`은 git 제외 유지' 방침으로 코드·requirements만 반영.

### [#6] KHOA LSS(저염분수/SSS) 2025년 7~8월 다운로더 + 전체 수신
- 작성자(팀원): srlee
- 목표: nosc.go.kr OPeNDAP에서 2025년 7~8월 LSS(저염분수) 자료를 받기
- 에이전트에게 시킨 것(실제 프롬프트 핵심 인용):
  > "https://nosc.go.kr/opendap/CONJUGATE/LSS/daily/contents.html 해당 사이트에서 lss자료를 2025년7월1일부터 8월31일까지 nc파일을 다운로드 해줘"
- 사용한 기법(있으면): (b) 외부 데이터 연동 / (c) 재사용 산출물 — SST 다운로더 패턴 재사용
- 결과: LSS 구조 실측(경로에 일 폴더가 한 단계 더, 파일 `KHOA_LSS_L3_Z002_D01_WGS250M_K{YYYYMMDD}.nc`, **NetCDF4/HDF5** ~34MB, 변수 `SSS`[psu], 격자 28~36N·119~129E 2667×3333 ~250m). SST와 형식이 달라 검증을 `CDF`/`\x89HDF` 둘 다 허용하도록 `src/download_lss.py` 작성. 2일치 검증 후 7/1~8/31 **62개 전부 수신(받음 62/실패 0/누락 0), 총 2.06GB**. 목록 `submit/evidence/khoa_lss_files.txt`, 로그 `data/lss_download.log`.
- 막힘 → 해결: ① 디렉터리 구조가 SST(연/월)와 달리 연/월/일 → URL 빌더에 일 폴더 추가. ② LSS는 HDF5라 SST의 `CDF` 검증으론 정상 파일이 실패 처리됨 → 매직 검증을 NetCDF3/NetCDF4 둘 다 허용.

### [#7] 원격 main 통합(divergent pull 해결) + 멀티페이지 Streamlit 실행 환경 구성
- 작성자(팀원): srlee
- 목표: 팀원이 올린 원격 main(고수온 연안재해 모니터링 웹 시스템)을 가져와 streamlit 실행 가능하게
- 에이전트에게 시킨 것(실제 프롬프트 핵심 인용):
  > "main 원격내용 가져와줘. streamlit 실행할 수 있게" / "이거 살려" (git pull divergent 실패 출력 첨부)
- 사용한 기법(있으면): (b) 도구연동 — git 머지·의존성 설치·앱 부팅 검증
- 결과: origin/main이 `8c5d8dc`(e45373c 웹시스템 초안 + dev/jnkim 통합)로 전진, dev/srlee와 divergent라 `git pull`이 reconcile 방식 미지정으로 실패. dev/srlee 변경이 `download_lss.py` 추가뿐이라 `git merge origin/main`으로 **충돌 없이 통합**(머지 `5efdf22`). 새 의존성 openai 2.44.0·python-docx 1.2.0 설치. `streamlit run app.py`(멀티페이지: pages/1~4·utils/·agents/) 헤드리스 부팅 성공 확인.
- 막힘 → 해결: ① `git pull`이 "divergent branches"로 중단 → merge 전략으로 완료(우리 쪽 변경이 겹치지 않아 무충돌). ② git 작업 중 작업트리의 submit 로그(PROCESS_LOG·BEFORE_AFTER)가 빈 템플릿으로 되돌아감 → 살아있던 영문 사본에서 PROCESS_LOG 복구, BEFORE_AFTER 재작성.

### [#8] 고수온(SST≥28℃) ∩ 저염분(LSS=1) 공통지역 추출 기능
- 작성자(팀원): srlee
- 목표: SST(1km)와 LSS(250m)를 같은 1km 격자로 맞춰, 고수온이면서 저염분인 공통지역을 추출
- 에이전트에게 시킨 것(실제 프롬프트 핵심 인용):
  > "해수면온도nc파일의 28도 이상의 지역과 … 저염분 nc 파일의 속성정보가 1인지역(저염분)이 공통적으로 발생되는 고수온 저염분 지역을 추출 … 저염분수 nc 파일을 공간해상도 1km로 재가공하여 … 28도 이상, 저염분 지역(속성정보 1인지역, 28 psu 미만지역) 추출"
- 사용한 기법(있으면): (b) 외부데이터 연동 / (c) 재사용 산출물 — sst_processing·sst_gridutil 재사용
- 결과: LSS의 SSS가 연속 염분값이 아니라 **범주 플래그**(1=저염분/2=정상/NaN=육지)임을 실측 확인 → 저염분=SSS==1로 정의. LSS 250m 저염분 플래그를 SST 1km 격자로 '면적집계'(각 1km칸의 저염분 250m칸 비율 lowsal_fraction, 기본 다수결 ≥0.5)해 재가공. SST≥28 ∩ 저염분 교집합을 `src/hot_lowsal.py`로 구현(NC: sst·lowsal_fraction·hot_mask·lowsal_mask·hotlowsal_mask·sst_common + 공통셀 CSV + 해안선 지도 PNG + 일자별 요약 CSV). 1일 검증: both⊆hot·both⊆lowsal 성립, 공통셀 SST 전부 ≥28℃. 7/1 결과 고수온 311,271 ∩ 저염분 75,407 → **공통 19,793칸**(양쯔강 하구·서남해 연안). 7/1~8/31 전체 일괄 처리.
- 막힘 → 해결: ① SSS를 '28 psu 미만 연속값'으로 보면 비교 불가(값이 1·2뿐) → 플래그 1=저염분으로 정의. ② SST(오름차순)·LSS(내림차순) 격자 방향·해상도(1km vs 250m) 불일치 → bin 경계 기반 면적집계로 1km 재가공.

### [#9] (피드백 반영) LSS 재가공을 '평균→다수결(1/2)'로 수정 + PNG 기본 생성
- 작성자(팀원): srlee
- 목표: 저염분 재가공 시 값을 평균하지 말고 속성값 1/2로 다수결 가공, 저염분=값1 적용. NC 외 PNG도 생성.
- 에이전트에게 시킨 것(실제 프롬프트 핵심 인용):
  > "저염분의 값은 평균이 되지 않고 1 또는 2의 값으로 가공이 되어야 하며, 저염분 값이 1인걸로 적용되어야 해" / "추가적으로 nc파일외 png이미지도 만들어줘"
- 사용한 기법(있으면): (c) 재사용 산출물 보완
- 결과: `regrid_lowsal`(비율/평균) → `regrid_lss_class`(다수결)로 교체 — 각 1km칸을 250m 속성의 최빈값(n1≥n2면 1, 아니면 2)으로 재가공. NC 변수 `lowsal_fraction` → `lss_class`(1/2/NaN)로 변경, 저염분=`lss_class==1`. 지도 PNG를 **기본 생성**(끄려면 `--no-image`). 1일 검증: lss_class 고유값 {1,2}, 저염분 75,407, 공통 19,793(기존과 동일 → 다수결 ⇔ 비율0.5 등가 확인). 7/1~8/31 전체 재생성.
- 막힘 → 해결: 없음(n1≥n2 ⇔ 비율≥0.5라 공통셀 집합은 동일, 표현만 '평균'에서 '카테고리 1/2'로 정정).

### [#10] dev/srlee 결과데이터 커밋(`데이터추가`)을 공유 main에 병합·push
- 작성자(팀원): srlee
- 목표: dev/srlee에 새로 커밋한 결과 데이터(`5c4b856 데이터추가`)를 공유 main에 반영
- 에이전트에게 시킨 것(실제 프롬프트 핵심 인용):
  > "지금 원격 브랜치엔 올렸는데 메인에 merge 해줘"
  > "지금 내 브랜치 커밋한거 merge 해줘 왜 바로 안될까"
- 사용한 기법(있으면): (b) 도구연동 — git 충돌 진단(merge-tree)·stash·병합·push
- 결과: 원인 진단 — dev/srlee의 이전 작업은 PR #1(`1bb2ea6`)로 이미 main 반영됨, 미반영은 새 커밋 `5c4b856 데이터추가`(191파일·약 257만 줄; `data/results/hotlowsal/csv` 112MB·62개 CSV 등)뿐. main이 공유 브랜치라 작업 중 `8c5d8dc→e9f76aa`로 19커밋+ 전진 → 로컬이 최신 main을 포함하지 않아 직접 push가 거부됨("바로 안되던" 이유). `git merge-tree`로 최신 main과 충돌 없음(exit 0) 사전 확인. **`data/results/`가 원래 `.gitignore` 제외(재생성 가능한 생성 산출물) 대상**임을 사용자에게 고지하고 확인 → 사용자가 "데이터까지 그대로 머지" 선택. 미커밋 변경(`.gitignore`·`submit/*.md`)은 `git stash`로 보호 → `main` ff-only 최신화(`e9f76aa`) → `git merge origin/dev/srlee`(머지 `ca15c76`, 무충돌) → `push origin main`(`e9f76aa..ca15c76`) → dev/srlee 복귀 후 `stash pop`으로 작업트리 복원. `origin/main..origin/dev/srlee` 빈 것으로 dev/srlee 작업 100% 반영 확인.
- 막힘 → 해결: ① 공유 main이 계속 전진해 직접 push가 reject(fetch first) → "최신 main을 먼저 내 쪽에 병합 → 머지/푸시" 순서로 해결(GitHub가 남의 커밋 덮어쓰기를 막는 정상 동작). ② 데이터(112MB+)를 git에 올릴지가 `.gitignore` 정책과 충돌 → 사용자에게 규모·되돌리기 어려움을 알리고 결정을 받아 진행.

### [#11] (추가) 지정 영역(남해 동부)만 잘라 공통지역 이미지 생성 → img_2
- 작성자(팀원): srlee
- 목표: 고수온∩저염분 공통지역 지도를 위도 33.7~35.1, 경도 125.2~130.2 영역만 잘라 img_2 폴더로 생산
- 에이전트에게 시킨 것(실제 프롬프트 핵심 인용):
  > "고수온, 저염분지역을 동시에 만족하는 이미지를 위도 33.7~35.1, 경도 125.2~130.2 영역만 추출하여 생산해줘 폴더는 img_2로 생성하여 저장해줘"
- 사용한 기법(있으면): (c) 재사용 산출물 — hot_lowsal/basemap 재사용, 영역 옵션 추가
- 결과: `hot_lowsal.py`에 `region_image_day`/`run_region_images` + CLI(`--region-images`, `--region S N W E`, `--region-dir`) 추가. SST를 요청 영역으로 잘라 그 격자에서 저염분(다수결1)·고수온을 재판정 → 지도 extent가 정확히 요청영역(저염분 자료 없는 129°E 동쪽은 빈칸). 1일(8/5) 검증: 프레임 125.2~130.2E·33.7~35.1N 정확, 공통 2,859칸. 7/1~8/31 전체를 `data/results/hotlowsal/img_2/HOTLOWSAL_{YYYYMMDD}_region.png`로 생성.
- 막힘 → 해결: 요청 경도(130.2E)가 LSS 범위(≤129E)를 넘음 → SST가 격자/프레임을 정의하게 해 영역은 그대로 표시하고 자료 없는 칸은 공통 불가로 처리.

### [#12] (피드백 반영) img_2 공통지역 이미지를 수온색상→단일 빨간색으로 변경
- 작성자(팀원): srlee
- 목표: 영역 한정 공통지역 이미지에서 해수면온도 색상 범례를 쓰지 않고 단일 빨간색으로 표시(생산코드 반영)
- 에이전트에게 시킨 것(실제 프롬프트 핵심 인용):
  > "img_2 이미지 생성시 해수면온도 색상 범례를 따르지않고 단일 빨간색으로 바꿔줘 생산코드에도 반영해줘"
- 사용한 기법(있으면): (c) 재사용 산출물 보완
- 결과: 공용 `basemap.plot_grid_map`에 (하위호환) `cmap` 객체 허용 + `add_colorbar` 옵션 추가. `hot_lowsal.region_image_day`를 수온값(turbo+컬러바) 대신 **공통=1 마스크를 `ListedColormap(["red"])` 단색·컬러바 없음**으로 그리도록 변경. 1일(8/5) 검증: 공통지역만 빨강, 컬러바 제거, 프레임 동일. 7/1~8/31 전체 img_2 재생성.
- 막힘 → 해결: 단색 표시를 위해 공용 함수가 Colormap 객체와 범례 끄기를 지원하도록 확장(기존 호출부는 기본값으로 영향 없음).

### [#13] data/sst/hot 폴더명을 sst_over28로 변경(+코드 참조 일괄 갱신)
- 작성자(팀원): srlee
- 목표: 고수온(SST≥28) 결과 폴더명을 의미가 분명한 sst_over28로 변경
- 에이전트에게 시킨 것(실제 프롬프트 핵심 인용):
  > "/Users/elice46/team-gvidia/data/sst/hot 폴더명을 sst_over28로 변경해줘"
- 사용한 기법(있으면): (b) 도구연동 — 폴더 rename + 코드 리팩터
- 결과: `data/sst/hot`(HOT 파일 62개) → `data/sst/sst_over28`로 변경(내용 보존). 폴더만 바꾸면 파이프라인이 깨지므로 기본 경로를 참조하던 5개 파일(`sst_processing.py`·`sst_gridutil.py`·`sst_persistence.py`·`sst_frequency.py`·`run_pipeline.py`)의 `data/sst/hot` 참조 11곳을 `data/sst/sst_over28`로 일괄 갱신. 잔여 0건, 전 파일 컴파일 OK. `list_hot_files()` 기본 경로에서 HOT 62개 정상 인식 확인.
- 막힘 → 해결: 처음 `src/`에서 검증해 상대경로(루트 기준)가 안 맞아 실패 → 루트에서 재검증해 정상.

### [#14] data/results/hotlowsal 폴더명을 HS28NLS26으로 변경(+코드·git rename)
- 작성자(팀원): srlee
- 목표: 고수온∩저염분 공통지역 결과 폴더명을 HS28NLS26으로 변경
- 에이전트에게 시킨 것(실제 프롬프트 핵심 인용):
  > "/Users/elice46/team-gvidia/data/results/hotlowsal의 폴더명을 HS28NLS26으로 바꿔줘"
- 사용한 기법(있으면): (b) 도구연동 — git mv 리네임 + 코드 참조 갱신
- 결과: `data/results/hotlowsal` → `data/results/HS28NLS26`로 변경(nc·img·img_2·csv 각 62 보존). 이 폴더는 git 추적 파일 125개라(병행 세션이 커밋) `git mv`로 옮겨 **125건 모두 rename(R)으로 인식**(무손실). 코드 참조 1곳(`hot_lowsal.py`의 `--out` 기본값) 갱신, 잔여 0, 컴파일 OK.
- 막힘 → 해결: 없음(추적 파일이라 plain mv 대신 git mv로 깔끔히 리네임).

### [#15] data/input 폴더 생성 + khoa_sst·lss 입력자료를 input으로 이동(+코드 경로 갱신)
- 작성자(팀원): srlee
- 목표: 입력 원자료(SST·LSS)를 data/input/ 아래로 정리
- 에이전트에게 시킨 것(실제 프롬프트 핵심 인용):
  > "data 내 input 폴더를 생성하고 data/khoa_sst와 data/lss 폴도를 input 폴더에 옮겨줘"
- 사용한 기법(있으면): (b) 도구연동 — 폴더 이동 + 코드 경로 리팩터
- 결과: `data/input` 생성, `data/khoa_sst`→`data/input/khoa_sst`, `data/lss`→`data/input/lss` 이동(각 nc 62 보존; 둘 다 git 미추적이라 git 영향 없음). 입력 경로를 참조하던 5개 파일(`download_khoa_sst`·`download_lss`·`hot_lowsal`·`sst_timeseries`·`run_pipeline`)의 기본 경로를 `data/input/...`로 일괄 갱신(옛 참조 0건, 전 파일 컴파일 OK). `pair_files` 새 기본경로에서 SST·LSS **62쌍 정상 매칭** 확인.
- 막힘 → 해결: 없음.

### [#16] data/sst → data/results/sst_analysis 로 이동·이름변경(+코드 경로 갱신, 팀 페이지 포함)
- 작성자(팀원): srlee
- 목표: SST 분석 산출물 폴더를 data/sst → data/results/sst_analysis 로 정리(결과 폴더 하위로)
- 에이전트에게 시킨 것(실제 프롬프트 핵심 인용):
  > "data/sst 폴더명을 sst_analysis로 변경하고, data/results 폴더내로 이동시켜줘"
- 사용한 기법(있으면): (b) 도구연동 — 폴더 이동 + 코드 경로 리팩터
- 결과: `data/sst`(하위 sst_over28·persistence·processed·raw·timeseries) → `data/results/sst_analysis`로 이동. `data/sst/` 경로를 참조하던 **7개 파일**(sst_processing·sst_gridutil·sst_frequency·sst_persistence·sst_timeseries·run_pipeline + 팀 멀티페이지 `pages/5_SST_Timeseries.py`)의 경로를 `data/results/sst_analysis/...`로 일괄 갱신(옛 참조 0건, 전 파일 컴파일 OK). `list_hot_files` 새 경로에서 HOT 62개 정상 인식.
- 막힘 → 해결: 이 폴더엔 병행 세션이 커밋한 추적 파일 66개(주로 HOT 지도 PNG)가 있어 이동 후 git이 옛 경로 66건을 삭제로 표시(새 경로는 미추적). 코드·기능엔 영향 없음 — 리오그를 팀과 함께 커밋할 때 rename으로 정리되도록 안내.

### [#17] (보류) 원격 main 46커밋 전진 확인 → 로컬 main만 동기화, 재정리 적용 보류
- 작성자(팀원): srlee
- 목표: 변경사항을 main에 적용하려 했으나, 안전 확인 후 동기화만
- 에이전트에게 시킨 것(실제 프롬프트 핵심 인용):
  > "git에 변경사항을 적용하고 싶어. main에 바로 적용시켜줘"
- 사용한 기법(있으면): (b) 도구연동 — git 상태 진단
- 결과: origin/main이 `ca15c76→c3858e6`로 **46커밋 전진**(팀 활발), main은 아직 옛 폴더구조(`data/sst`·`data/results/hotlowsal`) 사용 확인. 내 변경 상당부분이 폴더 재정리라 그대로 push 시 옛 경로 참조 팀원 코드가 깨질 위험 + `.gitignore`·`pages/3` 겹침을 사용자에게 고지. 사용자 결정 "**최신 main 동기화만, 적용 보류**" → `git branch -f main origin/main`로 로컬 main을 c3858e6에 맞춤(체크아웃 안 함 → 작업트리·미커밋 변경 209건 보존). push·커밋 없음.
- 막힘 → 해결: 직접 push 불가(46커밋 뒤처짐)+팀 구조 충돌 위험 → 적용 대신 동기화로 안전 보류.

### [#18] ...
(필요한 만큼 계속 추가)

---

## 마무리 요약 (1~2줄)
- 가장 효과적이었던 에이전트 활용법:
- 다른 팀이 그대로 따라 하려면 필요한 것:
