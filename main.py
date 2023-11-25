import math
import os
import re
import time
from flask import Flask, redirect, render_template, jsonify, request, send_file, session
from flask_session import Session
from flask_cors import CORS, cross_origin
from flask_socketio import SocketIO, emit, disconnect, join_room, leave_room, rooms
from flasgger import Swagger
from sql import DBHelper, db, Task, Team, User, Message, Invite
from sqlalchemy.sql import text
from sqlalchemy import or_, and_, not_
from werkzeug.utils import secure_filename

app = Flask(__name__, static_folder='./build', static_url_path='/')
app.config['CORS_HEADERS'] = 'Content-Type'
app.config['SECRET_KEY'] = 'secret!'
app.config['SESSION_TYPE'] = 'filesystem'
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///project.db"
app.config["UPLOAD_FOLDER"] = "./build/files/"
ALLOWED_EXTENSIONS = ["jpg", "jpeg", "png", "jfif"]

Session(app)
db.init_app(app)
swagger = Swagger(app)

cors = CORS(app, supports_credentials=True)
socketio = SocketIO(app=app, cors_allowed_origins='*')

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def index(path):
    return app.send_static_file('index.html')

@app.errorhandler(404)
def not_found(e):
    return app.send_static_file('index.html')

@app.route('/profile', methods=['GET'])
def profile():
    if DBHelper.authToken(session['token']):
        return app.send_static_file('index.html')
    return redirect('/login')

@app.route('/task/<id>', methods=['GET'])
def tour(id):
    if DBHelper.authToken(session['token']):
        return app.send_static_file('index.html')
    return redirect('/login')

@app.route('/tasks', methods=['GET'])
def tournaments():
    if DBHelper.authToken(session['token']):
        return app.send_static_file('index.html')
    return redirect('/login')

@app.route('/api/upload_cover/<typed>', methods=['POST'])
def upload_cover_typed(typed):
    if user := DBHelper.authToken(session['token']):
        file = request.files['file']
        
        if allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

            t, _ = typed.split("_")
            print(t)

            if t == "user":
                print(t, filename)
                User.query.get(user.id).cover = filename
                db.session.commit()

            return jsonify({'message': 'Обложка загружена', 'status': 1, 'result': filename})
        return jsonify({'message': 'Неверный формат обложки', 'status': 0})

@app.route('/api/download_file/', methods=['POST'])
def download_file():
    if DBHelper.authToken(session['token']):
        data = request.json

        return send_file(os.path.join(app.config['UPLOAD_FOLDER'], data['filename']), as_attachment=True)
    
    return redirect('/login')
