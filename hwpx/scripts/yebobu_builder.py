#!/usr/bin/env python3
"""yebobu_builder.py — 예보부 HWPX 보고서 빌더 v4

레퍼런스 (Ref A: OCE_AGRIF) 정밀 분석 기반:
  • 모든 paraPr keepWithNext=0, widowOrphan=0 → 자연 흐름
  • □ heading 뒤: paraPr 18 + charPr 16 (5pt 작은 갭)
  • 섹션 사이: paraPr 19 + charPr 22 (9pt 중간 갭)
  • 표/그림 뒤: paraPr 19 + charPr 45 (14pt 풀라인 갭)
  • 표 wrapper: paraPr 19 + charPr 45 (item-style)
  • 캡션: <hp:caption> 표 내부 embed, "표 N." BOLD + " 제목" regular
  • 사용자가 명시적 page_break() 호출 시에만 페이지 분리
"""

from __future__ import annotations
import re, subprocess, sys, tempfile, zipfile
from copy import deepcopy
from pathlib import Path
from lxml import etree

NS = {
    'hp': 'http://www.hancom.co.kr/hwpml/2011/paragraph',
    'hs': 'http://www.hancom.co.kr/hwpml/2011/section',
    'hh': 'http://www.hancom.co.kr/hwpml/2011/head',
    'hc': 'http://www.hancom.co.kr/hwpml/2011/core',
    'opf': 'http://www.idpf.org/2007/opf/',
}
NS_DECL = ' '.join(f'xmlns:{p}="{u}"' for p, u in NS.items() if p != 'opf')
OPF = '{%s}' % NS['opf']

# ============================================================
# 예보부(지오시스템리서치 예보사업부) 표준 스타일 매핑
# 실측 기준: 260211_AI 기반 해양생태계 자료 갭필링 방안.hwpx  (golden reference)
# 본문폭 48190 HWPUNIT, 좌우여백 20mm, 본문 글꼴 휴먼명조, 제목 HY헤드라인M
# ============================================================
# paraPr IDs (문단 스타일) — 모두 레퍼런스 header.xml에 정의됨
PARA_BODY      = '0'    # JUSTIFY 160%, 들여쓰기 없음 (페이지브레이크 spacer 등)
PARA_CENTER    = '1'    # CENTER 160% (셀 내부 / 그림·캡션)
PARA_BOX       = '18'   # □ 섹션 헤딩 (JUSTIFY 160%, 행거 indent -3010)
PARA_CIRCLE    = '19'   # ㅇ 본문 항목 (JUSTIFY 160%, 행거 indent -3043) / 표 wrapper
PARA_DASH      = '23'   # - 세부 항목 (JUSTIFY 158%, intent -1600 left 2000)
PARA_NOTE      = '26'   # ※ 주석/출처 (JUSTIFY 160%, intent -2352)
PARA_TABLE_LEFT= '34'   # 표 셀 좌측정렬 (LEFT 160%) — 국외사례 등 서술형 셀
PARA_CHAMGO_BADGE = '30'  # 참고N 네이비 배지 셀 (CENTER 160%)
PARA_CHAMGO_TITLE = '29'  # 참고N 제목 셀 (JUSTIFY 170%)

# ============================================================
# charPr IDs (글자 스타일) — 예보부 표준 (실측)
# ============================================================
# • □ 헤딩          → charPr 5  (15pt HY헤드라인M)
# • 배너 제목       → charPr 38 (17pt HY헤드라인M spacing=-5)
# • ㅇ 본문 항목    → charPr 45 (14pt 휴먼명조)              ★ 본문은 14pt (37=12pt는 참고/부록용)
# • ㅇ 라벨 강조    → charPr 55 (14pt 휴먼명조 BOLD)         ★ "(① 분석 DB 구축)" 같은 괄호 라벨
# • 인라인 파랑     → charPr 51 (14pt 휴먼명조 #0000FF)      ★ (참고1) 같은 상호참조
# • 표 헤더 셀      → charPr 29 (11pt 휴먼명조 BOLD spacing=-4)
# • 표 데이터 셀    → charPr 30 (11pt 휴먼명조 spacing=-4)
# • 표 강조(빨강)   → charPr 31 (11pt 휴먼명조 #FF0000 spacing=-4)
# • ※ 주석         → charPr 35 (12pt 한양중고딕 spacing=-3)
# • 각주 *  **      → charPr 18 (13pt 한양중고딕)
# • 프로세스 흐름   → charPr 50 (11pt 휴먼명조 BOLD)
# • 그림박스 캡션   → charPr 39 (11pt 휴먼명조 #0000FF BOLD spacing=-4) "<...>"
# • 참고N 흰글씨    → charPr 42 (16pt HY헤드라인M #FFFFFF)
# • 참고N 제목      → charPr 41 (16pt HY헤드라인M spacing=-8)
CHAR_BOX           = '5'    # □ 헤딩 15pt HY헤드라인M
CHAR_TITLE         = '38'   # 배너 제목 17pt HY헤드라인M
CHAR_BOX_SPACER    = '16'   # 5pt HY헤드라인M (□ 헤딩 직후 빈 줄)
CHAR_CIRCLE        = '45'   # 14pt 휴먼명조 (ㅇ 본문 항목, 표 wrapper)
CHAR_ITEM_BOLD     = '55'   # 14pt 휴먼명조 BOLD (괄호 라벨)
CHAR_ITEM_BLUE     = '51'   # 14pt 휴먼명조 파랑 (인라인 상호참조)
CHAR_ITEM_SMALL    = '37'   # 12pt 휴먼명조 (참고/부록 항목)
CHAR_CIRCLE_SPACER = '21'   # 5pt 휴먼명조 (항목 사이 빈 줄)
CHAR_BODY          = '0'
CHAR_NOTE          = '35'   # 12pt 한양중고딕 (※ 주석)
CHAR_FOOT          = '18'   # 13pt 한양중고딕 (각주 *, **)
CHAR_CELL_LABEL    = '29'   # 11pt BOLD (표 헤더/좌측 라벨 + 캡션 prefix)
CHAR_CELL_DATA     = '30'   # 11pt regular (표 데이터 + 캡션 제목)
CHAR_CELL_RED      = '31'   # 11pt 빨강 (표 강조 수치)
CHAR_FLOW          = '50'   # 11pt BOLD (프로세스 흐름 박스)
CHAR_FIGCAP_BLUE   = '39'   # 11pt 파랑 BOLD (그림박스 "<...>" 캡션)
CHAR_BADGE_WHITE   = '42'   # 참고N 흰글씨 16pt HY헤드라인M
CHAR_BADGE_GAP     = '43'   # 16pt HY헤드라인M (간격 셀)
CHAR_BADGE_TITLE   = '41'   # 참고N 제목 16pt HY헤드라인M

