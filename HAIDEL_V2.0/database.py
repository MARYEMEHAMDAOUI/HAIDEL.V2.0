"""HAIDEL v2.0 – Database Layer
All tables, queries and storage management.
Images stored as Base64 in SQLite.
"""
import sqlite3, hashlib, os, base64
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "haidel.db")

def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    return c

def _h(p): return hashlib.sha256(p.encode()).hexdigest()
def _rows(c): return [dict(r) for r in c.fetchall()]
def _row(c):  r = c.fetchone(); return dict(r) if r else None

# ─── Schema ───────────────────────────────────────────────────────────────────

def init_database():
    db = conn()
    db.executescript("""
    PRAGMA foreign_keys=ON;
    
    CREATE TABLE IF NOT EXISTS utilisateurs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN('admin','president','vp','membre','etudiant')),
        username TEXT UNIQUE,
        date_creation TEXT DEFAULT(datetime('now','localtime')),
        actif INTEGER DEFAULT 1,
        avatar_color TEXT DEFAULT '#7B4F2E');

    CREATE TABLE IF NOT EXISTS clubs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL, type TEXT NOT NULL,
        description TEXT DEFAULT '',
        date_creation TEXT DEFAULT(datetime('now','localtime')),
        president_id INTEGER, statut TEXT DEFAULT 'Actif',
        messagerie_mode TEXT DEFAULT 'all',
        FOREIGN KEY(president_id) REFERENCES utilisateurs(id));

    CREATE TABLE IF NOT EXISTS club_membres(
        club_id INTEGER, membre_id INTEGER,
        role TEXT DEFAULT 'membre', actif INTEGER DEFAULT 1,
        date_adhesion TEXT DEFAULT(datetime('now','localtime')),
        PRIMARY KEY(club_id,membre_id),
        FOREIGN KEY(club_id) REFERENCES clubs(id),
        FOREIGN KEY(membre_id) REFERENCES utilisateurs(id));

    CREATE TABLE IF NOT EXISTS demandes(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        titre TEXT NOT NULL, type TEXT NOT NULL,
        description TEXT DEFAULT '',
        statut TEXT DEFAULT 'Soumise',
        president_id INTEGER, club_id INTEGER,
        date_soumission TEXT DEFAULT(datetime('now','localtime')),
        date_traitement TEXT,
        commentaire_admin TEXT DEFAULT '',
        FOREIGN KEY(president_id) REFERENCES utilisateurs(id),
        FOREIGN KEY(club_id) REFERENCES clubs(id));

    CREATE TABLE IF NOT EXISTS annonces(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        titre TEXT NOT NULL, contenu TEXT NOT NULL,
        type TEXT NOT NULL DEFAULT 'General',
        statut TEXT DEFAULT 'Brouillon',
        auteur_id INTEGER, club_id INTEGER,
        image_data TEXT DEFAULT '',
        image_mime TEXT DEFAULT '',
        date_publication TEXT DEFAULT(datetime('now','localtime')),
        FOREIGN KEY(auteur_id) REFERENCES utilisateurs(id),
        FOREIGN KEY(club_id) REFERENCES clubs(id));

    CREATE TABLE IF NOT EXISTS recrutements(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        club_id INTEGER, titre TEXT NOT NULL,
        description TEXT DEFAULT '',
        statut TEXT DEFAULT 'Ouvert',
        date_limite TEXT,
        date_creation TEXT DEFAULT(datetime('now','localtime')),
        FOREIGN KEY(club_id) REFERENCES clubs(id));

    CREATE TABLE IF NOT EXISTS candidatures(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        recrutement_id INTEGER, etudiant_id INTEGER,
        statut TEXT DEFAULT 'En Attente',
        type_entretien TEXT DEFAULT '',
        date_entretien TEXT DEFAULT '',
        lieu TEXT DEFAULT '', lien_teams TEXT DEFAULT '',
        date_soumission TEXT DEFAULT(datetime('now','localtime')),
        FOREIGN KEY(recrutement_id) REFERENCES recrutements(id),
        FOREIGN KEY(etudiant_id) REFERENCES utilisateurs(id));

    CREATE TABLE IF NOT EXISTS activites(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        titre TEXT NOT NULL, description TEXT DEFAULT '',
        club_id INTEGER, date_activite TEXT,
        lieu TEXT DEFAULT '',
        statut TEXT DEFAULT 'En Planification',
        capacite INTEGER DEFAULT 50,
        FOREIGN KEY(club_id) REFERENCES clubs(id));

    CREATE TABLE IF NOT EXISTS certificats(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        etudiant_id INTEGER, club_id INTEGER,
        type TEXT DEFAULT 'Engagement',
        titre TEXT NOT NULL,
        date_delivrance TEXT DEFAULT(datetime('now','localtime')),
        statut TEXT DEFAULT 'Disponible',
        FOREIGN KEY(etudiant_id) REFERENCES utilisateurs(id),
        FOREIGN KEY(club_id) REFERENCES clubs(id));

    CREATE TABLE IF NOT EXISTS cert_requests(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        president_id INTEGER NOT NULL,
        club_id INTEGER NOT NULL,
        membre_id INTEGER NOT NULL,
        titre TEXT NOT NULL,
        type TEXT DEFAULT 'Engagement',
        statut TEXT DEFAULT 'En Attente',
        date_demande TEXT DEFAULT(datetime('now','localtime')),
        FOREIGN KEY(president_id) REFERENCES utilisateurs(id),
        FOREIGN KEY(club_id) REFERENCES clubs(id),
        FOREIGN KEY(membre_id) REFERENCES utilisateurs(id));

    CREATE TABLE IF NOT EXISTS taches(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        president_id INTEGER, titre TEXT NOT NULL,
        description TEXT DEFAULT '',
        terminee INTEGER DEFAULT 0,
        priorite TEXT DEFAULT 'Normale',
        date_echeance TEXT DEFAULT '',
        date_creation TEXT DEFAULT(datetime('now','localtime')),
        FOREIGN KEY(president_id) REFERENCES utilisateurs(id));

    CREATE TABLE IF NOT EXISTS group_messages(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        club_id INTEGER NOT NULL,
        expediteur_id INTEGER NOT NULL,
        contenu TEXT NOT NULL,
        date_envoi TEXT DEFAULT(datetime('now','localtime')),
        FOREIGN KEY(club_id) REFERENCES clubs(id),
        FOREIGN KEY(expediteur_id) REFERENCES utilisateurs(id));

    CREATE TABLE IF NOT EXISTS club_applications(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        etudiant_id INTEGER NOT NULL,
        club_id INTEGER NOT NULL,
        statut TEXT DEFAULT 'En Attente',
        date_soumission TEXT DEFAULT(datetime('now','localtime')),
        FOREIGN KEY(etudiant_id) REFERENCES utilisateurs(id),
        FOREIGN KEY(club_id) REFERENCES clubs(id));

    CREATE TABLE IF NOT EXISTS participants_externes(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL, email TEXT DEFAULT '',
        organisation TEXT DEFAULT '',
        activite_id INTEGER,
        date_ajout TEXT DEFAULT(datetime('now','localtime')));

    CREATE TABLE IF NOT EXISTS bilans(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        club_id INTEGER, president_id INTEGER,
        annee TEXT,
        resume TEXT DEFAULT '',
        activites_realises INTEGER DEFAULT 0,
        membres_actifs INTEGER DEFAULT 0,
        evenements INTEGER DEFAULT 0,
        statut TEXT DEFAULT 'Soumis',
        date_soumission TEXT DEFAULT(datetime('now','localtime')),
        FOREIGN KEY(club_id) REFERENCES clubs(id),
        FOREIGN KEY(president_id) REFERENCES utilisateurs(id));
    """)
    db.commit()
    _seed(db)
    db.close()
    run_migrations()
    run_v3_migrations()
    run_v2_migrations()
    ensure_social_tables()
    ensure_admin_requests_table()
    seed_admin_requests()

# ─── Seed ─────────────────────────────────────────────────────────────────────

