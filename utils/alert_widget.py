# -*- coding: utf-8 -*-
"""
alert_widget.py — 고수온 플로팅 알림 위젯

inject_alerts(alerts) 를 각 페이지에서 호출하면
화면 우상단에 토스트 알림이 자동으로 표시된다.

alerts: alert_agent.get_active_alerts() 반환값
"""

from __future__ import annotations

import json
import streamlit.components.v1 as components


def inject_alerts(alerts: list[dict]) -> None:
    """고수온 감지 알림을 우상단 플로팅 토스트로 표시."""
    if not alerts:
        return

    alerts_json = json.dumps(alerts, ensure_ascii=False)

    components.html(f"""<!DOCTYPE html>
<html><head></head><body>
<script>
(function() {{
  var doc = window.parent.document;

  // 이미 같은 알림이 떠 있으면 중복 방지
  if (doc.getElementById('hwa-container')) return;

  var alerts = {alerts_json};

  var style = doc.createElement('style');
  style.textContent = `
    #hwa-container {{
      position: fixed !important;
      top: 70px !important;
      right: 20px !important;
      z-index: 9999999 !important;
      display: flex !important;
      flex-direction: column !important;
      gap: 8px !important;
      pointer-events: none !important;
    }}
    .hwa-toast {{
      pointer-events: all !important;
      min-width: 260px !important;
      max-width: 320px !important;
      padding: 12px 16px !important;
      border-radius: 12px !important;
      font-family: 'Noto Sans KR', sans-serif !important;
      font-size: 13px !important;
      line-height: 1.55 !important;
      box-shadow: 0 4px 24px rgba(0,0,0,0.45) !important;
      display: flex !important;
      align-items: flex-start !important;
      gap: 10px !important;
      animation: hwaSlide .35s cubic-bezier(.4,0,.2,1) !important;
      position: relative !important;
    }}
    .hwa-alarm {{
      background: linear-gradient(135deg, #3a0a0a, #1a0505) !important;
      border: 1px solid rgba(255,80,80,0.4) !important;
      color: #ffcccc !important;
    }}
    .hwa-advisory {{
      background: linear-gradient(135deg, #2a2200, #1a1600) !important;
      border: 1px solid rgba(255,220,0,0.4) !important;
      color: #fff3aa !important;
    }}
    .hwa-icon {{
      font-size: 20px !important;
      line-height: 1 !important;
      flex-shrink: 0 !important;
      margin-top: 1px !important;
    }}
    .hwa-body {{ flex: 1 !important; }}
    .hwa-title {{
      font-weight: 700 !important;
      font-size: 13px !important;
      margin-bottom: 3px !important;
    }}
    .hwa-detail {{
      font-size: 11px !important;
      opacity: 0.75 !important;
    }}
    .hwa-close {{
      background: none !important;
      border: none !important;
      color: inherit !important;
      opacity: 0.5 !important;
      cursor: pointer !important;
      font-size: 14px !important;
      padding: 0 !important;
      line-height: 1 !important;
      flex-shrink: 0 !important;
    }}
    .hwa-close:hover {{ opacity: 1 !important; }}
    @keyframes hwaSlide {{
      from {{ transform: translateX(120%) !important; opacity: 0 !important; }}
      to   {{ transform: translateX(0) !important;   opacity: 1 !important; }}
    }}
    .hwa-bar {{
      position: absolute !important;
      bottom: 0 !important; left: 0 !important;
      height: 3px !important;
      border-radius: 0 0 12px 12px !important;
      animation: hwaBar 8s linear forwards !important;
    }}
    .hwa-alarm    .hwa-bar {{ background: #ff5050 !important; }}
    .hwa-advisory .hwa-bar {{ background: #ffd000 !important; }}
    @keyframes hwaBar {{
      from {{ width: 100% !important; }}
      to   {{ width: 0%   !important; }}
    }}
  `;
  doc.head.appendChild(style);

  var container = doc.createElement('div');
  container.id = 'hwa-container';
  doc.body.appendChild(container);

  alerts.forEach(function(a, i) {{
    var cls   = a.level === 'alarm' ? 'hwa-alarm' : 'hwa-advisory';
    var icon  = a.level === 'alarm' ? '🔴' : '🟡';
    var label = a.level === 'alarm' ? '고수온 경보' : '고수온 주의보';
    var detail = a.level === 'alarm'
      ? '현재 ' + a.current_streak + '일 연속 지속 중 · 최근 ' + a.latest_sst.toFixed(1) + '°C'
      : '현재 ' + a.current_streak + '일 연속 감지 중 · 최근 ' + a.latest_sst.toFixed(1) + '°C';

    var toast = doc.createElement('div');
    toast.className = 'hwa-toast ' + cls;
    toast.innerHTML = `
      <div class="hwa-icon">${{icon}}</div>
      <div class="hwa-body">
        <div class="hwa-title">${{a.region}} — ${{label}}</div>
        <div class="hwa-detail">${{detail}}</div>
      </div>
      <button class="hwa-close" onclick="this.closest('.hwa-toast').remove()">✕</button>
      <div class="hwa-bar"></div>
    `;
    container.appendChild(toast);

    // 8초 후 자동 제거
    setTimeout(function() {{
      if (toast.parentNode) {{
        toast.style.transition = 'opacity .4s, transform .4s';
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(120%)';
        setTimeout(function() {{ if (toast.parentNode) toast.remove(); }}, 400);
      }}
    }}, 8000 + i * 600);
  }});
}})();
</script>
</body></html>
""", height=1, scrolling=False)
