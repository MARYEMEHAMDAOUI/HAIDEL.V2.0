"""
HAIDEL Web — Flask Application
Déploiement : PythonAnywhere
"""
import os, io, base64
from datetime import datetime
from functools import wraps
from flask import (Flask, render_template, redirect, url_for, request,
                   session, flash, jsonify, send_file, Response)
import database as db

# ══════════════════════════════════════════════════════════════════════════════
#  APP SETUP
# ══════════════════════════════════════════════════════════════════════════════

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "haidel-encg-2025-xK9mP7#")
app.config.update(
    SESSION_COOKIE_HTTPONLY = True,
    SESSION_COOKIE_SAMESITE = "Lax",
    MAX_CONTENT_LENGTH      = 5 * 1024 * 1024,  # 5MB max upload
)

db.init_database()

# Blueprint réclamations (Supabase optionnel)
try:
    from reclamations import reclamations_bp
    app.register_blueprint(reclamations_bp)
except Exception as _e:
    print(f"[WARN] Réclamations blueprint not loaded: {_e}")

# ══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def current_user():
    return session.get("user") or {}

def _safe_session_user(user_dict):
    """Strip avatar_b64 — never store large images in session cookie (4KB limit)."""
    if not user_dict:
        return {}
    return {k: v for k, v in dict(user_dict).items() if k != "avatar_b64"}

app.jinja_env.globals["current_user"] = current_user
app.jinja_env.globals["now"] = datetime.now

@app.template_filter("datestr")
def datestr_filter(value, fmt=16):
    return str(value or "")[:int(fmt)]


# ── Security: login rate limiting ─────────────────────────────────────────────
import time as _time
_attempts: dict = {}

def _rate_ok(ip):
    entry = _attempts.get(ip)
    now   = _time.time()
    if entry and entry[0] >= 10 and (now - entry[1]) < 300:
        return False
    if entry and (now - entry[1]) >= 300:
        del _attempts[ip]
    return True

def _fail(ip):
    e = _attempts.get(ip)
    _attempts[ip] = ((e[0]+1 if e else 1), (e[1] if e else _time.time()))

def _ok(ip):
    _attempts.pop(ip, None)


# ── Before request: reload language/theme from DB ─────────────────────────────
@app.before_request
def reload_prefs():
    u = session.get("user")
    if not u or not u.get("id"):
        return
    try:
        fresh = db.get_user_by_id(u["id"])
        if fresh:
            for key in ("langue", "theme", "annee_etude", "avatar_color", "nom"):
                val = fresh.get(key)
                if val is not None:
                    session["user"][key] = val
            session.modified = True
    except Exception:
        pass


# ── Context processor: user_clubs available in all templates ──────────────────
@app.context_processor
def inject_globals():
    u = session.get("user")
    clubs = []
    if u and u.get("id"):
        try:
            raw  = db.get_user_clubs(u["id"]) or []
            seen = set()
            for c in raw:
                cid = c.get("id") or c.get("club_id")
                if cid not in seen:
                    seen.add(cid); clubs.append(c)
        except Exception:
            pass
    return {"user_clubs": clubs}


# ── Auth decorators ───────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def dec(*a, **kw):
        if not session.get("user"):
            return redirect(url_for("login"))
        return f(*a, **kw)
    return dec

def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def dec(*a, **kw):
            if not session.get("user"):
                return redirect(url_for("login"))
            if session["user"].get("role") not in roles:
                flash("Accès non autorisé.", "danger")
                return redirect(url_for("feed"))
            return f(*a, **kw)
        return dec
    return decorator