REAL_DATA = {
  'admin': {'nom': 'Nisrine Benhammou', 'email': 'nisrine.benhammou@uca.ac.ma', 'username': 'Benhammou.Nisrine', 'password': 'Benhammou8623'},
  'clubs': [
    {'nom': 'Théatrart', 'type': 'Général', 'pres_nom': 'Rafffaa Wissal', 'pres_email': 'raffaawissal@gmail.com', 'pres_tel': '0771430621', 'pres_username': 'Wissal.Rafffaa', 'pres_password': 'Wissal0621', 'vp_nom': 'LAMTOUNI YASSINE', 'vp_tel': '212700-671641', 'vp_username': 'Lamtouni.Yassine', 'vp_password': 'Lamtouni1641'},
    {'nom': 'JLM', 'type': 'Social', 'pres_nom': 'Achraf Nassar', 'pres_email': 'achrafnassar18@gmail.com', 'pres_tel': '0681662209', 'pres_username': 'Nassar.Achraf', 'pres_password': 'Nassar2209', 'vp_nom': None, 'vp_tel': None, 'vp_username': None, 'vp_password': None},
    {'nom': "Club d'Excellence", 'type': 'Débats, Public Speaking & Littérature', 'pres_nom': 'Rahma Errachidi', 'pres_email': 'rerrachidi@gmail.com', 'pres_tel': '0689489023', 'pres_username': 'Errachidi.Rahma', 'pres_password': 'Errachidi9023', 'vp_nom': 'EZZAHRAOUI AYMANE', 'vp_tel': '212698-335767', 'vp_username': 'Ezzahraoui.Aymane', 'vp_password': 'Ezzahraoui5767'},
    {'nom': 'Green Invest', 'type': 'Environnement et développement durable', 'pres_nom': 'Hali Ziad', 'pres_email': 'contactzyad01@gmail.com', 'pres_tel': '0657998263', 'pres_username': 'Ziad.Hali', 'pres_password': 'Ziad8263', 'vp_nom': 'ZOUINE TAHA', 'vp_tel': '212663-301419', 'vp_username': 'Zouine.Taha', 'vp_password': 'Zouine1419'},
    {'nom': 'United Cultures', 'type': 'Cultures étrangères', 'pres_nom': 'Christy Charles', 'pres_email': 'christycharles2002@gmail.com', 'pres_tel': '0675812479', 'pres_username': 'Charles.Christy', 'pres_password': 'Charles2479', 'vp_nom': 'BRENDA SONIA', 'vp_tel': '212651-065346', 'vp_username': 'Brenda.Sonia', 'vp_password': 'Brenda5346'},
    {'nom': 'Ethical Business', 'type': "Droits de l'homme et engagement civique", 'pres_nom': 'Ahmed Modaffar Idrissi', 'pres_email': 'modaffar.ahmed@gmail.com', 'pres_tel': '0688970176', 'pres_username': 'Idrissi.Ahmed', 'pres_password': 'Idrissi0176', 'vp_nom': 'EL OUFIR ADAM', 'vp_tel': '212644-213892', 'vp_username': 'El.Oufir', 'vp_password': 'El3892'},
    {'nom': 'Beventful', 'type': 'Evénementiel', 'pres_nom': 'El Idrissi Saad', 'pres_email': 'isaad5969@gmail.com', 'pres_tel': '0658405785', 'pres_username': 'ElIdrissi.Saad', 'pres_password': 'ElIdrissi5785', 'vp_nom': 'AMHAREF WALID', 'vp_tel': '212619-504305', 'vp_username': 'Amharef.Walid', 'vp_password': 'Amharef4305'},
    {'nom': 'Enactus ENCG Marrakech', 'type': 'Entrepreneuriat social', 'pres_nom': 'Ourik Meriem', 'pres_email': 'meriem.ourik05@gmail.com', 'pres_tel': '0703236110', 'pres_username': 'Meriem.Ourik', 'pres_password': 'Meriem6110', 'vp_nom': 'CHERKAOUI IKRAM', 'vp_tel': '212762-363875', 'vp_username': 'Cherkaoui.Ikram', 'vp_password': 'Cherkaoui3875'},
    {'nom': 'TIZI ENCG Marrakech', 'type': "Droits de l'homme et engagement civique", 'pres_nom': 'Jaouad Abderrahmane', 'pres_email': 'jaouadabderrahmane7@gmail.com', 'pres_tel': '0767029640', 'pres_username': 'Abderrahmane.Jaouad', 'pres_password': 'Abderrahmane9640', 'vp_nom': None, 'vp_tel': None, 'vp_username': None, 'vp_password': None},
    {'nom': 'Rotaract', 'type': 'Social', 'pres_nom': 'Fariss Idrissi Mouad', 'pres_email': 'fmouad107@gmail.com', 'pres_tel': '0631186287', 'pres_username': 'Mouad.Fariss', 'pres_password': 'Mouad6287', 'vp_nom': 'MAOUKIL HAITAM', 'vp_tel': '212733-23684', 'vp_username': 'Maoukil.Haitam', 'vp_password': 'Maoukil3684'},
    {'nom': 'Chessrise', 'type': 'Général', 'pres_nom': 'Rakib Adib', 'pres_email': 'adib.rakib777@gmail.com', 'pres_tel': '0679694212', 'pres_username': 'Adib.Rakib', 'pres_password': 'Adib4212', 'vp_nom': 'TOUMI AYA', 'vp_tel': '212656-504792', 'vp_username': 'Toumi.Aya', 'vp_password': 'Toumi4792'},
    {'nom': 'CLC In Moves', 'type': 'Divertissement', 'pres_nom': 'Kenza Lemdeghri Alaoui', 'pres_email': 'alaouikenza741@gmail.com', 'pres_tel': '0627372175', 'pres_username': 'Alaoui.Kenza', 'pres_password': 'Alaoui2175', 'vp_nom': 'HALIM ACHRAF', 'vp_tel': '212636-117104', 'vp_username': 'Halim.Achraf', 'vp_password': 'Halim7104'},
    {'nom': 'Club des Arts Visuels', 'type': 'Arts', 'pres_nom': 'Moussaddad Alaa', 'pres_email': 'moussaddadalaa@gmail.com', 'pres_tel': '0762456326', 'pres_username': 'Alaa.Moussaddad', 'pres_password': 'Alaa6326', 'vp_nom': 'NASDAMI AMINE', 'vp_tel': '212601-524503', 'vp_username': 'Nasdami.Amine', 'vp_password': 'Nasdami4503'},
    {'nom': 'Fintech Club', 'type': 'Fintech', 'pres_nom': 'Oumaima Benboukhris', 'pres_email': 'oumaimabenboukhris@gmail.com', 'pres_tel': '0628183186', 'pres_username': 'Benboukhris.Oumaima', 'pres_password': 'Benboukhris3186', 'vp_nom': 'ILYASS GISSER', 'vp_tel': '212 696-282063', 'vp_username': 'Ilyass.Gisser', 'vp_password': 'Ilyass2063'},
    {'nom': 'Club des Visionnaires en Action', 'type': 'Développement personnel & professionnel', 'pres_nom': 'Chorfi Narjiss', 'pres_email': 'narjisschorfii@gmail.com', 'pres_tel': '0635273766', 'pres_username': 'Narjiss.Chorfi', 'pres_password': 'Narjiss3766', 'vp_nom': 'EL ACHHAB WISSAL', 'vp_tel': '212716-044116', 'vp_username': 'El.Achhab', 'vp_password': 'El4116'},
    {'nom': 'Business Chef', 'type': 'Divertissement', 'pres_nom': 'Namous Aya', 'pres_email': 'ayanamous2017@gmail.com', 'pres_tel': '0615276771', 'pres_username': 'Aya.Namous', 'pres_password': 'Aya6771', 'vp_nom': 'RAFAA WISSAL', 'vp_tel': '212771-430621', 'vp_username': 'Rafaa.Wissal', 'vp_password': 'Rafaa0621'},
    {'nom': 'AJI', 'type': 'Social', 'pres_nom': 'El Mferrek Abdelwafi', 'pres_email': 'elmferrek@gmail.com', 'pres_tel': '0678406104', 'pres_username': 'ElMferrek.Abdelwafi', 'pres_password': 'ElMferrek6104', 'vp_nom': 'MERHARFI DOUAE', 'vp_tel': '212680-877939', 'vp_username': 'Merharfi.Douae', 'vp_password': 'Merharfi7939'},
    {'nom': 'Agoracle', 'type': 'Débats, Public Speaking & Littérature', 'pres_nom': 'Reha Ghita', 'pres_email': 'g.reha6056@uca.ac.ma', 'pres_tel': '0771376010', 'pres_username': 'Ghita.Reha', 'pres_password': 'Ghita6010', 'vp_nom': 'SOUHAIL FATIMA EZZAHRA', 'vp_tel': '212 621-063498', 'vp_username': 'Souhail.Fatima', 'vp_password': 'Souhail3498'},
    {'nom': 'Lions Club', 'type': 'Social', 'pres_nom': 'El Moustaquim Aboulkacem', 'pres_email': 'elmoustaquima@gmail.com', 'pres_tel': '0611682667', 'pres_username': 'ElMoustaquim.Aboulkacem', 'pres_password': 'ElMoustaquim2667', 'vp_nom': 'NIZAR HARRAT', 'vp_tel': '212609-512422', 'vp_username': 'Nizar.Harrat', 'vp_password': 'Nizar2422'},
    {'nom': 'KOTAKU', 'type': 'Cultures étrangères', 'pres_nom': 'Reda BADIA', 'pres_email': 'redabadia2@gmail.com', 'pres_tel': '0766247242', 'pres_username': 'BADIA.Reda', 'pres_password': 'BADIA7242', 'vp_nom': 'IDRISSI BACHA ADAM', 'vp_tel': '212666-992784', 'vp_username': 'Idrissi.Bacha', 'vp_password': 'Idrissi2784'},
    {'nom': 'Supply Chain Leaders', 'type': 'Supply chain', 'pres_nom': 'Chouraq Omaima', 'pres_email': 'oumaimachouraq4@gmail.com', 'pres_tel': '0653787437', 'pres_username': 'Omaima.Chouraq', 'pres_password': 'Omaima7437', 'vp_nom': 'EL GUEMADI HIND', 'vp_tel': '212689-596694', 'vp_username': 'El.Guemadi', 'vp_password': 'El6694'},
    {'nom': 'Epik Leaders', 'type': 'Leadership Afrique', 'pres_nom': 'Sonia Brenda', 'pres_email': 'soniabrendakr@gmail.com', 'pres_tel': '0651065346', 'pres_username': 'Brenda.Sonia', 'pres_password': 'Brenda5346', 'vp_nom': 'AABLA EL ASSALI', 'vp_tel': '212665-016795', 'vp_username': 'Aabla.El', 'vp_password': 'Aabla6795'},
    {'nom': 'Harmonia', 'type': 'Arts', 'pres_nom': 'El Oufir Adam', 'pres_email': 'adameloufir27@gmail.com', 'pres_tel': '0644213892', 'pres_username': 'ElOufir.Adam', 'pres_password': 'ElOufir3892', 'vp_nom': 'SABRI ARIJE', 'vp_tel': '21236-727585', 'vp_username': 'Sabri.Arije', 'vp_password': 'Sabri7585'},
    {'nom': 'Mic & Mind', 'type': 'Journalisme, Média & Podcast', 'pres_nom': 'Aya Chifaoui', 'pres_email': 'ayachifaoui19@gmail.com', 'pres_tel': '0614410952', 'pres_username': 'Chifaoui.Aya', 'pres_password': 'Chifaoui0952', 'vp_nom': 'RANIA EL FOUIRI', 'vp_tel': '212610-922743', 'vp_username': 'Rania.El', 'vp_password': 'Rania2743'},
    {'nom': 'Podfest', 'type': 'Journalisme, Média & Podcast', 'pres_nom': 'El Belghiti Islam', 'pres_email': 'islamelbelghiti@gmail.com', 'pres_tel': '0616195005', 'pres_username': 'ElBelghiti.Islam', 'pres_password': 'ElBelghiti5005', 'vp_nom': 'BOUFOUS BASMA', 'vp_tel': '212682-124370', 'vp_username': 'Boufous.Basma', 'vp_password': 'Boufous4370'},
    {'nom': 'Pythagoras Club', 'type': 'Employabilité', 'pres_nom': 'Bachar Salah Eddine', 'pres_email': 'salahbachar8@gmail.com', 'pres_tel': '0619377602', 'pres_username': 'Eddine.Bachar', 'pres_password': 'Eddine7602', 'vp_nom': 'BOUCETTA MERYEM', 'vp_tel': '212639-105752', 'vp_username': 'Boucetta.Meryem', 'vp_password': 'Boucetta5752'},
    {'nom': 'Symposium', 'type': 'Débats, Public Speaking & Littérature', 'pres_nom': 'El Baroudi Marwa', 'pres_email': 'marelshoax@outlook.com', 'pres_tel': '0688687002', 'pres_username': 'ElBaroudi.Marwa', 'pres_password': 'ElBaroudi7002', 'vp_nom': 'SANDIA YASSMINE', 'vp_tel': '212665-035213', 'vp_username': 'Sandia.Yassmine', 'vp_password': 'Sandia5213'},
    {'nom': 'Reach', 'type': 'Entrepreneuriat sportif et de santé', 'pres_nom': 'Baimik Salma', 'pres_email': 'baymiksalma@gmail.com', 'pres_tel': '0720860222', 'pres_username': 'Salma.Baimik', 'pres_password': 'Salma0222', 'vp_nom': 'AYA ABOU', 'vp_tel': '212647-116530', 'vp_username': 'Aya.Abou', 'vp_password': 'Aya6530'},
  ]
}

