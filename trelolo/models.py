from .extensions import db


class Emails(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.Unicode(45), nullable=False)
    email = db.Column(db.Unicode(45), nullable=False)


class Boards(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    trello_id = db.Column(db.Unicode(45), nullable=False)
    name = db.Column(db.Unicode(100), nullable=False)
    type = db.Column(db.Integer, default=3, nullable=False)
    hook_id = db.Column(db.Unicode(45), nullable=False)
    hook_url = db.Column(db.Unicode(400), nullable=False)


class Cards(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    card_id = db.Column(db.Unicode(45), nullable=False, index=True)
    board_id = db.Column(db.Unicode(45), nullable=False, index=True)
    parent_card_id = db.Column(db.Unicode(45), nullable=False, index=True)
    item_id = db.Column(db.Unicode(45), nullable=False, index=True)
    item_name = db.Column(db.Unicode(400), nullable=False)
    checked = db.Column(db.Boolean, default=False, nullable=False)
    label = db.Column(db.Unicode(100), nullable=False)
    hook_id = db.Column(db.Unicode(45), nullable=False)
    hook_url = db.Column(db.Unicode(400))


class Issues(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    issue_id = db.Column(db.Unicode(45), nullable=False, index=True)
    project_id = db.Column(db.Unicode(45), nullable=False, index=True)
    parent_card_id = db.Column(db.Unicode(45), nullable=False, index=True)
    item_id = db.Column(db.Unicode(45), nullable=False, index=True)
    item_name = db.Column(db.Unicode(400), nullable=False)
    label = db.Column(db.Unicode(100), nullable=False)
    milestone = db.Column(db.Unicode(100), default='', nullable=False)
    hook_id = db.Column(db.Unicode(45), nullable=False)
    hook_url = db.Column(db.Unicode(400), nullable=False)
    checked = db.Column(db.Boolean, default=False, nullable=False)
    target_type = db.Column(db.Unicode(10), default='issue', nullable=False)