# ══════════════════════════════════════════════════════════════════════════════
#  AVATAR ENDPOINT — images served from DB, never stored in session
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/avatar/<int:user_id>")
def serve_avatar(user_id):
    try:
        u = db.get_user_by_id(user_id)
        if u and u.get("avatar_b64"):
            data = base64.b64decode(u["avatar_b64"])
            r = Response(data, mimetype="image/jpeg")
            r.headers["Cache-Control"] = "public, max-age=3600"
            return r
    except Exception:
        pass
    # SVG placeholder
    try:
        u   = db.get_user_by_id(user_id)
        col = (u or {}).get("avatar_color", "#8B4513") or "#8B4513"
        let = ((u or {}).get("nom") or "?")[0].upper()
    except Exception:
        col, let = "#8B4513", "?"
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200">'
           f'<circle cx="100" cy="100" r="100" fill="{col}"/>'
           f'<text x="100" y="130" text-anchor="middle" fill="white" '
           f'font-size="90" font-family="Arial" font-weight="bold">{let}</text>'
           f'</svg>')
    r = Response(svg, mimetype="image/svg+xml")
    r.headers["Cache-Control"] = "public, max-age=3600"
    return r


# ══════════════════════════════════════════════════════════════════════════════
#  AUTH ROUTES
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user"):
        return redirect(url_for("feed"))
    error = None
    if request.method == "POST":
        ip  = request.remote_addr or "0.0.0.0"
        if not _rate_ok(ip):
            error = "Trop de tentatives. Réessayez dans 5 minutes."
        else:
            login_id = request.form.get("login", "").strip()
            password = request.form.get("password", "").strip()
            user     = db.authenticate(login_id, password)
            if user:
                _ok(ip)
                session["user"] = _safe_session_user(user)
                flash(f"Bienvenue, {user['nom']} !", "success")
                return redirect(url_for("feed"))
            else:
                _fail(ip)
                error = "Identifiant ou mot de passe incorrect."
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    clubs_list = db.get_clubs_list()
    error = None
    if request.method == "POST":
        prenom   = request.form.get("prenom", "").strip()
        nom      = request.form.get("nom", "").strip()
        email    = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        annee    = request.form.get("annee", "1ère année")
        club_id  = request.form.get("club_id") or None
        statut   = request.form.get("statut", "etudiant")
        if not all([prenom, nom, email, password]):
            error = "Tous les champs sont obligatoires."
        elif len(password) < 6:
            error = "Mot de passe trop court (min. 6 caractères)."
        else:
            ok, result = db.create_user(nom, prenom, email, annee,
                                         int(club_id) if club_id else None,
                                         statut, password=password)
            if ok:
                flash(f"Compte créé ! Identifiant : {result['username']}", "success")
                return redirect(url_for("login"))
            error = result
    return render_template("register.html", clubs=clubs_list, error=error)


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    step  = request.args.get("step", "1")
    error = None
    if request.method == "POST":
        if step == "1":
            login_id = request.form.get("login", "").strip()
            u = db.get_user_by_username(login_id)
            if not u:
                error = "Aucun compte trouvé."
            else:
                import random
                code = str(random.randint(100000, 999999))
                session["reset_code"] = code
                session["reset_uid"]  = u["id"]
                flash(f"Code de réinitialisation : {code}", "info")
                return redirect(url_for("forgot_password", step="2"))
        elif step == "2":
            code   = request.form.get("code", "").strip()
            new_pw = request.form.get("new_password", "").strip()
            conf   = request.form.get("confirm_password", "").strip()
            if code != session.get("reset_code", ""):
                error = "Code incorrect."
            elif len(new_pw) < 6:
                error = "Mot de passe trop court."
            elif new_pw != conf:
                error = "Les mots de passe ne correspondent pas."
            else:
                db.update_password(session["reset_uid"], new_pw)
                session.pop("reset_code", None); session.pop("reset_uid", None)
                flash("Mot de passe réinitialisé !", "success")
                return redirect(url_for("login"))
    return render_template("forgot_password.html", step=step, error=error)