def _gen_img(title, c1, c2, icon="🎓", w=800, h=400):
    """Generate a gradient announcement image. Returns (b64, mime)."""
    try:
        from PIL import Image, ImageDraw, ImageFont, ImageFilter
        import io as _io
        FP = None
        for p in ['/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
                  'C:/Windows/Fonts/arialbd.ttf', '/System/Library/Fonts/Helvetica.ttc']:
            import os
            if os.path.exists(p): FP=p; break
        img = Image.new("RGB",(w,h),c1)
        draw = ImageDraw.Draw(img)
        for y in range(h):
            t=y/h
            def L(a,b): return int(int(a,16)*(1-t)+int(b,16)*t)
            draw.line([(0,y),(w,y)],fill=(L(c1[1:3],c2[1:3]),L(c1[3:5],c2[3:5]),L(c1[5:7],c2[5:7])))
        h1=bytes.fromhex(c1[1:]); h2=bytes.fromhex(c2[1:])
        draw.ellipse([w-220,-80,w+80,220],fill=(*[min(255,int(x*1.25)) for x in h1],60))
        draw.ellipse([-80,h-160,160,h+60],fill=(*h2,45))
        draw.rounded_rectangle([32,32,w-32,h-32],radius=22,fill=(255,255,255,205))
        try: ef=ImageFont.truetype(FP,72) if FP else ImageFont.load_default()
        except: ef=ImageFont.load_default()
        draw.text((60,44),icon,font=ef,fill=(40,20,10))
        try: tf=ImageFont.truetype(FP,34) if FP else ImageFont.load_default()
        except: tf=ImageFont.load_default()
        short=title.replace("🚀","").replace("🎯","").replace("💼","").replace("📊","").replace("⚽","").strip()
        draw.text((60,130),short[:42],font=tf,fill=(30,20,10))
        try: sf=ImageFont.truetype(FP,20) if FP else ImageFont.load_default()
        except: sf=ImageFont.load_default()
        draw.rounded_rectangle([32,h-70,w-32,h-32],radius=14,fill=(*h1,200))
        draw.text((52,h-58),"HAIDEL • ENCG Marrakech",font=sf,fill=(255,255,255))
        img=img.filter(ImageFilter.SMOOTH)
        buf=_io.BytesIO(); img.save(buf,"JPEG",quality=88)
        return base64.b64encode(buf.getvalue()).decode(),"image/jpeg"
    except Exception as e:
        return "",""