BF_DATA = {
    'header': {'l': '9',  'm': '11', 'r': '13'},
    'first':  {'l': '17', 'm': '10', 'r': '12'},
    'mid':    {'l': '18', 'm': '3',  'r': '8'},
    'last':   {'l': '14', 'm': '15', 'r': '16'},
}
BF_CHAMGO = {'badge': '19', 'gap': '20', 'title': '3'}
# 프로세스 흐름 박스: 번호셀(연노랑 상단선) / 화살표셀(연노랑) / 라벨셀(연노랑 하단선)
BF_FLOW = {'num': '22', 'arrow': '21', 'label': '23'}
# 그림 박스: 외곽 0.12mm 4면(bf3), 내부 셀 무테(bf1)
BF_FIGBOX = {'outer': '3', 'cell': '1'}
# 원문자 ①②③… (U+2460~)
_CIRCLED = [chr(0x2460 + i) for i in range(20)]

_CAPTION_PREFIX_PAT = re.compile(
    r'^\s*(표\s*\d+\.|그림\s*\d+\.|Fig(?:ure)?\.?\s*\d+\.|Tab(?:le)?\.?\s*\d+\.)\s*(.*)$'
)

def _split_caption_prefix(text: str) -> tuple[str | None, str]:
    m = _CAPTION_PREFIX_PAT.match(text.strip())
    if m:
        return m.group(1), ' ' + m.group(2)
    return None, text.strip()


def patch_header(header_xml_path: Path) -> list[str]:
    """header.xml 비파괴 보정 (NON-DESTRUCTIVE).

    예보부 골든 레퍼런스(standard_template.hwpx)는 이미 모든 charPr/paraPr/
    borderFill이 정확히 정의돼 있으므로 이 함수는 사실상 no-op이다.
    **외부(타 부서) 레퍼런스**를 넘겨받았을 때만 누락 스타일을 보강한다:

      • 빌더가 사용하는 핵심 charPr(45/55/29/30/35/18/50/39/42/43/41 등)와
        paraPr(18/19/26/29/30/34)가 **없을 때만** 안전 템플릿을 복사해 추가
      • 이미 존재하면 절대 건드리지 않음 → 골든 레퍼런스의 실측 서식을 100% 보존

    [중요] 과거 버전은 paraPr 19/23 의 intent/left와 charPr 29/30/37 의 height를
    강제로 덮어써 레퍼런스 고유 들여쓰기(예: paraPr19 intent=-3043)를 망가뜨렸다.
    이제는 기존 값이 있으면 그대로 둔다.
    """
    tree = etree.parse(str(header_xml_path))
    root = tree.getroot()
    ns_hh = NS['hh']
    charprs = root.findall(f'.//{{{ns_hh}}}charPr')
    cp_by_id = {c.get('id'): c for c in charprs}
    cp_parent = charprs[0].getparent()
    paraprs = root.findall(f'.//{{{ns_hh}}}paraPr')
    pp_by_id = {p.get('id'): p for p in paraprs}
    pp_parent = paraprs[0].getparent()
    log = []

    # ── 줄바꿈 단위 정규화 (의도적 전역 보정): 한글=어절, 영어=단어 단위로 끊김 방지
    #    OWPML: breakNonLatinWord="KEEP_WORD"=한글 어절 단위, breakLatinWord="KEEP_WORD"=영어 단어 단위.
    #    (BREAK_WORD = 글자 단위 → 단어/어절 중간에서 줄이 잘림 → 사용 안 함)
    _bs = 0
    for pp in paraprs:
        bs = pp.find(f'{{{ns_hh}}}breakSetting')
        if bs is None:
            continue
        if bs.get('breakNonLatinWord') != 'KEEP_WORD':
            bs.set('breakNonLatinWord', 'KEEP_WORD'); _bs += 1
        if bs.get('breakLatinWord') != 'KEEP_WORD':
            bs.set('breakLatinWord', 'KEEP_WORD'); _bs += 1
    if _bs:
        log.append(f'breakSetting → KEEP_WORD (어절/단어 단위 줄바꿈), {_bs} attrs fixed')

    def _set_bold(cp_elem, want_bold):
        bold = cp_elem.find(f'{{{ns_hh}}}bold')
        if want_bold and bold is None:
            etree.SubElement(cp_elem, f'{{{ns_hh}}}bold', value='1')
        elif not want_bold and bold is not None:
            cp_elem.remove(bold)

    def _find_char_template(target_pt, want_bold):
        for c in charprs:
            ht = c.get('height')
            if ht and int(ht) / 100 == target_pt and \
               (c.find(f'{{{ns_hh}}}bold') is not None) == want_bold:
                return c
        for c in charprs:
            ht = c.get('height')
            if ht and int(ht) / 100 == target_pt:
                return c
        return charprs[0]

    # (id, pt, bold) — 빌더가 참조하는 charPr. **없을 때만** 추가.
    needed_chars = [
        ('5', 15, False), ('38', 17, False), ('16', 5, False),
        ('45', 14, False), ('55', 14, True), ('51', 14, False),
        ('37', 12, False), ('21', 5, False), ('35', 12, False),
        ('18', 13, False), ('29', 11, True), ('30', 11, False),
        ('31', 11, False), ('50', 11, True), ('39', 11, True),
        ('42', 16, False), ('43', 16, False), ('41', 16, False),
    ]
    for cid, pt, want_bold in needed_chars:
        if cid in cp_by_id:
            continue  # 존재 → 보존 (비파괴)
        new = deepcopy(_find_char_template(pt, want_bold))
        new.set('id', cid); new.set('height', str(pt * 100))
        _set_bold(new, want_bold)
        cp_parent.append(new)
        log.append(f'Added missing charPr {cid} ({pt}pt{" BOLD" if want_bold else ""})')
    if cp_parent.get('itemCnt'):
        cp_parent.set('itemCnt', str(len(cp_parent.findall(f'{{{ns_hh}}}charPr'))))

    # 빌더가 참조하는 paraPr — **없을 때만** 안전 템플릿(paraPr 0/1) 복사 후 추가.
    needed_paras = ['18', '19', '23', '26', '29', '30', '34']
    pp0 = pp_by_id.get('0')
    for pid in needed_paras:
        if pid in pp_by_id or pp0 is None:
            continue  # 존재 → 보존
        new = deepcopy(pp0); new.set('id', pid)
        pp_parent.append(new)
        log.append(f'Added missing paraPr {pid} (cloned from paraPr 0)')
    if pp_parent.get('itemCnt'):
        pp_parent.set('itemCnt', str(len(pp_parent.findall(f'{{{ns_hh}}}paraPr'))))

    if log:
        tree.write(str(header_xml_path), xml_declaration=True,
                   encoding='UTF-8', standalone=True)
    return log


