"""
캡챠 풀이 API 서버 - Railway 배포용
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime
import hashlib

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
CORS(app, origins="*")

# ==================== DB 연결 ====================
DATABASE_URL = os.environ.get('DATABASE_URL')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin1234')

def get_db():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return conn

def init_db():
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
    
    # 작업 테이블
    cur.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id SERIAL PRIMARY KEY,
            uid VARCHAR(100),
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
    
    # 결과 테이블
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
    
    # 출금 요청
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
    
    # 키워드
    cur.execute('''
        CREATE TABLE IF NOT EXISTS keywords (
            id SERIAL PRIMARY KEY,
            keyword VARCHAR(100) NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            priority INTEGER DEFAULT 0,
            max_count INTEGER DEFAULT 50,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    cur.close()
    conn.close()
    print("✅ DB 테이블 초기화 완료")


# ==================== 유저 API ====================
@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    user_id = data.get('user_id')
    password = data.get('password')
    
    if not user_id or not password:
        return jsonify({'success': False, 'message': '아이디/비밀번호 필요'})
    
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('SELECT * FROM users WHERE user_id = %s', (user_id,))
        if cur.fetchone():
            return jsonify({'success': False, 'message': '이미 존재하는 아이디'})
        
        cur.execute('''
            INSERT INTO users (user_id, password_hash) VALUES (%s, %s)
        ''', (user_id, password_hash))
        conn.commit()
        
        return jsonify({'success': True, 'message': '가입 완료'})
    finally:
        cur.close()
        conn.close()


@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    user_id = data.get('user_id')
    password = data.get('password')
    
    if not user_id or not password:
        return jsonify({'success': False, 'message': '아이디/비밀번호 필요'})
    
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('SELECT * FROM users WHERE user_id = %s', (user_id,))
        user = cur.fetchone()
        
        if not user:
            # 자동 가입
            cur.execute('''
                INSERT INTO users (user_id, password_hash) VALUES (%s, %s)
            ''', (user_id, password_hash))
            conn.commit()
            return jsonify({'success': True, 'user_id': user_id, 'rewards': 0, 'solved_count': 0, 'new_user': True})
        
        if user['password_hash'] != password_hash:
            return jsonify({'success': False, 'message': '비밀번호 불일치'})
        
        cur.execute('UPDATE users SET last_login = %s WHERE user_id = %s', (datetime.now(), user_id))
        conn.commit()
        
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
            return jsonify({'success': False, 'message': '유저 없음'})
        
        return jsonify({'success': True, 'user': dict(user)})
    finally:
        cur.close()
        conn.close()


# ==================== Worker API ====================
@app.route('/api/worker/add-task', methods=['POST'])
def add_task():
    data = request.json
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('SELECT id FROM tasks WHERE uid = %s', (data.get('uid'),))
        if cur.fetchone():
            return jsonify({'success': False, 'message': '이미 존재하는 작업'})
        
        cur.execute('''
            INSERT INTO tasks (uid, store_name, store_url, keyword)
            VALUES (%s, %s, %s, %s)
            RETURNING id
        ''', (data.get('uid'), data.get('store_name'), data.get('store_url'), data.get('keyword')))
        
        task_id = cur.fetchone()['id']
        conn.commit()
        
        return jsonify({'success': True, 'task_id': task_id})
    finally:
        cur.close()
        conn.close()


@app.route('/api/worker/upload-screenshot', methods=['POST'])
def upload_screenshot():
    data = request.json
    task_id = data.get('task_id')
    screenshot = data.get('screenshot')
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('''
            UPDATE tasks SET screenshot_base64 = %s, status = 'pending'
            WHERE id = %s
        ''', (screenshot, task_id))
        conn.commit()
        
        return jsonify({'success': True})
    finally:
        cur.close()
        conn.close()


@app.route('/api/worker/pending-answers')
def pending_answers():
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('''
            SELECT id, uid, user_answer FROM tasks
            WHERE status = 'assigned' AND user_answer IS NOT NULL
        ''')
        tasks = cur.fetchall()
        
        return jsonify({'success': True, 'tasks': [dict(t) for t in tasks]})
    finally:
        cur.close()
        conn.close()


@app.route('/api/worker/complete-task', methods=['POST'])
def complete_task():
    data = request.json
    task_id = data.get('task_id')
    seller_info = data.get('seller_info', {})
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('SELECT * FROM tasks WHERE id = %s', (task_id,))
        task = cur.fetchone()
        
        if not task:
            return jsonify({'success': False, 'message': '작업 없음'})
        
        # 결과 저장
        cur.execute('''
            INSERT INTO results (task_id, store_name, seller_name, business_number, 
                               representative, phone, email, address, store_url, solved_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            task_id, seller_info.get('store_name'), seller_info.get('seller_name'),
            seller_info.get('business_number'), seller_info.get('representative'),
            seller_info.get('phone'), seller_info.get('email'),
            seller_info.get('address'), seller_info.get('store_url'), task['assigned_to']
        ))
        
        # 작업 완료
        cur.execute('''
            UPDATE tasks SET status = 'completed', completed_at = %s WHERE id = %s
        ''', (datetime.now(), task_id))
        
        # 리워드 지급
        reward = 100
        if task['assigned_to']:
            cur.execute('''
                UPDATE users SET rewards = rewards + %s, solved_count = solved_count + 1
                WHERE user_id = %s
            ''', (reward, task['assigned_to']))
            
            cur.execute('''
                INSERT INTO rewards_history (user_id, amount, reason, task_id)
                VALUES (%s, %s, '캡챠 해결', %s)
            ''', (task['assigned_to'], reward, task_id))
        
        conn.commit()
        return jsonify({'success': True, 'reward': reward})
    finally:
        cur.close()
        conn.close()


@app.route('/api/worker/retry-task', methods=['POST'])
def retry_task():
    data = request.json
    task_id = data.get('task_id')
    screenshot = data.get('screenshot')
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('''
            UPDATE tasks SET screenshot_base64 = %s, user_answer = NULL, status = 'pending'
            WHERE id = %s
        ''', (screenshot, task_id))
        conn.commit()
        
        return jsonify({'success': True})
    finally:
        cur.close()
        conn.close()


# ==================== 유저 작업 API ====================
@app.route('/api/tasks/request', methods=['POST'])
def request_task():
    data = request.json
    user_id = data.get('user_id')
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('''
            SELECT * FROM tasks 
            WHERE status = 'pending' AND screenshot_base64 IS NOT NULL
            ORDER BY created_at ASC LIMIT 1
            FOR UPDATE SKIP LOCKED
        ''')
        task = cur.fetchone()
        
        if not task:
            return jsonify({'success': False, 'message': '대기 중인 작업 없음'})
        
        cur.execute('''
            UPDATE tasks SET status = 'assigned', assigned_to = %s, assigned_at = %s
            WHERE id = %s
        ''', (user_id, datetime.now(), task['id']))
        conn.commit()
        
        return jsonify({
            'success': True,
            'task_id': task['id'],
            'screenshot': task['screenshot_base64']
        })
    finally:
        cur.close()
        conn.close()


@app.route('/api/tasks/submit', methods=['POST'])
def submit_answer():
    data = request.json
    task_id = data.get('task_id')
    answer = data.get('answer')
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('''
            UPDATE tasks SET user_answer = %s WHERE id = %s
        ''', (answer, task_id))
        conn.commit()
        
        return jsonify({'success': True})
    finally:
        cur.close()
        conn.close()


@app.route('/api/tasks/pending')
def pending_count():
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute("SELECT COUNT(*) as cnt FROM tasks WHERE status = 'pending' AND screenshot_base64 IS NOT NULL")
        count = cur.fetchone()['cnt']
        return jsonify({'success': True, 'count': count})
    finally:
        cur.close()
        conn.close()


# ==================== 출금 API ====================
@app.route('/api/rewards/history/<user_id>')
def rewards_history(user_id):
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('''
            SELECT * FROM rewards_history WHERE user_id = %s
            ORDER BY created_at DESC LIMIT 50
        ''', (user_id,))
        history = cur.fetchall()
        return jsonify({'success': True, 'history': [dict(h) for h in history]})
    finally:
        cur.close()
        conn.close()


@app.route('/api/withdraw', methods=['POST'])
def withdraw():
    data = request.json
    user_id = data.get('user_id')
    amount = data.get('amount', 0)
    
    if amount < 10000:
        return jsonify({'success': False, 'message': '최소 10,000P부터 출금 가능'})
    
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
        cur.execute('''
            INSERT INTO rewards_history (user_id, amount, reason) VALUES (%s, %s, '출금 요청')
        ''', (user_id, -amount))
        
        conn.commit()
        return jsonify({'success': True})
    finally:
        cur.close()
        conn.close()


@app.route('/api/withdrawals/<user_id>')
def get_withdrawals(user_id):
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('SELECT * FROM withdrawals WHERE user_id = %s ORDER BY created_at DESC', (user_id,))
        return jsonify({'success': True, 'withdrawals': [dict(w) for w in cur.fetchall()]})
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
    return jsonify({'success': False, 'message': '비밀번호 불일치'})


@app.route('/api/admin/stats')
def admin_stats():
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
        
        cur.execute('SELECT COUNT(*) as cnt FROM results WHERE used = TRUE')
        stats['used_results'] = cur.fetchone()['cnt']
        
        cur.execute("SELECT COUNT(*) as cnt FROM tasks WHERE status = 'pending'")
        stats['pending_tasks'] = cur.fetchone()['cnt']
        
        cur.execute("SELECT COUNT(*) as cnt FROM withdrawals WHERE status = 'pending'")
        stats['pending_withdrawals'] = cur.fetchone()['cnt']
        
        cur.execute("SELECT COUNT(*) as cnt FROM results WHERE DATE(created_at) = CURRENT_DATE")
        stats['today_results'] = cur.fetchone()['cnt']
        
        cur.execute("SELECT COUNT(*) as cnt FROM users WHERE DATE(created_at) = CURRENT_DATE")
        stats['today_users'] = cur.fetchone()['cnt']
        
        return jsonify({'success': True, 'stats': stats})
    finally:
        cur.close()
        conn.close()


@app.route('/api/admin/results')
def admin_results():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    used = request.args.get('used', '')
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
            conditions.append('(store_name ILIKE %s OR business_number ILIKE %s)')
            params.extend([f'%{search}%', f'%{search}%'])
        
        where_clause = 'WHERE ' + ' AND '.join(conditions) if conditions else ''
        
        cur.execute(f'SELECT * FROM results {where_clause} ORDER BY created_at DESC LIMIT %s OFFSET %s',
                   params + [per_page, offset])
        results = cur.fetchall()
        
        cur.execute(f'SELECT COUNT(*) as cnt FROM results {where_clause}', params or None)
        total = cur.fetchone()['cnt']
        
        return jsonify({'success': True, 'results': [dict(r) for r in results], 'total': total, 'page': page})
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


@app.route('/api/admin/results/bulk-update', methods=['POST'])
def bulk_update_results():
    data = request.json
    ids = data.get('ids', [])
    used = data.get('used')
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('UPDATE results SET used = %s WHERE id = ANY(%s)', (used, ids))
        conn.commit()
        return jsonify({'success': True, 'updated': len(ids)})
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
    page = request.args.get('page', 1, type=int)
    per_page = 50
    offset = (page - 1) * per_page
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('SELECT * FROM users ORDER BY created_at DESC LIMIT %s OFFSET %s', (per_page, offset))
        users = cur.fetchall()
        
        cur.execute('SELECT COUNT(*) as cnt FROM users')
        total = cur.fetchone()['cnt']
        
        return jsonify({'success': True, 'users': [dict(u) for u in users], 'total': total, 'page': page})
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


@app.route('/api/admin/tasks')
def admin_tasks():
    status = request.args.get('status', '')
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        if status:
            cur.execute('''
                SELECT id, uid, store_name, keyword, status, assigned_to, created_at, completed_at
                FROM tasks WHERE status = %s ORDER BY created_at DESC LIMIT 100
            ''', (status,))
        else:
            cur.execute('''
                SELECT id, uid, store_name, keyword, status, assigned_to, created_at, completed_at
                FROM tasks ORDER BY created_at DESC LIMIT 100
            ''')
        
        return jsonify({'success': True, 'tasks': [dict(t) for t in cur.fetchall()], 'total': 100})
    finally:
        cur.close()
        conn.close()


@app.route('/api/admin/withdrawals')
def admin_withdrawals():
    status = request.args.get('status', 'pending')
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('''
            SELECT w.*, u.rewards as current_rewards FROM withdrawals w
            LEFT JOIN users u ON w.user_id = u.user_id
            WHERE w.status = %s ORDER BY w.created_at DESC
        ''', (status,))
        return jsonify({'success': True, 'withdrawals': [dict(w) for w in cur.fetchall()]})
    finally:
        cur.close()
        conn.close()


@app.route('/api/admin/withdrawals/<int:withdrawal_id>/process', methods=['POST'])
def process_withdrawal(withdrawal_id):
    data = request.json
    action = data.get('action')
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute('SELECT * FROM withdrawals WHERE id = %s', (withdrawal_id,))
        withdrawal = cur.fetchone()
        
        if not withdrawal:
            return jsonify({'success': False})
        
        if action == 'approve':
            cur.execute('UPDATE withdrawals SET status = %s, processed_at = %s WHERE id = %s',
                       ('completed', datetime.now(), withdrawal_id))
        elif action == 'reject':
            cur.execute('UPDATE users SET rewards = rewards + %s WHERE user_id = %s',
                       (withdrawal['amount'], withdrawal['user_id']))
            cur.execute('INSERT INTO rewards_history (user_id, amount, reason) VALUES (%s, %s, %s)',
                       (withdrawal['user_id'], withdrawal['amount'], '출금 거절 환불'))
            cur.execute('UPDATE withdrawals SET status = %s, processed_at = %s WHERE id = %s',
                       ('rejected', datetime.now(), withdrawal_id))
        
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
        cur.execute('INSERT INTO keywords (keyword, priority, max_count) VALUES (%s, %s, %s) RETURNING id',
                   (keyword, data.get('priority', 0), data.get('max_count', 50)))
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
        for field in ['keyword', 'is_active', 'priority', 'max_count']:
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


# ==================== 상태 체크 ====================
@app.route('/')
def index():
    return jsonify({'status': 'ok', 'message': '캡챠 API 서버'})


@app.route('/api/status')
def api_status():
    conn = get_db()
    cur = conn.cursor()
    
    try:
        cur.execute("SELECT COUNT(*) as cnt FROM tasks WHERE status = 'pending'")
        queue_size = cur.fetchone()['cnt']
        
        cur.execute('SELECT COUNT(*) as cnt FROM results')
        total_results = cur.fetchone()['cnt']
        
        return jsonify({
            'success': True,
            'queue_size': queue_size,
            'total_results': total_results
        })
    finally:
        cur.close()
        conn.close()


# ==================== 서버 시작 ====================
if DATABASE_URL:
    init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