def _seed(db):
    """Seed only with real data from BDD_Final_oum.xlsx. No demo accounts."""
    if db.execute("SELECT COUNT(*) FROM utilisateurs").fetchone()[0] > 0:
        return   # Already seeded

    import hashlib

    def _h(s):
        return hashlib.sha256(s.encode()).hexdigest()

    COLORS = ["#8B4513","#1877F2","#31A24C","#E67E22","#7B61FF",
              "#C0622F","#E8A838","#FA383E","#1B74E4","#6B3A2A",
              "#8B0000","#006400","#00008B","#8B4513","#4B0082",
              "#FF8C00","#008080","#800080","#DC143C","#2F4F4F"]

    # ── Admin ─────────────────────────────────────────────────────────────────
    adm = REAL_DATA['admin']
    db.execute("INSERT INTO utilisateurs(nom,email,password,role,avatar_color,username) VALUES(?,?,?,?,?,?)",
               (adm['nom'], adm['email'], _h(adm['password']), "admin", "#8B4513", adm['username']))
    admin_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

    # ── Présidents + VPs + Clubs ───────────────────────────────────────────────
    pres_ids = []
    for i, cl in enumerate(REAL_DATA['clubs']):
        col = COLORS[i % len(COLORS)]

        # President
        pres_id = None
        if cl['pres_nom']:
            try:
                db.execute("INSERT INTO utilisateurs(nom,email,password,role,avatar_color,username) VALUES(?,?,?,?,?,?)",
                           (cl['pres_nom'], cl['pres_email'], _h(cl['pres_password']),
                            "president", col, cl['pres_username']))
                pres_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            except Exception as e:
                # Duplicate username — append club index
                try:
                    uname = cl['pres_username'] + str(i)
                    db.execute("INSERT INTO utilisateurs(nom,email,password,role,avatar_color,username) VALUES(?,?,?,?,?,?)",
                               (cl['pres_nom'], cl['pres_email'], _h(cl['pres_password']),
                                "president", col, uname))
                    pres_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
                except: pass

        # VP
        vp_id = None
        if cl['vp_nom'] and cl['vp_username']:
            vp_email = f"{cl['vp_username'].lower()}@encg.ma"
            try:
                db.execute("INSERT INTO utilisateurs(nom,email,password,role,avatar_color,username) VALUES(?,?,?,?,?,?)",
                           (cl['vp_nom'], vp_email, _h(cl['vp_password']),
                            "vp", COLORS[(i+5) % len(COLORS)], cl['vp_username']))
                vp_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
            except: pass

        # Club
        desc = f"Club {cl['nom']} — ENCG Marrakech. Thématique : {cl['type']}."
        db.execute("INSERT INTO clubs(nom,type,description,president_id,statut) VALUES(?,?,?,?,'Actif')",
                   (cl['nom'], cl['type'], desc, pres_id))
        club_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Add president as member
        if pres_id:
            try:
                db.execute("INSERT OR IGNORE INTO club_membres(club_id,membre_id,role,actif) VALUES(?,?,?,1)",
                           (club_id, pres_id, 'president'))
            except: pass
        # Add VP as member
        if vp_id:
            try:
                db.execute("INSERT OR IGNORE INTO club_membres(club_id,membre_id,role,actif) VALUES(?,?,?,1)",
                           (club_id, vp_id, 'vp'))
            except: pass

        pres_ids.append((pres_id, club_id, cl))

    db.commit()

    # ── Demo images for announcements ──────────────────────────────────────────
    annonces = [
        ("🚀 Hackathon IA 2025 — ENCG Marrakech",
         "Participez au grand Hackathon Intelligence Artificielle de l'ENCG! 48h de création, des prix exceptionnels. Inscriptions: https://forms.encg-marrakech.ac.ma/hackathon-ia",
         "Evenement","Publiée",
         pres_ids[0][0] if pres_ids else admin_id,
         pres_ids[0][1] if pres_ids else None,
         "🤖","#1B4F8A","#0D2B4F"),
        ("💼 Forum Entrepreneuriat ENCG",
         "Le Club Enactus organise le Forum annuel de l'entrepreneuriat. Rencontrez des investisseurs et porteurs de projets. Plus d'infos: https://enactus-encg.ma/forum-2025",
         "Evenement","Publiée",
         pres_ids[7][0] if len(pres_ids)>7 else admin_id,
         pres_ids[7][1] if len(pres_ids)>7 else None,
         "💼","#1A6B3C","#0D3D22"),
        ("🎭 Spectacle Annuel Théatrart",
         "Le Club Théatrart vous invite à son spectacle annuel le 15 Juin. Entrée libre, places limitées!",
         "Evenement","Publiée",
         pres_ids[0][0] if pres_ids else admin_id,
         pres_ids[0][1] if pres_ids else None,
         "🎭","#6B2FA0","#3D1A5E"),
        ("📊 Atelier Fintech & Blockchain",
         "Le Fintech Club ENCG organise un atelier sur la Blockchain et les crypto-monnaies. Inscription obligatoire.",
         "Evenement","Publiée",
         pres_ids[13][0] if len(pres_ids)>13 else admin_id,
         pres_ids[13][1] if len(pres_ids)>13 else None,
         "📊","#B85C00","#6B3500"),
        ("⚽ Tournoi Inter-Clubs ENCG",
         "Reach Club organise le 3ème tournoi sportif inter-clubs! Inscriptions ouvertes jusqu'au 20 Mai.",
         "Activite","Publiée",
         pres_ids[27][0] if len(pres_ids)>27 else admin_id,
         pres_ids[27][1] if len(pres_ids)>27 else None,
         "⚽","#8B4513","#5C2D0A"),
    ]
    for titre,contenu,typ,statut,auteur,club_id,icon,c1,c2 in annonces:
        b64,mime=_gen_img(titre,c1,c2,icon)
        db.execute("INSERT INTO annonces(titre,contenu,type,statut,auteur_id,club_id,image_data,image_mime) VALUES(?,?,?,?,?,?,?,?)",
                   (titre,contenu,typ,statut,auteur,club_id,b64,mime))

    # Pending announcements for admin validation test
    pending = [
        ("🌍 Conférence des Droits de l'Homme",
         "TIZI ENCG organise une conférence sur les droits de l'homme. Intervenants nationaux et internationaux. Détails: https://tizi-encg.ma/conference-2025",
         "Evenement","En Attente",
         pres_ids[8][0] if len(pres_ids)>8 else admin_id,
         pres_ids[8][1] if len(pres_ids)>8 else None,
         "🌍","#1A6B3C","#0D3D22"),
    ]
    for titre,contenu,typ,statut,auteur,club_id,icon,c1,c2 in pending:
        b64,mime=_gen_img(titre,c1,c2,icon)
        db.execute("INSERT INTO annonces(titre,contenu,type,statut,auteur_id,club_id,image_data,image_mime) VALUES(?,?,?,?,?,?,?,?)",
                   (titre,contenu,typ,statut,auteur,club_id,b64,mime))

    db.commit()

def authenticate(login, password):
    """Supports: username (Nom.Prenom), email, or legacy login."""
    db2 = conn()
    ph = _h(password)
    # Try username first (Nom.Prenom format)
    r = _row(db2.execute(
        "SELECT * FROM utilisateurs WHERE username=? AND password=? AND actif=1",
        (login, ph)))
    if r: db2.close(); return r
    # Try email
    r = _row(db2.execute(
        "SELECT * FROM utilisateurs WHERE email=? AND password=? AND actif=1",
        (login, ph)))
    if r: db2.close(); return r
    # Try nom (fallback)
    r = _row(db2.execute(
        "SELECT * FROM utilisateurs WHERE nom=? AND password=? AND actif=1",
        (login, ph)))
    db2.close(); return r

def get_user_by_username(username):
    """Returns user info for forgot password flow."""
    db2 = conn()
    r = _row(db2.execute(
        "SELECT id,nom,email,username FROM utilisateurs WHERE username=? OR email=?",
        (username, username)))
    db2.close(); return r

# ─── Feed ─────────────────────────────────────────────────────────────────────

def get_annonces_feed(filter_type=None):
    db = conn()
    q = """SELECT a.*,u.nom AS auteur_nom,u.avatar_color AS auteur_color,cl.nom AS club_nom
           FROM annonces a
           LEFT JOIN utilisateurs u ON a.auteur_id=u.id
           LEFT JOIN clubs cl ON a.club_id=cl.id
           WHERE a.statut='Publiée'"""
    params = []
    if filter_type and filter_type != "Tous":
        q += " AND a.type=?"; params.append(filter_type)
    q += " ORDER BY a.date_publication DESC"
    r = _rows(db.execute(q, params)); db.close(); return r

# ─── Stats / Dashboard ────────────────────────────────────────────────────────

def get_clubs_stats():
    db = conn()
    total   = db.execute("SELECT COUNT(*) FROM clubs").fetchone()[0]
    by_type = _rows(db.execute("SELECT type,COUNT(*) AS n FROM clubs GROUP BY type ORDER BY n DESC"))
    active  = db.execute("SELECT COUNT(*) FROM demandes WHERE statut IN('Soumise','En Attente')").fetchone()[0]
    events  = db.execute("SELECT COUNT(*) FROM annonces WHERE type='Evenement' AND statut='Publiée'").fetchone()[0]
    membres = db.execute("SELECT COUNT(*) FROM utilisateurs WHERE role IN('membre','president','vp') AND actif=1").fetchone()[0]
    cert_req= db.execute("SELECT COUNT(*) FROM cert_requests WHERE statut='En Attente'").fetchone()[0]
    db.close()
    return {"total_clubs":total,"by_type":by_type,"active_demandes":active,
            "events_realises":events,"total_membres":membres,"cert_pending":cert_req}

def get_membres_per_club():
    db = conn()
    r = _rows(db.execute("""SELECT cl.nom,COUNT(cm.membre_id) AS n
        FROM clubs cl LEFT JOIN club_membres cm ON cl.id=cm.club_id AND cm.actif=1
        GROUP BY cl.id ORDER BY n DESC"""))
    db.close(); return r

def get_all_clubs():
    db = conn()
    r = _rows(db.execute("""SELECT cl.*,u.nom AS president_nom,
        (SELECT COUNT(*) FROM club_membres WHERE club_id=cl.id AND actif=1) AS nb_membres
        FROM clubs cl LEFT JOIN utilisateurs u ON cl.president_id=u.id ORDER BY cl.date_creation DESC"""))
    db.close(); return r

def get_all_clubs_with_details():
    return get_all_clubs()

# ─── Annonces ─────────────────────────────────────────────────────────────────

def get_annonces_pending():
    db = conn()
    r = _rows(db.execute("""SELECT a.*,u.nom AS auteur_nom,cl.nom AS club_nom
        FROM annonces a LEFT JOIN utilisateurs u ON a.auteur_id=u.id
        LEFT JOIN clubs cl ON a.club_id=cl.id WHERE a.statut='En Attente'"""))
    db.close(); return r

def approuver_annonce(aid, ok):
    db = conn()
    db.execute("UPDATE annonces SET statut=? WHERE id=?", ("Publiée" if ok else "Refusée", aid))
    db.commit(); db.close()

def publier_annonce_admin(titre, contenu, typ, auteur_id, image_b64="", image_mime=""):
    db = conn()
    db.execute("INSERT INTO annonces(titre,contenu,type,statut,auteur_id,image_data,image_mime) VALUES(?,?,?,'Publiée',?,?,?)",
               (titre, contenu, typ, auteur_id, image_b64, image_mime))
    db.commit(); db.close()

def publier_annonce_club(titre, contenu, typ, auteur_id, club_id, image_b64="", image_mime=""):
    """Président publishes directly — no admin confirmation required."""
    db = conn()
    db.execute("INSERT INTO annonces(titre,contenu,type,statut,auteur_id,club_id,image_data,image_mime) VALUES(?,?,?,'Publiée',?,?,?,?)",
               (titre, contenu, typ, auteur_id, club_id, image_b64, image_mime))
    db.commit(); db.close()

def encode_image(path):
    """Encode an image file to base64 for DB storage."""
    if not path or not os.path.exists(path): return "", ""
    ext = os.path.splitext(path)[1].lower()
    mime_map = {".jpg":"image/jpeg",".jpeg":"image/jpeg",".png":"image/png",".gif":"image/gif",".bmp":"image/bmp"}
    mime = mime_map.get(ext, "image/jpeg")
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8"), mime

