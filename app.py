from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash
import pickle
import pandas as pd
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash
import io
import random
import string
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
import numpy as np
import joblib

from tensorflow.keras.models import load_model

# --- REPORTLAB FOR PDF ---
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, 'skripsi_vina.db')
app.secret_key = 'rahasia_sidang_vina_2026'

# --- KONFIGURASI FLASK-MAIL ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USERNAME'] = 'ariskavina070@gmail.com'  
app.config['MAIL_PASSWORD'] = 'ppxw lwgq iutu zgen' 
app.config['MAIL_DEFAULT_SENDER'] = ('EduPredict ANN Admin', 'ariskavina070@gmail.com')

mail = Mail(app)
serializer = URLSafeTimedSerializer(app.secret_key)

# Load Model ANN (.h5) & Scaler
MODEL_PATH = os.path.join(BASE_DIR, "model_edupredict_11indikator.h5")
SCALER_PATH = os.path.join(BASE_DIR, "scaler_edupredict.pkl")

model = load_model(MODEL_PATH)
scaler = joblib.load(SCALER_PATH)

def get_db_connection():
    conn = sqlite3.connect(DB_FILE, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS admin (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            email TEXT UNIQUE,
            password_hash TEXT
        )
    ''')
    
    conn.execute('''
        CREATE TABLE IF NOT EXISTS data_prediksi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nim TEXT,
            nama TEXT,
            angkatan INTEGER,
            ipk REAL,
            sks_lulus INTEGER,
            sks_diambil INTEGER,
            mk_mengulang INTEGER,
            ekonomi INTEGER,
            lingkungan INTEGER,
            dukungan_keluarga INTEGER,
            paruh_waktu INTEGER,
            salah_jurusan INTEGER,
            nama_ortu TEXT,
            kontak_ortu TEXT,
            hasil_prediksi TEXT,
            saran_pakar TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def generate_saran_pakar(ipk, ekonomi, lingkungan, hasil):
    hasil_upper = hasil.upper()
    if "TINGGI" in hasil_upper:
        saran = "Prioritas Utama Intervensi! Mahasiswa wajib mengikuti bimbingan akademik intensif. "
        if ekonomi == 1:
            saran += "Ajukan bantuan beasiswa internal karena kendala finansial keluarga. "
        if lingkungan == 1:
            saran += "Berikan konseling mengenai adaptasi lingkungan sosial kampus. "
        saran += "Segera hubungi Orang Tua/Wali untuk koordinasi preventif demi penyelamatan masa studi mahasiswa."
    elif "SEDANG" in hasil_upper:
        saran = "Perlu Pengawasan Berkala. Disarankan pembatasan aktivitas non-akademik di luar ruang kelas dan monitoring indeks prestasi bulanan oleh dosen wali."
    else:
        saran = "Kondisi Aman dan Normal. Pertahankan ritme belajar yang baik. Mahasiswa direkomendasikan untuk aktif dalam program penunjang seperti MBKM atau riset internal."
    return saran

@app.route('/')
def index():
    return render_template('index.html', active_page='home')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password_hash')
        if not password:
            password = request.form.get('password')
            
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM admin WHERE email = ?', (email,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user['password_hash'], password):
            session['logged_in'] = True
            session['email'] = email
            session['username'] = user['username']
            return redirect(url_for('dashboard'))
        else:
            flash('Email atau Password Salah!', 'danger')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password_hash')
        if not password:
            password = request.form.get('password')
        hash_pwd = generate_password_hash(password)
        try:
            conn = get_db_connection()
            conn.execute('INSERT INTO admin (username, email, password_hash) VALUES (?, ?, ?)', (username, email, hash_pwd))
            conn.commit()
            conn.close()
            flash('Registrasi Berhasil! Silakan Login.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Email sudah terdaftar!', 'danger')
            return redirect(url_for('register'))
    return render_template('register.html')

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():

    if request.method == 'POST':

        email = request.form.get("email")

        conn = get_db_connection()

        user = conn.execute(
            "SELECT * FROM admin WHERE email=?",
            (email,)
        ).fetchone()

        conn.close()

        if not user:
            flash("Email tidak terdaftar!", "danger")
            return render_template("forgot_password.html")

        token = serializer.dumps(email, salt="reset-password")

        reset_link = url_for(
            "reset_password",
            token=token,
            _external=True
        )

        msg = Message(
            subject="Reset Password EduPredict ANN",
            recipients=[email]
        )

        msg.body = f"""
            Halo Admin,

            Klik link berikut untuk mengubah password Anda.

            {reset_link}

            Link berlaku selama 30 menit.

            Terima kasih.
            """

        mail.send(msg)

        flash("Link reset password berhasil dikirim ke email.", "success")

    return render_template("forgot_password.html")

@app.route('/reset_password/<token>', methods=['GET','POST'])
def reset_password(token):

    try:

        email = serializer.loads(
            token,
            salt="reset-password",
            max_age=1800
        )

    except:

        flash("Link reset password sudah kadaluarsa.", "danger")
        return redirect(url_for("login"))

    if request.method == "POST":

        password = request.form.get("password")
        konfirmasi = request.form.get("konfirmasi_password")

        if password != konfirmasi:
            flash("Konfirmasi password tidak sama!", "danger")
            return render_template("reset_password.html")

        hash_password = generate_password_hash(password)

        conn = get_db_connection()

        conn.execute(
            """
            UPDATE admin
            SET password_hash=?
            WHERE email=?
            """,
            (hash_password,email)
        )

        conn.commit()
        conn.close()

        flash("Password berhasil diperbarui.", "success")

        return redirect(url_for("login"))

    return render_template("reset_password.html")

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    conn = get_db_connection()
    riwayat = conn.execute('SELECT * FROM data_prediksi ORDER BY id DESC').fetchall()
    conn.close()
    return render_template('dashboard.html', riwayat=riwayat)

    # --- HALAMAN INFORMASI ---
@app.route('/tentang')
def tentang():
    return render_template('tentang.html')

@app.route('/hubungi')
def hubungi():
    return render_template('hubungi.html')

@app.route('/solusi')
def solusi():
    return render_template('solusi.html')

# --- MODUL MANIPULASI DATA (EDIT & HAPUS) ---
@app.route('/delete/<int:id>', methods=['POST'])
def delete_mahasiswa(id):
    try:
        conn = get_db_connection()
        conn.execute("DELETE FROM data_prediksi WHERE id = ?", (id,))
        conn.commit()
        conn.close()
        flash("Data log mahasiswa berhasil dihapus!", "success")
    except Exception as e:
        flash(f"Gagal menghapus data: {str(e)}", "danger")
    return redirect(url_for('dashboard'))


from reportlab.pdfbase import pdfmetrics
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas

@app.route("/cetak_surat/<int:id>")
def cetak_surat(id):

    conn = get_db_connection()

    data = conn.execute(
        "SELECT * FROM data_prediksi WHERE id=?",
        (id,)
    ).fetchone()

    conn.close()

    if data is None:
        flash("Data tidak ditemukan")
        return redirect(url_for("dashboard"))

    buffer = io.BytesIO()

    pdf = canvas.Canvas(buffer)

    pdf.setTitle("Surat Panggilan Orang Tua")

    # =====================
    # KOP SURAT
    # =====================

    pdf.setFont("Helvetica-Bold",16)
    pdf.drawCentredString(300,800,"UNIVERSITAS ISLAM NEGERI")
    pdf.drawCentredString(300,780,"SJECH M. DJAMIL DJAMBEK BUKITTINGGI")

    pdf.setFont("Helvetica",12)
    pdf.drawCentredString(300,760,"PROGRAM STUDI PENDIDIKAN TEKNIK INFORMATIKA DAN KOMPUTER")

    pdf.line(50,745,550,745)

    pdf.setFont("Helvetica-Bold",14)
    pdf.drawCentredString(300,720,"SURAT PANGGILAN ORANG TUA MAHASASISWA")

    pdf.setFont("Helvetica",11)

    y = 680

    pdf.drawString(60,y,"Nomor : 001/PA/PTIK/2026")

    y-=40

    pdf.drawString(60,y,f"Kepada Yth.")
    y-=20
    pdf.drawString(60,y,f"Bapak/Ibu : {data['nama_ortu']}")

    y-=40

    pdf.drawString(60,y,"Dengan hormat,")

    y-=30

    pdf.drawString(60,y,"Mahasiswa berikut terdeteksi memiliki risiko akademik:")

    y-=35

    pdf.drawString(80,y,f"Nama")
    pdf.drawString(170,y,":")
    pdf.drawString(190,y,data["nama"])

    y-=20

    pdf.drawString(80,y,"NIM")
    pdf.drawString(170,y,":")
    pdf.drawString(190,y,data["nim"])

    y-=20

    pdf.drawString(80,y,"Angkatan")
    pdf.drawString(170,y,":")
    pdf.drawString(190,y,str(data["angkatan"]))

    y-=20

    pdf.drawString(80,y,"IPK")
    pdf.drawString(170,y,":")
    pdf.drawString(190,y,str(data["ipk"]))

    y-=20

    pdf.drawString(80,y,"Kategori Risiko")
    pdf.drawString(170,y,":")
    pdf.drawString(190,y,data["hasil_prediksi"])

    y-=40

    pdf.drawString(60,y,"Berdasarkan hasil analisis Artificial Neural Network")

    y-=20

    pdf.drawString(60,y,"kami mengharapkan kehadiran Bapak/Ibu untuk melakukan")

    y-=20

    pdf.drawString(60,y,"diskusi mengenai perkembangan akademik mahasiswa.")

    y-=40

    pdf.drawString(60,y,"Hari/Tanggal : ........................................")

    y-=20

    pdf.drawString(60,y,"Jam                : ........................................")

    y-=20

    pdf.drawString(60,y,"Tempat          : Ruang Pembimbing Akademik")

    y-=60

    pdf.drawString(360,y,"Bukittinggi, ....................")

    y-=20

    pdf.drawString(360,y,"Pembimbing Akademik")

    y-=80

    pdf.line(360,y,500,y)

    y-=15

    pdf.drawString(360,y,"NIP. .........................")

    pdf.save()

    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=False,
        download_name="Surat_Panggilan.pdf",
        mimetype="application/pdf"
    )
