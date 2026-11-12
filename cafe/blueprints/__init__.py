def register_blueprints(app):
    from . import main, auth, account, menu, orders, admin
    for m in (main, auth, account, menu, orders, admin):
        app.register_blueprint(m.bp)
