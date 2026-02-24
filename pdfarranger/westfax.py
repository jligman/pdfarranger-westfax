import gettext
import base64
from gi.repository import Gtk

_ = gettext.gettext


def make_westfax_settings_handler(app):
    def handler(_action, _option=None, _unknown=None):
        prefs = app.config.data['preferences']

        username = prefs.get('westfax_username', '') or ''
        password = deobf(prefs.get('westfax_password', '') or '')
        product_id = prefs.get('westfax_product_id', '') or ''
        login_url = prefs.get('westfax_login_url', '') or ''
        
        d = Gtk.Dialog(
            title=_("WestFax Settings"),
            parent=app.window,
            flags=Gtk.DialogFlags.MODAL,
            buttons=(_("_Cancel"), Gtk.ResponseType.CANCEL,
                     _("_OK"), Gtk.ResponseType.OK)
        )
        d.set_resizable(False)

        grid = Gtk.Grid(row_spacing=6, column_spacing=12, border_width=12)

        grid.attach(Gtk.Label(label=_("Username:"), halign=Gtk.Align.START), 0, 0, 1, 1)
        entry_username = Gtk.Entry(text=username)
        grid.attach(entry_username, 1, 0, 1, 1)

        grid.attach(Gtk.Label(label=_("Password:"), halign=Gtk.Align.START), 0, 1, 1, 1)
        entry_password = Gtk.Entry(text=password)
        entry_password.set_visibility(False)
        grid.attach(entry_password, 1, 1, 1, 1)

        grid.attach(Gtk.Label(label=_("ProductId:"), halign=Gtk.Align.START), 0, 2, 1, 1)
        entry_product_id = Gtk.Entry(text=product_id)
        grid.attach(entry_product_id, 1, 2, 1, 1)

        grid.attach(Gtk.Label(label=_("Login URL:"), halign=Gtk.Align.START), 0, 3, 1, 1)
        entry_login = Gtk.Entry()
        entry_login.set_text(login_url)
        grid.attach(entry_login, 1, 3, 1, 1)

        d.vbox.pack_start(grid, True, True, 0)
        d.show_all()

        if d.run() == Gtk.ResponseType.OK:
            username_val = entry_username.get_text().strip()
            password_val = entry_password.get_text()
            product_id_val = entry_product_id.get_text().strip()
            login_url_val = entry_login.get_text().strip()

            prefs['westfax_username'] = username_val
            prefs['westfax_password'] = obf(password_val)
            prefs['westfax_product_id'] = product_id_val
            prefs['westfax_login_url'] = login_url_val

            try:
                app.config.save()
            except Exception:
                pass

        d.destroy()

    return handler

def obf(s: str) -> str:
    if not s:
        return ""
    return base64.b64encode(s.encode("utf-8")).decode("ascii")

def deobf(s: str) -> str:
    if not s:
        return ""
    try:
        return base64.b64decode(s.encode("ascii")).decode("utf-8")
    except Exception:
        return s

def make_westfax_send_handler(app):
    def handler(_action, _option=None, _unknown=None):
        d = Gtk.MessageDialog(
            transient_for=app.window,
            modal=True,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text="WestFax send is not implemented yet."
        )
        d.run()
        d.destroy()
    return handler