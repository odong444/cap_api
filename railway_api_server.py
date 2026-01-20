"""
캡챠 풀이 API 서버 - Railway 배포용
PostgreSQL로 유저/작업/정산 관리
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime
import hashlib
import secrets

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
CORS(app, origins="*")

# 더미 socketio (WebSocket 비활성화)
class DummySocketIO:
    def emit(self, *args, **kwargs): pass
    def on(self, *args, **kwargs):
        def decorator(f): return f
        return decorator
socketio = DummySocketIO()
def emit(*args, **kwargs): pass

# ==================== DB 연결 ====================
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return conn

def init_db():
    """테이블 생성"""
    conn = get_db()
    cur = conn.cursor()
    
    # 유저 테이블
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(50) UNIQUE NOT NULL,
            password_hash VARCHAR(128) NOT NULL,
            rewards INTEGER DEFAULT 0,
            solved_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    ''')
    
    # 작업 큐 테이블
    cur.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id SERIAL PRIMARY KEY,
            uid VARCHAR(100) NOT NULL,
            store_name VARCHAR(200),
            store_url VARCHAR(500),
            keyword VARCHAR(100),
            status VARCHAR(20) DEFAULT 'pending',
            assigned_to VARCHAR(50),
            screenshot_base64 TEXT,
            user_answer VARCHAR(100),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            assigned_at TIMESTAMP,
            completed_at TIMESTAMP
        )
    ''')
    
    # 수집 결과 테이블
    cur.execute('''
        CREATE TABLE IF NOT EXISTS results (
            id SERIAL PRIMARY KEY,
            task_id INTEGER REFERENCES tasks(id),
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
            task_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 정산 요청 테이블
    cur.execute('''
        CREATE TABLE IF NOT EXISTS withdrawals (
            id SERIAL PRIMARY KEY,
            user_id VARCHAR(50) NOT NULL,
            amount INTEGER NOT NULL,
            bank_name VARCHAR(50),
            account_number VARCHAR(50),
            account_holder VARCHAR(50),
            status VARCHAR(20) DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            processed_at TIMESTAMP
        )
    ''')
    
    conn.commit()
    cur.close()
    conn.close()
    print("✅ DB 테이블 초기화 완료")


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


# ==================== 유저 API ====================
@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    user_id = data.get('user_id', '').strip()
    password = data.get('password', '').strip()
    
    if not user_id or not password:
        return jsonify({'success': False, 'message': '아이디/비밀번호 필수'})
    
    if len(user_id) < 3 or len(password) < 4:
        return jsonify({'success': False, 'message': '아이디 3자, 비밀번호 4자 이상'})
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('SELECT id FROM users WHERE user_id = %s', (user_id,))
        if cur.fetchone():
            return jsonify({'success': False, 'message': '이미 존재하는 아이디'})
        
        cur.execute('''
            INSERT INTO users (user_id, password_hash) VALUES (%s, %s)
        ''', (user_id, hash_password(password)))
        conn.commit()
        
        return jsonify({'success': True, 'message': '가입 완료'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cur.close()
        conn.close()


@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    user_id = data.get('user_id', '').strip()
    password = data.get('password', '').strip()
    
    if not user_id or not password:
        return jsonify({'success': False, 'message': '아이디/비밀번호 입력'})
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('SELECT * FROM users WHERE user_id = %s', (user_id,))
        user = cur.fetchone()
        
        if not user:
            # 자동 회원가입
            cur.execute('''
                INSERT INTO users (user_id, password_hash) VALUES (%s, %s)
                RETURNING *
            ''', (user_id, hash_password(password)))
            user = cur.fetchone()
            conn.commit()
        elif user['password_hash'] != hash_password(password):
            return jsonify({'success': False, 'message': '비밀번호 불일치'})
        
        # 마지막 로그인 갱신
        cur.execute('UPDATE users SET last_login = %s WHERE user_id = %s', 
                    (datetime.now(), user_id))
        conn.commit()
        
        return jsonify({
            'success': True,
            'user_id': user['user_id'],
            'rewards': user['rewards'],
            'solved': user['solved_count'],
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
            return jsonify({'success': False, 'message': '유저 없음'})
        
        return jsonify({
            'success': True,
            'user_id': user['user_id'],
            'rewards': user['rewards'],
            'solved': user['solved_count'],
        })
    finally:
        cur.close()
        conn.close()


# ==================== 작업 API (윈도우 Worker용) ====================
@app.route('/api/worker/add-task', methods=['POST'])
def add_task():
    """윈도우 Worker가 새 작업 추가"""
    data = request.json
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('''
            INSERT INTO tasks (uid, store_name, store_url, keyword, status)
            VALUES (%s, %s, %s, %s, 'pending')
            RETURNING id
        ''', (
            data.get('uid'),
            data.get('store_name'),
            data.get('store_url'),
            data.get('keyword'),
        ))
        task_id = cur.fetchone()['id']
        conn.commit()
        
        # 연결된 클라이언트에게 새 작업 알림
        socketio.emit('new_task_available', {'task_id': task_id})
        
        return jsonify({'success': True, 'task_id': task_id})
    finally:
        cur.close()
        conn.close()


@app.route('/api/worker/upload-screenshot', methods=['POST'])
def upload_screenshot():
    """윈도우 Worker가 스크린샷 업로드"""
    data = request.json
    task_id = data.get('task_id')
    screenshot = data.get('screenshot')
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('''
            UPDATE tasks SET screenshot_base64 = %s WHERE id = %s
        ''', (screenshot, task_id))
        conn.commit()
        
        return jsonify({'success': True})
    finally:
        cur.close()
        conn.close()


@app.route('/api/worker/get-answer/<int:task_id>')
def get_answer(task_id):
    """윈도우 Worker가 유저가 입력한 답 가져오기"""
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('SELECT * FROM tasks WHERE id = %s', (task_id,))
        task = cur.fetchone()
        
        if task and task.get('user_answer'):
            return jsonify({
                'success': True,
                'answer': task['user_answer'],
            })
        return jsonify({'success': False, 'message': '답 없음'})
    finally:
        cur.close()
        conn.close()


@app.route('/api/worker/pending-answers')
def pending_answers():
    """유저가 답을 입력한 작업들 (Worker가 처리)"""
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('''
            SELECT * FROM tasks 
            WHERE status = 'assigned' AND user_answer IS NOT NULL
        ''')
        tasks = cur.fetchall()
        
        return jsonify({'success': True, 'tasks': tasks})
    finally:
        cur.close()
        conn.close()


@app.route('/api/worker/retry-task', methods=['POST'])
def retry_task():
    """오답시 재시도 - 새 스크린샷 업로드"""
    data = request.json
    task_id = data.get('task_id')
    screenshot = data.get('screenshot')
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('SELECT assigned_to FROM tasks WHERE id = %s', (task_id,))
        task = cur.fetchone()
        
        cur.execute('''
            UPDATE tasks 
            SET screenshot_base64 = %s, user_answer = NULL
            WHERE id = %s
        ''', (screenshot, task_id))
        conn.commit()
        
        # 유저에게 알림
        if task and task['assigned_to']:
            socketio.emit('captcha_retry', {
                'task_id': task_id,
                'image': screenshot,
                'message': '오답입니다. 다시 시도해주세요.',
            }, room=task['assigned_to'])
        
        return jsonify({'success': True})
    finally:
        cur.close()
        conn.close()


@app.route('/api/worker/complete-task', methods=['POST'])
def complete_task():
    """윈도우 Worker가 작업 완료 처리"""
    data = request.json
    task_id = data.get('task_id')
    success = data.get('success')
    seller_info = data.get('seller_info', {})
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('SELECT * FROM tasks WHERE id = %s', (task_id,))
        task = cur.fetchone()
        
        if not task:
            return jsonify({'success': False, 'message': '작업 없음'})
        
        if success:
            # 결과 저장
            cur.execute('''
                INSERT INTO results (task_id, store_name, seller_name, business_number,
                    representative, phone, email, address, store_url, solved_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                task_id,
                seller_info.get('store_name'),
                seller_info.get('seller_name'),
                seller_info.get('business_number'),
                seller_info.get('representative'),
                seller_info.get('phone'),
                seller_info.get('email'),
                seller_info.get('address'),
                seller_info.get('store_url'),
                task['assigned_to'],
            ))
            
            # 유저 리워드 지급
            user_id = task['assigned_to']
            if user_id:
                cur.execute('''
                    UPDATE users SET rewards = rewards + 100, solved_count = solved_count + 1
                    WHERE user_id = %s
                ''', (user_id,))
                
                cur.execute('''
                    INSERT INTO rewards_history (user_id, amount, reason, task_id)
                    VALUES (%s, 100, '캡챠 풀이 완료', %s)
                ''', (user_id, task_id))
                
                # 유저에게 알림
                socketio.emit('task_complete', {
                    'task_id': task_id,
                    'rewards': 100,
                    'user_id': user_id,
                }, room=user_id)
            
            # 작업 상태 업데이트
            cur.execute('''
                UPDATE tasks SET status = 'completed', completed_at = %s WHERE id = %s
            ''', (datetime.now(), task_id))
        else:
            # 실패 - 재시도 가능하게
            cur.execute('''
                UPDATE tasks SET status = 'pending', assigned_to = NULL, assigned_at = NULL
                WHERE id = %s
            ''', (task_id,))
            
            # 유저에게 알림
            if task['assigned_to']:
                socketio.emit('task_failed', {
                    'task_id': task_id,
                    'message': '오답입니다. 다시 시도해주세요.',
                }, room=task['assigned_to'])
        
        conn.commit()
        return jsonify({'success': True})
    finally:
        cur.close()
        conn.close()


# ==================== 유저 작업 API ====================
@app.route('/api/tasks/pending')
def get_pending_tasks():
    """대기 중인 작업 수"""
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute("SELECT COUNT(*) as cnt FROM tasks WHERE status = 'pending'")
        count = cur.fetchone()['cnt']
        return jsonify({'count': count})
    finally:
        cur.close()
        conn.close()


@app.route('/api/status')
def api_status():
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute("SELECT COUNT(*) as cnt FROM tasks WHERE status = 'pending'")
        pending = cur.fetchone()['cnt']
        
        cur.execute("SELECT COUNT(*) as cnt FROM tasks WHERE status = 'assigned'")
        active = cur.fetchone()['cnt']
        
        cur.execute("SELECT COUNT(*) as cnt FROM results")
        completed = cur.fetchone()['cnt']
        
        return jsonify({
            'queue_size': pending,
            'active_sessions': active,
            'total_results': completed,
        })
    finally:
        cur.close()
        conn.close()


# ==================== 정산 API ====================
@app.route('/api/rewards/history/<user_id>')
def rewards_history(user_id):
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('''
            SELECT * FROM rewards_history 
            WHERE user_id = %s 
            ORDER BY created_at DESC 
            LIMIT 50
        ''', (user_id,))
        history = cur.fetchall()
        
        return jsonify({'success': True, 'history': history})
    finally:
        cur.close()
        conn.close()


@app.route('/api/withdraw', methods=['POST'])
def request_withdraw():
    """정산 요청"""
    data = request.json
    user_id = data.get('user_id')
    amount = data.get('amount')
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        # 유저 잔액 확인
        cur.execute('SELECT rewards FROM users WHERE user_id = %s', (user_id,))
        user = cur.fetchone()
        
        if not user:
            return jsonify({'success': False, 'message': '유저 없음'})
        
        if user['rewards'] < amount:
            return jsonify({'success': False, 'message': '잔액 부족'})
        
        if amount < 10000:
            return jsonify({'success': False, 'message': '최소 출금액 10,000P'})
        
        # 출금 요청 생성
        cur.execute('''
            INSERT INTO withdrawals (user_id, amount, bank_name, account_number, account_holder)
            VALUES (%s, %s, %s, %s, %s)
        ''', (
            user_id, amount,
            data.get('bank_name'),
            data.get('account_number'),
            data.get('account_holder'),
        ))
        
        # 잔액 차감
        cur.execute('''
            UPDATE users SET rewards = rewards - %s WHERE user_id = %s
        ''', (amount, user_id))
        
        cur.execute('''
            INSERT INTO rewards_history (user_id, amount, reason)
            VALUES (%s, %s, '출금 요청')
        ''', (user_id, -amount))
        
        conn.commit()
        return jsonify({'success': True, 'message': '출금 요청 완료'})
    finally:
        cur.close()
        conn.close()


@app.route('/api/withdrawals/<user_id>')
def get_withdrawals(user_id):
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('''
            SELECT * FROM withdrawals 
            WHERE user_id = %s 
            ORDER BY created_at DESC
        ''', (user_id,))
        withdrawals = cur.fetchall()
        
        return jsonify({'success': True, 'withdrawals': withdrawals})
    finally:
        cur.close()
        conn.close()


# ==================== WebSocket ====================
@socketio.on('connect')
def handle_connect():
    print(f"🔌 연결: {request.sid}")


@socketio.on('join')
def handle_join(data):
    """유저가 자신의 room에 참가"""
    user_id = data.get('user_id')
    if user_id:
        print(f"👤 {user_id} joined room")


@socketio.on('request_task')
def handle_request_task(data):
    """유저가 작업 요청"""
    user_id = data.get('user_id')
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        # 대기 중인 작업 가져오기
        cur.execute('''
            SELECT * FROM tasks 
            WHERE status = 'pending' AND screenshot_base64 IS NOT NULL
            ORDER BY created_at ASC 
            LIMIT 1
            FOR UPDATE SKIP LOCKED
        ''')
        task = cur.fetchone()
        
        if not task:
            emit('no_task', {'message': '대기 중인 작업이 없습니다.'})
            return
        
        # 작업 할당
        cur.execute('''
            UPDATE tasks SET status = 'assigned', assigned_to = %s, assigned_at = %s
            WHERE id = %s
        ''', (user_id, datetime.now(), task['id']))
        conn.commit()
        
        emit('captcha_image', {
            'task_id': task['id'],
            'image': task['screenshot_base64'],
            'store_name': task['store_name'],
        })
    finally:
        cur.close()
        conn.close()


@socketio.on('submit_answer')
def handle_submit_answer(data):
    """유저가 답 제출"""
    user_id = data.get('user_id')
    task_id = data.get('task_id')
    answer = data.get('answer')
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        # 답 저장 (Worker가 가져감)
        cur.execute('''
            UPDATE tasks SET user_answer = %s WHERE id = %s AND assigned_to = %s
        ''', (answer, task_id, user_id))
        conn.commit()
        
        emit('answer_submitted', {'message': '확인 중...'})
    finally:
        cur.close()
        conn.close()


# ==================== 관리자 API ====================
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin1234')


@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    """관리자 로그인"""
    data = request.json
    password = data.get('password', '')
    
    if password == ADMIN_PASSWORD:
        return jsonify({'success': True})
    return jsonify({'success': False, 'message': '비밀번호 불일치'})


@app.route('/api/admin/stats')
def admin_stats():
    """관리자용 통계"""
    conn = get_db()
    cur = conn.cursor()
    
    try:
        stats = {}
        
        cur.execute('SELECT COUNT(*) as cnt FROM users')
        stats['total_users'] = cur.fetchone()['cnt']
        
        cur.execute('SELECT COALESCE(SUM(rewards), 0) as total FROM users')
        stats['total_rewards'] = cur.fetchone()['total']
        
        cur.execute('SELECT COUNT(*) as cnt FROM results')
        stats['total_results'] = cur.fetchone()['cnt']
        
        cur.execute("SELECT COUNT(*) as cnt FROM results WHERE used = TRUE")
        stats['used_results'] = cur.fetchone()['cnt']
        
        cur.execute("SELECT COUNT(*) as cnt FROM tasks WHERE status = 'pending'")
        stats['pending_tasks'] = cur.fetchone()['cnt']
        
        cur.execute("SELECT COUNT(*) as cnt FROM tasks WHERE status = 'assigned'")
        stats['assigned_tasks'] = cur.fetchone()['cnt']
        
        cur.execute("SELECT COUNT(*) as cnt FROM withdrawals WHERE status = 'pending'")
        stats['pending_withdrawals'] = cur.fetchone()['cnt']
        
        cur.execute("SELECT COALESCE(SUM(amount), 0) as total FROM withdrawals WHERE status = 'pending'")
        stats['pending_withdraw_amount'] = cur.fetchone()['total']
        
        # 오늘 통계
        cur.execute("SELECT COUNT(*) as cnt FROM results WHERE DATE(created_at) = CURRENT_DATE")
        stats['today_results'] = cur.fetchone()['cnt']
        
        cur.execute("SELECT COUNT(*) as cnt FROM users WHERE DATE(created_at) = CURRENT_DATE")
        stats['today_users'] = cur.fetchone()['cnt']
        
        return jsonify({'success': True, 'stats': stats})
    finally:
        cur.close()
        conn.close()


@app.route('/api/admin/users')
def admin_users():
    """유저 목록"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    search = request.args.get('search', '')
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        offset = (page - 1) * per_page
        
        if search:
            cur.execute('''
                SELECT * FROM users 
                WHERE user_id ILIKE %s
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            ''', (f'%{search}%', per_page, offset))
        else:
            cur.execute('''
                SELECT * FROM users 
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            ''', (per_page, offset))
        
        users = cur.fetchall()
        
        cur.execute('SELECT COUNT(*) as cnt FROM users')
        total = cur.fetchone()['cnt']
        
        return jsonify({
            'success': True,
            'users': users,
            'total': total,
            'page': page,
            'per_page': per_page
        })
    finally:
        cur.close()
        conn.close()


