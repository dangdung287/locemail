import streamlit as st
import pandas as pd
import psycopg2
import hashlib
import io
import os
from typing import List, Optional
from supabase import create_client, Client

import streamlit as st
import base64
# CSS để đặt ảnh nền
def set_background(image_url):
    bg_css = f"""
    <style>
    .stApp {{
        background-image: url("{image_url}");
        background-size: 100% 100%;
        background-position: center;
        background-repeat: no-repeat;
    }}
    </style>
    """
    st.markdown(bg_css, unsafe_allow_html=True)

# Nếu ảnh là file cục bộ, lưu trên GitHub rồi dùng raw URL
image_url = "https://raw.githubusercontent.com/dangdung287/locemail/main/logo.jpeg"
set_background(image_url)

# Hardcoded credentials for local development (REMOVE IN PRODUCTION!)
SUPABASE_URL = "https://ltnmxrecdwvuhdtwegsm.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imx0bm14cmVjZHd2dWhkdHdlZ3NtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDI3ODgzODQsImV4cCI6MjA1ODM2NDM4NH0.VUwvYcdtE3O9Pjoyza1842flkDPNZhUokR7qwk-zjeY"
DATABASE_URL = "postgresql://postgres.ltnmxrecdwvuhdtwegsm:Aa36579819$@aws-0-ap-southeast-1.pooler.supabase.com:5432/postgres"

# Thêm salt cho mã hóa mật khẩu
PASSWORD_SALT = "GLOBAL_LOGISTICS_SALT_2025"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_db_connection():
    """Kết nối đến PostgreSQL."""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        st.error(f"Lỗi kết nối database: {e}")
        return None

def hash_password(password):
    """Mã hóa mật khẩu bằng SHA-256 với salt."""
    return hashlib.sha256((password + PASSWORD_SALT).encode()).hexdigest()

def get_users():
    """Lấy danh sách người dùng từ Supabase."""
    try:
        response = supabase.table("users").select("*").execute()
        return pd.DataFrame(response.data) if response.data else pd.DataFrame()
    except Exception as e:
        st.error(f"Lỗi truy xuất người dùng: {e}")
        return pd.DataFrame()

def add_user(username, password, is_admin=False):
    """Thêm người dùng mới vào Supabase."""
    # Kiểm tra độ dài mật khẩu
    if len(password) < 8:
        st.error("Mật khẩu phải ít nhất 8 ký tự!")
        return False
    
    role = "admin" if is_admin else "user"
    hashed_password = hash_password(password)
    
    try:
        supabase.table("users").insert({
            "username": username,
            "password": hashed_password,
            "role": role
        }).execute()
        return True
    except Exception as e:
        st.error(f"Lỗi thêm người dùng: {e}")
        return False

def create_admin_account():
    """Tạo tài khoản admin nếu chưa tồn tại."""
    users = get_users()
    if "admin" not in users["username"].values:
        if add_user("admin", "Admin@2025!", is_admin=True):
            st.success("✅ Admin đã được tạo! User: admin | Pass: Admin@2025!")

def authenticate(username, password):
    """Xác thực đăng nhập người dùng."""
    hashed_password = hash_password(password)
    try:
        response = supabase.table("users").select("*").eq("username", username).eq("password", hashed_password).execute()
        if response.data:
            return response.data[0]["role"] == "admin"
        return None
    except Exception as e:
        st.error(f"Lỗi xác thực: {e}")
        return None