# ─── Demandes ─────────────────────────────────────────────────────────────────

def get_demandes(role=None, user_id=None):
    db = conn()
    if role == "admin":
        r = _rows(db.execute("""SELECT d.*,u.nom AS president_nom,cl.nom AS club_nom
            FROM demandes d LEFT JOIN utilisateurs u ON d.president_id=u.id
            LEFT JOIN clubs cl ON d.club_id=cl.id ORDER BY d.date_soumission DESC"""))
    else:
        r = _rows(db.execute("""SELECT d.*,cl.nom AS club_nom FROM demandes d
            LEFT JOIN clubs cl ON d.club_id=cl.id
            WHERE d.president_id=? ORDER BY d.date_soumission DESC""", (user_id,)))
    db.close(); return r

def update_demande_statut(did, statut, commentaire=""):
    db = conn()
    db.execute("UPDATE demandes SET statut=?,commentaire_admin=?,date_traitement=datetime('now','localtime') WHERE id=?",
               (statut, commentaire, did))
    db.commit(); db.close()

def add_demande(titre, typ, description, president_id, club_id):
    db = conn()
    db.execute("INSERT INTO demandes(titre,type,description,president_id,club_id) VALUES(?,?,?,?,?)",
               (titre, typ, description, president_id, club_id))
    db.commit(); db.close()

# ─── Certificats ─────────────────────────────────────────────────────────────

def get_certificats_a_emettre():
    """Members eligible: in a club, no cert yet for current year."""
    db = conn()
    r = _rows(db.execute("""SELECT u.id,u.nom,u.email,cl.nom AS club_nom,cl.id AS club_id
        FROM utilisateurs u JOIN club_membres cm ON u.id=cm.membre_id
        JOIN clubs cl ON cl.id=cm.club_id
        WHERE u.role IN('membre','vp') AND cm.actif=1 ORDER BY cl.nom,u.nom"""))
    db.close(); return r

def get_all_certificats():
    db = conn()
    r = _rows(db.execute("""SELECT cert.*,u.nom AS etudiant_nom,cl.nom AS club_nom
        FROM certificats cert LEFT JOIN utilisateurs u ON cert.etudiant_id=u.id
        LEFT JOIN clubs cl ON cert.club_id=cl.id ORDER BY cert.date_delivrance DESC"""))
    db.close(); return r

def emettre_certificat(etudiant_id, club_id, titre, typ="Engagement"):
    db = conn()
    db.execute("INSERT INTO certificats(etudiant_id,club_id,type,titre) VALUES(?,?,?,?)",
               (etudiant_id, club_id, typ, titre))
    db.commit(); db.close()

def get_certificats(etudiant_id):
    db = conn()
    r = _rows(db.execute("""SELECT cert.*,cl.nom AS club_nom FROM certificats cert
        LEFT JOIN clubs cl ON cert.club_id=cl.id
        WHERE cert.etudiant_id=? ORDER BY cert.date_delivrance DESC""", (etudiant_id,)))
    db.close(); return r

# ─── Cert Requests (President → Admin) ───────────────────────────────────────

def get_cert_requests(president_id=None, status="En Attente"):
    db = conn()
    if president_id:
        r = _rows(db.execute("""SELECT cr.*,u.nom AS membre_nom,u.email AS membre_email,
            cl.nom AS club_nom FROM cert_requests cr
            JOIN utilisateurs u ON cr.membre_id=u.id
            JOIN clubs cl ON cr.club_id=cl.id
            WHERE cr.president_id=? ORDER BY cr.date_demande DESC""", (president_id,)))
    else:
        r = _rows(db.execute("""SELECT cr.*,u.nom AS membre_nom,u.email AS membre_email,
            cl.nom AS club_nom,p.nom AS president_nom FROM cert_requests cr
            JOIN utilisateurs u ON cr.membre_id=u.id
            JOIN clubs cl ON cr.club_id=cl.id
            JOIN utilisateurs p ON cr.president_id=p.id
            WHERE cr.statut=? ORDER BY cr.date_demande DESC""", (status,)))
    db.close(); return r

def add_cert_request(president_id, club_id, membre_id, titre, typ="Engagement"):
    db = conn()
    # avoid duplicate pending
    ex = db.execute("SELECT id FROM cert_requests WHERE president_id=? AND membre_id=? AND statut='En Attente'",
                    (president_id, membre_id)).fetchone()
    if ex: db.close(); return False
    db.execute("INSERT INTO cert_requests(president_id,club_id,membre_id,titre,type) VALUES(?,?,?,?,?)",
               (president_id, club_id, membre_id, titre, typ))
    db.commit(); db.close(); return True

def approve_cert_request(req_id):
    db = conn()
    r = db.execute("SELECT * FROM cert_requests WHERE id=?", (req_id,)).fetchone()
    if not r: db.close(); return
    db.execute("INSERT INTO certificats(etudiant_id,club_id,type,titre) VALUES(?,?,?,?)",
               (r["membre_id"], r["club_id"], r["type"], r["titre"]))
    db.execute("UPDATE cert_requests SET statut='Émis' WHERE id=?", (req_id,))
    db.commit(); db.close()

def reject_cert_request(req_id):
    db = conn()
    db.execute("UPDATE cert_requests SET statut='Refusé' WHERE id=?", (req_id,))
    db.commit(); db.close()

# ─── Club / Members ───────────────────────────────────────────────────────────

def get_club_of_president(president_id):
    db = conn()
    r = _row(db.execute("SELECT * FROM clubs WHERE president_id=? LIMIT 1", (president_id,)))
    db.close(); return r

def get_membres_club(president_id):
    db = conn()
    r = _rows(db.execute("""SELECT u.*,cm.actif AS actif_club,cm.role AS role_club,cl.id AS club_id
        FROM utilisateurs u JOIN club_membres cm ON u.id=cm.membre_id
        JOIN clubs cl ON cl.id=cm.club_id
        WHERE cl.president_id=? ORDER BY cm.actif DESC,u.nom""", (president_id,)))
    db.close(); return r

def toggle_membre_actif(club_id, membre_id):
    db = conn()
    db.execute("UPDATE club_membres SET actif=1-actif WHERE club_id=? AND membre_id=?", (club_id, membre_id))
    db.commit(); db.close()

def get_user_club_id(user_id):
    db = conn()
    r = db.execute("SELECT id FROM clubs WHERE president_id=?", (user_id,)).fetchone()
    if r: db.close(); return r[0]
    r = db.execute("SELECT club_id FROM club_membres WHERE membre_id=? AND actif=1 LIMIT 1", (user_id,)).fetchone()
    db.close(); return r[0] if r else None

# ─── Tâches ───────────────────────────────────────────────────────────────────

def get_taches(president_id):
    db = conn()
    r = _rows(db.execute("""SELECT * FROM taches WHERE president_id=?
        ORDER BY terminee ASC,
        CASE priorite WHEN 'Haute' THEN 1 WHEN 'Normale' THEN 2 ELSE 3 END,
        date_echeance""", (president_id,)))
    db.close(); return r

def add_tache(president_id, titre, description, priorite, date_echeance):
    db = conn()
    db.execute("INSERT INTO taches(president_id,titre,description,priorite,date_echeance) VALUES(?,?,?,?,?)",
               (president_id, titre, description, priorite, date_echeance))
    db.commit(); db.close()

def toggle_tache(tid):
    db = conn()
    db.execute("UPDATE taches SET terminee=1-terminee WHERE id=?", (tid,))
    db.commit(); db.close()

def delete_tache(tid):
    db = conn()
    db.execute("DELETE FROM taches WHERE id=?", (tid,))
    db.commit(); db.close()

# ─── Recrutements ─────────────────────────────────────────────────────────────

def get_recrutements(president_id=None):
    db = conn()
    if president_id:
        r = _rows(db.execute("""SELECT r.*,cl.nom AS club_nom,
            (SELECT COUNT(*) FROM candidatures WHERE recrutement_id=r.id) AS nb_candidatures,
            (SELECT COUNT(*) FROM candidatures WHERE recrutement_id=r.id AND statut='Accepté') AS nb_acceptes
            FROM recrutements r JOIN clubs cl ON r.club_id=cl.id
            WHERE cl.president_id=? ORDER BY r.date_creation DESC""", (president_id,)))
    else:
        r = _rows(db.execute("""SELECT r.*,cl.nom AS club_nom,
            (SELECT COUNT(*) FROM candidatures WHERE recrutement_id=r.id) AS nb_candidatures, 0 AS nb_acceptes
            FROM recrutements r JOIN clubs cl ON r.club_id=cl.id"""))
    db.close(); return r

def add_recrutement(club_id, titre, description, date_limite):
    db = conn()
    db.execute("INSERT INTO recrutements(club_id,titre,description,date_limite) VALUES(?,?,?,?)",
               (club_id, titre, description, date_limite))
    db.commit(); db.close()

