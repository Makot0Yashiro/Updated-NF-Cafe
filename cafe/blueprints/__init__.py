def register_blueprints(app):
    from . import main, auth, account, menu, orders, admin, inventory
    for m in (main, auth, account, menu, orders, admin, inventory):
        app.register_blueprint(m.bp)
