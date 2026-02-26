"""
WestFax integration helpers for PDF Arranger.

- Dialogs for settings and sending faxes.
- Lightweight obfuscation for stored password (base64) is used today;
  this is NOT secure — consider keyring/os-specific secure storage.
"""
import base64
import os
import re
import tempfile
import gettext
from typing import Optional

import requests
from gi.repository import Gtk

_ = gettext.gettext

WESTFAX_SEND_URL = "https://api2.westfax.com/REST/Fax_SendFax/json"
WESTFAX_CONTACTS_URL = "https://api2.westfax.com/REST/Contact_GetContactList/json"
WESTFAX_USERINFO_URL = "https://api2.westfax.com/REST/Security_GetUserInfo/json"


def make_westfax_settings_handler(app):
    """Return a handler bound to the application instance that shows the Settings dialog."""
    def handler(_action, _option=None, _unknown=None):
        prefs = app.config.data['preferences']

        username = prefs.get('westfax_username', '') or ''
        password = _deobf(prefs.get('westfax_password', '') or '')
        product_id = prefs.get('westfax_product_id', '') or ''
        login_url = prefs.get('westfax_login_url', '') or ''
        ani = prefs.get('westfax_ani', '') or ''

        d = Gtk.Dialog(
            title=_("WestFax Settings"),
            parent=app.window,
            flags=Gtk.DialogFlags.MODAL,
            buttons=(_("_Cancel"), Gtk.ResponseType.CANCEL,
                     _("_OK"), Gtk.ResponseType.OK),
        )
        d.set_resizable(False)

        grid = Gtk.Grid(row_spacing=6, column_spacing=12, border_width=12, margin=8)

        grid.attach(Gtk.Label(label=_("Username:"), halign=Gtk.Align.START), 0, 0, 1, 1)
        entry_username = Gtk.Entry()
        entry_username.set_text(username)
        grid.attach(entry_username, 1, 0, 1, 1)

        grid.attach(Gtk.Label(label=_("Password:"), halign=Gtk.Align.START), 0, 1, 1, 1)
        entry_password = Gtk.Entry()
        entry_password.set_text(password)
        entry_password.set_visibility(False)
        entry_password.set_placeholder_text(_("Password"))
        grid.attach(entry_password, 1, 1, 1, 1)

        grid.attach(Gtk.Label(label=_("Product Id:"), halign=Gtk.Align.START), 0, 2, 1, 1)
        entry_product_id = Gtk.Entry()
        entry_product_id.set_text(product_id)
        grid.attach(entry_product_id, 1, 2, 1, 1)

        grid.attach(Gtk.Label(label=_("Login URL:"), halign=Gtk.Align.START), 0, 3, 1, 1)
        entry_login = Gtk.Entry()
        entry_login.set_text(login_url)
        grid.attach(entry_login, 1, 3, 1, 1)

        grid.attach(Gtk.Label(label=_("Sending Fax #:"), halign=Gtk.Align.START), 0, 4, 1, 1)
        entry_ani = Gtk.Entry()
        entry_ani.set_text(ani)
        entry_ani.set_placeholder_text("##########")
        grid.attach(entry_ani, 1, 4, 1, 1)

        d.vbox.pack_start(grid, True, True, 0)
        d.show_all()

        if d.run() == Gtk.ResponseType.OK:
            prefs['westfax_username'] = entry_username.get_text().strip()
            prefs['westfax_password'] = _obf(entry_password.get_text() or '')
            prefs['westfax_product_id'] = entry_product_id.get_text().strip()
            prefs['westfax_login_url'] = entry_login.get_text().strip()
            prefs['westfax_ani'] = entry_ani.get_text().strip()
            try:
                app.config.save()
            except Exception:
                # Do not crash the app if saving fails
                pass
        d.destroy()

    return handler