def extract_reference_assets(reference_hwpx: Path, work_dir: Path) -> dict:
    work_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(reference_hwpx) as z:
        names = z.namelist()
        header_path = work_dir / 'header.xml'
        with z.open('Contents/header.xml') as src, open(header_path, 'wb') as dst:
            dst.write(src.read())
        section_path = work_dir / 'ref_section.xml'
        with z.open('Contents/section0.xml') as src, open(section_path, 'wb') as dst:
            dst.write(src.read())
        bindata = {Path(n).stem: z.read(n)
                   for n in names if n.startswith('BinData/')}
    return {'header_path': header_path, 'section_path': section_path,
            'bindata': bindata}


def extract_first_paragraph(section_xml_path: Path) -> str:
    tree = etree.parse(str(section_xml_path))
    return etree.tostring(tree.getroot()[0], encoding='unicode')


def detect_reference_title(section_xml_path: Path) -> str | None:
    tree = etree.parse(str(section_xml_path))
    root = tree.getroot()
    first_p = root[0]
    for tbl in first_p.iter('{%s}tbl' % NS['hp']):
        for tc in tbl.findall('.//hp:tc', NS):
            addr = tc.find('hp:cellAddr', NS)
            if addr is not None and addr.get('rowAddr') == '1':
                for t in tc.iter('{%s}t' % NS['hp']):
                    if t.text and t.text.strip():
                        return t.text.strip()
        break
    return None