@app.route("/admin")
def admin():

    conn = get_db_connection()

    admins = conn.execute("""
        SELECT id,
               username,
               email
        FROM admin
        ORDER BY id DESC
    """).fetchall()

    total_admin = conn.execute(
        "SELECT COUNT(*) FROM admin"
    ).fetchone()[0]

    conn.close()

    return render_template(
        "admin.html",
        admins=admins,
        total_admin=total_admin
        
    )

@app.route("/predict", methods=["POST"])
def predict():
    if 'logged_in' not in session:
        flash("Silakan login terlebih dahulu.", "danger")
        return redirect(url_for("login"))
        
    # Ambil data dari form HTML
    nim = request.form.get("nim")
    nama = request.form.get("nama")
    angkatan = request.form.get("angkatan")
    ipk = request.form.get("ipk")
    sks_diambil = request.form.get("sks_diambil")
    sks_lulus = request.form.get("sks_lulus")
    mk_mengulang = request.form.get("mengulang") # Menangkap name="mengulang" dari HTML
    ekonomi = request.form.get("ekonomi")
    lingkungan = request.form.get("lingkungan")
    dukungan_keluarga = request.form.get("dukungan_keluarga")
    paruh_waktu = request.form.get("paruh_waktu")
    salah_jurusan = request.form.get("salah_jurusan")
    nama_ortu = request.form.get("nama_ortu")
    kontak_ortu = request.form.get("kontak_ortu")
    
    # Validasi input kosong wajib
    if not nim or not nama or not ipk or not angkatan or not sks_diambil or not sks_lulus:
        flash("NIM, Nama, Angkatan, IPK, SKS Diambil, dan SKS Lulus wajib diisi!", "danger")
        return redirect(url_for("dashboard"))

    try:
        # Konversi tipe data
        int_angkatan = int(angkatan)
        float_ipk = float(ipk)
        int_sks_diambil = int(sks_diambil)
        int_sks_lulus = int(sks_lulus)
        int_mk_mengulang = int(mk_mengulang) if mk_mengulang else 0
        int_ekonomi = int(ekonomi)
        int_lingkungan = int(lingkungan)
        int_dukungan = int(dukungan_keluarga)
        int_paruh = int(paruh_waktu)
        int_salah_jurusan = int(salah_jurusan)
        
        # HITUNG OTOMATIS PERSENTASE LULUS (Mencegah pembagian dengan nol)
        if int_sks_diambil > 0:
            persentase_lulus = (int_sks_lulus / int_sks_diambil) * 100
        else:
            persentase_lulus = 0.0

        # SUSUN ELEMEN SESUAI URUTAN FITUR JUPYTER NOTEBOOK (PAS 11 INDIKATOR)
        fitur_input = [
            int_angkatan,          # 1. Angkatan
            float_ipk,             # 2. IPK
            int_sks_diambil,       # 3. SKS_Diambil
            int_sks_lulus,         # 4. SKS_Lulus
            persentase_lulus,      # 5. Persentase_Lulus (Hasil Hitung Otomatis)
            int_mk_mengulang,      # 6. MK_Mengulang
            int_ekonomi,           # 7. Ekonomi
            int_lingkungan,        # 8. Lingkungan
            int_dukungan,          # 9. Dukungan_Keluarga
            int_paruh,             # 10. Paruh_Waktu
            int_salah_jurusan      # 11. Salah_Jurusan
        ]
        
        # Transformasikan data dengan Scaler bawaan skripsi
        input_data = np.array([fitur_input]) 
        input_data_scaled = scaler.transform(input_data)
        
        # Proses Prediksi dengan Model ANN (.h5)
        prediction = model.predict(input_data_scaled)
        
        # Ambil indeks dengan nilai probabilitas tertinggi (0, 1, atau 2)
        indeks_tertinggi = np.argmax(prediction[0])
        
        # Penentuan label klasifikasi ANN
        if indeks_tertinggi == 0:
            hasil = "RENDAH"
        elif indeks_tertinggi == 1:
            hasil = "SEDANG"
        else:
            hasil = "TINGGI"
            
        # Generate saran otomatis dari pakar
        saran = generate_saran_pakar(float_ipk, int_ekonomi, int_lingkungan, hasil)

        # Simpan riwayat pengujian log ke dalam tabel data_prediksi (Hanya 1 kali eksekusi)
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO data_prediksi (
                nim, nama, angkatan, ipk, sks_lulus, sks_diambil, mk_mengulang, 
                ekonomi, lingkungan, dukungan_keluarga, paruh_waktu, salah_jurusan, 
                nama_ortu, kontak_ortu, hasil_prediksi, saran_pakar
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                nim, nama, int_angkatan, float_ipk, int_sks_lulus, int_sks_diambil, int_mk_mengulang,
                int_ekonomi, int_lingkungan, int_dukungan, int_paruh, int_salah_jurusan,
                nama_ortu if nama_ortu else "-", kontak_ortu if kontak_ortu else "-", hasil, saran
            )
        )
        conn.commit()
        
        # AMBIL ID BARUSAN DI-INSERT UNTUK DITAMPILKAN DI HALAMAN RESULT
        new_id = cursor.lastrowid
        data_mhs = conn.execute("SELECT * FROM data_prediksi WHERE id = ?", (new_id,)).fetchone()
        conn.close()

        # OPER DATA KE HALAMAN RESULT.HTML
        return render_template("result.html", hasil=hasil, data_mhs=data_mhs)

    except Exception as e:
        flash(f"Terjadi kesalahan saat memproses analisis AI: {str(e)}", "danger")
        return redirect(url_for("dashboard"))
    
