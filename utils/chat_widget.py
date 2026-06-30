import streamlit as st
import streamlit.components.v1 as components


def inject():
    api_key = st.secrets.get("OPENAI_API_KEY", "")

    components.html(f"""
<script>
(function() {{
  var doc = window.parent.document;
  if (doc.getElementById('chat-fab')) return;

  var s = doc.createElement('style');
  s.textContent = `
    #chat-fab {{
      position: fixed !important;
      right: 28px !important; bottom: 32px !important;
      width: 56px !important; height: 56px !important;
      border-radius: 50% !important;
      background: linear-gradient(135deg,#005f6e,#00c2d4) !important;
      color: white !important; font-size: 26px !important;
      border: none !important; cursor: pointer !important;
      box-shadow: 0 4px 20px rgba(0,194,212,0.45) !important;
      z-index: 999999 !important;
      display: flex !important; align-items: center !important; justify-content: center !important;
      transition: transform .2s, box-shadow .2s !important;
    }}
    #chat-fab:hover {{ transform: scale(1.1) !important; }}
    #chat-panel {{
      position: fixed !important;
      top: 0 !important; right: -400px !important;
      width: 380px !important; height: 100vh !important;
      background: #020d1a !important;
      z-index: 999998 !important;
      display: flex !important; flex-direction: column !important;
      border-left: 1px solid rgba(0,194,212,0.15) !important;
      box-shadow: -4px 0 40px rgba(0,0,0,0.5) !important;
      transition: right .3s cubic-bezier(.4,0,.2,1) !important;
    }}
    #chat-panel.open {{ right: 0 !important; }}
    #chat-head {{
      background: #041529 !important; color: #e8f4f8 !important;
      padding: 16px 20px !important; font-weight: 700 !important; font-size: 15px !important;
      display: flex !important; justify-content: space-between !important; align-items: center !important;
      border-bottom: 1px solid rgba(0,194,212,0.12) !important; flex-shrink: 0 !important;
      font-family: 'Noto Sans KR', sans-serif !important;
    }}
    #chat-x {{ background:none !important;border:none !important;color:#7aacbf !important;font-size:20px !important;cursor:pointer !important; }}
    #chat-x:hover {{ color:#00e5ff !important; }}
    #chat-msgs {{
      flex:1 !important; overflow-y:auto !important; padding:14px !important;
      display:flex !important; flex-direction:column !important; gap:9px !important;
    }}
    #chat-msgs::-webkit-scrollbar {{ width:4px; }}
    #chat-msgs::-webkit-scrollbar-thumb {{ background:rgba(0,194,212,0.2);border-radius:4px; }}
    .cm-user {{
      background:linear-gradient(135deg,#005f6e,#00a896) !important; color:white !important;
      padding:9px 13px !important; border-radius:14px 14px 4px 14px !important;
      font-size:13px !important; line-height:1.6 !important; align-self:flex-end !important;
      max-width:83% !important; word-break:keep-all !important;
      font-family:'Noto Sans KR',sans-serif !important;
    }}
    .cm-bot {{
      background:rgba(0,194,212,0.07) !important; color:#c8e6f0 !important;
      padding:9px 13px !important; border-radius:14px 14px 14px 4px !important;
      font-size:13px !important; line-height:1.6 !important; align-self:flex-start !important;
      max-width:83% !important; border:1px solid rgba(0,194,212,0.1) !important;
      word-break:keep-all !important; font-family:'Noto Sans KR',sans-serif !important;
    }}
    .cm-thinking {{ color:#3a6a7a !important; font-style:italic !important; }}
    #chat-row {{
      display:flex !important; padding:11px 13px !important; gap:8px !important;
      border-top:1px solid rgba(0,194,212,0.1) !important;
      background:#041529 !important; flex-shrink:0 !important;
    }}
    #chat-inp {{
      flex:1 !important; background:rgba(0,194,212,0.06) !important;
      border:1px solid rgba(0,194,212,0.18) !important; border-radius:10px !important;
      padding:9px 13px !important; font-size:13px !important; color:#e8f4f8 !important; outline:none !important;
      font-family:'Noto Sans KR',sans-serif !important;
    }}
    #chat-inp:focus {{ border-color:#00c2d4 !important; }}
    #chat-inp::placeholder {{ color:rgba(200,230,240,0.3); }}
    #chat-btn {{
      background:linear-gradient(135deg,#005f6e,#00c2d4) !important;
      color:white !important; border:none !important; border-radius:10px !important;
      padding:9px 15px !important; cursor:pointer !important; font-size:14px !important; font-weight:700 !important;
      font-family:'Noto Sans KR',sans-serif !important;
    }}
    #chat-btn:hover {{ opacity:.85 !important; }}
  `;
  doc.head.appendChild(s);

  var fab = doc.createElement('button');
  fab.id = 'chat-fab'; fab.innerHTML = '💬';
  doc.body.appendChild(fab);

  var panel = doc.createElement('div');
  panel.id = 'chat-panel';
  panel.innerHTML = `
    <div id="chat-head">
      🌊 고수온 AI 챗봇
      <button id="chat-x">✕</button>
    </div>
    <div id="chat-msgs">
      <div class="cm-bot">안녕하세요! 고수온 분석 챗봇입니다.<br>관심지역, 수온 데이터, 분석 결과에 대해 질문하세요.</div>
    </div>
    <div id="chat-row">
      <input id="chat-inp" type="text" placeholder="질문을 입력하세요..."/>
      <button id="chat-btn">전송</button>
    </div>
  `;
  doc.body.appendChild(panel);

  var history = [
    {{role:'system', content:'당신은 고수온 연안재해 모니터링 시스템의 해양 기상 전문 AI입니다. 한국어로 간결하게 답하세요.'}}
  ];

  fab.onclick = function() {{
    panel.classList.toggle('open');
    fab.innerHTML = panel.classList.contains('open') ? '✕' : '💬';
  }};
  doc.getElementById('chat-x').onclick = function() {{
    panel.classList.remove('open'); fab.innerHTML = '💬';
  }};

  async function send() {{
    var inp = doc.getElementById('chat-inp');
    var msgs = doc.getElementById('chat-msgs');
    var text = inp.value.trim();
    if (!text) return;
    inp.value = '';
    msgs.innerHTML += '<div class="cm-user">' + text + '</div>';
    var el = doc.createElement('div');
    el.className = 'cm-bot cm-thinking'; el.id = 'cm-load'; el.textContent = '분석 중...';
    msgs.appendChild(el); msgs.scrollTop = msgs.scrollHeight;
    history.push({{role:'user', content:text}});
    try {{
      var res = await fetch('https://api.openai.com/v1/chat/completions', {{
        method: 'POST',
        headers: {{'Content-Type':'application/json','Authorization':'Bearer {api_key}'}},
        body: JSON.stringify({{model:'gpt-4o-mini', messages:history, max_tokens:512}})
      }});
      var data = await res.json();
      var reply = data.choices[0].message.content;
      history.push({{role:'assistant', content:reply}});
      var l = doc.getElementById('cm-load');
      if (l) {{ l.className='cm-bot'; l.removeAttribute('id'); l.innerHTML=reply.replace(/\\n/g,'<br>'); }}
    }} catch(e) {{
      var l = doc.getElementById('cm-load');
      if (l) {{ l.className='cm-bot'; l.removeAttribute('id'); l.textContent='⚠️ '+e.message; }}
    }}
    msgs.scrollTop = msgs.scrollHeight;
  }}

  doc.getElementById('chat-btn').onclick = send;
  doc.getElementById('chat-inp').addEventListener('keydown', function(e) {{
    if (e.key === 'Enter') send();
  }});
}})();
</script>
""", height=0)