def get_candidatures(recrutement_id):
    db = conn()
    r = _rows(db.execute("""SELECT ca.*,u.nom AS etudiant_nom,u.email AS etudiant_email
        FROM candidatures ca JOIN utilisateurs u ON ca.etudiant_id=u.id
        WHERE ca.recrutement_id=? ORDER BY ca.date_soumission DESC""", (recrutement_id,)))
    db.close(); return r

def update_candidature(cid, statut, type_entretien="", date_entretien="", lieu="", lien_teams=""):
    db = conn()
    db.execute("UPDATE candidatures SET statut=?,type_entretien=?,date_entretien=?,lieu=?,lien_teams=? WHERE id=?",
               (statut, type_entretien, date_entretien, lieu, lien_teams, cid))
    db.commit(); db.close()

# ─── Participants / Bilans ────────────────────────────────────────────────────

def get_participants_externes():
    db = conn()
    r = _rows(db.execute("""SELECT pe.*,ac.titre AS activite_titre
        FROM participants_externes pe LEFT JOIN activites ac ON pe.activite_id=ac.id
        ORDER BY pe.date_ajout DESC"""))
    db.close(); return r

def add_participant_externe(nom, email, organisation, activite_id):
    db = conn()
    db.execute("INSERT INTO participants_externes(nom,email,organisation,activite_id) VALUES(?,?,?,?)",
               (nom, email, organisation, activite_id))
    db.commit(); db.close()

def get_activites(club_id=None):
    db = conn()
    if club_id:
        r = _rows(db.execute("SELECT * FROM activites WHERE club_id=? ORDER BY date_activite", (club_id,)))
    else:
        r = _rows(db.execute("SELECT * FROM activites ORDER BY date_activite"))
    db.close(); return r

def soumettre_bilan(club_id, president_id, annee, resume, activites_n, membres_n, events_n):
    db = conn()
    db.execute("INSERT INTO bilans(club_id,president_id,annee,resume,activites_realises,membres_actifs,evenements) VALUES(?,?,?,?,?,?,?)",
               (club_id, president_id, annee, resume, activites_n, membres_n, events_n))
    db.commit(); db.close()

def get_bilans(president_id=None):
    db = conn()
    if president_id:
        r = _rows(db.execute("""SELECT b.*,cl.nom AS club_nom FROM bilans b
            JOIN clubs cl ON b.club_id=cl.id WHERE b.president_id=? ORDER BY b.annee DESC""", (president_id,)))
    else:
        r = _rows(db.execute("""SELECT b.*,cl.nom AS club_nom,u.nom AS president_nom
            FROM bilans b JOIN clubs cl ON b.club_id=cl.id
            JOIN utilisateurs u ON b.president_id=u.id ORDER BY b.annee DESC"""))
    db.close(); return r

# ─── Messaging ────────────────────────────────────────────────────────────────

def get_group_messages(club_id):
    db = conn()
    r = _rows(db.execute("""SELECT gm.*,u.nom AS exp_nom,u.role AS exp_role,u.avatar_color
        FROM group_messages gm JOIN utilisateurs u ON gm.expediteur_id=u.id
        WHERE gm.club_id=? ORDER BY gm.date_envoi""", (club_id,)))
    db.close(); return r

def send_group_message(club_id, expediteur_id, contenu):
    db = conn()
    db.execute("INSERT INTO group_messages(club_id,expediteur_id,contenu) VALUES(?,?,?)",
               (club_id, expediteur_id, contenu))
    db.commit(); db.close()

def get_messagerie_mode_by_club(club_id):
    db = conn()
    r = db.execute("SELECT messagerie_mode FROM clubs WHERE id=?", (club_id,)).fetchone()
    db.close(); return r["messagerie_mode"] if r else "all"

def set_messagerie_mode(president_id, mode):
    db = conn()
    db.execute("UPDATE clubs SET messagerie_mode=? WHERE president_id=?", (mode, president_id))
    db.commit(); db.close()

def can_send_message(sender_id, club_id):
    mode = get_messagerie_mode_by_club(club_id)
    if mode == "all": return True
    db = conn()
    r = db.execute("SELECT president_id FROM clubs WHERE id=?", (club_id,)).fetchone()
    db.close(); return bool(r and r["president_id"] == sender_id)

# ─── Club Applications ────────────────────────────────────────────────────────

def postuler_club(etudiant_id, club_id):
    db = conn()
    if db.execute("SELECT id FROM club_applications WHERE etudiant_id=? AND club_id=?",
                  (etudiant_id, club_id)).fetchone():
        db.close(); return False
    db.execute("INSERT INTO club_applications(etudiant_id,club_id) VALUES(?,?)", (etudiant_id, club_id))
    db.commit(); db.close(); return True

def get_user_application_status(etudiant_id, club_id):
    db = conn()
    r = db.execute("SELECT statut FROM club_applications WHERE etudiant_id=? AND club_id=?",
                   (etudiant_id, club_id)).fetchone()
    db.close(); return r["statut"] if r else None

def get_club_applications(president_id):
    db = conn()
    r = _rows(db.execute("""SELECT ca.*,u.nom AS etudiant_nom,u.email AS etudiant_email,cl.nom AS club_nom
        FROM club_applications ca JOIN utilisateurs u ON ca.etudiant_id=u.id
        JOIN clubs cl ON ca.club_id=cl.id
        WHERE cl.president_id=? AND ca.statut='En Attente' ORDER BY ca.date_soumission DESC""", (president_id,)))
    db.close(); return r

def get_all_club_applications(president_id):
    """All applications (all statuses) for history view."""
    db = conn()
    r = _rows(db.execute("""SELECT ca.*,u.nom AS etudiant_nom,u.email AS etudiant_email,cl.nom AS club_nom
        FROM club_applications ca JOIN utilisateurs u ON ca.etudiant_id=u.id
        JOIN clubs cl ON ca.club_id=cl.id
        WHERE cl.president_id=? ORDER BY ca.date_soumission DESC""", (president_id,)))
    db.close(); return r

def accept_club_application(app_id, etudiant_id, club_id):
    db = conn()
    db.execute("UPDATE club_applications SET statut='Accepté' WHERE id=?", (app_id,))
    db.execute("INSERT OR IGNORE INTO club_membres(club_id,membre_id) VALUES(?,?)", (club_id, etudiant_id))
    # Upgrade role from etudiant → membre so they get full member access
    db.execute("UPDATE utilisateurs SET role='membre' WHERE id=? AND role='etudiant'", (etudiant_id,))
    # Send welcome message to club chat
    try:
        nom_r = db.execute("SELECT nom FROM utilisateurs WHERE id=?", (etudiant_id,)).fetchone()
        nom = nom_r["nom"] if nom_r else "Nouveau membre"
        db.execute("INSERT INTO group_messages(club_id,expediteur_id,contenu) VALUES(?,?,?)",
                   (club_id, etudiant_id, f"👋 {nom} vient de rejoindre le club!"))
    except: pass
    db.commit(); db.close()

def reject_club_application(app_id):
    db = conn()
    db.execute("UPDATE club_applications SET statut='Refusé' WHERE id=?", (app_id,))
    db.commit(); db.close()

# ─── Schema migrations (run on every startup) ────────────────────────────────

def run_migrations():
    """Apply schema upgrades safely - idempotent."""
    db = conn()
    migrations = [
        "ALTER TABLE club_membres ADD COLUMN custom_role TEXT DEFAULT ''",
        """CREATE TABLE IF NOT EXISTS avertissements(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            club_id INTEGER NOT NULL,
            membre_id INTEGER NOT NULL,
            president_id INTEGER NOT NULL,
            motif TEXT NOT NULL,
            date_envoi TEXT DEFAULT(datetime('now','localtime')),
            FOREIGN KEY(club_id) REFERENCES clubs(id),
            FOREIGN KEY(membre_id) REFERENCES utilisateurs(id),
            FOREIGN KEY(president_id) REFERENCES utilisateurs(id))""",
    ]
    for sql in migrations:
        try:
            db.execute(sql); db.commit()
        except Exception:
            pass  # Already applied
    db.close()

# ─── Custom role & member management ─────────────────────────────────────────

def set_custom_role(club_id, membre_id, custom_role):
    """President assigns a custom role label (e.g. 'Responsable Trésor')."""
    db = conn()
    db.execute("UPDATE club_membres SET custom_role=? WHERE club_id=? AND membre_id=?",
               (custom_role, club_id, membre_id))
    db.commit(); db.close()

def get_custom_role(club_id, membre_id):
    db = conn()
    r = db.execute("SELECT custom_role FROM club_membres WHERE club_id=? AND membre_id=?",
                   (club_id, membre_id)).fetchone()
    db.close()
    return r["custom_role"] if r else ""

def supprimer_membre(club_id, membre_id):
    """Remove member from club (delete from club_membres)."""
    db = conn()
    db.execute("DELETE FROM club_membres WHERE club_id=? AND membre_id=?", (club_id, membre_id))
    db.commit(); db.close()

def envoyer_avertissement(club_id, membre_id, president_id, motif):
    db = conn()
    db.execute("INSERT INTO avertissements(club_id,membre_id,president_id,motif) VALUES(?,?,?,?)",
               (club_id, membre_id, president_id, motif))
    db.commit(); db.close()