@app.route('/download_pdf')
def download_pdf():
    print_type = request.args.get('type', 'all')
    val = request.args.get('val', '').strip()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if print_type == 'angkatan':
        cursor.execute("SELECT * FROM data_prediksi WHERE angkatan = ?", (val,))
        title_pdf = f"Laporan Mahasiswa Berisiko - Angkatan {val}"
    elif print_type == 'hasil':
        cursor.execute("SELECT * FROM data_prediksi WHERE hasil_prediksi = ?", (val.upper(),))
        title_pdf = f"Laporan Analisis - Kategori Risiko {val}"
    elif print_type == 'nim':
        cursor.execute("SELECT * FROM data_prediksi WHERE nim = ?", (val,))
        title_pdf = f"Rapor Evaluasi Academic - NIM {val}"
    else:
        cursor.execute("SELECT * FROM data_prediksi ORDER BY id DESC")
        title_pdf = "Laporan Keseluruhan Evaluasi Mahasiswa EduPredict ANN"
        
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        flash(f"Data tidak ditemukan!", "danger")
        return redirect(url_for('dashboard'))

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    styles = getSampleStyleSheet()
    
    style_normal = ParagraphStyle('TableText', parent=styles['Normal'], fontSize=8, leading=10)
    style_header = ParagraphStyle('TableHeader', parent=styles['Normal'], fontSize=9, fontName='Helvetica-Bold', textColor=colors.white, alignment=1)
    
    title_style = ParagraphStyle('TitleStyle', fontName='Helvetica-Bold', fontSize=14, leading=16, alignment=1, textColor=colors.HexColor('#065f46'))
    story.append(Paragraph("EDUPREDICT ANN - SISTEM EVALUASI AKADEMIK AI", title_style))
    
    subtitle_style = ParagraphStyle('SubTitleStyle', fontName='Helvetica', fontSize=10, leading=12, alignment=1, textColor=colors.HexColor('#475569'))
    story.append(Paragraph(title_pdf, subtitle_style))
    story.append(Spacer(1, 15))
    
    data = [[
        Paragraph("NIM", style_header), Paragraph("Nama Mahasiswa", style_header),
        Paragraph("Angkatan", style_header), Paragraph("IPK", style_header),
        Paragraph("Hasil AI", style_header), Paragraph("Nama Orang Tua", style_header),
        Paragraph("Kontak Wali", style_header)
    ]]
    
    for row in rows:
        nama_ortu = row['nama_ortu'] if row['nama_ortu'] else '-'
        kontak_ortu = row['kontak_ortu'] if row['kontak_ortu'] else '-'
        ipk_val = f"{row['ipk']:.2f}" if row['ipk'] is not None else '0.00'
        data.append([
            Paragraph(str(row['nim']), style_normal), Paragraph(str(row['nama']), style_normal),
            Paragraph(str(row['angkatan']), style_normal), Paragraph(ipk_val, style_normal),
            Paragraph(str(row['hasil_prediksi']), style_normal), Paragraph(str(nama_ortu), style_normal),
            Paragraph(str(kontak_ortu), style_normal)
        ])
    
    col_widths = [55, 125, 45, 30, 60, 115, 80]
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#065f46')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('TOPPADDING', (0,0), (-1,0), 8),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#f8fafc')]),
        ('TOPPADDING', (0,1), (-1,-1), 6),
        ('BOTTOMPADDING', (0,1), (-1,-1), 6),
    ]))
    
    story.append(t)
    doc.build(story)
    buffer.seek(0)
    return send_file(buffer, mimetype='application/pdf', as_attachment=False, download_name=f"Laporan_{print_type}.pdf")
@app.route("/edit_admin/<int:id>", methods=["GET","POST"])
def edit_admin(id):

    conn = get_db_connection()

    if request.method == "POST":

        username = request.form["username"]
        email = request.form["email"]

        conn.execute("""
            UPDATE admin
            SET username=?,
                email=?
            WHERE id=?
        """,(username,email,id))

        conn.commit()
        conn.close()

        flash("Admin berhasil diperbarui","success")
        return redirect(url_for("admin"))

    admin = conn.execute(
        "SELECT * FROM admin WHERE id=?",
        (id,)
    ).fetchone()

    conn.close()

    return render_template(
        "edit_admin.html",
        admin=admin
    )

if __name__ == '__main__':
    app.run(debug=True)