def add_emails_to_database(emails):
    """Thêm email vào cơ sở dữ liệu."""
    conn = get_db_connection()
    if not conn:
        return
    
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS emails (
            email TEXT PRIMARY KEY,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Lọc email hợp lệ
    valid_emails = [email for email in emails if '@' in email]
    
    for email in valid_emails:
        cursor.execute("INSERT INTO emails (email) VALUES (%s) ON CONFLICT (email) DO NOTHING", (email,))
    
    conn.commit()
    conn.close()
    st.success(f"Thêm {len(valid_emails)} email thành công!")

def filter_emails(uploaded_file):
    """Lọc email trùng lặp."""
    if uploaded_file is not None:
        try:
            df = pd.read_excel(uploaded_file)
            if "email" not in df.columns:
                st.error("File phải có cột 'email'.")
                return
            
            emails_to_check = set(df["email"].dropna().tolist())
            
            conn = get_db_connection()
            if not conn:
                return
            
            cursor = conn.cursor()
            cursor.execute("SELECT email FROM emails")
            existing_emails = {row[0] for row in cursor.fetchall()}
            conn.close()
            
            unique_emails = emails_to_check - existing_emails
            
            output = io.BytesIO()
            pd.DataFrame({"email": list(unique_emails)}).to_excel(output, index=False, engine="openpyxl")
            output.seek(0)
            
            st.download_button(
                label="Tải danh sách email hợp lệ", 
                data=output, 
                file_name="filtered_emails.xlsx", 
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        except Exception as e:
            st.error(f"Lỗi xử lý file: {e}")

def login_page():
    """Giao diện đăng nhập."""
    st.title("🔑 Đăng nhập")
    # Thêm key duy nhất cho các input
    username = st.text_input("Tên đăng nhập", key="login_username")
    password = st.text_input("Mật khẩu", type="password", key="login_password")
    
    if st.button("Đăng nhập", key="login_button"):
        is_admin = authenticate(username, password)
        if is_admin is not None:
            st.session_state["logged_in"] = True
            st.session_state["username"] = username
            st.session_state["is_admin"] = is_admin
            st.rerun()
        else:
            st.error("Sai tên đăng nhập hoặc mật khẩu!")

def register_page():
    """Giao diện đăng ký tài khoản."""
    st.title("📝 Đăng ký tài khoản")
    # Thêm key duy nhất cho các input
    username = st.text_input("Tên đăng nhập", key="register_username")
    password = st.text_input("Mật khẩu", type="password", key="register_password")
    confirm_password = st.text_input("Xác nhận mật khẩu", type="password", key="register_confirm_password")
    
    if st.button("Đăng ký", key="register_button"):
        users = get_users()
        
        if username in users["username"].values:
            st.error("Tên đăng nhập đã tồn tại!")
        elif password != confirm_password:
            st.error("Mật khẩu không khớp!")
        elif len(password) < 8:
            st.error("Mật khẩu phải ít nhất 8 ký tự!")
        else:
            if add_user(username, password):
                st.success("Đăng ký thành công! Hãy đăng nhập.")
                st.rerun()

def main_page():
    """Giao diện chính sau khi đăng nhập."""
    st.title("📧 GLOBAL LOGISTICS & TRADING CO., LTD")
    
    email = st.text_input("Nhập địa chỉ email:", key="main_email")
    if st.button("Thêm Email", key="add_email_button"):
        if email:
            add_emails_to_database([email])
        else:
            st.warning("Vui lòng nhập email!")
    
    uploaded_file = st.file_uploader("Tải file Excel", type=["xlsx"], key="excel_uploader")
    if uploaded_file:
        filter_emails(uploaded_file)
    
    if st.session_state.get("is_admin", False):
        st.subheader("Danh sách Người dùng")
        df = get_users()
        st.dataframe(df[['username', 'role']])
    
    # Nút đăng xuất
    if st.button("Đăng xuất", key="logout_button"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

def main():
    """Điểm đầu vào chính của ứng dụng."""
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False
    
    if not st.session_state["logged_in"]:
        tab1, tab2 = st.tabs(["🔑 Đăng nhập", "📝 Đăng ký"])
        with tab1:
            login_page()
        with tab2:
            register_page()
    else:
        main_page()

if __name__ == "__main__":
    # Tạo tài khoản admin lần đầu
    create_admin_account()
    main()