@app.route('/api/upload_file/task_<taskId>', methods=['POST'])
def upload_file(taskId):
    if DBHelper.authToken(session['token']):
        file = request.files['file']
        
        if file:
            filename = secure_filename("task_" + taskId + "_" + file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

            DBHelper.createFile(taskId, filename)

            return jsonify({'message': 'Обложка загружена', 'status': 1, 'result': filename})
    
    return redirect('/login')

@app.route('/api/login', methods=['POST'])
def login():
    """Используется для авторизации
    После успешной авторизации возвращается токен сессии в куки.
    ---
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            username:
              description: Имя пользователя
              type: string
              required: true
            password:
              description: Пароль
              type: string
              required: true
    definitions:
      components:
        securitySchemes:
          cookieAuth:
            type: apiKey
            in: cookie
            name: session
      security:
        - cookieAuth: []
    responses:
      200:
        description: Объект с сообщением и статусом запроса
        headers: 
            Set-Cookie:
              schema: 
                type: string
                example: session=abcde12345; Path=/; HttpOnly
        schema:
          type: object
          properties:
            message:
              description: Сообщение с информацией 
              type: string
            status:
              description: Статус исполнения запроса
              type: integer
        examples:
          {'message': 'string', 'status': 0}
    """

    data = request.json

    if not('username' in data and 'password' in data):
        return jsonify({'message': 'Укажите логин и пароль', 'status': 0})

    username = data['username']
    password = data['password']
    
    token, _ = DBHelper.authUser(username, password)

    if token:
        session['token'] = token
        res = jsonify({'message': 'Успешный вход', 'status': 1})
        res.headers.add('Access-Control-Allow-Origin', '*')
        return res
    
    return jsonify({'message': 'Ошибка входа', 'status': 0})

@app.route('/api/register', methods=['POST'])
def register():
    """Используется для регистрации
    После успешной регистрации редиректит на страницу логина
    ---
    parameters:
      - name: body
        in: body
        required: true
        schema:
          type: object
          properties:
            username:
              description: Имя пользователя
              type: string
              required: true
            password:
              description: Пароль
              type: string
              required: true
            role:
              description: Роль. Организатор не может учавствовать в турнире, а участники не могут их организовать
              type: string
              required: true
              enum: ['org', 'user']
    responses:
      200:
        description: Объект с сообщением и статусом запроса
        schema:
          type: object
          properties:
            message:
              description: Сообщение с информацией 
              type: string
            status:
              description: Статус исполнения запроса
              type: integer
        examples:
          {'message': 'string', 'status': 0}
    """

    data = request.json

    if not('username' in data and 'password' in data and 'role' in data) or (
        len(data['username']) < 4 or len(data['password']) < 4 or data['role'] not in ['org', 'user']):
        return jsonify({'message': 'Укажите логин и пароль', 'status': 0})

    username = data['username']
    password = data['password']
    role = data['role']

    status = DBHelper.createUser(username, password, role)

    if status:
        return jsonify({'message': 'Успешная регистрация', 'status': 1})
    else:
        return jsonify({'message': 'Ошибка регистрации', 'status': 0})

@app.route('/api/team/accept_invite/<id>', methods=['POST'])
def accept_invite(id):
    """Используется для принятия приглашения в команду
    ---
    security:
      - cookieAuth: []
    parameters:
      - name: id
        in: path
        required: true
        type: integer
        description: ID приглашения
    responses:
      200:
        description: Объект с сообщением и статусом запроса
        schema:
          type: object
          properties:
            message:
              description: Сообщение с информацией 
              type: string
            status:
              description: Статус исполнения запроса
              type: integer
        examples:
          {'message': 'string', 'status': 0}
    """

    if user := DBHelper.authToken(session['token']):
        invite = Invite.query.filter(and_(Invite.user_id == user.id, Invite.id == int(id))).first()

        print(invite, user.id, int(id))
        
        if not invite:
            return jsonify({'message': 'Приглашение не найдено', 'status': 0})

        if invite:
            if user.team_id:
                return jsonify({'message': 'Покиньте свою команду', 'status': 0})

            DBHelper.addInTeam(Team.query.get(invite.team_id), user)

            socketio.emit("ping", rooms=["/profile/" + str(user.id)])
            socketio.emit("ping", rooms=["/profile/" + str(invite.owner_id)])

            db.session.delete(invite)
            db.session.commit()

            return jsonify({'message': 'Вы приняли приглашение', 'status': 1})
        return jsonify({'message': 'Ошибка', 'status': 0})
    
    return redirect('/login')

@app.route('/api/team/decline_invite/<id>', methods=['POST'])
def decline_invite(id):
    """Используется для отклонения приглашения в команду
    ---
    security:
      - cookieAuth: []
    parameters:
      - name: id
        in: path
        required: true
        type: integer
        description: ID приглашения
    responses:
      200:
        description: Объект с сообщением и статусом запроса
        schema:
          type: object
          properties:
            message:
              description: Сообщение с информацией 
              type: string
            status:
              description: Статус исполнения запроса
              type: integer
        examples:
          {'message': 'string', 'status': 0}
    """

    if user := DBHelper.authToken(session['token']):
        invite = Invite.query.filter(and_(Invite.user_id == user.id, Invite.id == id)).first()

        if not invite:
            return jsonify({'message': 'Приглашение не найдено', 'status': 0})

        if invite:
            db.session.delete(invite)
            db.session.commit()

            socketio.emit("ping", rooms=["/profile/" + str(user.id)])

            return jsonify({'message': 'Вы отклонили приглашение', 'status': 2})
        return jsonify({'message': 'Ошибка', 'status': 1})

    return redirect('/login')

@app.route('/api/team/leave', methods=['POST'])
def leave_team():
    """Используется для выхода из команды
    Если вы лидером команды, она не будет расформирована
    Чтобы история матчей отсавалась доступной
    ---
    security:
      - cookieAuth: []
    responses:
      200:
        description: Объект с сообщением и статусом запроса
        schema:
          type: object
          properties:
            message:
              description: Сообщение с информацией 
              type: string
            status:
              description: Статус исполнения запроса
              type: integer
        examples:
          {'message': 'string', 'status': 0}
    """

    if user := DBHelper.authToken(session['token']):

        team = None
        if user.team_id:
            team = Team.query.get(user.team_id)

        if not team:
            return jsonify({'message': 'Вы не в команде', 'status': 0})
        
        if user.id == team.cap:
            teammate = team.users[-1]

            DBHelper.removeTeam(user, team)
            socketio.emit("ping", rooms=["/profile/" + str(user.id)])
            socketio.emit("ping", rooms=["/profile/" + str(teammate.id)])
        else:
            DBHelper.removeFromTeam(user, team)
            socketio.emit("ping", rooms=["/profile/" + str(user.id)])
            socketio.emit("ping", rooms=["/profile/" + str(team.cap)])
        
        return jsonify({'message': 'Вы вышли из команды', 'status': 1})
    
    return redirect('/login')

@app.route('/api/team/create_team/<name>', methods=['POST'])
def create_team(name):
    """Используется для создания команды
    Команды могут создавать только участники
    ---
    security:
      - cookieAuth: []
    parameters:
      - name: name
        in: path
        required: true
        type: string
        description: Название команды
    responses:
      200:
        description: Объект с сообщением и статусом запроса
        schema:
          type: object
          properties:
            message:
              description: Сообщение с информацией 
              type: string
            status:
              description: Статус исполнения запроса
              type: integer
        examples:
          {'message': 'string', 'status': 0}
    """

    if user := DBHelper.authToken(session['token']):
        if user.role != "org":
            return jsonify({'message': 'Только участники могут создавать команды', 'status': 0})

        if not name:
            return jsonify({'message': 'Укажите имя команды', 'status': 0})
        
        if user.team_id:
            return jsonify({'message': 'Вы уже в команде', 'status': 0})
        
        status = DBHelper.createTeam(name, user)
        socketio.emit("ping", rooms=["/profile/"])

        if status:
            return jsonify({'message': 'Команда создана', 'status': status})
        else:
            return jsonify({'message': 'Ошибка', 'status': status})

    return redirect('/login')

@app.route('/api/task/create_task', methods=['POST'])
def create_task():
    """Используется для создания турнира
    Может использовать только организатор
    ---
    security:
      - cookieAuth: []
    parameters:
      - name: body
        in: body
        required: true
        type: object
        schema:
          type: object
          properties:
            name:
              type: string
              required: true
            max_teams:
              type: integer
              default: 8
            size:
              type: string
              enum: ['small', 'medium', 'large']
              default: 'small'
            difficulty:
              type: string
              enum: ['easy', 'medium', 'hard']
              default: 'easy'
            win_score:
              type: integer
              default: 7
            start_date:
              type: integer
              default: 999999999999999
            cover:
              type: string
              default: 'placeholder_tour.jpg'
    responses:
      200:
        description: Объект с сообщением и статусом запроса
        schema:
          type: object
          properties:
            message:
              description: Сообщение с информацией 
              type: string
            status:
              description: Статус исполнения запроса
              type: integer
        examples:
          {'message': 'string', 'status': 0}
    """

    if user := DBHelper.authToken(session['token']):
        data = request.json

        if not user.team_id:
            return jsonify({'message': 'Вы не в команде', 'status': 0})

        if not 'text' in data:
            text = ''
        else:
            text = data['text']
        
        if not 'deadline' in data:
            deadline = 9999999999999999
        else:
            deadline = data['deadline']
        
        if not 'start_date' in data:
            start_date = round(time.time())
        else:
            start_date = data['start_date']
        
        if 'task_type' in data:
            task_type = data['task_type']
        else:
            task_type = 'task'
        
        if 'with_chat' in data:
            with_chat = data['with_chat']
        else:
            with_chat = False

        status = DBHelper.createTask(user, user.team_id,
                                           deadline=deadline,
                                           text=text,
                                           headline=data['name'],
                                           task_type=task_type,
                                           with_chat=with_chat,
                                           start=start_date)
        
        socketio.emit("ping", rooms=["/tasks"])

        if status:
            return jsonify({'message': 'Задача создана', 'status': 1})
        else:
            return jsonify({'message': 'Ошибка', 'status': 0})

    return redirect('/login')

@app.route('/api/getTasks', methods=['POST'])
def getTasks():
    """Используется для получения списка турниров
    Используются пагинация и фильтры
    ---
    security:
      - cookieAuth: []
    parameters:
      - name: id
        in: body
        required: true
        type: object
        schema:
          type: object
          properties:
            query:
              description: Поиск
              type: string
            size:
              description: Размер турнира
              type: string
              enum: ['all', 'small', 'medium', 'large']
              default: 'all'
            difficulty:
              description: Сложность турнира
              type: string
              enum: ['all', 'easy', 'medium', 'hard']
              default: 'all'
            sort_by:
              description: Сортировка
              type: string
              enum: ['date', 'name']
              default: 'date'
            order:
              description: Порядок сортировки
              type: string
              enum: ['asc', 'desc']
              default: 'desc'
            page:
              description: Страница для пагинации
              type: integer
              default: 1
            count:
              description: Количество элементов на странице
              type: integer
              default: 10
            only_mine:
              description: Только мои турниры
              type: boolean
              default: false
            i_org:
              description: Только организованные турниры
              type: boolean
              default: false
    responses:
      200:
        description: Объект с сообщением, статусом запроса и данными
        schema:
          type: object
          properties:
            message:
              description: Сообщение с информацией 
              type: string
            status:
              description: Статус исполнения запроса
              type: integer
            result:
              type: array
              items:
                type: object
                properties:
                  id:
                    description: ID турнира
                    type: integer
                  name:
                    description: Название турнира
                    type: string
                  cover:
                    description: Ссылка на обложку турнира
                    type: string
                  status:
                    description: Статус турнира
                    type: string
                    enum: ['open', 'active', 'closed']
                  start_date:
                    description: Дата начала турнира
                    type: integer
                  players:
                    description: Количество участников / всего
                    type: string
                    example: '2/4'
                  difficulty:
                    description: Сложность турнира
                    type: string
                    enum: ['easy', 'medium', 'hard']
                  size:
                    description: Размер турнира
                    type: string
                    enum: ['small', 'medium', 'large']
                  i_in:
                    description: Участвует текущий пользователь в турнире
                    type: boolean
    """

    if user := DBHelper.authToken(session['token']):
        data = request.json

        team = None
        if user.team_id:
            team = Team.query.get(user.team_id)
        else:
            return jsonify({'message': 'У вас нет команды', 'status': 0})

        tasks = Task.query.filter(Task.team.contains(team)).order_by(
            text(
            f"{'deadline' if data['sort_by'] == 'date' else 'headline'} {'desc' if data['order'] == 'desc' else 'asc'}"
            )
        ).filter(
            or_(Task.headline.contains(data['query']), Task.text.contains(data['query']))
        )

        if data['done'] != True:
            tasks = tasks.filter(
                Task.done == data['done']
            )
        
        if data['type'] != "all":
            tasks = tasks.filter(
                Task.task_type == data['type']
            )

        all_records = len(tasks.all())
        tasks = tasks.paginate(page=data['page'], error_out=False, max_per_page=data['count'])

        return jsonify({'message': 'Успех', 'status': 1, 'count': round(all_records), 'result': [
            {
                'id': task.id,
                'name': task.headline,
                'users': str(len(task.users)),
                'deadline': task.deadline,
                'start_date': task.start,
                'type': task.task_type,
                'done': task.done,
                'phase': task.phase,
                'files': [file.file_url for file in task.files],
                'all_phases': [
                    {
                        "id": phase.id,
                        "text": phase.text,
                        "deadline": phase.deadline,
                        "by": phase.by,
                        "by_name": (User.query.filter_by(id=phase.by).first().username if type(phase.by) == int else None),
                        "done": phase.done
                    } for phase in task.phases ]
            } for task in tasks
        ]})

    return redirect('/login')

@app.route('/api/getTask/<taskId>', methods=['POST'])
def getTask(taskId):
    """Используется для получения списка турниров
    Используются пагинация и фильтры
    ---
    security:
      - cookieAuth: []
    parameters:
      - name: id
        in: body
        required: true
        type: object
        schema:
          type: object
          properties:
            query:
              description: Поиск
              type: string
            size:
              description: Размер турнира
              type: string
              enum: ['all', 'small', 'medium', 'large']
              default: 'all'
            difficulty:
              description: Сложность турнира
              type: string
              enum: ['all', 'easy', 'medium', 'hard']
              default: 'all'
            sort_by:
              description: Сортировка
              type: string
              enum: ['date', 'name']
              default: 'date'
            order:
              description: Порядок сортировки
              type: string
              enum: ['asc', 'desc']
              default: 'desc'
            page:
              description: Страница для пагинации
              type: integer
              default: 1
            count:
              description: Количество элементов на странице
              type: integer
              default: 10
            only_mine:
              description: Только мои турниры
              type: boolean
              default: false
            i_org:
              description: Только организованные турниры
              type: boolean
              default: false
    responses:
      200:
        description: Объект с сообщением, статусом запроса и данными
        schema:
          type: object
          properties:
            message:
              description: Сообщение с информацией 
              type: string
            status:
              description: Статус исполнения запроса
              type: integer
            result:
              type: array
              items:
                type: object
                properties:
                  id:
                    description: ID турнира
                    type: integer
                  name:
                    description: Название турнира
                    type: string
                  cover:
                    description: Ссылка на обложку турнира
                    type: string
                  status:
                    description: Статус турнира
                    type: string
                    enum: ['open', 'active', 'closed']
                  start_date:
                    description: Дата начала турнира
                    type: integer
                  players:
                    description: Количество участников / всего
                    type: string
                    example: '2/4'
                  difficulty:
                    description: Сложность турнира
                    type: string
                    enum: ['easy', 'medium', 'hard']
                  size:
                    description: Размер турнира
                    type: string
                    enum: ['small', 'medium', 'large']
                  i_in:
                    description: Участвует текущий пользователь в турнире
                    type: boolean
    """

    if user := DBHelper.authToken(session['token']):
        task = Task.query.filter_by(id=taskId).first()

        return jsonify({'message': 'Успех', 'status': 1, 'result':
            {
                'id': task.id,
                'name': task.headline,
                'users_len': str(len(task.users)),
                'users': [
                    {
                        "id": user.id,
                        "name": user.username,
                        'cover': user.cover
                    } for user in task.users[:5] ],
                'deadline': task.deadline,
                'start_date': task.start,
                'type': task.task_type,
                'done': task.done,
                'text': task.text,
                'phase': task.phase,
                'files': [file.file_url for file in task.files],
                'all_phases': [
                    {
                        "id": phase.id,
                        "text": phase.text,
                        "deadline": phase.deadline,
                        "by": phase.by,
                        "by_name": (User.query.filter_by(id=phase.by).first().username if type(phase.by) == int else None),
                        "done": phase.done
                    } for phase in task.phases ]
            }
        })

    return redirect('/login')

@app.route('/api/task/query_invite/<taskId>/<query>', methods=['POST'])
def query_invite(taskId, query):
    """Используется для поиска среди игроков
    Для приглашения в команду
    ---
    security:
      - cookieAuth: []
    parameters:
      - name: query
        in: path
        required: true
        additionalProperties:
          type: [string, integer] 
        description: Строка поиска или ID пользователя для поиска
    responses:
      200:
        description: Объект с сообщением и статусом запроса и результатом запроса
        schema:
          type: object
          properties:
            message:
              type: string
            status:
              type: integer
            result:
              type: array
              items:
                type: object
                properties:
                  id:
                    description: ID пользователя
                    type: integer
                  name:
                    description: Имя пользователя
                    type: string
                  cover:
                    description: Ссылка на аватар пользователя
                    type: string
        examples:
          {'message': 'string', 'status': 1, result: [
            {
                'id': 0,
                'name': "string",
                'cover': "string"
            }
          ]}
    """

    if user := DBHelper.authToken(session['token']):
        if not query:
            return jsonify({'message': 'Передайте айди пользователя', 'status': 0})
        
        if not user.team_id:
            return jsonify({'message': 'Вы не в команде', 'status': 0})
        
        team = Team.query.get(user.team_id)
        task = Task.query.get(taskId)
        
        data = User.query.filter(User.team_id == team.id).filter(not_(User.id.in_(list(map(lambda x: x.id, task.users))))).filter(or_(User.id == query, User.username.contains(query))).all()

        return jsonify({'message': 'success', 'status': True, 'result': [
            {
                'id': user.id,
                'name': user.username,
                'cover': user.cover
            } for user in data
        ]})

    return jsonify({'message': 'Вы отправили приглашение', 'status': 1})

@app.route('/api/task/invite/', methods=['POST'])
def task_invite():
    """Используется для приглашения игрока в команду
    ---
    security:
      - cookieAuth: []
    parameters:
      - name: user_id
        in: path
        required: true
        type: integer
        description: ID пользователя для приглашения
    responses:
      200:
        description: Объект с сообщением и статусом запроса
        schema:
          type: object
          properties:
            message:
              description: Сообщение с информацией 
              type: string
            status:
              description: Статус исполнения запроса
              type: integer
        examples:
          {'message': 'string', 'status': 0}
    """

    if user := DBHelper.authToken(session['token']):
        data = request.json

        if not 'user_id' in data:
            return jsonify({'message': 'Передайте айди пользователя', 'status': 0})

        user_id = data['user_id']
        
        if not 'task_id' in data:
            return jsonify({'message': 'Передайте айди задачи', 'status': 0})
        
        task_id = data['task_id']

        if not (Task.query.get(task_id)):
            return jsonify({'message': 'Задача не найдена', 'status': 0})
        
        if not user.team_id:
            return jsonify({'message': 'Вы не в команде', 'status': 0})
        
        if not (user_to_invite := User.query.get(user_id)):
            return jsonify({'message': 'Пользователь не найден', 'status': 0})
        
        team = Team.query.get(user.team_id)

        if user_to_invite.team_id != user.team_id:
            return jsonify({'message': 'Он не член вашей команды', 'status': 0})
        
        DBHelper.addToTask(data['task_id'], data['user_id'])
        socketio.emit("ping", rooms=["/task/" + str(task_id)])

        return jsonify({'message': 'success', 'status': True})

    return jsonify({'message': 'Вы отправили приглашение', 'status': 1})

@app.route('/api/task/remove/', methods=['POST'])
def task_remove():
    """Используется для приглашения игрока в команду
    ---
    security:
      - cookieAuth: []
    parameters:
      - name: user_id
        in: path
        required: true
        type: integer
        description: ID пользователя для приглашения
    responses:
      200:
        description: Объект с сообщением и статусом запроса
        schema:
          type: object
          properties:
            message:
              description: Сообщение с информацией 
              type: string
            status:
              description: Статус исполнения запроса
              type: integer
        examples:
          {'message': 'string', 'status': 0}
    """

    if user := DBHelper.authToken(session['token']):
        data = request.json

        if not 'user_id' in data:
            return jsonify({'message': 'Передайте айди пользователя', 'status': 0})

        user_id = data['user_id']
        
        if not 'task_id' in data:
            return jsonify({'message': 'Передайте айди задачи', 'status': 0})
        
        task_id = data['task_id']

        if not (task_to_remove := Task.query.get(task_id)):
            return jsonify({'message': 'Задача не найдена', 'status': 0})

        if not user.team_id:
            return jsonify({'message': 'Вы не в команде', 'status': 0})
        
        if not (user_to_remove := User.query.get(user_id)):
            return jsonify({'message': 'Пользователь не найден', 'status': 0})
        
        if not user_to_remove in task_to_remove.users:
            return jsonify({'message': 'Человек не учавствует в задаче', 'status': 0})
        
        team = Team.query.get(user.team_id)
        
        DBHelper.removeFromTask(data['task_id'], data['user_id'])
        socketio.emit("ping", rooms=["/task/" + str(task_id)])

        return jsonify({'message': 'success', 'status': True})

    return jsonify({'message': 'Вы отправили приглашение', 'status': 1})

@app.route('/api/task/update/<taskId>', methods=['POST'])
def task_update(taskId):
    """Используется для приглашения игрока в команду
    ---
    security:
      - cookieAuth: []
    parameters:
      - name: user_id
        in: path
        required: true
        type: integer
        description: ID пользователя для приглашения
    responses:
      200:
        description: Объект с сообщением и статусом запроса
        schema:
          type: object
          properties:
            message:
              description: Сообщение с информацией 
              type: string
            status:
              description: Статус исполнения запроса
              type: integer
        examples:
          {'message': 'string', 'status': 0}
    """

    if user := DBHelper.authToken(session['token']):
        data = request.json
        
        task_id = taskId

        if not (task := Task.query.get(task_id)):
            return jsonify({'message': 'Задача не найдена', 'status': 0})
        
        if 'text' in data:
            text = data['text']
        else:
            text = task.text
        
        if 'headline' in data:
            headline = data['headline']
        else:
            headline = task.headline
        
        if 'deadline' in data:
            deadline = data['deadline']
        else:
            deadline = task.deadline
        
        if 'start' in data:
            start = data['start']
        else:
            start = task.start
        
        if 'phase' in data:
            phase = data['phase']
        else:
            phase = task.phase
        
        if 'phases' in data:
            phases = [{
                        "text": phase["text"],
                        "deadline": phase["deadline"],
                        "by": user.id if phase["by"] == "me" else phase["by"],
                        "done": phase["done"]
                    } for phase in data['phases'] ]
        else:
            phases = [
                    {
                        "id": phase.id,
                        "text": phase.text,
                        "deadline": phase.deadline,
                        "by": user.id if phase.by == "me" else phase.by,
                        "done": phase.done
                    } for phase in task.phases ]

        if not user.team_id:
            return jsonify({'message': 'Вы не в команде', 'status': 0})
        
        DBHelper.updateTask(taskId, text, headline, deadline, phase, phases, start)
        socketio.emit("ping", rooms=["/task/" + str(task_id)])
        socketio.emit("ping", rooms=["/tasks"])

        return jsonify({'message': 'success', 'status': True})

    return jsonify({'message': 'Вы отправили приглашение', 'status': 1})

@app.route('/api/getMe', methods=['POST'])
def getMe():
    """Используется для получения информации о текущем пользователе
    ---
    security:
      - cookieAuth: []
    responses:
      200:
        description: Объект с сообщением, статусом запроса и данными
        schema:
          type: object
          properties:
            message:
              description: Сообщение с информацией 
              type: string
            status:
              description: Статус исполнения запроса
              type: integer
            result:
              description: Объект данных
              type: object
              properties:
                id:
                  description: ID пользователя
                  type: integer
                username:
                  description: Имя пользователя
                  type: string
                role:
                  description: Роль пользователя
                  type: string
                  enum: ['user', 'org']
                cover:
                  description: Ссылка на обложку пользователя
                  type: string
                all_games:
                  description: Количество матчей
                  type: integer
                wins:
                  description: Количество побед
                  type: integer
                matches:
                  description: Последние 10 матчей
                  type: array
                  items:
                    type: object
                    properties:
                      T1:
                        description: Название команды 1
                        type: string
                      T2:
                        description: Название команды 2
                        type: string
                      score:
                        description: Счёт матча
                        type: string
                        example: '8:0'
                      tournament:
                        description: ID турнира
                        type: integer
                invites:
                  description: Последние 10 приглашений
                  type: array
                  items:
                    type: object
                    properties:
                      id:
                        description: ID приглашения
                        type: integer
                      team_id:
                        description: ID команды для приглашения
                        type: integer
                      team_name:
                        description: Название команды
                        type: string
                team:
                  description: Информация о команде
                  type: object
                  properties:
                    id:
                      description: ID команды
                      type: integer
                    name:
                      description: Название команды
                      type: string
                    cap:
                      description: ID лидера команды
                      type: integer
                    cover:
                      description: Ссылка на обложку команды
                      type: string
                    members:
                      description: Список участников команды
                      type: array
                      items:
                        type: object
                        properties:
                          id:
                            description: ID участника
                            type: integer
                          username:
                            description: Имя участника
                            type: string
                          cover:
                            description: Ссылка на обложку участника
                            type: string
    """

    if user := DBHelper.authToken(session['token']):
        team = None
        if user.team_id:
            team = Team.query.get(user.team_id)

        invites = Invite.query.filter(Invite.user_id == user.id).all()

        return jsonify({'message': 'Успех', 'status': 1, 'result': {
            'id': user.id,
            'username': user.username,
            'role': user.role,
            'cover': user.cover,
            'invites': [
                {
                    'id': invite.id,
                    'team_id': invite.team_id,
                    'team_name': Team.query.get(invite.team_id).name
                } if Team.query.get(invite.team_id) else None for invite in invites
            ] if invites else None,
            'team': {
                'id': team.id,
                'name': team.name,
                'cap': team.cap,
                'cover': team.cover,
                'members': [
                    {
                        'id': member.id,
                        'username': member.username,
                        'cover': member.cover
                    } for member in team.users
                ]
            } if team else None
        }})
    
    return redirect('/login')

@app.route('/api/team/query_invite/<query>', methods=['POST'])
def query_invite_team(query):
    """Используется для поиска среди игроков
    Для приглашения в команду
    ---
    security:
      - cookieAuth: []
    parameters:
      - name: query
        in: path
        required: true
        additionalProperties:
          type: [string, integer] 
        description: Строка поиска или ID пользователя для поиска
    responses:
      200:
        description: Объект с сообщением и статусом запроса и результатом запроса
        schema:
          type: object
          properties:
            message:
              type: string
            status:
              type: integer
            result:
              type: array
              items:
                type: object
                properties:
                  id:
                    description: ID пользователя
                    type: integer
                  name:
                    description: Имя пользователя
                    type: string
                  cover:
                    description: Ссылка на аватар пользователя
                    type: string
        examples:
          {'message': 'string', 'status': 1, result: [
            {
                'id': 0,
                'name': "string",
                'cover': "string"
            }
          ]}
    """

    if user := DBHelper.authToken(session['token']):
        if not query:
            return jsonify({'message': 'Передайте айди пользователя', 'status': 0})
        
        if not user.team_id:
            return jsonify({'message': 'Вы не в команде', 'status': 0})
        
        team = Team.query.get(user.team_id)
        
        if not team or team.cap != user.id:
            return jsonify({'message': 'Вы не капитан команды', 'status': 0})
        
        data = User.query.filter(and_(or_(User.id == query, User.username.contains(query)), User.id != user.id)).all()

        return jsonify({'message': 'success', 'status': True, 'result': [
            {
                'id': user.id,
                'name': user.username,
                'cover': user.cover
            } for user in data
        ]})

    return jsonify({'message': 'Вы отправили приглашение', 'status': 1})

@app.route('/api/team/invite/<user_id>', methods=['POST'])
def team_invite(user_id):
    """Используется для приглашения игрока в команду
    ---
    security:
      - cookieAuth: []
    parameters:
      - name: user_id
        in: path
        required: true
        type: integer
        description: ID пользователя для приглашения
    responses:
      200:
        description: Объект с сообщением и статусом запроса
        schema:
          type: object
          properties:
            message:
              description: Сообщение с информацией 
              type: string
            status:
              description: Статус исполнения запроса
              type: integer
        examples:
          {'message': 'string', 'status': 0}
    """

    if user := DBHelper.authToken(session['token']):
        if not user_id:
            return jsonify({'message': 'Передайте айди пользователя', 'status': 0})
        
        if not user.team_id:
            return jsonify({'message': 'Вы не в команде', 'status': 0})
        
        if not User.query.get(user_id):
            return jsonify({'message': 'Пользователь не найден', 'status': 0})
        
        team = Team.query.get(user.team_id)

        if not team or team.cap != user.id:
            return jsonify({'message': 'Вы не капитан команды', 'status': 0})
        
        DBHelper.createInvite(user_id, user.team_id, user.id)
        socketio.emit("ping", rooms=["/profile/" + str(user.id)])
        socketio.emit("ping", rooms=["/profile/" + str(user_id)])

        return jsonify({'message': 'success', 'status': True})

    return jsonify({'message': 'Вы отправили приглашение', 'status': 1})

@app.route('/api/task/chat/send/<taskId>', methods=['POST'])
def task_chat_send(taskId):
    """Используется для приглашения игрока в команду
    ---
    security:
      - cookieAuth: []
    parameters:
      - name: user_id
        in: path
        required: true
        type: integer
        description: ID пользователя для приглашения
    responses:
      200:
        description: Объект с сообщением и статусом запроса
        schema:
          type: object
          properties:
            message:
              description: Сообщение с информацией 
              type: string
            status:
              description: Статус исполнения запроса
              type: integer
        examples:
          {'message': 'string', 'status': 0}
    """

    if user := DBHelper.authToken(session['token']):
        data = request.json

        if not taskId:
            return jsonify({'message': 'Передайте айди задачи', 'status': 0})
        
        task = Task.query.get(taskId)
        if not task:
            return jsonify({'message': 'Задача не найдена', 'status': 0})
        if not user in task.users and task.owner != user.id:
            print(task.users, user, task.owner, user.id)
            return jsonify({'message': 'Вы не учавствуете в задаче', 'status': 0})

        if not 'text' in data:
            return jsonify({'message': 'Передайте текст', 'status': 0})
        
        if not user.team_id:
            return jsonify({'message': 'Вы не в команде', 'status': 0})
        
        team = Team.query.get(user.team_id)
        
        DBHelper.createMessage(taskId, user.id, data['text'])
        socketio.emit("ping", rooms=["/task/" + str(taskId)])

        return jsonify({'message': 'success', 'status': True})

    return jsonify({'message': 'Вы отправили сообщение', 'status': 1})

@app.route('/api/task/chat/get/<taskId>', methods=['POST'])
def task_chat_history(taskId):
    """Используется для приглашения игрока в команду
    ---
    security:
      - cookieAuth: []
    parameters:
      - name: user_id
        in: path
        required: true
        type: integer
        description: ID пользователя для приглашения
    responses:
      200:
        description: Объект с сообщением и статусом запроса
        schema:
          type: object
          properties:
            message:
              description: Сообщение с информацией 
              type: string
            status:
              description: Статус исполнения запроса
              type: integer
        examples:
          {'message': 'string', 'status': 0}
    """

    if user := DBHelper.authToken(session['token']):
        data = request.json

        if not taskId:
            return jsonify({'message': 'Передайте айди задачи', 'status': 0})
        
        task = Task.query.get(taskId)
        if not task:
            return jsonify({'message': 'Задача не найдена', 'status': 0})
        
        if not user in task.users and task.owner != user.id:
            print(task.users, user, task.owner, user.id)
            return jsonify({'message': 'Вы не учавствуете в задаче', 'status': 0})

        if not 'limit' in data:
            limit = 10
        else:
            limit = max(50, data['limit'])
        
        if not user.team_id:
            return jsonify({'message': 'Вы не в команде', 'status': 0})
        
        team = Team.query.get(user.team_id)
        
        res = Message.query.filter(Message.task_id == taskId).order_by(Message.id.asc()).limit(limit).all()

        return jsonify({'message': 'success', 'status': True, 'result': [
            {
                'id': message.id,
                'me': message.user_id == user.id,
                'username': User.query.get(message.user_id).username,
                'cover': User.query.get(message.user_id).cover,
                'text': message.text,
            } for message in res
        ]})

    return jsonify({'message': 'Вы не отправили сообщение', 'status': 1})

def auth_ws(session):
    if 'token' in session:
        return DBHelper.authToken(session['token'])
    
@socketio.on('connect')
def on_connect(*args):
    if user := auth_ws(session):
        emit('connected', {'id': user.id})
    else:
        disconnect()

@socketio.on('unsub_all')
def unsub_all():
    if user := auth_ws(session):
        pass
    else:
        disconnect()

@socketio.on('listen_for')
def listen_for(data):
    if user := auth_ws(session):
        room = data['room']

        for room in rooms():
            if room != "tasks":
                leave_room(room)

        if room in ["/register", "/login"]:
            return
        
        join_room(room)
    else:
        disconnect()

@socketio.on('message')
def send_message(data):
    if user := auth_ws(session):
        taskId = data['task_id']

        if not taskId:
            return jsonify({'message': 'Передайте айди задачи', 'status': 0})
        
        task = Task.query.get(taskId)
        if not task:
            return jsonify({'message': 'Задача не найдена', 'status': 0})
        if not user in task.users and task.owner != user.id:
            print(task.users, user, task.owner, user.id)
            return jsonify({'message': 'Вы не учавствуете в задаче', 'status': 0})

        if not 'text' in data:
            return jsonify({'message': 'Передайте текст', 'status': 0})
        
        if not user.team_id:
            return jsonify({'message': 'Вы не в команде', 'status': 0})
        
        team = Team.query.get(user.team_id)
        
        m = DBHelper.createMessage(taskId, user.id, data['text'])
        socketio.emit("ping_message", data={
                'id': m.id,
                'me': m.user_id == user.id,
                'username': User.query.get(m.user_id).username,
                'cover': User.query.get(m.user_id).cover,
                'text': m.text,
            }, rooms=["/task/" + str(taskId)])

        return jsonify({'message': 'success', 'status': True})
    else:
        disconnect()
    

if __name__ == '__main__':
    with app.app_context():
        db.create_all()

    socketio.run(app, host="0.0.0.0", port=443, certfile='./certificate.crt', keyfile='./privatkey.pem', server_side=True)