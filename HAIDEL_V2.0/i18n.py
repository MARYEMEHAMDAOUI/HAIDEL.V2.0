"""HAIDEL – Internationalisation (i18n)
Usage: from i18n import t, set_language, current_language
"""

_LANG = "Français"

TRANSLATIONS = {
    "Français": {},   # default — keys are the French strings themselves
    "English": {
        # Nav
        "Accueil": "Home", "Demandes": "Requests", "Membres": "Members",
        "Messagerie": "Messaging", "Mon Profil": "My Profile",
        "Recrutements": "Recruitment", "Bilan Annuel": "Annual Report",
        "Clubs ENCG": "ENCG Clubs", "To-Do": "To-Do", "Bilan": "Report",
        "Mes Certif.": "My Certs.", "Demander Certif.": "Request Certs.",
        "Dashboard": "Dashboard", "Certificats": "Certificates",
        "Demandes Docs": "Doc Requests", "Bilans Clubs": "Club Reports",
        "Docs Admin": "Admin Docs", "Ext.": "Ext.",
        # Actions
        "Se connecter": "Sign In", "Créer un nouveau compte": "Create Account",
        "Mot de passe oublié ?": "Forgot password?",
        "Sauvegarder": "Save", "Annuler": "Cancel", "Modifier": "Edit",
        "Publier": "Publish", "Soumettre": "Submit", "Envoyer": "Send",
        "Accepter": "Accept", "Refuser": "Decline", "Supprimer": "Delete",
        "Fermer": "Close", "Télécharger": "Download", "Partager": "Share",
        # Labels
        "Mes Clubs & Rôles": "My Clubs & Roles", "Année d'étude": "Study Year",
        "Langue": "Language", "Thème": "Theme",
        "Changer le mot de passe": "Change Password",
        "Modifier mes informations": "Edit my information",
        "Profil mis à jour avec succès!": "Profile updated successfully!",
        "Se connecter à HAIDEL": "Sign in to HAIDEL",
        "Entrez vos identifiants ENCG": "Enter your ENCG credentials",
    },
    "العربية": {
        "Accueil": "الرئيسية", "Demandes": "الطلبات", "Membres": "الأعضاء",
        "Messagerie": "الرسائل", "Mon Profil": "ملفي الشخصي",
        "Recrutements": "التوظيف", "Bilan Annuel": "التقرير السنوي",
        "Clubs ENCG": "نوادي ENCG", "Dashboard": "لوحة التحكم",
        "Se connecter": "تسجيل الدخول", "Créer un nouveau compte": "إنشاء حساب",
        "Sauvegarder": "حفظ", "Annuler": "إلغاء", "Modifier": "تعديل",
        "Fermer": "إغلاق", "Accepter": "قبول", "Refuser": "رفض",
        "Année d'étude": "السنة الدراسية", "Langue": "اللغة", "Thème": "المظهر",
    },
    "Español": {
        "Accueil": "Inicio", "Demandes": "Solicitudes", "Membres": "Miembros",
        "Messagerie": "Mensajería", "Mon Profil": "Mi Perfil",
        "Recrutements": "Reclutamiento", "Bilan Annuel": "Informe Anual",
        "Clubs ENCG": "Clubs ENCG", "Dashboard": "Panel",
        "Se connecter": "Iniciar sesión", "Créer un nouveau compte": "Crear cuenta",
        "Sauvegarder": "Guardar", "Annuler": "Cancelar", "Modifier": "Editar",
        "Fermer": "Cerrar", "Accepter": "Aceptar", "Refuser": "Rechazar",
        "Année d'étude": "Año de estudio", "Langue": "Idioma", "Thème": "Tema",
    },
}

def set_language(lang: str):
    global _LANG
    if lang in TRANSLATIONS:
        _LANG = lang

def current_language() -> str:
    return _LANG

def t(key: str) -> str:
    """Translate key to current language."""
    if _LANG == "Français" or _LANG not in TRANSLATIONS:
        return key
    return TRANSLATIONS[_LANG].get(key, key)