class YeoboBuilder:
    """Build a 예보부-style HWPX report (v4 — natural-flow, no keepWithNext)."""

    def __init__(self, reference_hwpx=None, skill_dir=None, work_dir=None):
        self.skill_dir = Path(skill_dir).resolve() if skill_dir else \
            Path(__file__).resolve().parent
        if reference_hwpx is None:
            bundled = (self.skill_dir.parent / 'templates' / 'yebobu'
                       / 'standard_template.hwpx')
            if not bundled.is_file():
                raise FileNotFoundError(f'Bundled template not found: {bundled}')
            reference_hwpx = bundled
        self.reference_hwpx = Path(reference_hwpx).resolve()
        if not self.reference_hwpx.is_file():
            raise FileNotFoundError(self.reference_hwpx)
        if work_dir:
            self.work_dir = Path(work_dir).resolve()
            self.work_dir.mkdir(parents=True, exist_ok=True)
        else:
            self._tmp = tempfile.TemporaryDirectory()
            self.work_dir = Path(self._tmp.name)

        assets = extract_reference_assets(self.reference_hwpx, self.work_dir)
        self._header_path = assets['header_path']
        self._reference_bindata = assets['bindata']
        patch_header(self._header_path)

        self._first_para = extract_first_paragraph(assets['section_path'])
        self._ref_title = detect_reference_title(assets['section_path'])

        self._body: list[str] = []
        self._pid = 3_000_000_000
        self._tbl_id = 4_000_000_000
        self._image_counter = 100
        self._images: dict[str, tuple] = {}
        if 'image1' in self._reference_bindata:
            self._images['image1'] = ('ref', 'image1', 'image/jpg')
        if 'image2' in self._reference_bindata:
            self._images['image2'] = ('ref', 'image2', 'image/jpg')
        self._title_set = False
        self._last_was_blank = False
        self._last_was_table_or_fig = False

    def _pid_new(self) -> str:
        self._pid += 1; return str(self._pid)

    def _tbl_new(self) -> str:
        self._tbl_id += 1; return str(self._tbl_id)

    @staticmethod
    def _esc(text: str) -> str:
        return text.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')

    def _p_text(self, text, paraPr, charPr, pageBreak='0'):
        return (f'<hp:p id="{self._pid_new()}" paraPrIDRef="{paraPr}" '
                f'styleIDRef="0" pageBreak="{pageBreak}" columnBreak="0" '
                f'merged="0"><hp:run charPrIDRef="{charPr}">'
                f'<hp:t>{self._esc(text)}</hp:t></hp:run></hp:p>')

    def _p_blank(self, paraPr, charPr, pageBreak='0'):
        return (f'<hp:p id="{self._pid_new()}" paraPrIDRef="{paraPr}" '
                f'styleIDRef="0" pageBreak="{pageBreak}" columnBreak="0" '
                f'merged="0"><hp:run charPrIDRef="{charPr}"><hp:t/></hp:run></hp:p>')

    def _add_heading_spacer(self):
        """Small 5pt spacer after □ heading."""
        self._body.append(self._p_blank(PARA_BOX, CHAR_BOX_SPACER))
        self._last_was_blank = True

    def _add_medium_spacer(self):
        """Medium 9pt spacer (between sections, after table/figure)."""
        self._body.append(self._p_blank(PARA_CIRCLE, CHAR_CIRCLE_SPACER))
        self._last_was_blank = True

    def _add_full_spacer(self):
        """Full-line 14pt spacer (before table/fig after items)."""
        self._body.append(self._p_blank(PARA_CIRCLE, CHAR_CIRCLE))
        self._last_was_blank = True

    def _ensure_gap_before_block(self):
        """Insert one spacer before a table/figure if previous was content."""
        if self._last_was_blank or not self._body:
            return
        self._add_full_spacer()

    def _ensure_gap_before_section(self):
        """Insert a clearly visible blank line before a new section's □ heading."""
        if self._last_was_blank or not self._body:
            return
        self._add_full_spacer()

    # ── Public API ────────────────────────────────────────────────

    def title(self, new_title):
        if self._title_set:
            raise RuntimeError('title() can only be called once')
        if self._ref_title:
            self._first_para = self._first_para.replace(self._ref_title, new_title)
        self._title_set = True
        return self

    def section(self, heading, page_break=False):
        self._ensure_gap_before_section()
        pb = '1' if page_break else '0'
        self._body.append(self._p_text(f'□ {heading}',
                                        PARA_BOX, CHAR_BOX, pageBreak=pb))
        self._add_heading_spacer()
        self._last_was_table_or_fig = False
        return self

    def _p_runs(self, runs, paraPr, pageBreak='0'):
        """runs = [(charPrIDRef, text), ...] → 혼합 서식 문단."""
        body = ''.join(
            (f'<hp:run charPrIDRef="{cp}"><hp:t>{self._esc(t)}</hp:t></hp:run>'
             if t else f'<hp:run charPrIDRef="{cp}"><hp:t/></hp:run>')
            for cp, t in runs)
        return (f'<hp:p id="{self._pid_new()}" paraPrIDRef="{paraPr}" '
                f'styleIDRef="0" pageBreak="{pageBreak}" columnBreak="0" '
                f'merged="0">{body}</hp:p>')

    def item(self, text='', label=None, small=False):
        """ㅇ 본문 항목.  label 지정 시 " ㅇ (label) text" 에서 (label)을 굵게.

          item('단순 항목')
          item('설명 문장', label='① 분석 DB 구축')   # → ㅇ (① 분석 DB 구축) 설명 문장
        small=True 면 참고/부록용 12pt(charPr 37)로 출력.
        """
        if self._last_was_table_or_fig and not self._last_was_blank:
            self._add_full_spacer()
        base = CHAR_ITEM_SMALL if small else CHAR_CIRCLE
        if label:
            runs = [(base, ' ㅇ '), (CHAR_ITEM_BOLD, f'({label})')]
            if text:
                runs.append((base, f' {text}'))
        else:
            runs = [(base, f' ㅇ {text}')]
        self._body.append(self._p_runs(runs, PARA_CIRCLE))
        self._last_was_blank = False
        self._last_was_table_or_fig = False
        return self

    def item_runs(self, runs, small=False):
        """완전 수동 혼합 런 ㅇ 항목.  runs=[('plain'|'bold'|'blue'|'red', text), ...]
        마커 ' ㅇ '는 자동으로 앞에 붙는다."""
        if self._last_was_table_or_fig and not self._last_was_blank:
            self._add_full_spacer()
        base = CHAR_ITEM_SMALL if small else CHAR_CIRCLE
        cmap = {'plain': base, 'bold': CHAR_ITEM_BOLD,
                'blue': CHAR_ITEM_BLUE, 'red': CHAR_CELL_RED}
        out = [(base, ' ㅇ ')]
        for kind, t in runs:
            out.append((cmap.get(kind, base), t))
        self._body.append(self._p_runs(out, PARA_CIRCLE))
        self._last_was_blank = False
        self._last_was_table_or_fig = False
        return self

    def sub(self, text):
        if self._last_was_table_or_fig and not self._last_was_blank:
            self._add_full_spacer()
        self._body.append(self._p_text(f'- {text}',
                                        PARA_DASH, CHAR_CIRCLE))
        self._last_was_blank = False
        self._last_was_table_or_fig = False
        return self

    def note(self, text):
        """※ 주석/출처 한 줄 (12pt 한양중고딕)."""
        self._body.append(self._p_text(f' ※ {text}', PARA_NOTE, CHAR_NOTE))
        self._last_was_blank = False
        self._last_was_table_or_fig = False
        return self

    def footnote(self, text, marker='*'):
        """각주 (들여쓰기 + 13pt 한양중고딕).  '   * 설명' 형식."""
        self._body.append(self._p_text(f'   {marker} {text}',
                                        PARA_CIRCLE, CHAR_FOOT))
        self._last_was_blank = False
        self._last_was_table_or_fig = False
        return self

    def fig_caption(self, text):
        prefix, rest = _split_caption_prefix(text)
        if prefix:
            runs = (f'<hp:run charPrIDRef="{CHAR_CELL_LABEL}">'
                    f'<hp:t>{self._esc(prefix)}</hp:t></hp:run>'
                    f'<hp:run charPrIDRef="{CHAR_CELL_DATA}">'
                    f'<hp:t>{self._esc(rest)}</hp:t></hp:run>')
        else:
            runs = (f'<hp:run charPrIDRef="{CHAR_CELL_DATA}">'
                    f'<hp:t>{self._esc(rest)}</hp:t></hp:run>')
        self._body.append(
            f'<hp:p id="{self._pid_new()}" paraPrIDRef="{PARA_CENTER}" '
            f'styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
            f'{runs}</hp:p>')
        self._last_was_blank = False
        return self

    def _cell(self, text, bf, col, row, width, height=3363,
              paraPr=PARA_CENTER, charPr=CHAR_CELL_DATA):
        run = (f'<hp:run charPrIDRef="{charPr}">'
               f'<hp:t>{self._esc(text)}</hp:t></hp:run>' if text
               else f'<hp:run charPrIDRef="{charPr}"><hp:t/></hp:run>')
        inner = (f'<hp:p id="{self._pid_new()}" paraPrIDRef="{paraPr}" '
                 f'styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">{run}</hp:p>')
        return (f'<hp:tc name="" header="0" hasMargin="0" protect="0" '
                f'editable="0" dirty="0" borderFillIDRef="{bf}">'
                f'<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" '
                f'vertAlign="CENTER" linkListIDRef="0" linkListNextIDRef="0" '
                f'textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">'
                f'{inner}</hp:subList>'
                f'<hp:cellAddr colAddr="{col}" rowAddr="{row}"/>'
                f'<hp:cellSpan colSpan="1" rowSpan="1"/>'
                f'<hp:cellSz width="{width}" height="{height}"/>'
                f'<hp:cellMargin left="510" right="510" top="141" bottom="141"/>'
                f'</hp:tc>')

    def _make_hp_caption(self, caption_text, side, total_width):
        prefix, rest = _split_caption_prefix(caption_text)
        if prefix:
            runs = (f'<hp:run charPrIDRef="{CHAR_CELL_LABEL}">'
                    f'<hp:t>{self._esc(prefix)}</hp:t></hp:run>'
                    f'<hp:run charPrIDRef="{CHAR_CELL_DATA}">'
                    f'<hp:t>{self._esc(rest)}</hp:t></hp:run>')
        else:
            runs = (f'<hp:run charPrIDRef="{CHAR_CELL_DATA}">'
                    f'<hp:t>{self._esc(rest)}</hp:t></hp:run>')
        return (
            f'<hp:caption side="{side}" fullSz="0" width="8504" gap="850" '
            f'lastWidth="{total_width}">'
            f'<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" '
            f'vertAlign="TOP" linkListIDRef="0" linkListNextIDRef="0" '
            f'textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">'
            f'<hp:p id="{self._pid_new()}" paraPrIDRef="{PARA_CENTER}" '
            f'styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
            + runs +
            f'</hp:p></hp:subList></hp:caption>'
        )

    def data_table(self, headers, rows, col_widths,
                   caption=None, caption_side=None, row_height=3363):
        self._ensure_gap_before_block()
        n_cols = len(col_widths)
        if len(headers) != n_cols:
            raise ValueError(f'data_table: headers({len(headers)}) != col_widths({n_cols})')
        for ri, row in enumerate(rows):
            if len(row) != n_cols:
                raise ValueError(f'data_table: row {ri} has {len(row)} cells, expected {n_cols}')
        n_rows = 1 + len(rows)
        total_w = sum(col_widths)
        total_h = n_rows * row_height

        if caption and caption_side is None:
            prefix, _ = _split_caption_prefix(caption)
            caption_side = 'BOTTOM' if prefix else 'TOP'
        elif caption_side is None:
            caption_side = 'TOP'

        rows_xml = []
        h_cells = []
        for c, txt in enumerate(headers):
            bf = (BF_DATA['header']['l'] if c == 0
                  else BF_DATA['header']['r'] if c == n_cols - 1
                  else BF_DATA['header']['m'])
            h_cells.append(self._cell(txt, bf, c, 0, col_widths[c], row_height,
                                       charPr=CHAR_CELL_LABEL))
        rows_xml.append('<hp:tr>' + ''.join(h_cells) + '</hp:tr>')
        for r_idx, row_data in enumerate(rows):
            is_first = (r_idx == 0)
            is_last  = (r_idx == len(rows) - 1)
            band = ('first' if (is_first and len(rows) > 1)
                    else 'last' if (is_last and len(rows) > 1)
                    else 'mid')
            cells_xml = []
            for c, txt in enumerate(row_data):
                bf = (BF_DATA[band]['l'] if c == 0
                      else BF_DATA[band]['r'] if c == n_cols - 1
                      else BF_DATA[band]['m'])
                cpr = CHAR_CELL_LABEL if c == 0 else CHAR_CELL_DATA
                cells_xml.append(self._cell(txt, bf, c, r_idx + 1,
                                             col_widths[c], row_height, charPr=cpr))
            rows_xml.append('<hp:tr>' + ''.join(cells_xml) + '</hp:tr>')

        caption_xml = (self._make_hp_caption(caption, caption_side, total_w)
                       if caption else '')

        tbl = (f'<hp:tbl id="{self._tbl_new()}" zOrder="0" numberingType="TABLE" '
               f'textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" lock="0" '
               f'dropcapstyle="None" pageBreak="CELL" repeatHeader="1" '
               f'rowCnt="{n_rows}" colCnt="{n_cols}" cellSpacing="0" '
               f'borderFillIDRef="3" noAdjust="0">'
               f'<hp:sz width="{total_w}" widthRelTo="ABSOLUTE" '
               f'height="{total_h}" heightRelTo="ABSOLUTE" protect="0"/>'
               f'<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" '
               f'allowOverlap="0" holdAnchorAndSO="0" vertRelTo="PARA" '
               f'horzRelTo="COLUMN" vertAlign="TOP" horzAlign="CENTER" '
               f'vertOffset="0" horzOffset="0"/>'
               f'<hp:outMargin left="0" right="0" top="0" bottom="0"/>'
               + caption_xml +
               f'<hp:inMargin left="510" right="510" top="141" bottom="141"/>'
               + ''.join(rows_xml) + f'</hp:tbl>')

        # Wrapper paragraph uses paraPr 19 (matches reference Ref A)
        self._body.append(
            f'<hp:p id="{self._pid_new()}" paraPrIDRef="{PARA_CIRCLE}" '
            f'styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
            f'<hp:run charPrIDRef="{CHAR_CIRCLE}">{tbl}<hp:t/></hp:run></hp:p>')
        self._add_medium_spacer()
        self._last_was_table_or_fig = True
        return self

    def figure(self, image_path, caption=None, caption_side='BOTTOM',
               width_hwpunit=38000, image_id=None):
        self._ensure_gap_before_block()
        from PIL import Image as PILImage
        path = Path(image_path).resolve()
        if not path.is_file():
            raise FileNotFoundError(path)
        if image_id is None:
            image_id = f'image{self._image_counter}'
            self._image_counter += 1
        ext = path.suffix.lower()
        media = {'.jpg':'image/jpg','.jpeg':'image/jpg','.png':'image/png'}.get(ext)
        if media is None:
            raise ValueError(f'Unsupported image type: {ext}')
        self._images[image_id] = ('file', str(path), media)
        with PILImage.open(path) as im:
            orig_w, orig_h = im.size
        target_h = int(width_hwpunit * orig_h / orig_w)
        dim_w = orig_w * 75; dim_h = orig_h * 75

        pic = (f'<hp:pic id="{self._pid_new()}" zOrder="0" numberingType="PICTURE" '
               f'textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" lock="0" '
               f'dropcapstyle="None" href="" groupLevel="0" '
               f'instid="{self._pid_new()}" reverse="0">'
               f'<hp:offset x="0" y="0"/>'
               f'<hp:orgSz width="{width_hwpunit}" height="{target_h}"/>'
               f'<hp:curSz width="{width_hwpunit}" height="{target_h}"/>'
               f'<hp:flip horizontal="0" vertical="0"/>'
               f'<hp:rotationInfo angle="0" centerX="{width_hwpunit//2}" '
               f'centerY="{target_h//2}" rotateimage="1"/>'
               f'<hp:renderingInfo>'
               f'<hc:transMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/>'
               f'<hc:scaMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/>'
               f'<hc:rotMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/>'
               f'</hp:renderingInfo>'
               f'<hc:img binaryItemIDRef="{image_id}" bright="0" contrast="0" '
               f'effect="REAL_PIC" alpha="0"/>'
               f'<hp:imgRect>'
               f'<hc:pt0 x="0" y="0"/><hc:pt1 x="{width_hwpunit}" y="0"/>'
               f'<hc:pt2 x="{width_hwpunit}" y="{target_h}"/>'
               f'<hc:pt3 x="0" y="{target_h}"/></hp:imgRect>'
               f'<hp:imgClip left="0" right="{dim_w}" top="0" bottom="{dim_h}"/>'
               f'<hp:inMargin left="0" right="0" top="0" bottom="0"/>'
               f'<hp:imgDim dimwidth="{dim_w}" dimheight="{dim_h}"/>'
               f'<hp:effects/>'
               f'<hp:sz width="{width_hwpunit}" widthRelTo="ABSOLUTE" '
               f'height="{target_h}" heightRelTo="ABSOLUTE" protect="0"/>'
               f'<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" '
               f'allowOverlap="0" holdAnchorAndSO="0" vertRelTo="PARA" '
               f'horzRelTo="COLUMN" vertAlign="TOP" horzAlign="CENTER" '
               f'vertOffset="0" horzOffset="0"/>'
               f'<hp:outMargin left="0" right="0" top="0" bottom="0"/>'
               f'<hp:shapeComment>그림입니다.</hp:shapeComment></hp:pic>')

        if caption and caption_side == 'TOP':
            self.fig_caption(caption)
        # Figure wrapper (paraPr 1 CENTER, no keepWithNext)
        self._body.append(
            f'<hp:p id="{self._pid_new()}" paraPrIDRef="{PARA_CENTER}" '
            f'styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
            f'<hp:run charPrIDRef="0">{pic}<hp:t/></hp:run></hp:p>')
        if caption and caption_side == 'BOTTOM':
            self.fig_caption(caption)
        self._add_medium_spacer()
        self._last_was_table_or_fig = True
        return self

    def chamgo_badge(self, num, title, force_page_break=True):
        if force_page_break:
            self._body.append(self._p_blank(PARA_BODY, CHAR_BODY, pageBreak='1'))
            self._last_was_blank = True

        c0 = (f'<hp:tc name="" header="0" hasMargin="0" protect="0" '
              f'editable="0" dirty="0" borderFillIDRef="{BF_CHAMGO["badge"]}">'
              f'<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" '
              f'vertAlign="CENTER" linkListIDRef="0" linkListNextIDRef="0" '
              f'textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">'
              f'<hp:p id="{self._pid_new()}" paraPrIDRef="{PARA_CHAMGO_BADGE}" '
              f'styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
              f'<hp:run charPrIDRef="{CHAR_BADGE_WHITE}">'
              f'<hp:t>참고{self._esc(str(num))}</hp:t></hp:run></hp:p></hp:subList>'
              f'<hp:cellAddr colAddr="0" rowAddr="0"/>'
              f'<hp:cellSpan colSpan="1" rowSpan="1"/>'
              f'<hp:cellSz width="5868" height="2830"/>'
              f'<hp:cellMargin left="141" right="141" top="141" bottom="141"/>'
              f'</hp:tc>')
        c1 = (f'<hp:tc name="" header="0" hasMargin="0" protect="0" '
              f'editable="0" dirty="0" borderFillIDRef="{BF_CHAMGO["gap"]}">'
              f'<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" '
              f'vertAlign="CENTER" linkListIDRef="0" linkListNextIDRef="0" '
              f'textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">'
              f'<hp:p id="{self._pid_new()}" paraPrIDRef="{PARA_CENTER}" '
              f'styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
              f'<hp:run charPrIDRef="{CHAR_BADGE_GAP}"><hp:t/></hp:run>'
              f'</hp:p></hp:subList>'
              f'<hp:cellAddr colAddr="1" rowAddr="0"/>'
              f'<hp:cellSpan colSpan="1" rowSpan="1"/>'
              f'<hp:cellSz width="848" height="2830"/>'
              f'<hp:cellMargin left="141" right="141" top="141" bottom="141"/>'
              f'</hp:tc>')
        c2 = (f'<hp:tc name="" header="0" hasMargin="0" protect="0" '
              f'editable="0" dirty="0" borderFillIDRef="{BF_CHAMGO["title"]}">'
              f'<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" '
              f'vertAlign="CENTER" linkListIDRef="0" linkListNextIDRef="0" '
              f'textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">'
              f'<hp:p id="{self._pid_new()}" paraPrIDRef="{PARA_CHAMGO_TITLE}" '
              f'styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
              f'<hp:run charPrIDRef="{CHAR_BADGE_TITLE}">'
              f'<hp:t> {self._esc(title)}</hp:t></hp:run></hp:p></hp:subList>'
              f'<hp:cellAddr colAddr="2" rowAddr="0"/>'
              f'<hp:cellSpan colSpan="1" rowSpan="1"/>'
              f'<hp:cellSz width="40676" height="2830"/>'
              f'<hp:cellMargin left="141" right="141" top="141" bottom="141"/>'
              f'</hp:tc>')
        tbl = (f'<hp:tbl id="{self._tbl_new()}" zOrder="0" numberingType="TABLE" '
               f'textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" lock="0" '
               f'dropcapstyle="None" pageBreak="CELL" repeatHeader="1" '
               f'rowCnt="1" colCnt="3" cellSpacing="0" borderFillIDRef="3" '
               f'noAdjust="0">'
               f'<hp:sz width="47392" widthRelTo="ABSOLUTE" height="2830" '
               f'heightRelTo="ABSOLUTE" protect="0"/>'
               f'<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" '
               f'allowOverlap="0" holdAnchorAndSO="0" vertRelTo="PARA" '
               f'horzRelTo="PARA" vertAlign="TOP" horzAlign="LEFT" '
               f'vertOffset="0" horzOffset="0"/>'
               f'<hp:outMargin left="283" right="283" top="283" bottom="283"/>'
               f'<hp:inMargin left="141" right="141" top="141" bottom="141"/>'
               f'<hp:tr>{c0}{c1}{c2}</hp:tr></hp:tbl>')
        self._body.append(
            f'<hp:p id="{self._pid_new()}" paraPrIDRef="{PARA_CIRCLE}" '
            f'styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
            f'<hp:run charPrIDRef="0">{tbl}<hp:t/></hp:run></hp:p>')
        self._add_medium_spacer()
        self._last_was_table_or_fig = False
        return self

    def _span_cell(self, inner_p, bf, col, row, w, h, colspan=1, rowspan=1):
        cm = '<hp:cellMargin left="510" right="510" top="141" bottom="141"/>'
        return (f'<hp:tc name="" header="0" hasMargin="0" protect="0" '
                f'editable="0" dirty="0" borderFillIDRef="{bf}">'
                f'<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" '
                f'vertAlign="CENTER" linkListIDRef="0" linkListNextIDRef="0" '
                f'textWidth="0" textHeight="0" hasTextRef="0" hasNumRef="0">'
                f'{inner_p}</hp:subList>'
                f'<hp:cellAddr colAddr="{col}" rowAddr="{row}"/>'
                f'<hp:cellSpan colSpan="{colspan}" rowSpan="{rowspan}"/>'
                f'<hp:cellSz width="{w}" height="{h}"/>{cm}</hp:tc>')

    def process_flow(self, steps, num_h=1789, label_h=6406, arrow_w=3850):
        """프로세스 흐름 박스 (① → ② → ③ … 연노랑 박스 + 화살표).

          process_flow(['분석 DB 구축', '대상 변수 선정', 'AI 모델 학습', '검증'])
        Row0 = 원문자 번호(연노랑 상단), 화살표(rowSpan2); Row1 = 단계 라벨(연노랑 하단).
        """
        self._ensure_gap_before_block()
        if not steps:
            raise ValueError('process_flow requires at least one step')
        n = len(steps)
        n_cols = 2 * n - 1
        total_h = num_h + label_h
        step_total = 47600 - arrow_w * (n - 1)
        step_w = step_total // n
        widths = []
        for i in range(n_cols):
            widths.append(step_w if i % 2 == 0 else arrow_w)
        total_w = sum(widths)

        def cp(text, paraPr=PARA_CENTER, charPr=CHAR_FLOW):
            t = (f'<hp:run charPrIDRef="{charPr}"><hp:t>{self._esc(text)}</hp:t></hp:run>'
                 if text else f'<hp:run charPrIDRef="{charPr}"><hp:t/></hp:run>')
            return (f'<hp:p id="{self._pid_new()}" paraPrIDRef="{paraPr}" '
                    f'styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">{t}</hp:p>')

        row0, row1 = [], []
        for i in range(n_cols):
            col = i
            if i % 2 == 0:            # 단계 컬럼
                s = i // 2
                row0.append(self._span_cell(cp(_CIRCLED[s]), BF_FLOW['num'],
                                            col, 0, widths[i], num_h))
                row1.append(self._span_cell(cp(steps[s]), BF_FLOW['label'],
                                            col, 1, widths[i], label_h))
            else:                     # 화살표 컬럼 (rowSpan 2)
                row0.append(self._span_cell(cp('→'), BF_FLOW['arrow'],
                                            col, 0, widths[i], total_h, rowspan=2))
        tbl = (f'<hp:tbl id="{self._tbl_new()}" zOrder="0" numberingType="TABLE" '
               f'textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" lock="0" '
               f'dropcapstyle="None" pageBreak="CELL" repeatHeader="0" '
               f'rowCnt="2" colCnt="{n_cols}" cellSpacing="0" borderFillIDRef="3" '
               f'noAdjust="0">'
               f'<hp:sz width="{total_w}" widthRelTo="ABSOLUTE" height="{total_h}" '
               f'heightRelTo="ABSOLUTE" protect="0"/>'
               f'<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" '
               f'allowOverlap="0" holdAnchorAndSO="0" vertRelTo="PARA" '
               f'horzRelTo="COLUMN" vertAlign="TOP" horzAlign="CENTER" '
               f'vertOffset="0" horzOffset="0"/>'
               f'<hp:outMargin left="0" right="0" top="0" bottom="0"/>'
               f'<hp:inMargin left="510" right="510" top="141" bottom="141"/>'
               f'<hp:tr>{"".join(row0)}</hp:tr><hp:tr>{"".join(row1)}</hp:tr></hp:tbl>')
        self._body.append(
            f'<hp:p id="{self._pid_new()}" paraPrIDRef="{PARA_CIRCLE}" '
            f'styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
            f'<hp:run charPrIDRef="{CHAR_CIRCLE}">{tbl}<hp:t/></hp:run></hp:p>')
        self._add_medium_spacer()
        self._last_was_table_or_fig = True
        return self

    def _pic_xml(self, image_id, image_path, width_hwpunit):
        from PIL import Image as PILImage
        with PILImage.open(image_path) as im:
            ow, oh = im.size
        th = int(width_hwpunit * oh / ow)
        dw, dh = ow * 75, oh * 75
        pic = (f'<hp:pic id="{self._pid_new()}" zOrder="0" numberingType="PICTURE" '
               f'textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" lock="0" '
               f'dropcapstyle="None" href="" groupLevel="0" instid="{self._pid_new()}" '
               f'reverse="0"><hp:offset x="0" y="0"/>'
               f'<hp:orgSz width="{width_hwpunit}" height="{th}"/>'
               f'<hp:curSz width="{width_hwpunit}" height="{th}"/>'
               f'<hp:flip horizontal="0" vertical="0"/>'
               f'<hp:rotationInfo angle="0" centerX="{width_hwpunit//2}" '
               f'centerY="{th//2}" rotateimage="1"/>'
               f'<hp:renderingInfo>'
               f'<hc:transMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/>'
               f'<hc:scaMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/>'
               f'<hc:rotMatrix e1="1" e2="0" e3="0" e4="0" e5="1" e6="0"/>'
               f'</hp:renderingInfo>'
               f'<hc:img binaryItemIDRef="{image_id}" bright="0" contrast="0" '
               f'effect="REAL_PIC" alpha="0"/>'
               f'<hp:imgRect><hc:pt0 x="0" y="0"/><hc:pt1 x="{width_hwpunit}" y="0"/>'
               f'<hc:pt2 x="{width_hwpunit}" y="{th}"/><hc:pt3 x="0" y="{th}"/></hp:imgRect>'
               f'<hp:imgClip left="0" right="{dw}" top="0" bottom="{dh}"/>'
               f'<hp:inMargin left="0" right="0" top="0" bottom="0"/>'
               f'<hp:imgDim dimwidth="{dw}" dimheight="{dh}"/><hp:effects/>'
               f'<hp:sz width="{width_hwpunit}" widthRelTo="ABSOLUTE" height="{th}" '
               f'heightRelTo="ABSOLUTE" protect="0"/>'
               f'<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" '
               f'allowOverlap="0" holdAnchorAndSO="0" vertRelTo="PARA" '
               f'horzRelTo="COLUMN" vertAlign="TOP" horzAlign="CENTER" '
               f'vertOffset="0" horzOffset="0"/>'
               f'<hp:outMargin left="0" right="0" top="0" bottom="0"/>'
               f'<hp:shapeComment>그림입니다.</hp:shapeComment></hp:pic>')
        return pic, th

    def figure_box(self, image_path=None, caption=None, image_id=None,
                   img_width=46000, box_width=47624):
        """그림 박스: 외곽 테두리 1칸 안에 [그림] + 파랑 "<캡션>".

          figure_box('chart.png', caption='포워드필(forward fill)')
        image_path 생략 시 그림 자리는 비워두고 캡션만(수동 그림 삽입용).
        """
        self._ensure_gap_before_block()
        if image_path:
            from pathlib import Path as _P
            p = _P(image_path).resolve()
            if not p.is_file():
                raise FileNotFoundError(p)
            if image_id is None:
                image_id = f'image{self._image_counter}'; self._image_counter += 1
            ext = p.suffix.lower()
            media = {'.jpg': 'image/jpg', '.jpeg': 'image/jpg',
                     '.png': 'image/png'}.get(ext)
            if media is None:
                raise ValueError(f'Unsupported image type: {ext}')
            self._images[image_id] = ('file', str(p), media)
            pic, th = self._pic_xml(image_id, p, img_width)
            img_run = f'<hp:run charPrIDRef="0">{pic}<hp:t/></hp:run>'
            img_cell_h = th + 600
        else:
            img_run = '<hp:run charPrIDRef="0"><hp:t/></hp:run>'
            img_cell_h = 12000
        img_p = (f'<hp:p id="{self._pid_new()}" paraPrIDRef="{PARA_CENTER}" '
                 f'styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
                 f'{img_run}</hp:p>')
        cap = caption or ''
        if cap and not cap.lstrip().startswith('<'):
            cap = f'<{cap}>'
        cap_p = (f'<hp:p id="{self._pid_new()}" paraPrIDRef="{PARA_CENTER}" '
                 f'styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
                 f'<hp:run charPrIDRef="{CHAR_FIGCAP_BLUE}">'
                 f'<hp:t>{self._esc(cap)}</hp:t></hp:run></hp:p>')
        c0 = self._span_cell(img_p, BF_FIGBOX['cell'], 0, 0, box_width, img_cell_h)
        c1 = self._span_cell(cap_p, BF_FIGBOX['cell'], 0, 1, box_width, 1200)
        total_h = img_cell_h + 1200
        tbl = (f'<hp:tbl id="{self._tbl_new()}" zOrder="0" numberingType="TABLE" '
               f'textWrap="TOP_AND_BOTTOM" textFlow="BOTH_SIDES" lock="0" '
               f'dropcapstyle="None" pageBreak="CELL" repeatHeader="0" '
               f'rowCnt="2" colCnt="1" cellSpacing="0" '
               f'borderFillIDRef="{BF_FIGBOX["outer"]}" noAdjust="0">'
               f'<hp:sz width="{box_width}" widthRelTo="ABSOLUTE" height="{total_h}" '
               f'heightRelTo="ABSOLUTE" protect="0"/>'
               f'<hp:pos treatAsChar="1" affectLSpacing="0" flowWithText="1" '
               f'allowOverlap="0" holdAnchorAndSO="0" vertRelTo="PARA" '
               f'horzRelTo="COLUMN" vertAlign="TOP" horzAlign="CENTER" '
               f'vertOffset="0" horzOffset="0"/>'
               f'<hp:outMargin left="0" right="0" top="0" bottom="0"/>'
               f'<hp:inMargin left="510" right="510" top="141" bottom="141"/>'
               f'<hp:tr>{c0}</hp:tr><hp:tr>{c1}</hp:tr></hp:tbl>')
        self._body.append(
            f'<hp:p id="{self._pid_new()}" paraPrIDRef="{PARA_CIRCLE}" '
            f'styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
            f'<hp:run charPrIDRef="{CHAR_CIRCLE}">{tbl}<hp:t/></hp:run></hp:p>')
        self._add_medium_spacer()
        self._last_was_table_or_fig = True
        return self

    def page_break(self):
        self._body.append(self._p_blank(PARA_BODY, CHAR_BODY, pageBreak='1'))
        self._last_was_blank = True
        return self

    def spacer(self, size='medium'):
        if size == 'small': self._add_heading_spacer()
        elif size == 'full': self._add_full_spacer()
        else: self._add_medium_spacer()
        return self

    def build(self, output_path, title='', creator='(주)지오시스템리서치 예보사업부', validate=True):
        output_path = Path(output_path).resolve()
        section_xml_path = self.work_dir / 'new_section0.xml'
        section_xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<hs:sec {NS_DECL}>'
            f'{self._first_para}{"".join(self._body)}'
            '</hs:sec>')
        section_xml_path.write_text(section_xml, encoding='utf-8')

        build_script = self.skill_dir / 'build_hwpx.py'
        result = subprocess.run(
            [sys.executable, str(build_script),
             '--header', str(self._header_path),
             '--section', str(section_xml_path),
             '--title', title or 'Untitled',
             '--creator', creator,
             '--output', str(output_path)],
            capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f'build_hwpx.py failed:\n{result.stderr}')
        self._inject_images(output_path)
        if validate:
            validate_script = self.skill_dir / 'validate.py'
            if validate_script.is_file():
                r = subprocess.run([sys.executable, str(validate_script),
                                    str(output_path)], capture_output=True, text=True)
                if r.returncode != 0:
                    print(f'WARNING: {r.stdout}', file=sys.stderr)
        return output_path

    def _inject_images(self, hwpx_path):
        if not self._images: return
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            with zipfile.ZipFile(hwpx_path) as z:
                z.extractall(td)
            bindata_dir = td / 'BinData'
            bindata_dir.mkdir(exist_ok=True)
            ref_zip = zipfile.ZipFile(self.reference_hwpx)
            placed = []
            for img_id, (kind, source, media) in self._images.items():
                if kind == 'ref':
                    ref_files = [n for n in ref_zip.namelist()
                                 if Path(n).stem == source]
                    if not ref_files: continue
                    data = ref_zip.read(ref_files[0])
                    ext = Path(ref_files[0]).suffix
                else:
                    data = Path(source).read_bytes()
                    ext = Path(source).suffix
                dest = f'{img_id}{ext}'
                (bindata_dir / dest).write_bytes(data)
                placed.append((img_id, dest, media))
            ref_zip.close()
            hpf = td / 'Contents' / 'content.hpf'
            tree = etree.parse(str(hpf))
            root = tree.getroot()
            manifest = root.find('opf:manifest', NS)
            existing = {item.get('id') for item in manifest.findall('opf:item', NS)}
            for img_id, dest, media in placed:
                if img_id in existing: continue
                item = etree.SubElement(manifest, OPF + 'item')
                item.set('id', img_id); item.set('href', f'BinData/{dest}')
                item.set('media-type', media); item.set('isEmbeded', '1')
            tree.write(str(hpf), xml_declaration=True,
                       encoding='UTF-8', standalone=True)
            out_tmp = hwpx_path.with_suffix('.tmp.hwpx')
            with zipfile.ZipFile(out_tmp, 'w', zipfile.ZIP_DEFLATED) as zout:
                mt = (td / 'mimetype').read_bytes()
                zi = zipfile.ZipInfo('mimetype'); zi.compress_type = zipfile.ZIP_STORED
                zout.writestr(zi, mt)
                for f in sorted(td.rglob('*')):
                    if not f.is_file(): continue
                    rel = f.relative_to(td).as_posix()
                    if rel == 'mimetype': continue
                    zout.write(f, rel, compress_type=zipfile.ZIP_DEFLATED)
            out_tmp.replace(hwpx_path)


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--reference', default=None)
    ap.add_argument('--output', required=True)
    ap.add_argument('--title', default='샘플')
    args = ap.parse_args()
    b = YeoboBuilder(reference_hwpx=args.reference)
    b.title(args.title)
    b.section('배경 및 필요성')
    b.item('첫 번째 배경 항목 — 개조식 한 문장으로 끝맺음')
    b.item('설명 문장이 이어지는 항목', label='핵심 배경')
    b.section('방법')
    b.process_flow(['분석 DB 구축', '대상 변수 선정', 'AI 모델 학습', '수행 및 검증'])
    b.item('첫 단계 설명', label='① 분석 DB 구축')
    b.footnote('각주 예시 — 용어 정의')
    b.section('선행연구 결과')
    b.data_table(headers=['구분','수온','염분','DO'],
                 rows=[['Kriging','0.81','0.53','0.48'],
                       ['AI','0.91','0.80','0.36']],
                 col_widths=[12000,11866,11866,11868])
    b.note('출처: 예시 연구 결과')
    b.chamgo_badge(1, '참고 자료 예시')
    b.item('참고 항목', small=True)
    out = b.build(args.output, title=args.title)
    print(f'BUILT: {out}')
