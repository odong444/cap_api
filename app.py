"""
캡챠 API 서버 - Polling 방식 (WebSocket 제거)
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import psycopg
from psycopg.rows import dict_row
import os
from datetime import datetime, timedelta
import hashlib

app = Flask(__name__)
CORS(app, origins="*")

DATABASE_URL = os.environ.get('DATABASE_URL')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin1234')


def get_db():
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def init_db():
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(50) UNIQUE NOT NULL,
            password_hash VARCHAR(128) NOT NULL,
            name VARCHAR(50),
            phone VARCHAR(20),
            email VARCHAR(100),
            bank_name VARCHAR(50),
            bank_account VARCHAR(50),
            account_holder VARCHAR(50),
            rewards INTEGER DEFAULT 0,
            solved_count INTEGER DEFAULT 0,
            is_approved BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 기존 테이블에 컬럼 추가 (이미 테이블이 있을 경우)
    cur.execute('''
        DO $$ 
        BEGIN
            BEGIN ALTER TABLE users ADD COLUMN name VARCHAR(50); EXCEPTION WHEN duplicate_column THEN NULL; END;
            BEGIN ALTER TABLE users ADD COLUMN phone VARCHAR(20); EXCEPTION WHEN duplicate_column THEN NULL; END;
            BEGIN ALTER TABLE users ADD COLUMN email VARCHAR(100); EXCEPTION WHEN duplicate_column THEN NULL; END;
            BEGIN ALTER TABLE users ADD COLUMN bank_name VARCHAR(50); EXCEPTION WHEN duplicate_column THEN NULL; END;
            BEGIN ALTER TABLE users ADD COLUMN bank_account VARCHAR(50); EXCEPTION WHEN duplicate_column THEN NULL; END;
            BEGIN ALTER TABLE users ADD COLUMN account_holder VARCHAR(50); EXCEPTION WHEN duplicate_column THEN NULL; END;
            BEGIN ALTER TABLE users ADD COLUMN is_approved BOOLEAN DEFAULT FALSE; EXCEPTION WHEN duplicate_column THEN NULL; END;
        END $$;
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS uid_queue (
            id SERIAL PRIMARY KEY,
            uid VARCHAR(100) UNIQUE NOT NULL,
            store_name VARCHAR(200),
            store_url VARCHAR(500),
            keyword VARCHAR(100),
            status VARCHAR(20) DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS results (
            id SERIAL PRIMARY KEY,
            task_id INTEGER,
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
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS rewards_history (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(50) NOT NULL,
            amount INTEGER NOT NULL,
            reason VARCHAR(200),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
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
    
    cur.execute('''
        CREATE TABLE IF NOT EXISTS keywords (
            id SERIAL PRIMARY KEY,
            keyword VARCHAR(100) NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            priority INTEGER DEFAULT 0,
            max_count INTEGER DEFAULT 100,
            collected_count INTEGER DEFAULT 0,
            status VARCHAR(20) DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 작업 세션 (작업자 상태 관리)
    cur.execute('''
        CREATE TABLE IF NOT EXISTS work_sessions (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(50) UNIQUE NOT NULL,
            current_uid_id INTEGER,
            screenshot TEXT,
            answer VARCHAR(100),
            message VARCHAR(200),
            last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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
    """회원가입"""
    data = request.json
    
    # 필수 필드 검증
    required_fields = ['user_id', 'password', 'name', 'phone', 'email', 'bank_name', 'bank_account', 'account_holder']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'success': False, 'message': f'{field} 필드가 필요합니다.'})
    
    user_id = data.get('user_id')
    password = data.get('password')
    password_confirm = data.get('password_confirm')
    
    # 비밀번호 확인
    if password != password_confirm:
        return jsonify({'success': False, 'message': '비밀번호가 일치하지 않습니다.'})
    
    # 비밀번호 길이 검증
    if len(password) < 4:
        return jsonify({'success': False, 'message': '비밀번호는 4자 이상이어야 합니다.'})
    
    pw_hash = hashlib.sha256(password.encode()).hexdigest()
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        # 아이디 중복 체크
        cur.execute('SELECT user_id FROM users WHERE user_id = %s', (user_id,))
        if cur.fetchone():
            return jsonify({'success': False, 'message': '이미 사용 중인 아이디입니다.'})
        
        # 회원가입
        cur.execute('''
            INSERT INTO users (user_id, password_hash, name, phone, email, bank_name, bank_account, account_holder, is_approved)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, FALSE)
        ''', (
            user_id, 
            pw_hash, 
            data.get('name'),
            data.get('phone'),
            data.get('email'),
            data.get('bank_name'),
            data.get('bank_account'),
            data.get('account_holder')
        ))
        conn.commit()
        
        return jsonify({'success': True, 'message': '회원가입이 완료되었습니다. 관리자 승인 후 이용 가능합니다.'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'회원가입 실패: {str(e)}'})
    finally:
        cur.close()
        conn.close()


@app.route('/api/check-userid', methods=['POST'])
def check_userid():
    """아이디 중복 체크"""
    data = request.json
    user_id = data.get('user_id')
    
    if not user_id:
        return jsonify({'available': False, 'message': '아이디를 입력하세요.'})
    
    if len(user_id) < 4:
        return jsonify({'available': False, 'message': '아이디는 4자 이상이어야 합니다.'})
    
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute('SELECT user_id FROM users WHERE user_id = %s', (user_id,))
        if cur.fetchone():
            return jsonify({'available': False, 'message': '이미 사용 중인 아이디입니다.'})
        return jsonify({'available': True, 'message': '사용 가능한 아이디입니다.'})
    finally:
        cur.close()
        conn.close()


@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    user_id = data.get('user_id')
    password = data.get('password')
    
    if not user_id or not password:
        return jsonify({'success': False, 'message': '아이디/비밀번호를 입력하세요.'})
    
    pw_hash = hashlib.sha256(password.encode()).hexdigest()
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('SELECT * FROM users WHERE user_id = %s', (user_id,))
        user = cur.fetchone()
        
        if not user:
            return jsonify({'success': False, 'message': '존재하지 않는 아이디입니다.'})
        
        if user['password_hash'] != pw_hash:
            return jsonify({'success': False, 'message': '비밀번호가 올바르지 않습니다.'})
        
        # 승인 여부 체크
        if not user.get('is_approved', True):
            return jsonify({'success': False, 'message': '관리자 승인 대기 중입니다.'})
        
        return jsonify({
            'success': True, 
            'user_id': user_id, 
            'name': user.get('name', ''),
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
        if user:
            return jsonify({'success': True, 'user': dict(user)})
        return jsonify({'success': False})
    finally:
        cur.close()
        conn.close()


# ==================== 작업 세션 API ====================
MAX_WORKERS = 4  # 동시 작업자 제한

@app.route('/api/session/start', methods=['POST'])
def start_session():
    """작업자가 작업 시작"""
    data = request.json
    user_id = data.get('user_id')
    
    conn = get_db()
    cur = conn.cursor()
    try:
        # 현재 활성 세션 수 체크 (자기 자신 제외)
        cur.execute('SELECT COUNT(*) as cnt FROM work_sessions WHERE user_id != %s', (user_id,))
        result = cur.fetchone()
        current_count = result['cnt'] if result else 0
        
        if current_count >= MAX_WORKERS:
            return jsonify({
                'success': False, 
                'error': 'full', 
                'message': f'작업자가 많아 진행할 수 없습니다. (현재 {current_count}명 작업 중)'
            })
        
        # 세션 시작 시 이전 데이터 모두 클리어
        cur.execute('''
            INSERT INTO work_sessions (user_id, last_activity)
            VALUES (%s, %s)
            ON CONFLICT (user_id) DO UPDATE SET 
                last_activity = %s, 
                answer = NULL,
                screenshot = NULL,
                current_uid_id = NULL,
                message = NULL
        ''', (user_id, datetime.now(), datetime.now()))
        conn.commit()
        return jsonify({'success': True, 'workers': current_count + 1})
    finally:
        cur.close()
        conn.close()


@app.route('/api/session/end', methods=['POST'])
def end_session():
    """작업자가 작업 종료"""
    data = request.json
    user_id = data.get('user_id')
    
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute('DELETE FROM work_sessions WHERE user_id = %s', (user_id,))
        conn.commit()
        return jsonify({'success': True})
    finally:
        cur.close()
        conn.close()


@app.route('/api/session/submit-answer', methods=['POST'])
def submit_answer():
    """작업자가 답변 제출"""
    data = request.json
    user_id = data.get('user_id')
    answer = data.get('answer')
    
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute('UPDATE work_sessions SET answer = %s, last_activity = %s WHERE user_id = %s',
                   (answer, datetime.now(), user_id))
        conn.commit()
        return jsonify({'success': True})
    finally:
        cur.close()
        conn.close()


@app.route('/api/session/poll/<user_id>')
def poll_session(user_id):
    """작업자가 현재 상태 폴링"""
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute('SELECT screenshot, message, current_uid_id FROM work_sessions WHERE user_id = %s', (user_id,))
        session = cur.fetchone()
        
        if not session:
            return jsonify({'success': False, 'message': '세션 없음'})
        
        # 활동 시간 갱신
        cur.execute('UPDATE work_sessions SET last_activity = %s WHERE user_id = %s', (datetime.now(), user_id))
        conn.commit()
        
        return jsonify({
            'success': True,
            'screenshot': session['screenshot'],
            'message': session['message'],
            'uid_id': session['current_uid_id']
        })
    finally:
        cur.close()
        conn.close()


# ==================== Worker API ====================
@app.route('/api/worker/active-sessions')
def active_sessions():
    """Worker: 활성 세션 목록"""
    conn = get_db()
    cur = conn.cursor()
    try:
        # 5분 이내 활동한 세션만
        cur.execute('''
            SELECT user_id, current_uid_id, last_activity 
            FROM work_sessions 
            WHERE last_activity > %s
        ''', (datetime.now() - timedelta(minutes=5),))
        sessions = cur.fetchall()
        return jsonify({'success': True, 'sessions': [dict(s) for s in sessions]})
    finally:
        cur.close()
        conn.close()


@app.route('/api/worker/check-answer/<user_id>')
def check_answer(user_id):
    """Worker: 답변 확인"""
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute('SELECT answer FROM work_sessions WHERE user_id = %s AND answer IS NOT NULL', (user_id,))
        row = cur.fetchone()
        
        if row:
            # 답변 가져왔으면 비우기
            cur.execute('UPDATE work_sessions SET answer = NULL WHERE user_id = %s', (user_id,))
            conn.commit()
            return jsonify({'success': True, 'answer': row['answer']})
        
        return jsonify({'success': True, 'answer': None})
    finally:
        cur.close()
        conn.close()


@app.route('/api/worker/update-screenshot', methods=['POST'])
def update_screenshot():
    """Worker: 스크린샷 업데이트"""
    data = request.json
    user_id = data.get('user_id')
    screenshot = data.get('screenshot')
    uid_id = data.get('uid_id')
    message = data.get('message', '')
    
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute('''
            UPDATE work_sessions 
            SET screenshot = %s, current_uid_id = %s, message = %s, answer = NULL
            WHERE user_id = %s
        ''', (screenshot, uid_id, message, user_id))
        conn.commit()
        return jsonify({'success': True})
    finally:
        cur.close()
        conn.close()


@app.route('/api/worker/session-timeout', methods=['POST'])
def session_timeout():
    """Worker: 세션 타임아웃"""
    data = request.json
    user_id = data.get('user_id')
    
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute('UPDATE work_sessions SET message = %s WHERE user_id = %s',
                   ('5분간 응답 없어 작업 종료됨', user_id))
        conn.commit()
        return jsonify({'success': True})
    finally:
        cur.close()
        conn.close()


# ==================== UID API ====================
@app.route('/api/worker/add-uids', methods=['POST'])
def add_uids():
    """UID 추가"""
    data = request.json
    uids = data.get('uids', [])
    
    conn = get_db()
    cur = conn.cursor()
    try:
        added = 0
        for u in uids:
            try:
                cur.execute('''
                    INSERT INTO uid_queue (uid, store_name, store_url, keyword)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (uid) DO NOTHING
                ''', (u['uid'], u.get('store_name'), u.get('store_url'), u.get('keyword')))
                added += cur.rowcount
            except:
                pass
        conn.commit()
        return jsonify({'success': True, 'added': added})
    finally:
        cur.close()
        conn.close()


@app.route('/api/worker/get-pending-uid')
def get_pending_uid():
    """대기 중인 UID 가져오기"""
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute('''
            UPDATE uid_queue SET status = 'processing'
            WHERE id = (
                SELECT id FROM uid_queue WHERE status = 'pending'
                ORDER BY created_at LIMIT 1
                FOR UPDATE SKIP LOCKED
            )
            RETURNING *
        ''')
        uid = cur.fetchone()
        conn.commit()
        
        if uid:
            return jsonify({'success': True, 'uid': dict(uid)})
        return jsonify({'success': False, 'message': '대기 중인 UID 없음'})
    finally:
        cur.close()
        conn.close()


@app.route('/api/worker/complete-uid', methods=['POST'])
def complete_uid():
    """UID 완료 + 결과 저장"""
    data = request.json
    uid_id = data.get('uid_id')
    user_id = data.get('user_id')
    info = data.get('seller_info', {})
    
    conn = get_db()
    cur = conn.cursor()
    try:
        # task_id 없이 저장 (foreign key 문제 회피)
        cur.execute('''
            INSERT INTO results (store_name, seller_name, business_number,
                               representative, phone, email, address, store_url, solved_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (info.get('store_name'), info.get('seller_name'),
              info.get('business_number'), info.get('representative'),
              info.get('phone'), info.get('email'), info.get('address'),
              info.get('store_url'), user_id))
        
        cur.execute('UPDATE uid_queue SET status = %s WHERE id = %s', ('completed', uid_id))
        
        reward = 100
        if user_id:
            cur.execute('UPDATE users SET rewards = rewards + %s, solved_count = solved_count + 1 WHERE user_id = %s', (reward, user_id))
            cur.execute('INSERT INTO rewards_history (user_id, amount, reason) VALUES (%s, %s, %s)', (user_id, reward, '캡챠 해결'))
        
        conn.commit()
        return jsonify({'success': True, 'reward': reward})
    except Exception as e:
        print(f"complete_uid 오류: {e}")
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)})
    finally:
        cur.close()
        conn.close()


@app.route('/api/worker/release-uid', methods=['POST'])
def release_uid():
    """UID 반환"""
    data = request.json
    uid_id = data.get('uid_id')
    
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute('UPDATE uid_queue SET status = %s WHERE id = %s', ('pending', uid_id))
        conn.commit()
        return jsonify({'success': True})
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
    if request.json.get('password') == ADMIN_PASSWORD:
        return jsonify({'success': True})
    return jsonify({'success': False})


@app.route('/api/admin/stats')
def admin_stats():
    conn = get_db()
    cur = conn.cursor()
    try:
        stats = {}
        cur.execute('SELECT COUNT(*) as c FROM users')
        stats['total_users'] = cur.fetchone()['c']
        cur.execute('SELECT COUNT(*) as c FROM users WHERE is_approved = FALSE')
        stats['pending_users'] = cur.fetchone()['c']
        cur.execute('SELECT COUNT(*) as c FROM results')
        stats['total_results'] = cur.fetchone()['c']
        cur.execute("SELECT COUNT(*) as c FROM uid_queue WHERE status = 'pending'")
        stats['pending_uids'] = cur.fetchone()['c']
        cur.execute("SELECT COUNT(*) as c FROM work_sessions WHERE last_activity > %s", (datetime.now() - timedelta(minutes=5),))
        stats['active_sessions'] = cur.fetchone()['c']
        cur.execute("SELECT COUNT(*) as c FROM results WHERE DATE(created_at) = CURRENT_DATE")
        stats['today_results'] = cur.fetchone()['c']
        return jsonify({'success': True, 'stats': stats})
    finally:
        cur.close()
        conn.close()


@app.route('/api/admin/results')
def admin_results():
    page = int(request.args.get('page', 1))
    used = request.args.get('used', '')
    search = request.args.get('search', '')
    
    conn = get_db()
    cur = conn.cursor()
    try:
        where = []
        params = []
        if used == 'true':
            where.append('used = TRUE')
        elif used == 'false':
            where.append('used = FALSE')
        if search:
            where.append('(store_name ILIKE %s OR business_number ILIKE %s)')
            params.extend([f'%{search}%', f'%{search}%'])
        
        sql = 'SELECT * FROM results'
        if where:
            sql += ' WHERE ' + ' AND '.join(where)
        sql += ' ORDER BY created_at DESC LIMIT 50 OFFSET %s'
        params.append((page-1)*50)
        
        cur.execute(sql, params)
        results = cur.fetchall()
        
        cur.execute('SELECT COUNT(*) as c FROM results')
        total = cur.fetchone()['c']
        
        return jsonify({'success': True, 'results': [dict(r) for r in results], 'total': total})
    finally:
        cur.close()
        conn.close()


@app.route('/api/admin/results/<int:rid>/update', methods=['POST'])
def update_result(rid):
    data = request.json
    conn = get_db()
    cur = conn.cursor()
    try:
        if 'used' in data:
            cur.execute('UPDATE results SET used = %s WHERE id = %s', (data['used'], rid))
        if 'memo' in data:
            cur.execute('UPDATE results SET memo = %s WHERE id = %s', (data['memo'], rid))
        conn.commit()
        return jsonify({'success': True})
    finally:
        cur.close()
        conn.close()


@app.route('/api/admin/results/bulk-update', methods=['POST'])
def bulk_update():
    data = request.json
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute('UPDATE results SET used = %s WHERE id = ANY(%s)', (data['used'], data['ids']))
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
    filter_type = request.args.get('filter', '')  # pending, approved, or empty for all
    
    conn = get_db()
    cur = conn.cursor()
    try:
        if filter_type == 'pending':
            cur.execute('SELECT * FROM users WHERE is_approved = FALSE ORDER BY created_at DESC')
        elif filter_type == 'approved':
            cur.execute('SELECT * FROM users WHERE is_approved = TRUE ORDER BY created_at DESC')
        else:
            cur.execute('SELECT * FROM users ORDER BY created_at DESC')
        return jsonify({'success': True, 'users': [dict(u) for u in cur.fetchall()]})
    finally:
        cur.close()
        conn.close()


@app.route('/api/admin/users/<user_id>/approve', methods=['POST'])
def approve_user(user_id):
    """회원 승인"""
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute('UPDATE users SET is_approved = TRUE WHERE user_id = %s', (user_id,))
        conn.commit()
        return jsonify({'success': True, 'message': '회원 승인 완료'})
    finally:
        cur.close()
        conn.close()


@app.route('/api/admin/users/<user_id>/reject', methods=['POST'])
def reject_user(user_id):
    """회원 거절 (삭제)"""
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute('DELETE FROM users WHERE user_id = %s AND is_approved = FALSE', (user_id,))
        conn.commit()
        return jsonify({'success': True, 'message': '회원 거절 (삭제) 완료'})
    finally:
        cur.close()
        conn.close()


@app.route('/api/admin/users/<user_id>/suspend', methods=['POST'])
def suspend_user(user_id):
    """회원 정지"""
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute('UPDATE users SET is_approved = FALSE WHERE user_id = %s', (user_id,))
        conn.commit()
        return jsonify({'success': True, 'message': '회원 정지 완료'})
    finally:
        cur.close()
        conn.close()


@app.route('/api/admin/users/<user_id>/adjust-rewards', methods=['POST'])
def adjust_rewards(user_id):
    data = request.json
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute('UPDATE users SET rewards = rewards + %s WHERE user_id = %s', (data['amount'], user_id))
        cur.execute('INSERT INTO rewards_history (user_id, amount, reason) VALUES (%s, %s, %s)',
                   (user_id, data['amount'], data.get('reason', '관리자 조정')))
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
            cur.execute('UPDATE withdrawals SET status = %s WHERE id = %s', ('completed', wid))
        elif action == 'reject':
            cur.execute('UPDATE users SET rewards = rewards + %s WHERE user_id = %s', (w['amount'], w['user_id']))
            cur.execute('INSERT INTO rewards_history (user_id, amount, reason) VALUES (%s, %s, %s)',
                       (w['user_id'], w['amount'], '출금 거절 환불'))
            cur.execute('UPDATE withdrawals SET status = %s WHERE id = %s', ('rejected', wid))
        
        conn.commit()
        return jsonify({'success': True})
    finally:
        cur.close()
        conn.close()


@app.route('/api/admin/keywords')
def admin_keywords():
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute('SELECT * FROM keywords ORDER BY priority DESC')
        return jsonify({'success': True, 'keywords': [dict(k) for k in cur.fetchall()]})
    finally:
        cur.close()
        conn.close()


@app.route('/api/admin/keywords', methods=['POST'])
def add_keyword():
    data = request.json
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute('INSERT INTO keywords (keyword, priority, max_count) VALUES (%s, %s, %s) RETURNING id',
                   (data['keyword'], data.get('priority', 0), data.get('max_count', 100)))
        conn.commit()
        return jsonify({'success': True, 'id': cur.fetchone()['id']})
    finally:
        cur.close()
        conn.close()


@app.route('/api/admin/keywords/<int:kid>', methods=['PUT'])
def update_keyword(kid):
    data = request.json
    conn = get_db()
    cur = conn.cursor()
    try:
        for f in ['keyword', 'is_active', 'priority', 'max_count']:
            if f in data:
                cur.execute(f'UPDATE keywords SET {f} = %s WHERE id = %s', (data[f], kid))
        conn.commit()
        return jsonify({'success': True})
    finally:
        cur.close()
        conn.close()


@app.route('/api/admin/keywords/<int:kid>', methods=['DELETE'])
def delete_keyword(kid):
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute('DELETE FROM keywords WHERE id = %s', (kid,))
        conn.commit()
        return jsonify({'success': True})
    finally:
        cur.close()
        conn.close()


@app.route('/api/admin/keywords/bulk', methods=['POST'])
def bulk_add_keywords():
    """키워드 대량 등록"""
    data = request.json
    keywords_text = data.get('keywords', '')
    max_count = data.get('max_count', 100)
    
    keywords = [k.strip() for k in keywords_text.split('\n') if k.strip()]
    
    conn = get_db()
    cur = conn.cursor()
    try:
        added = 0
        for kw in keywords:
            try:
                cur.execute('''
                    INSERT INTO keywords (keyword, max_count, status)
                    VALUES (%s, %s, 'pending')
                ''', (kw, max_count))
                added += 1
            except:
                pass
        conn.commit()
        return jsonify({'success': True, 'added': added})
    finally:
        cur.close()
        conn.close()


# ==================== Collector API ====================
@app.route('/api/collector/pending-keyword')
def get_pending_keyword():
    """수집할 키워드 가져오기 (pending → collecting)"""
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute('''
            UPDATE keywords SET status = 'collecting'
            WHERE id = (
                SELECT id FROM keywords 
                WHERE status = 'pending' AND is_active = TRUE
                ORDER BY priority DESC, created_at ASC
                LIMIT 1
                FOR UPDATE SKIP LOCKED
            )
            RETURNING *
        ''')
        keyword = cur.fetchone()
        conn.commit()
        
        if keyword:
            return jsonify({'success': True, 'keyword': dict(keyword)})
        return jsonify({'success': False, 'message': '대기 중인 키워드 없음'})
    finally:
        cur.close()
        conn.close()


@app.route('/api/collector/update-progress', methods=['POST'])
def update_keyword_progress():
    """수집 진행 상황 업데이트"""
    data = request.json
    keyword_id = data.get('keyword_id')
    collected_count = data.get('collected_count', 0)
    
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute('UPDATE keywords SET collected_count = %s WHERE id = %s',
                   (collected_count, keyword_id))
        conn.commit()
        return jsonify({'success': True})
    finally:
        cur.close()
        conn.close()


@app.route('/api/collector/complete-keyword', methods=['POST'])
def complete_keyword():
    """키워드 수집 완료"""
    data = request.json
    keyword_id = data.get('keyword_id')
    collected_count = data.get('collected_count', 0)
    
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute('''
            UPDATE keywords SET status = 'completed', collected_count = %s
            WHERE id = %s
        ''', (collected_count, keyword_id))
        conn.commit()
        return jsonify({'success': True})
    finally:
        cur.close()
        conn.close()


@app.route('/api/collector/reset-keyword/<int:kid>', methods=['POST'])
def reset_keyword(kid):
    """키워드 다시 수집 (pending으로 리셋)"""
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute('''
            UPDATE keywords SET status = 'pending', collected_count = 0
            WHERE id = %s
        ''', (kid,))
        conn.commit()
        return jsonify({'success': True})
    finally:
        cur.close()
        conn.close()


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
        
        cur.execute('INSERT INTO withdrawals (user_id, amount, bank_name, account_number, account_holder) VALUES (%s, %s, %s, %s, %s)',
                   (user_id, amount, data.get('bank_name'), data.get('account_number'), data.get('account_holder')))
        cur.execute('UPDATE users SET rewards = rewards - %s WHERE user_id = %s', (amount, user_id))
        cur.execute('INSERT INTO rewards_history (user_id, amount, reason) VALUES (%s, %s, %s)', (user_id, -amount, '출금 요청'))
        conn.commit()
        return jsonify({'success': True})
    finally:
        cur.close()
        conn.close()


# ==================== 상태 ====================
@app.route('/')
def index():
    return jsonify({'status': 'ok', 'message': '캡챠 API 서버 v2 polling'})


@app.route('/api/status')
def status():
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) as c FROM uid_queue WHERE status = 'pending'")
        pending = cur.fetchone()['c']
        cur.execute("SELECT COUNT(*) as c FROM work_sessions WHERE last_activity > %s", (datetime.now() - timedelta(minutes=5),))
        active = cur.fetchone()['c']
        return jsonify({'success': True, 'pending_uids': pending, 'active_sessions': active})
    finally:
        cur.close()
        conn.close()


if DATABASE_URL:
    init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
