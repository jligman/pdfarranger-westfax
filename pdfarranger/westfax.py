import gettext
import base64
import os
import re
import tempfile
import requests
from gi.repository import Gtk

_ = gettext.gettext


def make_westfax_settings_handler(app):
    def handler(_action, _option=None, _unknown=None):
        prefs = app.config.data['preferences']

        username = prefs.get('westfax_username', '') or ''
        password = deobf(prefs.get('westfax_password', '') or '')
        product_id = prefs.get('westfax_product_id', '') or ''
        login_url = prefs.get('westfax_login_url', '') or ''
        ani = prefs.get('westfax_ani', '') or ''
        
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

        grid.attach(Gtk.Label(label=_("Password:"), halign=Gtk.Align.START), 0, 2, 1, 1)
        entry_password = Gtk.Entry(text=password)
        entry_password.set_visibility(False)
        grid.attach(entry_password, 1, 2, 1, 1)

        grid.attach(Gtk.Label(label=_("Product Id:"), halign=Gtk.Align.START), 0, 3, 1, 1)
        entry_product_id = Gtk.Entry(text=product_id)
        grid.attach(entry_product_id, 1, 3, 1, 1)

        grid.attach(Gtk.Label(label=_("Login URL:"), halign=Gtk.Align.START), 0, 4, 1, 1)
        entry_login = Gtk.Entry()
        entry_login.set_text(login_url)
        grid.attach(entry_login, 1, 4, 1, 1)

        grid.attach(Gtk.Label(label=_("Sending Fax #:"), halign=Gtk.Align.START), 0, 5, 1, 1)
        entry_ani = Gtk.Entry(text=ani)
        entry_ani.set_placeholder_text("##########")
        grid.attach(entry_ani, 1, 5, 1, 1)

        d.vbox.pack_start(grid, True, True, 0)
        d.show_all()

        if d.run() == Gtk.ResponseType.OK:
            username_val = entry_username.get_text().strip()
            password_val = entry_password.get_text()
            product_id_val = entry_product_id.get_text().strip()
            login_url_val = entry_login.get_text().strip()
            ani_val = entry_ani.get_text().strip()

            prefs['westfax_username'] = username_val
            prefs['westfax_password'] = obf(password_val)
            prefs['westfax_product_id'] = product_id_val
            prefs['westfax_login_url'] = login_url_val
            prefs['westfax_ani'] = ani_val

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
        # 1) Ask for destination fax number
        d = Gtk.Dialog(
            title=_("Send Fax"),
            parent=app.window,
            flags=Gtk.DialogFlags.MODAL,
            buttons=(_("_Cancel"), Gtk.ResponseType.CANCEL,
                     _("_Send"), Gtk.ResponseType.OK)
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
        entry_subject.set_placeholder_text("Subject / Job name")
        grid.attach(entry_subject, 1, 1, 1, 1)

        # Reference (BillingCode)
        grid.attach(Gtk.Label(label=_("Reference:"), halign=Gtk.Align.START), 0, 2, 1, 1)
        entry_ref = Gtk.Entry()
        entry_ref.set_placeholder_text("Reference / Billing code")
        grid.attach(entry_ref, 1, 2, 1, 1)

        chk_receipt = Gtk.CheckButton(label=_("Send Delivery Receipt"))
        chk_receipt.set_active(True)
        grid.attach(chk_receipt, 1, 3, 2, 1)

        d.vbox.pack_start(grid, True, True, 0)

        def _lookup_clicked(_btn):
            prefs = app.config.data['preferences']
            username = (prefs.get('westfax_username', '') or '').strip()
            password = deobf(prefs.get('westfax_password', '') or '')
            product_id = (prefs.get('westfax_product_id', '') or '').strip()

            from pprint import pprint
            info = westfax_get_user_info(username, password, product_id)
            print("Security_GetUserInfo keys:", sorted(info.keys()) if isinstance(info, dict) else type(info))
            pprint(info)

            try:
                resp = westfax_get_contacts(username, password, product_id)
            except Exception as ex:
                app.error_message_dialog(str(ex))
                return

            contacts = resp.get("Result") or []            

            dlg = Gtk.Dialog(
                title=_("WestFax Contacts"),
                parent=d,  # modal to Send Fax window
                flags=Gtk.DialogFlags.MODAL,
                buttons=(_("_Cancel"), Gtk.ResponseType.CANCEL,
                         _("_Select"), Gtk.ResponseType.OK)
            )
            dlg.set_default_size(520, 360)

            vbox = dlg.get_content_area()

            search = Gtk.Entry()
            search.set_placeholder_text(_("Search (first, last, company, fax)..."))
            vbox.pack_start(search, False, False, 6)

            # --- Data model ---
            store = Gtk.ListStore(str, str, str, str)
            # 0 First, 1 Last, 2 Company, 3 Fax

            def refill(filter_text=""):
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

                    # Combine fields for searching
                    haystack = f"{first} {last} {company} {fax}".lower()

                    if not q or q in haystack:
                        store.append([first, last, company, fax])

            # initial load
            refill()

            # live search (no button)
            search.connect("changed", lambda e: refill(e.get_text()))

            for c in contacts:
                if not isinstance(c, dict):
                    continue

                first = (c.get("FirstName") or "").strip()
                last = (c.get("LastName") or "").strip()
                company = (c.get("CompanyName") or "").strip()
                fax = (c.get("Fax") or "").strip()

                # Skip entries that have no usable fax number
                if not fax:
                    continue

                store.append([first, last, company, fax])

            tree = Gtk.TreeView(model=store)

            def on_row_activated(_tree, _path, _column):
                dlg.response(Gtk.ResponseType.OK)

            tree.connect("row-activated", on_row_activated)

            tree.append_column(Gtk.TreeViewColumn(_("First"), Gtk.CellRendererText(), text=0))
            tree.append_column(Gtk.TreeViewColumn(_("Last"), Gtk.CellRendererText(), text=1))
            tree.append_column(Gtk.TreeViewColumn(_("Company"), Gtk.CellRendererText(), text=2))
            tree.append_column(Gtk.TreeViewColumn(_("Fax"), Gtk.CellRendererText(), text=3))

            sc = Gtk.ScrolledWindow()
            sc.add(tree)
            vbox.pack_start(sc, True, True, 6)

            dlg.show_all()
            search.grab_focus()

            # Make sure GTK has computed column sizes
            while Gtk.events_pending():
                Gtk.main_iteration()

            # Sum the actual column widths
            total_cols = sum(col.get_width() for col in tree.get_columns())

            # Add padding for scrollbars + dialog borders
            pad = 80

            dlg.resize(total_cols + pad, 420)

            if dlg.run() == Gtk.ResponseType.OK:
                model, it = tree.get_selection().get_selected()
                if it:
                    entry_to.set_text(model[it][3])
            dlg.destroy()

        btn_lookup.connect("clicked", _lookup_clicked)

        d.show_all()

        if d.run() != Gtk.ResponseType.OK:
            d.destroy()
            return

        to_number = entry_to.get_text().strip()
        job_name = entry_subject.get_text().strip() or ""
        billing_code = entry_ref.get_text().strip() or ""

        send_receipt = chk_receipt.get_active()

        d.destroy()

        # Very basic validation (digits plus optional leading +)
        if not re.fullmatch(r"\+?\d{7,20}", to_number):
            app.error_message_dialog(_("Invalid fax number. Use digits, optionally starting with +."))
            return

        # 2) Required preset fields (placeholders)
        header = "YYY"
        start_date = None  # we'll set real formatting later

        # 2.5) Read ANI from settings
        prefs = app.config.data['preferences']
        ani = (prefs.get('westfax_ani', '') or '').strip()

        if not ani:
            app.error_message_dialog(_("Fax number is not set. Open WestFax Settings."))
            return

        # digits-only cleanup (optional but helpful)
        ani = re.sub(r"\D", "", ani)
        if not re.fullmatch(r"\d{7,20}", ani):
            app.error_message_dialog(_("Invalid ANI. Use digits only (e.g. 2105551234)."))
            return

        # 3) Get "current PDF"
        # Basic rule for now: require it to be saved to disk.
        pdf_path = app.save_file or (app.pdfqueue[0].filename if app.pdfqueue else None)
        if not pdf_path or not os.path.exists(pdf_path):
            app.error_message_dialog(_("No saved PDF to fax. Please save the document first."))
            return

        # 4) Copy to a temp file (so we can delete it after sending)
        fd, tmp_pdf = tempfile.mkstemp(suffix=".pdf", prefix="westfax_", dir=app.tmp_dir)
        os.close(fd)
        try:
            with open(pdf_path, "rb") as src, open(tmp_pdf, "wb") as dst:
                dst.write(src.read())

            # 5) API call placeholder (we'll implement next)
            # send_fax(job_name, header, billing_code, to_number, tmp_pdf, ani, start_date)

            prefs = app.config.data['preferences']

            username = (prefs.get('westfax_username', '') or '').strip()
            password = deobf(prefs.get('westfax_password', '') or '')
            product_id = (prefs.get('westfax_product_id', '') or '').strip()
            ani = re.sub(r"\D", "", (prefs.get('westfax_ani', '') or '').strip())

            try:
                feedback_email = None
                if chk_receipt.get_active():
                    feedback_email = westfax_get_user_email(username, password, product_id)

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
                    error=None
                )

            except Exception as ex:
                show_westfax_result_dialog(
                    parent=app.window,
                    to_number=to_number,
                    job_name=job_name,
                    result=None,
                    error=ex
                )

        finally:
            # Always delete temp
            try:
                os.remove(tmp_pdf)
            except Exception:
                pass

    return handler