def get_avertissements_membre(club_id, membre_id):
    db = conn()
    r = _rows(db.execute("""SELECT aw.*,p.nom AS president_nom FROM avertissements aw
        JOIN utilisateurs p ON aw.president_id=p.id
        WHERE aw.club_id=? AND aw.membre_id=?
        ORDER BY aw.date_envoi DESC""", (club_id, membre_id)))
    db.close(); return r

def get_membres_club_full(president_id):
    """Returns members with custom_role included."""
    db = conn()
    r = _rows(db.execute("""SELECT u.*,cm.actif AS actif_club,cm.role AS role_club,
        cm.custom_role, cl.id AS club_id
        FROM utilisateurs u JOIN club_membres cm ON u.id=cm.membre_id
        JOIN clubs cl ON cl.id=cm.club_id
        WHERE cl.president_id=? ORDER BY u.nom""", (president_id,)))
    db.close(); return r

def get_membre_custom_role_for_display(user_id):
    """What custom role did the president assign to this user (for member display)?"""
    db = conn()
    r = db.execute("""SELECT cm.custom_role,cl.nom AS club_nom FROM club_membres cm
        JOIN clubs cl ON cm.club_id=cl.id
        WHERE cm.membre_id=? AND cm.actif=1 LIMIT 1""", (user_id,)).fetchone()
    db.close()
    return dict(r) if r else {}

# ─── Registration / Signup ────────────────────────────────────────────────────

def get_clubs_list():
    db = conn()
    r = _rows(db.execute("SELECT id,nom FROM clubs ORDER BY nom"))
    db.close(); return r

def create_user(nom, prenom, email, annee, club_id, statut, password=None):
    """Register a new etudiant/membre. Returns (True,user) or (False,error)."""
    db_c = conn()
    existing = db_c.execute("SELECT id FROM utilisateurs WHERE email=?", (email,)).fetchone()
    if existing:
        db_c.close(); return False, "Cet email est déjà enregistré."
    role = "membre" if statut == "membre" else "etudiant"
    colors = ["#8B4513","#1877F2","#31A24C","#E67E22","#7B61FF",
              "#C0622F","#E8A838","#FA383E","#1B74E4","#6B3A2A"]
    color = colors[hash(email) % len(colors)]
    full_nom = f"{prenom} {nom}"
    # Generate username: Nom.Prenom
    username = f"{nom}.{prenom}".replace(" ","")
    # Check username uniqueness
    i = 0
    base_uname = username
    while db_c.execute("SELECT id FROM utilisateurs WHERE username=?", (username,)).fetchone():
        i += 1; username = f"{base_uname}{i}"
    # Password: user-chosen or generated
    if password:
        pwd_plain = password
    else:
        pwd_plain = nom + (email.split("@")[0][-4:])
    cur = db_c.execute(
        "INSERT INTO utilisateurs(nom,email,password,role,avatar_color,username,annee_etude) VALUES(?,?,?,?,?,?,?)",
        (full_nom, email, _h(pwd_plain), role, color, username, annee))
    uid = cur.lastrowid
    if club_id and role == "membre":
        try:
            db_c.execute("INSERT OR IGNORE INTO club_membres(club_id,membre_id) VALUES(?,?)", (club_id, uid))
        except Exception: pass
    db_c.commit(); db_c.close()
    return True, {"id":uid,"nom":full_nom,"email":email,"role":role,
                  "avatar_color":color,"actif":1,"pwd_plain":pwd_plain,
                  "username":username}


# ─── Profile / Password ───────────────────────────────────────────────────────

def get_user_by_id(user_id):
    db = conn()
    r = _row(db.execute("SELECT * FROM utilisateurs WHERE id=?", (user_id,)))
    db.close(); return r

def update_password(user_id, new_plain):
    db = conn()
    db.execute("UPDATE utilisateurs SET password=? WHERE id=?",
               (_h(new_plain), user_id))
    db.commit(); db.close()

def update_profile(user_id, nom):
    db = conn()
    db.execute("UPDATE utilisateurs SET nom=? WHERE id=?", (nom, user_id))
    db.commit(); db.close()

def get_user_clubs(user_id):
    """All clubs a user belongs to (member or president)."""
    db = conn()
    r = _rows(db.execute("""
        SELECT cl.*, cm.role AS role_club, cm.custom_role,
               'membre' AS membership_type
        FROM clubs cl
        JOIN club_membres cm ON cl.id=cm.club_id
        WHERE cm.membre_id=? AND cm.actif=1
        UNION
        SELECT cl.*, 'president' AS role_club, '' AS custom_role,
               'president' AS membership_type
        FROM clubs cl
        WHERE cl.president_id=?
        ORDER BY cl.nom
    """, (user_id, user_id)))
    db.close(); return r

def forgot_password_request(email):
    """Returns a reset code if email found, else None."""
    import random
    db = conn()
    r = db.execute("SELECT id,nom FROM utilisateurs WHERE email=? AND actif=1", (email,)).fetchone()
    db.close()
    if not r: return None, None
    code = str(random.randint(100000, 999999))
    return code, dict(r)

def reset_password_with_code(email, new_plain):
    db = conn()
    db.execute("UPDATE utilisateurs SET password=? WHERE email=?",
               (_h(new_plain), email))
    db.commit(); db.close()

# ─── Schema v3 migrations ─────────────────────────────────────────────────────

def run_v3_migrations():
    db = conn()
    for sql in [
        "ALTER TABLE utilisateurs ADD COLUMN avatar_b64 TEXT DEFAULT ''",
        "ALTER TABLE utilisateurs ADD COLUMN theme TEXT DEFAULT 'Light'",
        "ALTER TABLE utilisateurs ADD COLUMN annee_etude TEXT DEFAULT ''",
        "ALTER TABLE utilisateurs ADD COLUMN langue TEXT DEFAULT 'Français'",
        "ALTER TABLE utilisateurs ADD COLUMN username TEXT",
        "ALTER TABLE clubs ADD COLUMN applications_ouvertes INTEGER DEFAULT 1",
        "ALTER TABLE club_applications ADD COLUMN message_reponse TEXT DEFAULT ''",
        "ALTER TABLE club_applications ADD COLUMN message_resp TEXT DEFAULT ''",
    ]:
        try: db.execute(sql); db.commit()
        except: pass
    db.close()

def update_avatar(user_id, b64_str):
    db = conn()
    db.execute("UPDATE utilisateurs SET avatar_b64=? WHERE id=?", (b64_str, user_id))
    db.commit(); db.close()

def update_theme(user_id, theme):
    db = conn()
    db.execute("UPDATE utilisateurs SET theme=? WHERE id=?", (theme, user_id))
    db.commit(); db.close()

def set_applications_ouvertes(club_id, ouvert):
    db = conn()
    db.execute("UPDATE clubs SET applications_ouvertes=? WHERE id=?", (1 if ouvert else 0, club_id))
    db.commit(); db.close()

def get_applications_ouvertes(club_id):
    db = conn()
    r = db.execute("SELECT applications_ouvertes FROM clubs WHERE id=?", (club_id,)).fetchone()
    db.close()
    return bool(r["applications_ouvertes"]) if r else True

def postuler_club_v2(etudiant_id, club_id):
    """Returns False if already applied or closed."""
    if not get_applications_ouvertes(club_id):
        return False, "Les candidatures sont fermées pour ce club."
    db_c = conn()
    existing = db_c.execute("SELECT id,statut FROM club_applications WHERE etudiant_id=? AND club_id=?",
                             (etudiant_id, club_id)).fetchone()
    if existing:
        db_c.close(); return False, "Vous avez déjà postulé à ce club."
    db_c.execute("INSERT INTO club_applications(etudiant_id,club_id) VALUES(?,?)", (etudiant_id, club_id))
    db_c.commit(); db_c.close()
    return True, "Candidature envoyée!"

def accept_application_with_message(app_id, etudiant_id, club_id, message=""):
    """Accept + upgrade role + add to messaging."""
    db = conn()
    db.execute("UPDATE club_applications SET statut='Accepté',message_reponse=? WHERE id=?",
               (message, app_id))
    db.execute("INSERT OR IGNORE INTO club_membres(club_id,membre_id) VALUES(?,?)", (club_id, etudiant_id))
    db.execute("UPDATE utilisateurs SET role='membre' WHERE id=? AND role='etudiant'", (etudiant_id,))
    db.commit(); db.close()

def reject_application_with_message(app_id, message=""):
    db = conn()
    db.execute("UPDATE club_applications SET statut='Refusé',message_reponse=? WHERE id=?",
               (message, app_id))
    db.commit(); db.close()

def get_all_club_applications(president_id):
    """All applications (not just pending) for president's club."""
    db = conn()
    r = _rows(db.execute("""
        SELECT ca.*,u.nom AS etudiant_nom,u.email AS etudiant_email,cl.nom AS club_nom
        FROM club_applications ca
        JOIN utilisateurs u ON ca.etudiant_id=u.id
        JOIN clubs cl ON ca.club_id=cl.id
        WHERE cl.president_id=? ORDER BY ca.date_soumission DESC
    """, (president_id,)))
    db.close(); return r

