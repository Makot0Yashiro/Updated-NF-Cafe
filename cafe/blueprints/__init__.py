def register_blueprints(app):
    from . import main, auth, account, menu, orders, admin, inventory, media
    for m in (main, auth, account, menu, orders, admin, inventory, media):
        app.register_blueprint(m.bp)
