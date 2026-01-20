"""
캡챠 풀이 API 서버 v2
- 작업자별 세션 관리
- Worker ↔ 작업자 중계
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import psycopg
from psycopg.rows import dict_row
import os
from datetime import datetime, timedelta
import hashlib
import secrets

app = Flask(__name__)
CORS(app, origins="*")

DATABASE_URL = os.environ.get('DATABASE_URL')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin1234')
SESSION_TIMEOUT = 300  # 5분


def get_db():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def init_db():
    conn = get_db()
    cur = conn.cursor()
    
    # 유저
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(50) UNIQUE NOT NULL,
            password_hash VARCHAR(128) NOT NULL,
            rewards INTEGER DEFAULT 0,
            solved_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 키워드
    cur.execute('''
        CREATE TABLE IF NOT EXISTS keywords (
            id SERIAL PRIMARY KEY,
            keyword VARCHAR(100) NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            priority INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # UID 목록 (수집된 스토어)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS uids (
            id SERIAL PRIMARY KEY,
            uid VARCHAR(100) UNIQUE NOT NULL,
            store_name VARCHAR(200),
            store_url VARCHAR(500),
            keyword VARCHAR(100),
            status VARCHAR(20) DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 작업자 세션
    cur.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            id SERIAL PRIMARY KEY,
            session_id VARCHAR(100) UNIQUE NOT NULL,
            user_id VARCHAR(50) NOT NULL,
            status VARCHAR(20) DEFAULT 'waiting',
            current_uid_id INTEGER,
            screenshot_base64 TEXT,
            user_answer VARCHAR(100),
            last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 수집 결과
    cur.execute('''
        CREATE TABLE IF NOT EXISTS results (
            id SERIAL PRIMARY KEY,
            uid VARCHAR(100),
            store_name VARCHAR(200),
            seller_name VARCHAR(200),
            business_number VARCHAR(50),
            representative VARCHAR(100),
            phone VARCHAR(50),
            email VARCHAR(100),
            address TEXT,
            store_url VARCHAR(500),
            solved_by VARCHAR(50),
            used BOOLEAN DEFAULT FALSE,
            memo TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 리워드 히스토리
    cur.execute('''
        CREATE TABLE IF NOT EXISTS rewards_history (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(50) NOT NULL,
            amount INTEGER NOT NULL,
            reason VARCHAR(200),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 출금
    cur.execute('''
        CREATE TABLE IF NOT EXISTS withdrawals (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(50) NOT NULL,
            amount INTEGER NOT NULL,
            bank_name VARCHAR(50),
            account_number VARCHAR(50),
            account_holder VARCHAR(50),
            status VARCHAR(20) DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    cur.close()
    conn.close()
    print("✅ DB 초기화 완료")


# ==================== 유저 API ====================
@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    user_id = data.get('user_id', '').strip()
    password = data.get('password', '')
    
    if not user_id or not password:
        return jsonify({'success': False, 'message': '아이디/비밀번호 필요'})
    
    pw_hash = hashlib.sha256(password.encode()).hexdigest()
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('SELECT id FROM users WHERE user_id = %s', (user_id,))
        if cur.fetchone():
            return jsonify({'success': False, 'message': '이미 존재하는 아이디'})
        
        cur.execute('INSERT INTO users (user_id, password_hash) VALUES (%s, %s)', (user_id, pw_hash))
        conn.commit()
        return jsonify({'success': True})
    finally:
        cur.close()
        conn.close()


@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    user_id = data.get('user_id', '').strip()
    password = data.get('password', '')
    
    if not user_id or not password:
        return jsonify({'success': False, 'message': '아이디/비밀번호 필요'})
    
    pw_hash = hashlib.sha256(password.encode()).hexdigest()
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('SELECT * FROM users WHERE user_id = %s', (user_id,))
        user = cur.fetchone()
        
        if not user:
            # 자동 가입
            cur.execute('INSERT INTO users (user_id, password_hash) VALUES (%s, %s)', (user_id, pw_hash))
            conn.commit()
            return jsonify({'success': True, 'user_id': user_id, 'rewards': 0, 'solved_count': 0})
        
        if user['password_hash'] != pw_hash:
            return jsonify({'success': False, 'message': '비밀번호 불일치'})
        
        return jsonify({
            'success': True,
            'user_id': user['user_id'],
            'rewards': user['rewards'],
            'solved_count': user['solved_count']
        })
    finally:
        cur.close()
        conn.close()


@app.route('/api/user/<user_id>')
def get_user(user_id):
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('SELECT user_id, rewards, solved_count FROM users WHERE user_id = %s', (user_id,))
        user = cur.fetchone()
        if not user:
            return jsonify({'success': False})
        return jsonify({'success': True, 'user': dict(user)})
    finally:
        cur.close()
        conn.close()


# ==================== 작업자 세션 API ====================
@app.route('/api/session/start', methods=['POST'])
def start_session():
    """작업자가 작업 시작 요청"""
    data = request.json
    user_id = data.get('user_id')
    
    if not user_id:
        return jsonify({'success': False, 'message': '로그인 필요'})
    
    session_id = secrets.token_hex(16)
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        # 기존 세션 정리
        cur.execute("DELETE FROM sessions WHERE user_id = %s", (user_id,))
        
        # 새 세션 생성
        cur.execute('''
            INSERT INTO sessions (session_id, user_id, status)
            VALUES (%s, %s, 'waiting')
        ''', (session_id, user_id))
        conn.commit()
        
        return jsonify({'success': True, 'session_id': session_id})
    finally:
        cur.close()
        conn.close()


@app.route('/api/session/<session_id>/status')
def get_session_status(session_id):
    """작업자가 현재 세션 상태 확인 (폴링)"""
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('SELECT * FROM sessions WHERE session_id = %s', (session_id,))
        session = cur.fetchone()
        
        if not session:
            return jsonify({'success': False, 'message': '세션 없음'})
        
        # 타임아웃 체크
        if session['last_activity']:
            elapsed = (datetime.now() - session['last_activity']).total_seconds()
            if elapsed > SESSION_TIMEOUT:
                cur.execute("UPDATE sessions SET status = 'timeout' WHERE session_id = %s", (session_id,))
                conn.commit()
                return jsonify({'success': False, 'message': '세션 타임아웃', 'timeout': True})
        
        return jsonify({
            'success': True,
            'status': session['status'],
            'screenshot': session['screenshot_base64'] if session['status'] == 'captcha' else None
        })
    finally:
        cur.close()
        conn.close()


@app.route('/api/session/<session_id>/answer', methods=['POST'])
def submit_answer(session_id):
    """작업자가 캡챠 답변 제출"""
    data = request.json
    answer = data.get('answer', '').strip()
    
    if not answer:
        return jsonify({'success': False, 'message': '답변 필요'})
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('''
            UPDATE sessions 
            SET user_answer = %s, status = 'answered', last_activity = %s
            WHERE session_id = %s
        ''', (answer, datetime.now(), session_id))
        conn.commit()
        
        return jsonify({'success': True})
    finally:
        cur.close()
        conn.close()


@app.route('/api/session/<session_id>/end', methods=['POST'])
def end_session(session_id):
    """작업자가 작업 종료"""
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute("UPDATE sessions SET status = 'ended' WHERE session_id = %s", (session_id,))
        conn.commit()
        return jsonify({'success': True})
    finally:
        cur.close()
        conn.close()


# ==================== Worker API ====================
@app.route('/api/worker/active-sessions')
def get_active_sessions():
    """Worker가 활성 세션 목록 조회"""
    conn = get_db()
    cur = conn.cursor()
    
    try:
        # waiting 또는 answered 상태인 세션
        cur.execute('''
            SELECT session_id, user_id, status, current_uid_id, user_answer, last_activity
            FROM sessions 
            WHERE status IN ('waiting', 'captcha', 'answered')
            ORDER BY created_at ASC
        ''')
        sessions = cur.fetchall()
        
        # 타임아웃 체크
        result = []
        now = datetime.now()
        for s in sessions:
            if s['last_activity']:
                elapsed = (now - s['last_activity']).total_seconds()
                if elapsed > SESSION_TIMEOUT:
                    cur.execute("UPDATE sessions SET status = 'timeout' WHERE session_id = %s", (s['session_id'],))
                    continue
            result.append(dict(s))
        
        conn.commit()
        return jsonify({'success': True, 'sessions': result})
    finally:
        cur.close()
        conn.close()


@app.route('/api/worker/session/<session_id>/assign-uid', methods=['POST'])
def assign_uid(session_id):
    """Worker가 세션에 UID 할당"""
    data = request.json
    uid_id = data.get('uid_id')
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('''
            UPDATE sessions SET current_uid_id = %s, status = 'working', last_activity = %s
            WHERE session_id = %s
        ''', (uid_id, datetime.now(), session_id))
        
        cur.execute("UPDATE uids SET status = 'processing' WHERE id = %s", (uid_id,))
        conn.commit()
        
        return jsonify({'success': True})
    finally:
        cur.close()
        conn.close()


@app.route('/api/worker/session/<session_id>/screenshot', methods=['POST'])
def upload_screenshot(session_id):
    """Worker가 스크린샷 업로드"""
    data = request.json
    screenshot = data.get('screenshot')
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('''
            UPDATE sessions 
            SET screenshot_base64 = %s, status = 'captcha', user_answer = NULL, last_activity = %s
            WHERE session_id = %s
        ''', (screenshot, datetime.now(), session_id))
        conn.commit()
        
        return jsonify({'success': True})
    finally:
        cur.close()
        conn.close()


@app.route('/api/worker/session/<session_id>/get-answer')
def get_answer(session_id):
    """Worker가 답변 확인"""
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('SELECT user_answer, status FROM sessions WHERE session_id = %s', (session_id,))
        session = cur.fetchone()
        
        if not session:
            return jsonify({'success': False})
        
        if session['status'] == 'answered' and session['user_answer']:
            return jsonify({'success': True, 'answer': session['user_answer']})
        
        return jsonify({'success': True, 'answer': None})
    finally:
        cur.close()
        conn.close()


@app.route('/api/worker/session/<session_id>/complete', methods=['POST'])
def complete_captcha(session_id):
    """Worker가 캡챠 성공 처리 - 결과 저장 + 리워드 지급"""
    data = request.json
    seller_info = data.get('seller_info', {})
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('SELECT * FROM sessions WHERE session_id = %s', (session_id,))
        session = cur.fetchone()
        
        if not session:
            return jsonify({'success': False})
        
        # 결과 저장
        cur.execute('''
            INSERT INTO results (uid, store_name, seller_name, business_number, 
                               representative, phone, email, address, store_url, solved_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            seller_info.get('uid'), seller_info.get('store_name'), seller_info.get('seller_name'),
            seller_info.get('business_number'), seller_info.get('representative'),
            seller_info.get('phone'), seller_info.get('email'),
            seller_info.get('address'), seller_info.get('store_url'), session['user_id']
        ))
        
        # UID 완료 처리
        if session['current_uid_id']:
            cur.execute("UPDATE uids SET status = 'completed' WHERE id = %s", (session['current_uid_id'],))
        
        # 리워드 지급
        reward = 100
        cur.execute('UPDATE users SET rewards = rewards + %s, solved_count = solved_count + 1 WHERE user_id = %s',
                   (reward, session['user_id']))
        cur.execute('INSERT INTO rewards_history (user_id, amount, reason) VALUES (%s, %s, %s)',
                   (session['user_id'], reward, '캡챠 해결'))
        
        # 세션 초기화 (다음 UID 대기)
        cur.execute('''
            UPDATE sessions 
            SET current_uid_id = NULL, screenshot_base64 = NULL, user_answer = NULL, 
                status = 'waiting', last_activity = %s
            WHERE session_id = %s
        ''', (datetime.now(), session_id))
        
        conn.commit()
        return jsonify({'success': True, 'reward': reward})
    finally:
        cur.close()
        conn.close()


@app.route('/api/worker/session/<session_id>/fail', methods=['POST'])
def fail_captcha(session_id):
    """Worker가 캡챠 실패 처리 - 새로고침 후 다시 스크린샷"""
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('''
            UPDATE sessions 
            SET user_answer = NULL, status = 'working', last_activity = %s
            WHERE session_id = %s
        ''', (datetime.now(), session_id))
        conn.commit()
        
        return jsonify({'success': True})
    finally:
        cur.close()
        conn.close()


# ==================== UID 관리 API ====================
@app.route('/api/worker/add-uid', methods=['POST'])
def add_uid():
    """Worker가 UID 추가"""
    data = request.json
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('SELECT id FROM uids WHERE uid = %s', (data.get('uid'),))
        if cur.fetchone():
            return jsonify({'success': False, 'message': '이미 존재'})
        
        cur.execute('''
            INSERT INTO uids (uid, store_name, store_url, keyword)
            VALUES (%s, %s, %s, %s) RETURNING id
        ''', (data.get('uid'), data.get('store_name'), data.get('store_url'), data.get('keyword')))
        
        uid_id = cur.fetchone()['id']
        conn.commit()
        
        return jsonify({'success': True, 'uid_id': uid_id})
    finally:
        cur.close()
        conn.close()


@app.route('/api/worker/pending-uids')
def get_pending_uids():
    """Worker가 처리 안된 UID 목록 조회"""
    limit = request.args.get('limit', 10, type=int)
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('''
            SELECT * FROM uids WHERE status = 'pending'
            ORDER BY created_at ASC LIMIT %s
        ''', (limit,))
        
        return jsonify({'success': True, 'uids': [dict(u) for u in cur.fetchall()]})
    finally:
        cur.close()
        conn.close()


# ==================== 키워드 API ====================
@app.route('/api/keywords')
def get_keywords():
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('SELECT * FROM keywords WHERE is_active = TRUE ORDER BY priority DESC')
        return jsonify({'success': True, 'keywords': [dict(k) for k in cur.fetchall()]})
    finally:
        cur.close()
        conn.close()


# ==================== 어드민 API ====================
@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    data = request.json
    if data.get('password') == ADMIN_PASSWORD:
        return jsonify({'success': True})
    return jsonify({'success': False})


@app.route('/api/admin/stats')
def admin_stats():
    conn = get_db()
    cur = conn.cursor()
    
    try:
        stats = {}
        cur.execute('SELECT COUNT(*) as cnt FROM users')
        stats['total_users'] = cur.fetchone()['cnt']
        
        cur.execute('SELECT COUNT(*) as cnt FROM results')
        stats['total_results'] = cur.fetchone()['cnt']
        
        cur.execute('SELECT COUNT(*) as cnt FROM results WHERE used = FALSE')
        stats['unused_results'] = cur.fetchone()['cnt']
        
        cur.execute("SELECT COUNT(*) as cnt FROM uids WHERE status = 'pending'")
        stats['pending_uids'] = cur.fetchone()['cnt']
        
        cur.execute("SELECT COUNT(*) as cnt FROM sessions WHERE status IN ('waiting', 'captcha', 'answered')")
        stats['active_sessions'] = cur.fetchone()['cnt']
        
        cur.execute("SELECT COUNT(*) as cnt FROM results WHERE DATE(created_at) = CURRENT_DATE")
        stats['today_results'] = cur.fetchone()['cnt']
        
        return jsonify({'success': True, 'stats': stats})
    finally:
        cur.close()
        conn.close()


@app.route('/api/admin/keywords')
def admin_keywords():
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('SELECT * FROM keywords ORDER BY priority DESC, created_at ASC')
        return jsonify({'success': True, 'keywords': [dict(k) for k in cur.fetchall()]})
    finally:
        cur.close()
        conn.close()


@app.route('/api/admin/keywords', methods=['POST'])
def add_keyword():
    data = request.json
    keyword = data.get('keyword', '').strip()
    
    if not keyword:
        return jsonify({'success': False, 'message': '키워드 필요'})
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('INSERT INTO keywords (keyword, priority) VALUES (%s, %s) RETURNING id',
                   (keyword, data.get('priority', 0)))
        keyword_id = cur.fetchone()['id']
        conn.commit()
        return jsonify({'success': True, 'id': keyword_id})
    finally:
        cur.close()
        conn.close()


@app.route('/api/admin/keywords/<int:keyword_id>', methods=['PUT'])
def update_keyword(keyword_id):
    data = request.json
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        for field in ['keyword', 'is_active', 'priority']:
            if field in data:
                cur.execute(f'UPDATE keywords SET {field} = %s WHERE id = %s', (data[field], keyword_id))
        conn.commit()
        return jsonify({'success': True})
    finally:
        cur.close()
        conn.close()


@app.route('/api/admin/keywords/<int:keyword_id>', methods=['DELETE'])
def delete_keyword(keyword_id):
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('DELETE FROM keywords WHERE id = %s', (keyword_id,))
        conn.commit()
        return jsonify({'success': True})
    finally:
        cur.close()
        conn.close()


@app.route('/api/admin/results')
def admin_results():
    page = request.args.get('page', 1, type=int)
    per_page = 50
    used = request.args.get('used', '')
    search = request.args.get('search', '')
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        conditions = []
        params = []
        
        if used == 'true':
            conditions.append('used = TRUE')
        elif used == 'false':
            conditions.append('used = FALSE')
        
        if search:
            conditions.append('(store_name ILIKE %s OR business_number ILIKE %s)')
            params.extend([f'%{search}%', f'%{search}%'])
        
        where = 'WHERE ' + ' AND '.join(conditions) if conditions else ''
        
        cur.execute(f'SELECT * FROM results {where} ORDER BY created_at DESC LIMIT %s OFFSET %s',
                   params + [per_page, (page - 1) * per_page])
        results = cur.fetchall()
        
        cur.execute(f'SELECT COUNT(*) as cnt FROM results {where}', params or None)
        total = cur.fetchone()['cnt']
        
        return jsonify({'success': True, 'results': [dict(r) for r in results], 'total': total})
    finally:
        cur.close()
        conn.close()


@app.route('/api/admin/results/<int:result_id>/update', methods=['POST'])
def update_result(result_id):
    data = request.json
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        if 'used' in data:
            cur.execute('UPDATE results SET used = %s WHERE id = %s', (data['used'], result_id))
        if 'memo' in data:
            cur.execute('UPDATE results SET memo = %s WHERE id = %s', (data['memo'], result_id))
        conn.commit()
        return jsonify({'success': True})
    finally:
        cur.close()
        conn.close()


@app.route('/api/admin/results/export')
def export_results():
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('SELECT * FROM results ORDER BY created_at DESC')
        return jsonify({'success': True, 'results': [dict(r) for r in cur.fetchall()]})
    finally:
        cur.close()
        conn.close()


@app.route('/api/admin/users')
def admin_users():
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('SELECT user_id, rewards, solved_count, created_at FROM users ORDER BY created_at DESC')
        return jsonify({'success': True, 'users': [dict(u) for u in cur.fetchall()]})
    finally:
        cur.close()
        conn.close()


@app.route('/api/admin/users/<user_id>/adjust-rewards', methods=['POST'])
def adjust_rewards(user_id):
    data = request.json
    amount = data.get('amount', 0)
    reason = data.get('reason', '관리자 조정')
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('UPDATE users SET rewards = rewards + %s WHERE user_id = %s', (amount, user_id))
        cur.execute('INSERT INTO rewards_history (user_id, amount, reason) VALUES (%s, %s, %s)',
                   (user_id, amount, reason))
        conn.commit()
        return jsonify({'success': True})
    finally:
        cur.close()
        conn.close()


@app.route('/api/admin/withdrawals')
def admin_withdrawals():
    status = request.args.get('status', 'pending')
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('SELECT * FROM withdrawals WHERE status = %s ORDER BY created_at DESC', (status,))
        return jsonify({'success': True, 'withdrawals': [dict(w) for w in cur.fetchall()]})
    finally:
        cur.close()
        conn.close()


@app.route('/api/admin/withdrawals/<int:wid>/process', methods=['POST'])
def process_withdrawal(wid):
    data = request.json
    action = data.get('action')
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('SELECT * FROM withdrawals WHERE id = %s', (wid,))
        w = cur.fetchone()
        
        if action == 'approve':
            cur.execute("UPDATE withdrawals SET status = 'completed' WHERE id = %s", (wid,))
        elif action == 'reject':
            cur.execute('UPDATE users SET rewards = rewards + %s WHERE user_id = %s', (w['amount'], w['user_id']))
            cur.execute('INSERT INTO rewards_history (user_id, amount, reason) VALUES (%s, %s, %s)',
                       (w['user_id'], w['amount'], '출금 거절 환불'))
            cur.execute("UPDATE withdrawals SET status = 'rejected' WHERE id = %s", (wid,))
        
        conn.commit()
        return jsonify({'success': True})
    finally:
        cur.close()
        conn.close()


# ==================== 출금 API ====================
@app.route('/api/withdraw', methods=['POST'])
def withdraw():
    data = request.json
    user_id = data.get('user_id')
    amount = data.get('amount', 0)
    
    if amount < 10000:
        return jsonify({'success': False, 'message': '최소 10,000P'})
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('SELECT rewards FROM users WHERE user_id = %s', (user_id,))
        user = cur.fetchone()
        
        if not user or user['rewards'] < amount:
            return jsonify({'success': False, 'message': '잔액 부족'})
        
        cur.execute('''
            INSERT INTO withdrawals (user_id, amount, bank_name, account_number, account_holder)
            VALUES (%s, %s, %s, %s, %s)
        ''', (user_id, amount, data.get('bank_name'), data.get('account_number'), data.get('account_holder')))
        
        cur.execute('UPDATE users SET rewards = rewards - %s WHERE user_id = %s', (amount, user_id))
        cur.execute('INSERT INTO rewards_history (user_id, amount, reason) VALUES (%s, %s, %s)',
                   (user_id, -amount, '출금 요청'))
        
        conn.commit()
        return jsonify({'success': True})
    finally:
        cur.close()
        conn.close()


@app.route('/api/rewards/history/<user_id>')
def rewards_history(user_id):
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('SELECT * FROM rewards_history WHERE user_id = %s ORDER BY created_at DESC LIMIT 50', (user_id,))
        return jsonify({'success': True, 'history': [dict(h) for h in cur.fetchall()]})
    finally:
        cur.close()
        conn.close()


# ==================== 상태 ====================
@app.route('/')
def index():
    return jsonify({'status': 'ok', 'message': '캡챠 API 서버 v2'})


@app.route('/api/status')
def status():
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute("SELECT COUNT(*) as cnt FROM uids WHERE status = 'pending'")
        pending = cur.fetchone()['cnt']
        
        cur.execute("SELECT COUNT(*) as cnt FROM sessions WHERE status IN ('waiting', 'captcha', 'answered')")
        active = cur.fetchone()['cnt']
        
        return jsonify({'success': True, 'pending_uids': pending, 'active_sessions': active})
    finally:
        cur.close()
        conn.close()


if DATABASE_URL:
    init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