# ══════════════════════════════════════════════════════════════════════════════
#  FEED
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/", methods=["GET", "POST"])
@login_required
def feed():
    user = current_user()
    if request.method == "POST":
        titre   = request.form.get("titre", "").strip()
        contenu = request.form.get("contenu", "").strip()
        typ     = request.form.get("type", "General")
        ev_date = request.form.get("event_date", "")
        if ev_date:
            contenu += f"\n\n📅 Date : {ev_date}"
        b64 = ""; mime = ""
        f = request.files.get("image")
        if f and f.filename:
            try:
                from PIL import Image as _I
                img = _I.open(f.stream).convert("RGB")
                img.thumbnail((800, 400), _I.LANCZOS)
                buf = io.BytesIO(); img.save(buf, "JPEG", quality=80)
                b64 = base64.b64encode(buf.getvalue()).decode(); mime = "image/jpeg"
            except Exception:
                f.seek(0)
                b64 = base64.b64encode(f.read()).decode(); mime = f.mimetype or "image/jpeg"
        if titre and contenu:
            if user.get("role") == "admin":
                db.publier_annonce_admin(titre, contenu, typ, user["id"], b64, mime)
            else:
                club = db.get_club_of_president(user["id"])
                db.publier_annonce_club(titre, contenu, typ, user["id"],
                                         club["id"] if club else None, b64, mime)
            flash("Annonce publiée !", "success")
            return redirect(url_for("feed"))

    posts  = db.get_annonces_feed()
    events = db.get_annonces_feed("Evenement")[:5]
    uid    = user.get("id")
    for p in posts:
        try:
            p["reactions"]   = db.get_reactions(p["id"])
            p["my_reaction"] = db.get_user_reaction(p["id"], uid) if uid else None
            p["comments"]    = db.get_comments(p["id"])
        except Exception:
            p.setdefault("reactions", {}); p.setdefault("my_reaction", None); p.setdefault("comments", [])
    return render_template("index.html", posts=posts, events=events)


@app.route("/react/<int:post_id>/<rtype>", methods=["POST"])
@login_required
def react(post_id, rtype):
    db.toggle_reaction(post_id, current_user()["id"], rtype)
    return jsonify({"ok": True, "reactions": db.get_reactions(post_id)})


@app.route("/comment/<int:post_id>", methods=["POST"])
@login_required
def add_comment(post_id):
    contenu = (request.json or {}).get("contenu", "").strip()
    if contenu:
        db.add_comment(post_id, current_user()["id"], contenu)
    coms = db.get_comments(post_id)
    return jsonify([{"auteur_nom": c["auteur_nom"],
                     "contenu": c["contenu"],
                     "date": str(c.get("date_commentaire", ""))[:16]} for c in coms])


# ══════════════════════════════════════════════════════════════════════════════
#  ADMIN
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/admin/dashboard")
@role_required("admin")
def admin_dashboard():
    return render_template("admin/dashboard.html",
                           stats=db.get_clubs_stats(),
                           clubs=db.get_all_clubs(),
                           bilans=db.get_bilans())


@app.route("/admin/demandes", methods=["GET", "POST"])
@role_required("admin")
def admin_demandes():
    if request.method == "POST":
        db.update_demande_statut(int(request.form["dem_id"]),
                                  request.form["statut"],
                                  request.form.get("motif", ""))
        flash("Demande mise à jour.", "success")
    return render_template("admin/demandes.html",
                           demandes=db.get_demandes(role="admin"))


@app.route("/admin/certificats", methods=["GET", "POST"])
@role_required("admin")
def admin_certificats():
    if request.method == "POST":
        action = request.form.get("action")
        req_id = int(request.form["req_id"])
        if action == "emit":
            db.approve_cert_request(req_id); flash("Certificat émis !", "success")
        elif action == "refuse":
            db.reject_cert_request(req_id); flash("Refusé.", "warning")
    return render_template("admin/certificats.html",
                           reqs=db.get_cert_requests(),
                           certs=db.get_all_certificats())


@app.route("/admin/bilans")
@role_required("admin")
def admin_bilans():
    return render_template("admin/bilans.html", bilans=db.get_bilans())


