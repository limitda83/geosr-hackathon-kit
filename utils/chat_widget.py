import streamlit as st
import streamlit.components.v1 as components


def inject():
    api_key = st.secrets.get("OPENAI_API_KEY", "")

    components.html(f"""
<script>
(function() {{
    var doc = window.parent.document;
    if (doc.getElementById('chat-fab')) return;

    // ── CSS ──
    var s = doc.createElement('style');
    s.textContent = `
        #chat-fab {{
            position: fixed !important;
            right: 28px;
            bottom: 32px;
            width: 56px;
            height: 56px;
            border-radius: 50%;
            background: linear-gradient(135deg,#005f6e,#00c2d4);
            color: white;
            font-size: 24px;
            border: none;
            cursor: pointer;
            box-shadow: 0 4px 20px rgba(0,194,212,0.45);
            z-index: 999999;
            transition: transform .2s, box-shadow .2s;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        #chat-fab:hover {{ transform:scale(1.1); box-shadow:0 6px 28px rgba(0,194,212,0.65); }}

        #chat-panel {{
            position: fixed !important;
            top: 0;
            right: -400px;
            width: 380px;
            height: 100vh;
            background: #020d1a;
            z-index: 999998;
            display: flex;
            flex-direction: column;
            border-left: 1px solid rgba(0,194,212,0.15);
            box-shadow: -4px 0 40px rgba(0,0,0,0.5);
            transition: right .3s cubic-bezier(.4,0,.2,1);
        }}
        #chat-panel.open {{ right: 0 !important; }}

        #chat-header {{
            background: #041529;
            color: #e8f4f8;
            padding: 16px 20px;
            font-size: 15px;
            font-weight: 700;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid rgba(0,194,212,0.12);
            flex-shrink: 0;
            font-family: 'Pretendard','Noto Sans KR',sans-serif;
        }}
        #chat-close {{
            background: none; border: none;
            color: #7aacbf; font-size: 20px; cursor: pointer;
        }}
        #chat-close:hover {{ color: #00e5ff; }}

        #chat-msgs {{
            flex: 1;
            overflow-y: auto;
            padding: 14px;
            display: flex;
            flex-direction: column;
            gap: 9px;
        }}
        #chat-msgs::-webkit-scrollbar {{ width: 4px; }}
        #chat-msgs::-webkit-scrollbar-thumb {{ background: rgba(0,194,212,0.2); border-radius: 4px; }}

        .cm-user {{
            background: linear-gradient(135deg,#005f6e,#00a896);
            color: white;
            padding: 9px 13px;
            border-radius: 14px 14px 4px 14px;
            font-size: 13px;
            line-height: 1.6;
            align-self: flex-end;
            max-width: 83%;
            word-break: keep-all;
            font-family: 'Pretendard','Noto Sans KR',sans-serif;
        }}
        .cm-bot {{
            background: rgba(0,194,212,0.07);
            color: #c8e6f0;
            padding: 9px 13px;
            border-radius: 14px 14px 14px 4px;
            font-size: 13px;
            line-height: 1.6;
            align-self: flex-start;
            max-width: 83%;
            border: 1px solid rgba(0,194,212,0.1);
            word-break: keep-all;
            font-family: 'Pretendard','Noto Sans KR',sans-serif;
        }}
        .cm-bot.thinking {{ color: #3a6a7a; font-style: italic; }}

        #chat-input-row {{
            display: flex;
            padding: 11px 13px;
            gap: 8px;
            border-top: 1px solid rgba(0,194,212,0.1);
            background: #041529;
            flex-shrink: 0;
        }}
        #chat-inp {{
            flex: 1;
            background: rgba(0,194,212,0.06);
            border: 1px solid rgba(0,194,212,0.18);
            border-radius: 10px;
            padding: 9px 13px;
            font-size: 13px;
            color: #e8f4f8;
            outline: none;
            font-family: 'Pretendard','Noto Sans KR',sans-serif;
        }}
        #chat-inp::placeholder {{ color: rgba(200,230,240,0.3); }}
        #chat-inp:focus {{ border-color: #00c2d4; background: rgba(0,194,212,0.1); }}
        #chat-send {{
            background: linear-gradient(135deg,#005f6e,#00c2d4);
            color: white; border: none; border-radius: 10px;
            padding: 9px 15px; cursor: pointer;
            font-size: 14px; font-weight: 700;
            font-family: 'Pretendard','Noto Sans KR',sans-serif;
        }}
        #chat-send:hover {{ opacity: .85; }}
    `;
    doc.head.appendChild(s);

    // ── HTML ──
    var fab = doc.createElement('button');
    fab.id = 'chat-fab';
    fab.innerHTML = '💬';
    doc.body.appendChild(fab);

    var panel = doc.createElement('div');
    panel.id = 'chat-panel';
    panel.innerHTML = `
        <div id="chat-header">
            🌊 고수온 AI 챗봇
            <button id="chat-close">✕</button>
        </div>
        <div id="chat-msgs">
            <div class="cm-bot">안녕하세요! 고수온 분석 챗봇입니다.<br>관심지역, 수온 데이터, 분석 결과에 대해 질문하세요.</div>
        </div>
        <div id="chat-input-row">
            <input id="chat-inp" type="text" placeholder="질문을 입력하세요..."/>
            <button id="chat-send">전송</button>
        </div>
    `;
    doc.body.appendChild(panel);

    // ── 이벤트 ──
    var history = [
        {{role:'system', content:'당신은 고수온 연안재해 모니터링 시스템의 해양 기상 전문 AI입니다. 관심지역, 수온 분석, 재난 데이터에 대해 간결하게 답하세요. 한국어로 답변하세요.'}}
    ];

    fab.onclick = function() {{
        panel.classList.toggle('open');
        fab.innerHTML = panel.classList.contains('open') ? '✕' : '💬';
    }};
    doc.getElementById('chat-close').onclick = function() {{
        panel.classList.remove('open');
        fab.innerHTML = '💬';
    }};

    async function send() {{
        var inp = doc.getElementById('chat-inp');
        var msgs = doc.getElementById('chat-msgs');
        var text = inp.value.trim();
        if (!text) return;

        inp.value = '';
        msgs.innerHTML += '<div class="cm-user">' + text + '</div>';

        var loading = doc.createElement('div');
        loading.className = 'cm-bot thinking';
        loading.id = 'cm-loading';
        loading.textContent = '분석 중...';
        msgs.appendChild(loading);
        msgs.scrollTop = msgs.scrollHeight;

        history.push({{role:'user', content:text}});

        try {{
            var apiKey = '{api_key}';
            if (!apiKey) throw new Error('API 키 없음');

            var res = await fetch('https://api.openai.com/v1/chat/completions', {{
                method: 'POST',
                headers: {{
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer ' + apiKey
                }},
                body: JSON.stringify({{
                    model: 'gpt-4o-mini',
                    messages: history,
                    max_tokens: 512
                }})
            }});
            var data = await res.json();
            var reply = data.choices[0].message.content;
            history.push({{role:'assistant', content:reply}});

            var el = doc.getElementById('cm-loading');
            if (el) {{ el.className='cm-bot'; el.removeAttribute('id'); el.innerHTML=reply.replace(/\\n/g,'<br>'); }}
        }} catch(e) {{
            var el = doc.getElementById('cm-loading');
            if (el) {{ el.className='cm-bot'; el.removeAttribute('id'); el.textContent='⚠️ ' + e.message; }}
        }}
        msgs.scrollTop = msgs.scrollHeight;
    }}

    doc.getElementById('chat-send').onclick = send;
    doc.getElementById('chat-inp').addEventListener('keydown', function(e) {{
        if (e.key === 'Enter') send();
    }});
}})();
</script>
""", height=1, scrolling=False)
