<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>캡챠 풀이 - 포인트 적립</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            width: 100%;
            max-width: 600px;
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 12px;
            text-align: center;
        }
        .header h1 { font-size: 18px; margin-bottom: 3px; }
        .header p { opacity: 0.9; font-size: 12px; }
        
        .content { padding: 15px; }
        
        /* 로그인 폼 */
        .login-form input {
            width: 100%;
            padding: 15px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-size: 16px;
            margin-bottom: 15px;
            transition: border-color 0.3s;
        }
        .login-form input:focus {
            outline: none;
            border-color: #667eea;
        }
        .btn {
            width: 100%;
            padding: 12px;
            border: none;
            border-radius: 10px;
            font-size: 14px;
            font-weight: bold;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .btn:active { transform: scale(0.98); }
        .btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
        }
        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .btn-success {
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
            color: white;
        }
        .btn-danger {
            background: #e74c3c;
            color: white;
        }
        .btn-secondary {
            background: #95a5a6;
            color: white;
        }
        
        /* 대시보드 */
        .dashboard { display: none; }
        .stats {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
            margin-bottom: 10px;
        }
        .stat-card {
            background: #f8f9fa;
            padding: 8px;
            border-radius: 8px;
            text-align: center;
        }
        .stat-card .value {
            font-size: 18px;
            font-weight: bold;
            color: #667eea;
        }
        .stat-card .label {
            color: #666;
            font-size: 11px;
        }
        
        /* 질문 표시 */
        .question-box {
            background: #fff3cd;
            border: 2px solid #ffc107;
            border-radius: 10px;
            padding: 12px;
            margin-bottom: 10px;
            text-align: center;
            font-size: 16px;
            font-weight: bold;
            color: #856404;
        }
        
        /* 작업 영역 */
        .work-area {
            display: none;
            margin-top: 10px;
        }
        .screenshot-container {
            background: #f0f0f0;
            border-radius: 12px;
            padding: 8px;
            margin-bottom: 10px;
            min-height: 250px;
            display: flex;
            justify-content: center;
            align-items: center;
            overflow: auto;
            position: relative;
        }
        .screenshot-container img {
            max-width: 100%;
            min-width: 100%;
            border-radius: 8px;
        }
        
        /* 결과 오버레이 */
        .result-overlay {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            display: none;
            justify-content: center;
            align-items: center;
            border-radius: 12px;
            font-size: 32px;
            font-weight: bold;
            z-index: 10;
            flex-direction: column;
            gap: 10px;
        }
        .result-overlay.show {
            display: flex;
        }
        .result-overlay.correct {
            background: rgba(39, 174, 96, 0.9);
            color: white;
        }
        .result-overlay.wrong {
            background: rgba(231, 76, 60, 0.9);
            color: white;
        }
        .result-overlay.loading {
            background: rgba(0, 0, 0, 0.75);
            color: white;
            font-size: 18px;
        }
        
        /* 로딩 스피너 */
        .spinner {
            width: 40px;
            height: 40px;
            border: 4px solid rgba(255,255,255,0.3);
            border-top-color: white;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        .hidden { display: none !important; }
        .answer-form {
            display: flex;
            gap: 10px;
        }
        .answer-form input {
            flex: 1;
            padding: 15px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-size: 18px;
            text-align: center;
            letter-spacing: 3px;
        }
        .answer-form input:focus {
            outline: none;
            border-color: #667eea;
        }
        .answer-form input:disabled {
            background: #f0f0f0;
            cursor: not-allowed;
        }
        .answer-form button {
            padding: 15px 25px;
        }
        
        /* 상태 표시 */
        .status {
            text-align: center;
            padding: 8px;
            color: #666;
            font-size: 13px;
        }
        .status.waiting { color: #f39c12; }
        .status.working { color: #3498db; }
        .status.success { color: #27ae60; }
        .status.error { color: #e74c3c; }
        
        /* 메시지 */
        .message {
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 15px;
            text-align: center;
            display: none;
        }
        .message.success { background: #d4edda; color: #155724; }
        .message.error { background: #f8d7da; color: #721c24; }
        .message.info { background: #e7f1ff; color: #004085; }
        
        .hidden { display: none !important; }
        
        /* 로딩 */
        .loading {
            display: inline-block;
            width: 20px;
            height: 20px;
            border: 3px solid rgba(102,126,234,.3);
            border-radius: 50%;
            border-top-color: #667eea;
            animation: spin 1s ease-in-out infinite;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        
        /* TTS 버튼 */
        .tts-btn {
            background: none;
            border: none;
            font-size: 24px;
            cursor: pointer;
            padding: 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>💰 캡챠 풀이</h1>
            <p>문자를 입력하고 포인트를 적립하세요!</p>
        </div>
        
        <div class="content">
            <div id="message" class="message"></div>
            
            <!-- 로그인 -->
            <div id="login-section" class="login-form">
                <input type="text" id="user-id" placeholder="아이디">
                <input type="password" id="password" placeholder="비밀번호">
                <button class="btn btn-primary" onclick="login()">로그인 / 자동가입</button>
            </div>
            
            <!-- 대시보드 -->
            <div id="dashboard" class="dashboard">
                <div class="stats">
                    <div class="stat-card">
                        <div class="value" id="rewards">0</div>
                        <div class="label">보유 포인트</div>
                    </div>
                    <div class="stat-card">
                        <div class="value" id="solved">0</div>
                        <div class="label">해결 횟수</div>
                    </div>
                </div>
                
                <button id="start-btn" class="btn btn-success" onclick="startWork()">
                    🚀 작업 시작하기
                </button>
                <button id="stop-btn" class="btn btn-danger hidden" onclick="stopWork()">
                    ⏹ 작업 종료
                </button>
                
                <!-- 작업 영역 -->
                <div id="work-area" class="work-area">
                    <div id="status-text" class="status waiting">⏳ 작업 대기 중... (브라우저 준비 중)</div>
                    
                    <div id="captcha-section" class="hidden">
                        <div id="question-box" class="question-box">
                            영수증을 보고 질문에 답하세요
                        </div>
                        
                        <div class="screenshot-container">
                            <img id="screenshot" src="" alt="캡챠 이미지">
                            <div id="result-overlay" class="result-overlay hidden"></div>
                        </div>
                        
                        <div class="answer-form">
                            <input type="text" id="answer-input" placeholder="정답을 입력하세요." 
                                   onkeypress="if(event.key==='Enter')submitAnswer()">
                            <button class="tts-btn" onclick="refreshScreenshot()" title="새로고침">🔄</button>
                            <button class="tts-btn" onclick="speakText()" title="음성으로 듣기">🔊</button>
                        </div>
                        <button class="btn btn-primary" style="margin-top:10px" onclick="submitAnswer()">확인</button>
                    </div>
                </div>
                
                <button class="btn btn-secondary" style="margin-top:20px" onclick="logout()">로그아웃</button>
            </div>
        </div>
    </div>

    <script>
        const API_SERVER = 'https://capapi-production.up.railway.app';
        
        let currentUser = null;
        let pollInterval = null;
        let isWorking = false;
        let lastMessageShown = '';  // 중복 메시지 방지
        let isWaitingResult = false;  // 답변 제출 후 결과 대기 중
        let lastScreenshot = '';  // 이전 스크린샷 (변경 감지용)
        
        // 로그인
        async function login() {
            const userId = document.getElementById('user-id').value.trim();
            const password = document.getElementById('password').value;
            
            if (!userId || !password) {
                showMessage('아이디와 비밀번호를 입력하세요', 'error');
                return;
            }
            
            try {
                const resp = await fetch(`${API_SERVER}/api/login`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({user_id: userId, password})
                });
                const data = await resp.json();
                
                if (data.success) {
                    currentUser = {user_id: userId, ...data};
                    localStorage.setItem('user', JSON.stringify(currentUser));
                    showDashboard();
                } else {
                    showMessage(data.message || '로그인 실패', 'error');
                }
            } catch (e) {
                showMessage('서버 연결 실패', 'error');
            }
        }
        
        // 대시보드 표시
        function showDashboard() {
            document.getElementById('login-section').classList.add('hidden');
            document.getElementById('dashboard').style.display = 'block';
            updateStats();
        }
        
        // 통계 업데이트
        async function updateStats() {
            if (!currentUser) return;
            
            try {
                const resp = await fetch(`${API_SERVER}/api/user/${currentUser.user_id}`);
                const data = await resp.json();
                
                if (data.success) {
                    document.getElementById('rewards').textContent = data.user.rewards.toLocaleString();
                    document.getElementById('solved').textContent = data.user.solved_count;
                }
            } catch (e) {}
        }
        
        // 작업 시작
        async function startWork() {
            if (!currentUser) return;
            
            try {
                const resp = await fetch(`${API_SERVER}/api/session/start`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({user_id: currentUser.user_id})
                });
                const data = await resp.json();
                
                if (data.success) {
                    isWorking = true;
                    lastMessageShown = '';
                    isWaitingResult = false;
                    lastScreenshot = '';
                    
                    document.getElementById('start-btn').classList.add('hidden');
                    document.getElementById('stop-btn').classList.remove('hidden');
                    document.getElementById('work-area').style.display = 'block';
                    
                    setStatus('waiting', '⏳ 작업 대기 중... (브라우저 준비 중)');
                    
                    // 폴링 시작 (2초마다)
                    pollInterval = setInterval(pollSession, 2000);
                    pollSession(); // 즉시 한 번 호출
                }
            } catch (e) {
                showMessage('작업 시작 실패', 'error');
            }
        }
        
        // 세션 상태 폴링 - 수정된 API 호출
        async function pollSession() {
            if (!currentUser || !isWorking) return;
            
            try {
                // 올바른 API 경로: /api/session/poll/<user_id>
                const resp = await fetch(`${API_SERVER}/api/session/poll/${currentUser.user_id}`);
                const data = await resp.json();
                
                if (!data.success) {
                    setStatus('waiting', '⏳ 세션 준비 중...');
                    return;
                }
                
                // 메시지가 있으면 처리
                if (data.message) {
                    if (data.message.includes('타임아웃') || data.message.includes('종료')) {
                        showMessage(data.message, 'error');
                        stopWork();
                        return;
                    }
                }
                
                // 스크린샷이 있으면 처리
                if (data.screenshot) {
                    // 새로운 스크린샷인지 확인
                    const isNewScreenshot = data.screenshot !== lastScreenshot;
                    
                    if (isWaitingResult && isNewScreenshot) {
                        // 결과 대기 중이었고 새 스크린샷이 왔다 = 결과 처리
                        if (data.message && data.message.includes('틀렸')) {
                            // 틀림
                            showResultOverlay('wrong', '❌ 틀렸습니다!');
                            setTimeout(() => {
                                hideResultOverlay();
                                updateScreenshot(data);
                                isWaitingResult = false;
                                disableInput(false);
                            }, 1500);
                        } else {
                            // 맞음 (새 문제로 넘어감)
                            showResultOverlay('correct', '✅ 정답!');
                            updateStats();
                            setTimeout(() => {
                                hideResultOverlay();
                                updateScreenshot(data);
                                isWaitingResult = false;
                                disableInput(false);
                            }, 1500);
                        }
                        lastScreenshot = data.screenshot;
                    } else if (!isWaitingResult) {
                        // 일반 상태 - 스크린샷 표시
                        updateScreenshot(data);
                        lastScreenshot = data.screenshot;
                    }
                } else {
                    setStatus('waiting', '⏳ 다음 작업 대기 중...');
                    document.getElementById('captcha-section').classList.add('hidden');
                }
                
            } catch (e) {
                console.error('Poll error:', e);
            }
        }
        
        // 스크린샷 업데이트 함수
        function updateScreenshot(data) {
            setStatus('working', '📝 캡챠를 입력하세요!');
            document.getElementById('screenshot').src = 'data:image/png;base64,' + data.screenshot;
            document.getElementById('captcha-section').classList.remove('hidden');
            document.getElementById('answer-input').focus();
            
            // 질문 표시
            if (data.message && !data.message.includes('틀렸') && !data.message.includes('타임아웃')) {
                document.getElementById('question-box').textContent = data.message;
            }
        }
        
        // 결과 오버레이 표시
        function showResultOverlay(type, text) {
            const overlay = document.getElementById('result-overlay');
            overlay.className = 'result-overlay show ' + type;
            
            if (type === 'loading') {
                overlay.innerHTML = '<div class="spinner"></div><div>' + text + '</div>';
            } else {
                overlay.innerHTML = text;
            }
        }
        
        // 결과 오버레이 숨기기
        function hideResultOverlay() {
            const overlay = document.getElementById('result-overlay');
            overlay.className = 'result-overlay';
            overlay.innerHTML = '';
        }
        
        // 입력 비활성화/활성화
        function disableInput(disabled) {
            document.getElementById('answer-input').disabled = disabled;
            const confirmBtn = document.querySelector('#captcha-section .btn-primary');
            if (confirmBtn) confirmBtn.disabled = disabled;
        }
        
        // 답변 제출 - 수정된 API 호출
        async function submitAnswer() {
            const answer = document.getElementById('answer-input').value.trim();
            
            if (!answer) {
                showMessage('답변을 입력하세요', 'error');
                return;
            }
            
            // 이미 대기 중이면 무시
            if (isWaitingResult) return;
            
            try {
                // 로딩 상태 표시
                isWaitingResult = true;
                showResultOverlay('loading', '⏳ 확인 중...');
                disableInput(true);
                
                // 올바른 API 경로: /api/session/submit-answer
                const resp = await fetch(`${API_SERVER}/api/session/submit-answer`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        user_id: currentUser.user_id,
                        answer: answer
                    })
                });
                const data = await resp.json();
                
                if (data.success) {
                    document.getElementById('answer-input').value = '';
                    setStatus('working', '⏳ 답변 확인 중...');
                    lastMessageShown = '';
                    // 결과는 pollSession에서 처리
                } else {
                    showMessage('답변 제출 실패', 'error');
                    isWaitingResult = false;
                    hideResultOverlay();
                    disableInput(false);
                }
            } catch (e) {
                showMessage('답변 제출 실패', 'error');
                isWaitingResult = false;
                hideResultOverlay();
                disableInput(false);
            }
        }
        
        // 스크린샷 새로고침
        function refreshScreenshot() {
            pollSession();
        }
        
        // TTS (간단한 알림)
        function speakText() {
            showMessage('음성 기능은 준비 중입니다', 'info');
        }
        
        // 작업 종료
        async function stopWork() {
            if (pollInterval) {
                clearInterval(pollInterval);
                pollInterval = null;
            }
            
            isWorking = false;
            isWaitingResult = false;
            lastScreenshot = '';
            hideResultOverlay();
            disableInput(false);
            
            if (currentUser) {
                try {
                    await fetch(`${API_SERVER}/api/session/end`, {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({user_id: currentUser.user_id})
                    });
                } catch (e) {}
            }
            
            document.getElementById('start-btn').classList.remove('hidden');
            document.getElementById('stop-btn').classList.add('hidden');
            document.getElementById('work-area').style.display = 'none';
            document.getElementById('captcha-section').classList.add('hidden');
            
            updateStats();
        }
        
        // 상태 표시
        function setStatus(type, text) {
            const el = document.getElementById('status-text');
            el.className = 'status ' + type;
            el.textContent = text;
        }
        
        // 메시지 표시
        function showMessage(text, type) {
            const el = document.getElementById('message');
            el.className = 'message ' + type;
            el.textContent = text;
            el.style.display = 'block';
            
            setTimeout(() => el.style.display = 'none', 3000);
        }
        
        // 로그아웃
        function logout() {
            stopWork();
            currentUser = null;
            localStorage.removeItem('user');
            
            document.getElementById('login-section').classList.remove('hidden');
            document.getElementById('dashboard').style.display = 'none';
        }
        
        // 초기화
        window.onload = function() {
            const saved = localStorage.getItem('user');
            if (saved) {
                currentUser = JSON.parse(saved);
                showDashboard();
            }
        };
    </script>
</body>
</html>