@app.route("/admin/bilans/<int:bilan_id>/export")
@role_required("admin")
def admin_bilan_export(bilan_id):
    bilans = db.get_bilans()
    b = next((x for x in bilans if x["id"] == bilan_id), None)
    if not b:
        flash("Bilan introuvable.", "warning"); return redirect(url_for("admin_bilans"))
    txt = (f"BILAN ANNUEL — HAIDEL ENCG\n{'='*48}\n"
           f"Club      : {b['club_nom']}\nAnnée     : {b['annee']}\n"
           f"Activités : {b['activites_realises']}\nMembres   : {b['membres_actifs']}\n"
           f"Événements: {b.get('evenements', 0)}\n\nRésumé:\n{b.get('resume','')}\n"
           f"{'='*48}\n{datetime.now().strftime('%d/%m/%Y %H:%M')}\n")
    return send_file(io.BytesIO(txt.encode("utf-8")),
                     mimetype="text/plain",
                     download_name=f"Bilan_{b['club_nom']}_{b['annee']}.txt",
                     as_attachment=True)


@app.route("/admin/requests", methods=["GET", "POST"])
@role_required("admin")
def admin_requests():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "create":
            titre   = request.form.get("titre", "").strip()
            club_id = int(request.form.get("club_id", 0))
            clubs   = db.get_all_clubs()
            pres_id = next((c.get("president_id") for c in clubs if c["id"] == club_id), None)
            if titre:
                db.add_admin_request(titre,
                                      request.form.get("description", ""),
                                      request.form.get("type", "document"),
                                      pres_id, club_id)
                flash("Demande envoyée !", "success")
        elif action == "delete":
            db.delete_admin_request(int(request.form["req_id"]))
            flash("Supprimée.", "info")
    return render_template("admin/requests.html",
                           reqs=db.get_admin_requests(),
                           clubs=db.get_all_clubs())


@app.route("/admin/requests/<int:req_id>/download")
@role_required("admin")
def download_admin_file(req_id):
    reqs = db.get_admin_requests()
    req  = next((r for r in reqs if r["id"] == req_id), None)
    if not req or not req.get("fichier_b64"):
        flash("Fichier non disponible.", "warning"); return redirect(url_for("admin_requests"))
    data = base64.b64decode(req["fichier_b64"])
    return send_file(io.BytesIO(data),
                     download_name=req.get("fichier_nom", "document"),
                     as_attachment=True)


# ══════════════════════════════════════════════════════════════════════════════
#  PRESIDENT
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/president/membres", methods=["GET", "POST"])
@role_required("president", "vp")
def pres_membres():
    user = current_user()
    if request.method == "POST":
        action  = request.form.get("action")
        club_id = request.form.get("club_id")
        mem_id  = request.form.get("mem_id")
        if action == "set_role" and club_id and mem_id:
            db.set_custom_role(int(club_id), int(mem_id),
                                request.form.get("custom_role", ""))
            flash("Rôle mis à jour.", "success")
        elif action == "warn" and club_id and mem_id:
            db.envoyer_avertissement(int(club_id), int(mem_id),
                                      user["id"], request.form.get("motif", ""))
            flash("Avertissement envoyé.", "warning")
        elif action == "remove" and club_id and mem_id:
            db.supprimer_membre(int(club_id), int(mem_id))
            flash("Membre retiré.", "info")
    return render_template("president/membres.html",
                           membres=db.get_membres_club_full(user["id"]),
                           candidatures=db.get_club_applications(user["id"]))


@app.route("/president/accept-app/<int:app_id>", methods=["POST"])
@role_required("president", "vp")
def pres_accept_app(app_id):
    apps = db.get_club_applications(current_user()["id"])
    ap   = next((a for a in apps if a["id"] == app_id), None)
    if ap:
        db.accept_application_with_message(ap["id"], ap["etudiant_id"],
                                            ap["club_id"], "Bienvenue !")
        flash(f"{ap['etudiant_nom']} accepté !", "success")
    return redirect(url_for("pres_recrutement"))


