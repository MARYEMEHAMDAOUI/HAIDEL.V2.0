"""
HAIDEL — Blueprint Réclamations
Fichier autonome : n'importe aucun fichier existant.
Enregistrer dans app.py avec :
    from reclamations import reclamations_bp
    app.register_blueprint(reclamations_bp)
"""

import os
from datetime import datetime, timezone
from flask import (Blueprint, render_template, redirect, url_for,
                   request, session, flash, jsonify)
from supabase import create_client, Client

# ── Blueprint ──────────────────────────────────────────────────────────────────

reclamations_bp = Blueprint("reclamations", __name__)

# ── Supabase client (service_role key = bypasse le RLS côté serveur) ──────────

_supabase: Client = None

def get_supabase() -> Client:
    global _supabase
    if _supabase is None:
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_SERVICE_KEY", "")
        if not url or not key:
            return None          # ← retourne None au lieu de planter
        _supabase = create_client(url, key)
    return _supabase

# ── Helpers ────────────────────────────────────────────────────────────────────

def _current_user():
    return session.get("user", {})

def _require_login(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def _require_role(*roles):
    from functools import wraps
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user = session.get("user", {})
            if not user:
                return redirect(url_for("login"))
            if user.get("role") not in roles:
                flash("Accès non autorisé.", "danger")
                return redirect(url_for("feed"))
            return f(*args, **kwargs)
        return decorated
    return decorator

# ── Routes Président ───────────────────────────────────────────────────────────

@reclamations_bp.route("/president/reclamations", methods=["GET", "POST"])
@_require_role("president", "vp")
def pres_reclamations():
    user  = _current_user()
    sb    = get_supabase()
    error = None

    if sb is None:
        flash("⚠️ Supabase non configuré. Contactez l'administrateur.", "warning")
        return render_template("president/reclamations.html",
                               reclamations=[], error=None)

    if request.method == "POST":
        titre       = request.form.get("titre", "").strip()
        description = request.form.get("description", "").strip()
        if not titre or not description:
            error = "Le titre et la description sont obligatoires."
        else:
            try:
                sb.table("reclamations").insert({
                    "president_id":  user.get("username") or user.get("email"),
                    "president_nom": user.get("nom", ""),
                    "titre":         titre,
                    "description":   description,
                    "statut":        "en attente",
                }).execute()
                flash("✅ Réclamation envoyée à l'administration !", "success")
                return redirect(url_for("reclamations.pres_reclamations"))
            except Exception as e:
                error = f"Erreur Supabase : {e}"

    try:
        uid  = user.get("username") or user.get("email")
        resp = (sb.table("reclamations")
                  .select("*")
                  .eq("president_id", uid)
                  .order("created_at", desc=True)
                  .execute())
        reclamations = resp.data or []
    except Exception as e:
        reclamations = []
        flash(f"Impossible de charger les réclamations : {e}", "warning")

    return render_template("president/reclamations.html",
                           reclamations=reclamations, error=error)


# ── Routes Admin ───────────────────────────────────────────────────────────────

@reclamations_bp.route("/admin/reclamations", methods=["GET"])
@_require_role("admin")
def admin_reclamations():
    sb = get_supabase()
    if sb is None:
        flash("⚠️ Supabase non configuré. Ajoutez SUPABASE_URL et SUPABASE_SERVICE_KEY dans vos variables d'environnement Vercel.", "warning")
        return render_template("admin/reclamations.html",
                               en_attente=[], repondues=[], total=0)
    try:
        resp = (sb.table("reclamations")
                  .select("*")
                  .order("created_at", desc=True)
                  .execute())
        reclamations = resp.data or []
    except Exception as e:
        reclamations = []
        flash(f"Erreur Supabase : {e}", "warning")

    en_attente = [r for r in reclamations if r["statut"] == "en attente"]
    repondues  = [r for r in reclamations if r["statut"] == "répondu"]
    return render_template("admin/reclamations.html",
                           en_attente=en_attente,
                           repondues=repondues,
                           total=len(reclamations))


@reclamations_bp.route("/admin/reclamations/<rec_id>/repondre", methods=["POST"])
@_require_role("admin")
def admin_repondre(rec_id):
    sb = get_supabase()
    if sb is None:
        flash("Supabase non configuré.", "danger")
        return redirect(url_for("reclamations.admin_reclamations"))
    reponse = request.form.get("reponse", "").strip()
    if not reponse:
        flash("La réponse ne peut pas être vide.", "danger")
        return redirect(url_for("reclamations.admin_reclamations"))
    try:
        sb.table("reclamations").update({
            "reponse_admin": reponse,
            "statut":        "répondu",
        }).eq("id", rec_id).execute()
        flash("✅ Réponse envoyée au président.", "success")
    except Exception as e:
        flash(f"Erreur lors de la réponse : {e}", "danger")
    return redirect(url_for("reclamations.admin_reclamations"))


@reclamations_bp.route("/api/reclamations/count")
@_require_role("admin")
def api_reclamations_count():
    try:
        sb = get_supabase()
        if sb is None:
            return jsonify({"count": 0})
        resp = (sb.table("reclamations")
                  .select("id", count="exact")
                  .eq("statut", "en attente")
                  .execute())
        return jsonify({"count": resp.count or 0})
    except Exception:
        return jsonify({"count": 0})


@reclamations_bp.route("/api/reclamations/latest")
@_require_role("admin")
def api_reclamations_latest():
    try:
        sb = get_supabase()
        if sb is None:
            return jsonify([])
        resp = (sb.table("reclamations")
                  .select("id, titre, president_nom, created_at")
                  .eq("statut", "en attente")
                  .order("created_at", desc=True)
                  .limit(5)
                  .execute())
        return jsonify(resp.data or [])
    except Exception:
        return jsonify([])