@app.route('/api/admin/users/<user_id>/adjust-rewards', methods=['POST'])
def adjust_rewards(user_id):
    """리워드 조정"""
    data = request.json
    amount = data.get('amount', 0)
    reason = data.get('reason', '관리자 조정')
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('UPDATE users SET rewards = rewards + %s WHERE user_id = %s', (amount, user_id))
        cur.execute('''
            INSERT INTO rewards_history (user_id, amount, reason)
            VALUES (%s, %s, %s)
        ''', (user_id, amount, reason))
        conn.commit()
        
        return jsonify({'success': True})
    finally:
        cur.close()
        conn.close()


@app.route('/api/admin/results')
def admin_results():
    """수집 결과 목록"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    used = request.args.get('used', '')  # all, true, false
    search = request.args.get('search', '')
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        offset = (page - 1) * per_page
        conditions = []
        params = []
        
        if used == 'true':
            conditions.append('used = TRUE')
        elif used == 'false':
            conditions.append('used = FALSE')
        
        if search:
            conditions.append('(store_name ILIKE %s OR business_number ILIKE %s OR seller_name ILIKE %s)')
            params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])
        
        where_clause = 'WHERE ' + ' AND '.join(conditions) if conditions else ''
        
        query = f'''
            SELECT * FROM results 
            {where_clause}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        '''
        params.extend([per_page, offset])
        
        cur.execute(query, params)
        results = cur.fetchall()
        
        # 총 개수
        count_query = f'SELECT COUNT(*) as cnt FROM results {where_clause}'
        cur.execute(count_query, params[:-2] if params[:-2] else None)
        total = cur.fetchone()['cnt']
        
        return jsonify({
            'success': True,
            'results': results,
            'total': total,
            'page': page,
            'per_page': per_page
        })
    finally:
        cur.close()
        conn.close()


@app.route('/api/admin/results/<int:result_id>/update', methods=['POST'])
def update_result(result_id):
    """결과 업데이트 (사용여부, 메모)"""
    data = request.json
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        updates = []
        params = []
        
        if 'used' in data:
            updates.append('used = %s')
            params.append(data['used'])
        
        if 'memo' in data:
            updates.append('memo = %s')
            params.append(data['memo'])
        
        if updates:
            params.append(result_id)
            cur.execute(f'''
                UPDATE results SET {', '.join(updates)} WHERE id = %s
            ''', params)
            conn.commit()
        
        return jsonify({'success': True})
    finally:
        cur.close()
        conn.close()


@app.route('/api/admin/results/bulk-update', methods=['POST'])
def bulk_update_results():
    """결과 일괄 업데이트"""
    data = request.json
    ids = data.get('ids', [])
    used = data.get('used')
    
    if not ids:
        return jsonify({'success': False, 'message': 'ID 목록 필요'})
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('''
            UPDATE results SET used = %s WHERE id = ANY(%s)
        ''', (used, ids))
        conn.commit()
        
        return jsonify({'success': True, 'updated': len(ids)})
    finally:
        cur.close()
        conn.close()


@app.route('/api/admin/results/export')
def export_results():
    """결과 CSV 내보내기"""
    used = request.args.get('used', '')
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        if used == 'true':
            cur.execute('SELECT * FROM results WHERE used = TRUE ORDER BY created_at DESC')
        elif used == 'false':
            cur.execute('SELECT * FROM results WHERE used = FALSE ORDER BY created_at DESC')
        else:
            cur.execute('SELECT * FROM results ORDER BY created_at DESC')
        
        results = cur.fetchall()
        
        return jsonify({'success': True, 'results': results})
    finally:
        cur.close()
        conn.close()


@app.route('/api/admin/tasks')
def admin_tasks():
    """작업 목록"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    status = request.args.get('status', '')
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        offset = (page - 1) * per_page
        
        if status:
            cur.execute('''
                SELECT id, uid, store_name, store_url, keyword, status, assigned_to, created_at, completed_at
                FROM tasks 
                WHERE status = %s
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            ''', (status, per_page, offset))
        else:
            cur.execute('''
                SELECT id, uid, store_name, store_url, keyword, status, assigned_to, created_at, completed_at
                FROM tasks 
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            ''', (per_page, offset))
        
        tasks = cur.fetchall()
        
        cur.execute('SELECT COUNT(*) as cnt FROM tasks')
        total = cur.fetchone()['cnt']
        
        return jsonify({
            'success': True,
            'tasks': tasks,
            'total': total,
            'page': page,
            'per_page': per_page
        })
    finally:
        cur.close()
        conn.close()