@app.route("/president/reject-app/<int:app_id>", methods=["POST"])
@role_required("president", "vp")
def pres_reject_app(app_id):
    db.reject_application_with_message(app_id, "Candidature non retenue.")
    flash("Candidature refusée.", "warning")
    return redirect(url_for("pres_recrutement"))


@app.route("/president/recrutement", methods=["GET", "POST"])
@role_required("president", "vp")
def pres_recrutement():
    user = current_user()
    if request.method == "POST":
        action = request.form.get("action")
        if action == "toggle_apps":
            cid = int(request.form["club_id"])
            db.set_applications_ouvertes(cid, not db.get_applications_ouvertes(cid))
            flash("Statut mis à jour.", "success")
        elif action == "new_rec":
            club = db.get_club_of_president(user["id"])
            if club:
                db.add_recrutement(user["id"], club["id"],
                                    request.form.get("titre", ""),
                                    request.form.get("description", ""),
                                    request.form.get("date_limite", ""),
                                    request.form.get("criteres", ""))
                flash("Recrutement créé !", "success")
    club   = db.get_club_of_president(user["id"])
    ouvert = db.get_applications_ouvertes(club["id"]) if club else True
    return render_template("president/recrutement.html",
                           recs=db.get_recrutements(president_id=user["id"]),
                           club=club, ouvert=ouvert,
                           apps=db.get_club_applications(user["id"]),
                           all_apps=db.get_all_club_applications(user["id"]))


@app.route("/president/publier", methods=["GET", "POST"])
@role_required("president", "vp")
def pres_publier():
    user = current_user()
    if request.method == "POST":
        titre   = request.form.get("titre", "").strip()
        contenu = request.form.get("contenu", "").strip()
        typ     = request.form.get("type", "General")
        ev_date = request.form.get("event_date", "")
        if ev_date:
            contenu += f"\n\n📅 Date : {ev_date}"
        b64 = ""; mime = ""
        f = request.files.get("image")
        if f and f.filename:
            try:
                from PIL import Image as _I
                img = _I.open(f.stream).convert("RGB")
                img.thumbnail((800, 400), _I.LANCZOS)
                buf = io.BytesIO(); img.save(buf, "JPEG", quality=80)
                b64 = base64.b64encode(buf.getvalue()).decode(); mime = "image/jpeg"
            except Exception:
                f.seek(0); b64 = base64.b64encode(f.read()).decode(); mime = f.mimetype or "image/jpeg"
        club = db.get_club_of_president(user["id"])
        db.publier_annonce_club(titre, contenu, typ, user["id"],
                                 club["id"] if club else None, b64, mime)
        flash("Annonce publiée !", "success")
        return redirect(url_for("feed"))
    return render_template("president/publier.html")


@app.route("/president/bilan", methods=["GET", "POST"])
@role_required("president", "vp")
def pres_bilan():
    user = current_user()
    club = db.get_club_of_president(user["id"])
    if request.method == "POST":
        try:
            db.soumettre_bilan(club["id"], user["id"],
                                request.form.get("annee", ""),
                                request.form.get("resume", ""),
                                int(request.form.get("activites", 0) or 0),
                                int(request.form.get("membres", 0) or 0),
                                int(request.form.get("evenements", 0) or 0))
            flash("Bilan soumis !", "success")
        except Exception as e:
            flash(f"Erreur : {e}", "danger")
    return render_template("president/bilan.html",
                           club=club,
                           bilans=db.get_bilans(user["id"]),
                           activites=db.get_activites(club["id"] if club else None),
                           participants=db.get_participants_externes())


@app.route("/president/demandes", methods=["GET", "POST"])
@role_required("president", "vp")
def pres_demandes():
    user = current_user()
    if request.method == "POST":
        titre = request.form.get("titre", "").strip()
        club  = db.get_club_of_president(user["id"])
        if titre and club:
            db.add_demande(titre, request.form.get("type", "autre"),
                            request.form.get("description", ""),
                            user["id"], club["id"])
            flash("Demande soumise !", "success")
    return render_template("president/demandes.html",
                           demandes=db.get_demandes(user_id=user["id"]))