def make_westfax_send_handler(app):
    """Return a handler that shows the Send Fax dialog and performs the API call."""
    def handler(_action, _option=None, _unknown=None):
        # 1) Ask for destination fax number
        d = Gtk.Dialog(
            title=_("Send Fax"),
            parent=app.window,
            flags=Gtk.DialogFlags.MODAL,
            buttons=(_("_Cancel"), Gtk.ResponseType.CANCEL,
                     _("_Send"), Gtk.ResponseType.OK),
        )
        d.set_resizable(False)

        grid = Gtk.Grid(row_spacing=6, column_spacing=12, border_width=12, margin=8)
        grid.attach(Gtk.Label(label=_("Destination Fax Number:"), halign=Gtk.Align.START), 0, 0, 1, 1)
        entry_to = Gtk.Entry()
        entry_to.set_placeholder_text("+1##########")
        grid.attach(entry_to, 1, 0, 1, 1)

        btn_lookup = Gtk.Button(label=_("Lookup..."))
        grid.attach(btn_lookup, 2, 0, 1, 1)

        grid.attach(Gtk.Label(label=_("Subject:"), halign=Gtk.Align.START), 0, 1, 1, 1)
        entry_subject = Gtk.Entry()
        entry_subject.set_placeholder_text(_("Subject / Job name"))
        grid.attach(entry_subject, 1, 1, 1, 1)

        grid.attach(Gtk.Label(label=_("Reference:"), halign=Gtk.Align.START), 0, 2, 1, 1)
        entry_ref = Gtk.Entry()
        entry_ref.set_placeholder_text(_("Reference / Billing code"))
        grid.attach(entry_ref, 1, 2, 1, 1)

        chk_receipt = Gtk.CheckButton(label=_("Send Delivery Receipt"))
        chk_receipt.set_active(True)
        grid.attach(chk_receipt, 1, 3, 2, 1)

        d.vbox.pack_start(grid, True, True, 0)

        def _lookup_clicked(_btn):
            prefs = app.config.data['preferences']
            username = (prefs.get('westfax_username', '') or '').strip()
            password = _deobf(prefs.get('westfax_password', '') or '')
            product_id = (prefs.get('westfax_product_id', '') or '').strip()

            try:
                resp = westfax_get_contacts(username, password, product_id)
            except Exception as ex:
                app.error_message_dialog(str(ex))
                return

            contacts = resp.get("Result") or []

            dlg = Gtk.Dialog(
                title=_("WestFax Contacts"),
                parent=d,
                flags=Gtk.DialogFlags.MODAL,
                buttons=(_("_Cancel"), Gtk.ResponseType.CANCEL,
                         _("_Select"), Gtk.ResponseType.OK),
            )
            dlg.set_default_size(520, 360)

            vbox = dlg.get_content_area()

            search = Gtk.Entry()
            search.set_placeholder_text(_("Search (first, last, company, fax)..."))
            vbox.pack_start(search, False, False, 6)

            # Data model: First, Last, Company, Fax
            store = Gtk.ListStore(str, str, str, str)

            def refill(filter_text: str = ""):
                store.clear()
                q = (filter_text or "").strip().lower()
                for c in contacts:
                    if not isinstance(c, dict):
                        continue
                    first = (c.get("FirstName") or "").strip()
                    last = (c.get("LastName") or "").strip()
                    company = (c.get("CompanyName") or "").strip()
                    fax = (c.get("Fax") or "").strip()
                    if not fax:
                        continue
                    haystack = f"{first} {last} {company} {fax}".lower()
                    if not q or q in haystack:
                        store.append([first, last, company, fax])

            refill()
            search.connect("changed", lambda e: refill(e.get_text()))

            tree = Gtk.TreeView(model=store)

            def on_row_activated(_tree, _path, _column):
                dlg.response(Gtk.ResponseType.OK)

            tree.connect("row-activated", on_row_activated)

            tree.append_column(Gtk.TreeViewColumn(_("First"), Gtk.CellRendererText(), text=0))
            tree.append_column(Gtk.TreeViewColumn(_("Last"), Gtk.CellRendererText(), text=1))
            tree.append_column(Gtk.TreeViewColumn(_("Company"), Gtk.CellRendererText(), text=2))
            tree.append_column(Gtk.TreeViewColumn(_("Fax"), Gtk.CellRendererText(), text=3))

            sc = Gtk.ScrolledWindow()
            sc.set_hexpand(True)
            sc.set_vexpand(True)
            sc.add(tree)
            vbox.pack_start(sc, True, True, 6)

            dlg.show_all()
            search.grab_focus()

            # Make sure GTK has computed column sizes
            while Gtk.events_pending():
                Gtk.main_iteration()

            total_cols = sum(col.get_width() for col in tree.get_columns())
            pad = 80
            dlg.resize(total_cols + pad, 420)

            if dlg.run() == Gtk.ResponseType.OK:
                model, it = tree.get_selection().get_selected()
                if it:
                    entry_to.set_text(model[it][3])
            dlg.destroy()

        btn_lookup.connect("clicked", _lookup_clicked)

        d.show_all()
        entry_to.grab_focus()

        if d.run() != Gtk.ResponseType.OK:
            d.destroy()
            return

        to_number = entry_to.get_text().strip()
        to_number = re.sub(r"\D", "", to_number)
        if not re.fullmatch(r"\d{7,20}", to_number):
            app.error_message_dialog(_("Invalid fax number. Use digits only (e.g. 2105551234)."))
            return
        job_name = entry_subject.get_text().strip() or ""
        billing_code = entry_ref.get_text().strip() or ""
        send_receipt = chk_receipt.get_active()
        d.destroy()

        if not _validate_phone(to_number):
            app.error_message_dialog(_("Invalid fax number. Use digits, optionally starting with +."))
            return

        header = ""
        prefs = app.config.data['preferences']
        ani = (prefs.get('westfax_ani', '') or '').strip()
        if not ani:
            app.error_message_dialog(_("Fax number is not set. Open WestFax Settings."))
            return

        ani = re.sub(r"\D", "", ani)
        if not re.fullmatch(r"\d{7,20}", ani):
            app.error_message_dialog(_("Invalid ANI. Use digits only (e.g. 2105551234)."))
            return

        pdf_path = app.save_file or (app.pdfqueue[0].filename if app.pdfqueue else None)
        if not pdf_path or not os.path.exists(pdf_path):
            app.error_message_dialog(_("No saved PDF to fax. Please save the document first."))
            return

        fd, tmp_pdf = tempfile.mkstemp(suffix=".pdf", prefix="westfax_", dir=app.tmp_dir)
        os.close(fd)
        try:
            with open(pdf_path, "rb") as src, open(tmp_pdf, "wb") as dst:
                while True:
                    buf = src.read(1024 * 1024)
                    if not buf:
                        break
                    dst.write(buf)

            prefs = app.config.data['preferences']
            username = (prefs.get('westfax_username', '') or '').strip()
            password = _deobf(prefs.get('westfax_password', '') or '')
            product_id = (prefs.get('westfax_product_id', '') or '').strip()
            ani = re.sub(r"\D", "", (prefs.get('westfax_ani', '') or '').strip())

            try:
                feedback_email = None
                if send_receipt:
                    feedback_email = (prefs.get("westfax_user_email") or "").strip()
                    if not feedback_email:
                        feedback_email = westfax_get_user_email(username, password, product_id)
                        prefs["westfax_user_email"] = feedback_email
                        try:
                            app.config.save()
                        except Exception:
                            pass

                result = westfax_send_fax(
                    username=username,
                    password=password,
                    product_id=product_id,
                    ani=ani,
                    to_number=to_number,
                    pdf_path=tmp_pdf,
                    job_name=job_name,
                    billing_code=billing_code,
                    header=header,
                    feedback_email=feedback_email,
                )

                show_westfax_result_dialog(
                    parent=app.window,
                    to_number=to_number,
                    job_name=job_name,
                    result=result,
                    error=None,
                )

            except Exception as ex:
                show_westfax_result_dialog(
                    parent=app.window,
                    to_number=to_number,
                    job_name=job_name,
                    result=None,
                    error=ex,
                )

        finally:
            try:
                os.remove(tmp_pdf)
            except Exception:
                pass

    return handler