def show_westfax_result_dialog(parent, to_number, job_name, result, error=None):
    """
    Clean WestFax result dialog.
    Treats result["Success"] == False as failure even if no exception was thrown.
    Does NOT display Fax ID.
    """
    # Determine outcome
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

    # Secondary text (clean + human)
    lines = []
    if to_number:
        lines.append(_("To: ") + str(to_number))
    if job_name:
        lines.append(_("Subject: ") + str(job_name))

    # If the API says failure, surface the error strings
    if isinstance(result, dict) and api_success is False:
        info = (result.get("InfoString") or "").strip()
        err = (result.get("ErrorString") or "").strip()

        if info or err:
            lines.append("")  # spacing
        if info:
            lines.append(info)
        if err and err != info:
            lines.append(err)

    # Exceptions still win
    if error is not None:
        lines.append("")
        lines.append(str(error))

    dlg.format_secondary_text("\n".join(lines) if lines else "")

    # Details expander (raw JSON / exception) for debugging
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

WESTFAX_SEND_URL = "https://apisecure.westfax.com/REST/Fax_SendFax/json"

def westfax_send_fax(username, password, product_id, ani, to_number, pdf_path,
                     job_name, billing_code, header = "", feedback_email=None):
    # WestFax expects Numbers1 in ###-###-#### style per their docs; they also accept digits in practice.
    data = {
        "Username": username,
        "Password": password,
        "Cookies": "false",
        "ProductId": product_id,
        "JobName": job_name,
        "Header": header,
        "BillingCode": billing_code,
        "Numbers1": to_number,
        "ANI": ani,                 # ##########
        "StartDate": "1/1/1999",    # "send now" per WestFax docs
    }

    if feedback_email:
        data["FeedbackEmail"] = feedback_email

    with open(pdf_path, "rb") as f:
        files = {
            "Files0": (os.path.basename(pdf_path), f, "application/pdf")
        }
        r = requests.post(WESTFAX_SEND_URL, data=data, files=files, timeout=60)
        r.raise_for_status()
        return r.json()