@app.route("/president/certif", methods=["GET", "POST"])
@role_required("president", "vp")
def pres_certif():
    user = current_user()
    club = db.get_club_of_president(user["id"])
    if request.method == "POST":
        db.add_cert_request(user["id"], club["id"] if club else None,
                             int(request.form["membre_id"]),
                             request.form.get("titre", "Certificat d'Engagement"),
                             request.form.get("type", "Engagement"))
        flash("Demande soumise !", "success")
    return render_template("president/certif.html",
                           club=club,
                           actifs=db.get_membres_club_full(user["id"]),
                           reqs=db.get_cert_requests(president_id=user["id"]))


@app.route("/president/ext-participants", methods=["GET", "POST"])
@role_required("president", "vp")
def pres_ext():
    if request.method == "POST":
        nom = request.form.get("nom", "").strip()
        if nom:
            db.add_participant_externe(nom, request.form.get("email", ""),
                                        request.form.get("organisation", ""), None)
            flash("Participant ajouté !", "success")
    return render_template("president/ext.html",
                           participants=db.get_participants_externes())


@app.route("/president/docs", methods=["GET", "POST"])
@role_required("president", "vp")
def pres_docs():
    user = current_user()
    if request.method == "POST":
        req_id = int(request.form["req_id"])
        f = request.files.get("file")
        if f and f.filename:
            b64 = base64.b64encode(f.read()).decode("utf-8")
            db.respond_admin_request(req_id, b64, f.filename)
            flash("Fichier déposé !", "success")
    return render_template("president/docs.html",
                           reqs=db.get_admin_requests(president_id=user["id"]))


# ══════════════════════════════════════════════════════════════════════════════
#  MESSAGERIE
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/messaging", methods=["GET", "POST"])
@login_required
def messaging():
    user     = current_user()
    clubs    = db.get_user_all_clubs(user["id"])
    sel_club = request.args.get("club")
    msgs     = []; cur_club = None
    if clubs:
        cid = int(sel_club) if sel_club else (clubs[0].get("id") or clubs[0].get("club_id"))
        cur_club = next((c for c in clubs
                         if (c.get("id") or c.get("club_id")) == cid), clubs[0])
        if request.method == "POST":
            text = request.form.get("message", "").strip()
            if text and db.can_send_message(user["id"], cid):
                db.send_group_message(cid, user["id"], text)
                return redirect(url_for("messaging", club=cid))
        msgs = db.get_group_messages(cid)
    return render_template("messaging.html",
                           clubs=clubs, msgs=msgs,
                           cur_club=cur_club, sel_cid=sel_club)


# ══════════════════════════════════════════════════════════════════════════════
#  PROFILE
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = current_user()
    if request.method == "POST":
        action = request.form.get("action")

        if action == "update_prefs":
            annee = request.form.get("annee", "")
            lang  = request.form.get("langue", "Français")
            theme = request.form.get("theme", "Light")
            # Save to DB
            db.update_annee_etude(user["id"], annee)
            try: db.update_language(user["id"], lang)
            except Exception: pass
            db.update_theme(user["id"], theme)
            # Update session immediately — NO avatar_b64
            session["user"]["annee_etude"] = annee
            session["user"]["langue"]      = lang
            session["user"]["theme"]       = theme
            session.modified = True
            flash("Préférences mises à jour !", "success")

        elif action == "change_pwd":
            old_pw = request.form.get("old_password", "")
            new_pw = request.form.get("new_password", "")
            conf   = request.form.get("confirm_password", "")
            ident  = user.get("username") or user.get("email", "")
            if not db.authenticate(ident, old_pw):
                flash("Mot de passe actuel incorrect.", "danger")
            elif len(new_pw) < 6:
                flash("Mot de passe trop court (min. 6 caractères).", "danger")
            elif new_pw != conf:
                flash("Les mots de passe ne correspondent pas.", "danger")
            else:
                db.update_password(user["id"], new_pw)
                flash("Mot de passe changé !", "success")

        elif action == "upload_avatar":
            f = request.files.get("avatar")
            if f and f.filename:
                try:
                    from PIL import Image as _I
                    img = _I.open(f.stream).convert("RGB")
                    img.thumbnail((200, 200), _I.LANCZOS)
                    buf = io.BytesIO(); img.save(buf, "JPEG", quality=75)
                    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
                except Exception:
                    f.seek(0); b64 = base64.b64encode(f.read()).decode("utf-8")
                db.update_avatar(user["id"], b64)
                # ⚠️ NEVER put avatar_b64 in session (4KB cookie limit!)
                # Avatar served via /avatar/<user_id>
                flash("Photo de profil mise à jour !", "success")

        return redirect(url_for("profile"))

    # Load user fresh from DB but strip avatar_b64 from template
    fresh = db.get_user_by_id(user["id"]) or user
    safe_fresh = {k: v for k, v in dict(fresh).items() if k != "avatar_b64"}
    clubs = db.get_user_clubs(user["id"])
    return render_template("profile.html", user=safe_fresh, clubs=clubs)