def get_user_all_clubs(user_id):
    """All clubs a user can chat in."""
    db = conn()
    r = _rows(db.execute("""
        SELECT DISTINCT cl.id, cl.nom, cl.type, cm.role AS role_club
        FROM clubs cl
        JOIN club_membres cm ON cl.id=cm.club_id
        WHERE cm.membre_id=? AND cm.actif=1
        UNION
        SELECT DISTINCT id, nom, type, 'president' AS role_club
        FROM clubs WHERE president_id=?
    """, (user_id, user_id)))
    db.close(); return r

# ─── Club application: accept/reject with message + open/close ──────────────

def accept_application_with_message(app_id, etudiant_id, club_id, message=""):
    """Accept + send message to applicant in chat + upgrade role."""
    accept_club_application(app_id, etudiant_id, club_id)
    if message:
        try:
            db2 = conn()
            # store acceptance message as system notification
            db2.execute("UPDATE club_applications SET message_resp=? WHERE id=?", (message, app_id))
            db2.commit(); db2.close()
        except: pass

def reject_application_with_message(app_id, message=""):
    db2 = conn()
    try:
        db2.execute("ALTER TABLE club_applications ADD COLUMN message_resp TEXT DEFAULT ''")
        db2.commit()
    except: pass
    db2.execute("UPDATE club_applications SET statut='Refusé', message_resp=? WHERE id=?",
                (message, app_id))
    db2.commit(); db2.close()

def run_v2_migrations():
    """Add message_resp column and new club type."""
    db2 = conn()
    for sql in [
        "ALTER TABLE club_applications ADD COLUMN message_resp TEXT DEFAULT ''",
        "ALTER TABLE utilisateurs ADD COLUMN theme TEXT DEFAULT 'Light'",
    ]:
        try: db2.execute(sql); db2.commit()
        except: pass
    db2.close()

# ─── Reactions & Comments ─────────────────────────────────────────────────────

def ensure_social_tables():
    db = conn()
    db.executescript("""
    CREATE TABLE IF NOT EXISTS reactions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        annonce_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        type TEXT DEFAULT 'like',
        date_reaction TEXT DEFAULT(datetime('now','localtime')),
        UNIQUE(annonce_id, user_id),
        FOREIGN KEY(annonce_id) REFERENCES annonces(id),
        FOREIGN KEY(user_id) REFERENCES utilisateurs(id));

    CREATE TABLE IF NOT EXISTS comments(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        annonce_id INTEGER NOT NULL,
        auteur_id INTEGER NOT NULL,
        contenu TEXT NOT NULL,
        date_commentaire TEXT DEFAULT(datetime('now','localtime')),
        FOREIGN KEY(annonce_id) REFERENCES annonces(id),
        FOREIGN KEY(auteur_id) REFERENCES utilisateurs(id));
    """)
    db.commit(); db.close()

def get_reactions(annonce_id):
    db = conn()
    rows = _rows(db.execute(
        "SELECT type, COUNT(*) as n FROM reactions WHERE annonce_id=? GROUP BY type",
        (annonce_id,)))
    my = None  # no user context here
    db.close()
    return {r["type"]: r["n"] for r in rows}

def get_user_reaction(annonce_id, user_id):
    db = conn()
    r = db.execute("SELECT type FROM reactions WHERE annonce_id=? AND user_id=?",
                   (annonce_id, user_id)).fetchone()
    db.close(); return r["type"] if r else None

def toggle_reaction(annonce_id, user_id, rtype="like"):
    db = conn()
    existing = db.execute("SELECT type FROM reactions WHERE annonce_id=? AND user_id=?",
                          (annonce_id, user_id)).fetchone()
    if existing:
        if existing["type"] == rtype:
            db.execute("DELETE FROM reactions WHERE annonce_id=? AND user_id=?",
                       (annonce_id, user_id))
        else:
            db.execute("UPDATE reactions SET type=? WHERE annonce_id=? AND user_id=?",
                       (rtype, annonce_id, user_id))
    else:
        db.execute("INSERT INTO reactions(annonce_id,user_id,type) VALUES(?,?,?)",
                   (annonce_id, user_id, rtype))
    db.commit(); db.close()

def get_comments(annonce_id):
    db = conn()
    r = _rows(db.execute("""SELECT c.*,u.nom AS auteur_nom,u.avatar_color
        FROM comments c JOIN utilisateurs u ON c.auteur_id=u.id
        WHERE c.annonce_id=? ORDER BY c.date_commentaire""", (annonce_id,)))
    db.close(); return r

def add_comment(annonce_id, auteur_id, contenu):
    db = conn()
    db.execute("INSERT INTO comments(annonce_id,auteur_id,contenu) VALUES(?,?,?)",
               (annonce_id, auteur_id, contenu))
    db.commit(); db.close()

# ─── Profile extended ────────────────────────────────────────────────────────

def update_annee_etude(user_id, annee):
    db = conn()
    db.execute("UPDATE utilisateurs SET annee_etude=? WHERE id=?", (annee, user_id))
    db.commit(); db.close()

def update_language(user_id, lang):
    db = conn()
    try:
        db.execute("ALTER TABLE utilisateurs ADD COLUMN langue TEXT DEFAULT 'Français'")
        db.commit()
    except: pass
    db.execute("UPDATE utilisateurs SET langue=? WHERE id=?", (lang, user_id))
    db.commit(); db.close()

def get_user_language(user_id):
    db = conn()
    try:
        r = db.execute("SELECT langue FROM utilisateurs WHERE id=?", (user_id,)).fetchone()
        db.close(); return r["langue"] if r and r["langue"] else "Français"
    except: db.close(); return "Français"

# ─── Admin document requests to presidents ────────────────────────────────────

def ensure_admin_requests_table():
    db2 = conn()
    db2.execute("""CREATE TABLE IF NOT EXISTS admin_requests(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        titre TEXT NOT NULL,
        description TEXT DEFAULT '',
        type TEXT DEFAULT 'document',
        president_id INTEGER,
        club_id INTEGER,
        statut TEXT DEFAULT 'En Attente',
        fichier_b64 TEXT DEFAULT '',
        fichier_nom TEXT DEFAULT '',
        date_envoi TEXT DEFAULT(datetime('now','localtime')),
        date_reponse TEXT,
        FOREIGN KEY(president_id) REFERENCES utilisateurs(id),
        FOREIGN KEY(club_id) REFERENCES clubs(id))""")
    db2.commit(); db2.close()

def add_admin_request(titre, description, typ, president_id, club_id):
    db2 = conn()
    db2.execute("INSERT INTO admin_requests(titre,description,type,president_id,club_id) VALUES(?,?,?,?,?)",
                (titre, description, typ, president_id, club_id))
    db2.commit(); db2.close()

def get_admin_requests(president_id=None):
    db2 = conn()
    if president_id:
        r = _rows(db2.execute("""SELECT ar.*,u.nom AS president_nom,cl.nom AS club_nom
            FROM admin_requests ar
            LEFT JOIN utilisateurs u ON ar.president_id=u.id
            LEFT JOIN clubs cl ON ar.club_id=cl.id
            WHERE ar.president_id=? ORDER BY ar.date_envoi DESC""", (president_id,)))
    else:
        r = _rows(db2.execute("""SELECT ar.*,u.nom AS president_nom,cl.nom AS club_nom
            FROM admin_requests ar
            LEFT JOIN utilisateurs u ON ar.president_id=u.id
            LEFT JOIN clubs cl ON ar.club_id=cl.id
            ORDER BY ar.date_envoi DESC"""))
    db2.close(); return r

def respond_admin_request(req_id, fichier_b64, fichier_nom):
    db2 = conn()
    db2.execute("""UPDATE admin_requests SET statut='Déposé', fichier_b64=?,
        fichier_nom=?, date_reponse=datetime('now','localtime') WHERE id=?""",
                (fichier_b64, fichier_nom, req_id))
    db2.commit(); db2.close()

def delete_admin_request(req_id):
    db2 = conn()
    db2.execute("DELETE FROM admin_requests WHERE id=?", (req_id,))
    db2.commit(); db2.close()

def seed_admin_requests():
    """Add demo requests if none exist."""
    db2 = conn()
    n = db2.execute("SELECT COUNT(*) FROM admin_requests").fetchone()[0]
    if n == 0:
        clubs = _rows(db2.execute("SELECT id,president_id FROM clubs WHERE president_id IS NOT NULL LIMIT 3"))
        for cl in clubs:
            db2.execute("INSERT INTO admin_requests(titre,description,type,president_id,club_id) VALUES(?,?,?,?,?)",
                        (f"Bilan Annuel 2024-2025",
                         "Veuillez déposer le bilan annuel de votre club incluant les activités réalisées, le nombre de membres actifs et les événements organisés.",
                         "bilan", cl["president_id"], cl["id"]))
            db2.execute("INSERT INTO admin_requests(titre,description,type,president_id,club_id) VALUES(?,?,?,?,?)",
                        ("Liste des Membres Actifs",
                         "Merci de fournir la liste actualisée des membres actifs de votre club avec leurs informations de contact.",
                         "document", cl["president_id"], cl["id"]))
    db2.commit(); db2.close()
