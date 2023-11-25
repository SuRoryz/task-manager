from json import loads, dumps
import sqlite3
import random
import uuid
import time

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Boolean, event, func
from sqlalchemy_events import listen_events, on

from datetime import datetime

import math
import more_itertools as mit

from flask_socketio import SocketIO, emit

class Base(DeclarativeBase):
  pass

db = SQLAlchemy(model_class=Base)

class User(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    username: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, default='user', nullable=False)

    cover: Mapped[str] = mapped_column(String, nullable=True, default='placeholder_user.jpg')

    team_id: Mapped[int] = db.Column(db.Integer, db.ForeignKey('team.id'))

    def __repr__(self) -> str:
        return f"<User {self.id} {self.username} {self.role} {self.team_id}>"

class AuthToken(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    token: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    user_id: Mapped[int] = db.Column(Integer, db.ForeignKey('user.id'), nullable=False)
    user: Mapped['User'] = db.relationship('User')

class Invite(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    team_id: Mapped[int] = db.Column(Integer, db.ForeignKey('team.id'), nullable=False)
    user_id: Mapped[int] = db.Column(Integer, db.ForeignKey('user.id'), nullable=False)
    owner_id: Mapped[int] = db.Column(Integer, db.ForeignKey('user.id'), nullable=False)

class TeamTasks(db.Model):
    __tablename__ = 'team_tasks'
    id = db.Column(db.Integer, primary_key=True)
    team_id: Mapped[int] = db.Column(Integer, db.ForeignKey('team.id'), nullable=False)
    task_id: Mapped[int] = db.Column(Integer, db.ForeignKey('task.id'), nullable=False)

class UserTasks(db.Model):
    __tablename__ = 'user_tasks'
    id = db.Column(db.Integer, primary_key=True)
    user_id: Mapped[int] = db.Column(Integer, db.ForeignKey('user.id'), nullable=False)
    task_id: Mapped[int] = db.Column(Integer, db.ForeignKey('task.id'), nullable=False)

class Message(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    text: Mapped[str] = mapped_column(String, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    user_id: Mapped[int] = db.Column(Integer, db.ForeignKey('user.id'), nullable=False)
    user: Mapped['User'] = db.relationship('User')
    task_id: Mapped[int] = db.Column(Integer, db.ForeignKey('task.id'), nullable=False)
    task: Mapped['Task'] = db.relationship('Task')

class Team(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    cap: Mapped[int] = db.Column(Integer, db.ForeignKey('user.id'), nullable=True)
    users: Mapped[list['User']] = db.relationship('User', backref='team', foreign_keys='User.team_id')

    cover: Mapped[str] = mapped_column(String, nullable=True, default='placeholder_team.jpg')

    def addUser(self, user=None, user_id=None):

        if not user:
            user = User.query.get(user_id)

        user.team_id = self.id

        db.session.commit()

    def __repr__(self) -> str:
        return f"<Team {self.id} {self.name} CAP: {self.cap} TEAM: {self.users}>"

class Task(db.Model, ):
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner: Mapped[int] = mapped_column(Integer, nullable=True)
    deadline: Mapped[int] = mapped_column(Integer, nullable=True)
    start: Mapped[int] = mapped_column(Integer, nullable=True)

    headline: Mapped[str] = mapped_column(String, nullable=True, default="0:0")
    text: Mapped[bool] = mapped_column(String, default="")
    task_type: Mapped[str] = mapped_column(String, default="task")

    with_chat: Mapped[bool] = mapped_column(Boolean, default=False)
    with_files: Mapped[bool] = mapped_column(Boolean, default=True)

    done: Mapped[bool] = mapped_column(Boolean, default=False)

    files: Mapped[list['TaskFile']] = db.relationship('TaskFile', backref='task', foreign_keys='TaskFile.task_id')

    phase: Mapped[int] = mapped_column(Integer, default=0)
    phases: Mapped[list['TaskPhase']] = db.relationship('TaskPhase', backref='task', foreign_keys='TaskPhase.task_id')

    team = db.relationship('Team', secondary=TeamTasks.__table__, backref='tasks')
    users = db.relationship('User', secondary=UserTasks.__table__, backref='tasks')

    def createStartPhases(self):
        start = TaskPhase(task_id=self.id, deadline=0, text="Начало")
        end = TaskPhase(task_id=self.id, deadline=0, text="Задача выполнена")

        db.session.add(start)
        db.session.add(end)
        db.session.commit()

    def __repr__(self) -> str:
        return (f"<Match {self.id} TOURNAMENT:  AGREED DONE: {self.done} |"
                f" | PHASE: {self.phase} | Users: {[user.id for user in self.users]}>"
        )

class TaskPhase(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(Integer, db.ForeignKey('task.id'), nullable=False)
    deadline: Mapped[int] = mapped_column(Integer, nullable=True)
    by: Mapped[int] = mapped_column(Integer, nullable=True)
    text: Mapped[str] = mapped_column(String, nullable=True, default="0:0")
    done: Mapped[bool] = mapped_column(Boolean, default=False)

class TaskFile(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(Integer, db.ForeignKey('task.id'), nullable=False)
    file_url: Mapped[str] = mapped_column(String, nullable=False)

class DBHelper:
    db = db

    @classmethod
    def authToken(cls, token):
        token = cls.db.session.query(AuthToken).filter_by(token=token).first()

        if not token:
            return False
        
        if datetime.timestamp(token.created_at) + 3600 > int(time.time()):
            db.session.delete(token)
            db.session.commit()
            return None
        
        return token.user
    
    @classmethod
    def deleteToken(cls, user):
        cls.db.session.query(AuthToken).filter_by(user_id=user.id).delete()
        cls.db.session.commit()

    @classmethod
    def authUser(cls, username, password):
        user = User.query.filter(func.lower(User.username) == username.lower()).first()

        if user and user.password == password:
            token = str(uuid.uuid4())
            cls.db.session.add(AuthToken(token=token, user_id=user.id))
            cls.db.session.commit()
            return token, user.id
        
        return None, None

    @classmethod
    def createUser(cls, username, password, role):
        user = cls.db.session.query(User).filter_by(username=username).first()

        if user:
            return False
        
        user = User(username=username, password=password, role=role)

        cls.db.session.add(user)
        cls.db.session.commit()

        return True
    
    @classmethod
    def createTeam(cls, name, user):
        team = cls.db.session.query(Team).filter_by(name=name).first()

        if team:
            return False
        
        team = Team(name=name, cap=user.id)
        
        cls.db.session.add(team)
        cls.db.session.commit()

        user.team_id = team.id

        print('TD', user.team_id)

        cls.db.session.commit()

        return True

    @classmethod
    def addInTeam(cls, team, user):
        team.addUser(user)
    
    @classmethod
    def createTask(cls, user, team_id, deadline, headline, text, task_type="task", with_chat=False, with_files=True, start=0):
        team1 = cls.db.session.query(Team).filter_by(id=team_id).first()

        if not(team1):
            return False

        task = Task(owner=user.id, team=[team1], deadline=deadline, headline=headline, text=text, task_type=task_type, with_chat=with_chat, with_files=with_files, start=start)

        cls.db.session.add(task)
        cls.db.session.commit()

        task.createStartPhases()

        return True
    
    @classmethod
    def createInvite(cls, userId, teamId, ownerId):
        invite = Invite(user_id=userId, team_id=teamId, owner_id = ownerId)
        cls.db.session.add(invite)

        cls.db.session.commit()

        return True

    @classmethod
    def addToTask(cls, task_id, user_id):
        user = cls.db.session.query(User).filter_by(id=user_id).first()
        task = cls.db.session.query(Task).filter_by(id=task_id).first()

        task.users.append(user)

        cls.db.session.commit()
    
    @classmethod
    def removeFromTask(cls, task_id, user_id):
        user = cls.db.session.query(User).filter_by(id=user_id).first()
        task = cls.db.session.query(Task).filter_by(id=task_id).first()

        task.users.remove(user)

        cls.db.session.commit()
    
    @classmethod
    def updateTask(cls, task_id, text, headline, deadline, phase, phases, start):
        task = cls.db.session.query(Task).filter_by(id=task_id).first()

        task.deadline = deadline
        task.text = text
        task.headline = headline
        task.phase = phase
        task.start = start

        if phase >= len(phases):
            task.done = True
        
        for phase in task.phases:
            cls.db.session.query(TaskPhase).filter_by(id=phase.id).delete()
        
        q = []
        for phase in phases:
            q.append(TaskPhase(text=phase["text"], deadline=phase["deadline"], done=phase["done"], by=phase["by"]))

        task.phases = q

        cls.db.session.commit()

    @classmethod
    def removeFromTeam(cls, user, team):
        team.users.remove(user)
        
        cls.db.session.commit()
    
    @classmethod
    def removeTeam(cls, team):
        for u in team.users:
            u.team_id = None
        
        cls.db.session.query(Invite).filter_by(team_id=team.id).delete()
        cls.db.session.query(Team).filter_by(id=team.id).delete()
        cls.db.session.commit()
    
    @classmethod
    def createMessage(cls, task_id, user_id, text):
        message = Message(task_id=task_id, user_id=user_id, text=text)

        cls.db.session.add(message)
        cls.db.session.commit()

        return message
    
    @classmethod
    def createFile(cls, task_id, filename):
        file = TaskFile(task_id=task_id, file_url=filename)

        cls.db.session.add(file)
        cls.db.session.commit()



    
            