# ══════════════════════════════════════════════════════════════════════════════
#  CLUBS & CERTIFICATS
# ══════════════════════════════════════════════════════════════════════════════

@app.route("/clubs", methods=["GET", "POST"])
@login_required
def clubs_explorer():
    user = current_user()
    if request.method == "POST":
        db.postuler_club(user["id"], int(request.form["club_id"]))
        flash("Candidature envoyée !", "success")
    clubs = db.get_all_clubs()
    my_ids = {c.get("id") or c.get("club_id") for c in db.get_user_clubs(user["id"])}
    return render_template("clubs.html", clubs=clubs, my_clubs=my_ids)


@app.route("/mes-certificats")
@login_required
def mes_certificats():
    certs = db.get_certificats(current_user()["id"])
    return render_template("certificats.html", certs=certs)


@app.route("/certificat/<int:cert_id>/download")
@login_required
def download_cert(cert_id):
    user  = current_user()
    certs = db.get_certificats(user["id"])
    cert  = next((c for c in certs if c["id"] == cert_id), None)
    if not cert:
        flash("Certificat non trouvé.", "danger")
        return redirect(url_for("mes_certificats"))
    try:
        from PIL import Image as _I, ImageDraw
        W, H = 794, 562
        img  = _I.new("RGB", (W, H), "#FFFDF8")
        draw = ImageDraw.Draw(img)
        for y in range(H):
            t = y / H
            r = int(0x8B * (1-t) + 0x5C * t)
            draw.line([(0, y), (W, y)], fill=(r, 37, 8))
        draw.rounded_rectangle([20, 20, W-20, H-20], radius=18, fill="#FFFFFF")
        draw.rectangle([20, 20, W-20, 80], fill=(139, 69, 19))
        fnt = ImageDraw.ImageDraw
        for text, y in [
            ("HAIDEL  •  ENCG Marrakech", 50),
            ("CERTIFICAT D'ENGAGEMENT", 150),
            (user.get("nom", "").upper(), 220),
            (cert.get("club_nom", "ENCG"), 270),
            (cert.get("titre", ""), 320),
            (f"Délivré le : {str(cert.get('date_delivrance',''))[:10]}", 380),
        ]:
            draw.text((W//2, y), text, fill="#FFF" if y == 50 else (80, 40, 20),
                       anchor="mm")
        buf = io.BytesIO(); img.save(buf, "PNG"); buf.seek(0)
        return send_file(buf, mimetype="image/png",
                         download_name=f"Certificat_{user['nom'].replace(' ','_')}.png",
                         as_attachment=True)
    except Exception as e:
        flash(f"Erreur : {e}", "danger")
        return redirect(url_for("mes_certificats"))


# ══════════════════════════════════════════════════════════════════════════════
#  RUN (local dev only — PythonAnywhere uses wsgi.py)
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)