def show_westfax_result_dialog(parent, to_number, job_name, result, error=None):
    """Show result dialog. Treat a returned Success=False as failure."""
    api_success = None
    if isinstance(result, dict) and "Success" in result:
        api_success = bool(result.get("Success"))

    ok = (error is None) and (api_success is not False)
    title = _("Fax sent") if ok else _("Fax failed")
    msg_type = Gtk.MessageType.INFO if ok else Gtk.MessageType.ERROR

    dlg = Gtk.MessageDialog(
        transient_for=parent,
        modal=True,
        message_type=msg_type,
        buttons=Gtk.ButtonsType.OK,
        text=title,
    )

    lines = []
    if to_number:
        lines.append(_("To: ") + str(to_number))
    if job_name:
        lines.append(_("Subject: ") + str(job_name))

    if isinstance(result, dict) and api_success is False:
        info = (result.get("InfoString") or "").strip()
        err = (result.get("ErrorString") or "").strip()
        if info or err:
            lines.append("")
        if info:
            lines.append(info)
        if err and err != info:
            lines.append(err)

    if error is not None:
        lines.append("")
        lines.append(str(error))

    dlg.format_secondary_text("\n".join(lines) if lines else "")

    exp = Gtk.Expander(label=_("Details"))
    exp.set_expanded(False)

    if error is not None:
        details = str(error)
    else:
        try:
            import json
            details = json.dumps(result, indent=2, ensure_ascii=False)
        except Exception:
            details = str(result)

    tv = Gtk.TextView(editable=False, monospace=True)
    tv.get_buffer().set_text(details)
    tv.set_wrap_mode(Gtk.WrapMode.NONE)

    sc = Gtk.ScrolledWindow()
    sc.set_size_request(640, 260)
    sc.add(tv)

    exp.add(sc)
    dlg.get_content_area().pack_start(exp, False, False, 6)

    dlg.show_all()
    dlg.run()
    dlg.destroy()