@app.route('/api/admin/withdrawals')
def admin_withdrawals():
    """출금 요청 목록"""
    status = request.args.get('status', 'pending')
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('''
            SELECT w.*, u.rewards as current_rewards
            FROM withdrawals w
            LEFT JOIN users u ON w.user_id = u.user_id
            WHERE w.status = %s
            ORDER BY w.created_at DESC
        ''', (status,))
        withdrawals = cur.fetchall()
        
        return jsonify({'success': True, 'withdrawals': withdrawals})
    finally:
        cur.close()
        conn.close()


@app.route('/api/admin/withdrawals/<int:withdrawal_id>/process', methods=['POST'])
def process_withdrawal(withdrawal_id):
    """출금 처리 (승인/거절)"""
    data = request.json
    action = data.get('action')  # approve, reject
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('SELECT * FROM withdrawals WHERE id = %s', (withdrawal_id,))
        withdrawal = cur.fetchone()
        
        if not withdrawal:
            return jsonify({'success': False, 'message': '출금 요청 없음'})
        
        if action == 'approve':
            cur.execute('''
                UPDATE withdrawals 
                SET status = 'completed', processed_at = %s 
                WHERE id = %s
            ''', (datetime.now(), withdrawal_id))
        elif action == 'reject':
            # 금액 환불
            cur.execute('''
                UPDATE users SET rewards = rewards + %s WHERE user_id = %s
            ''', (withdrawal['amount'], withdrawal['user_id']))
            
            cur.execute('''
                INSERT INTO rewards_history (user_id, amount, reason)
                VALUES (%s, %s, '출금 거절 환불')
            ''', (withdrawal['user_id'], withdrawal['amount']))
            
            cur.execute('''
                UPDATE withdrawals 
                SET status = 'rejected', processed_at = %s 
                WHERE id = %s
            ''', (datetime.now(), withdrawal_id))
        
        conn.commit()
        return jsonify({'success': True})
    finally:
        cur.close()
        conn.close()


# ==================== 메인 ====================
if __name__ == '__main__':
    print("="*60)
    print("🚀 캡챠 풀이 API 서버 (Railway)")
    print("="*60)
    
    if not DATABASE_URL:
        print("⚠️ DATABASE_URL 환경변수 필요!")
        print("   Railway PostgreSQL 연결 후 실행하세요.")
    else:
        init_db()
        
    port = int(os.environ.get('PORT', 5001))
    print(f"🌐 서버: http://localhost:{port}")
    app.run(host='0.0.0.0', port=port, debug=False)