WESTFAX_CONTACTS_URL = "https://apih.westfax.com/REST/Contact_GetContactList/json"

def westfax_get_contacts(username, password, product_id=None):
    data = {
        "Username": username,
        "Password": password,
        "Cookies": "false",
    }
    if product_id:
        data["ProductId"] = product_id  # optional per docs :contentReference[oaicite:1]{index=1}

    r = requests.post(WESTFAX_CONTACTS_URL, data=data, timeout=30)
    r.raise_for_status()
    return r.json()

WESTFAX_USERINFO_URL = "https://api2.westfax.com/REST/Security_GetUserInfo/json"

def westfax_get_user_info(username, password, product_id=None):
    data = {
        "Username": username,
        "Password": password,
        "Cookies": "false",
    }
    if product_id:
        data["ProductId"] = product_id

    r = requests.post(WESTFAX_USERINFO_URL, data=data, timeout=30)
    r.raise_for_status()
    return r.json()

def westfax_get_user_email(username, password, product_id=None):
    info = westfax_get_user_info(username, password, product_id)

    if not isinstance(info, dict) or not info.get("Success"):
        # WestFax sometimes returns Success=False with error strings on other endpoints,
        # so be defensive.
        raise Exception(info.get("ErrorString") or info.get("InfoString") or "Failed to get user info.")

    result = info.get("Result") or {}
    email = (result.get("Email") or "").strip()

    if not email:
        raise Exception("WestFax user email was empty.")
    return email