def westfax_send_fax(username, password, product_id, ani, to_number, pdf_path,
                     job_name, billing_code, header="", feedback_email=None):
    """
    Send fax via WestFax REST endpoint. Returns parsed JSON on success.
    Raises requests.RequestException or ValueError on non-JSON response.
    """
    data = {
        "Username": username,
        "Password": password,
        "Cookies": "false",
        "ProductId": product_id,
        "JobName": job_name,
        "Header": header,
        "BillingCode": billing_code,
        "Numbers1": to_number,
        "ANI": ani,
        "StartDate": "1/1/1999",
    }
    if feedback_email:
        data["FeedbackEmail"] = feedback_email

    with open(pdf_path, "rb") as f:
        files = {"Files0": (os.path.basename(pdf_path), f, "application/pdf")}
        r = requests.post(WESTFAX_SEND_URL, data=data, files=files, timeout=60)
        r.raise_for_status()
        try:
            return r.json()
        except Exception as ex:
            raise ValueError("Invalid JSON response from WestFax") from ex


def westfax_get_contacts(username, password, product_id=None):
    data = {"Username": username, "Password": password, "Cookies": "false"}
    if product_id:
        data["ProductId"] = product_id
    r = requests.post(WESTFAX_CONTACTS_URL, data=data, timeout=30)
    r.raise_for_status()
    return r.json()


def westfax_get_user_info(username, password, product_id=None):
    data = {"Username": username, "Password": password, "Cookies": "false"}
    if product_id:
        data["ProductId"] = product_id
    r = requests.post(WESTFAX_USERINFO_URL, data=data, timeout=30)
    r.raise_for_status()
    return r.json()


def westfax_get_user_email(username, password, product_id=None) -> str:
    info = westfax_get_user_info(username, password, product_id)
    if not isinstance(info, dict) or not info.get("Success"):
        raise Exception(info.get("ErrorString") or info.get("InfoString") or "Failed to get user info.")
    result = info.get("Result") or {}
    email = (result.get("Email") or "").strip()
    if not email:
        raise Exception("WestFax user email was empty.")
    return email


def _obf(s: str) -> str:
    """Obfuscate (base64) — NOT secure. Consider secure storage for passwords."""
    if not s:
        return ""
    return base64.b64encode(s.encode("utf-8")).decode("ascii")


def _deobf(s: str) -> str:
    if not s:
        return ""
    try:
        return base64.b64decode(s.encode("ascii")).decode("utf-8")
    except Exception:
        return s


def _validate_phone(num: Optional[str]) -> bool:
    if not num:
        return False
    return bool(re.fullmatch(r"\+?\d{7,20}", num))