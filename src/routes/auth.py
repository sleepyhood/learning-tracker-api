from flask import Blueprint, request, render_template, redirect, session as fsession
from login import clear_active_session, do_login

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        success, session_or_msg = do_login(username, password)

        if success:
            return redirect("/")
        else:
            print("로그인 실패!:", session_or_msg)
            return render_template("login.html", error="로그인에 실패했습니다.")

    return render_template("login.html")


@auth_bp.route("/logout", methods=["GET", "POST"])
def logout():
    try:
        fsession.clear()
    except Exception:
        pass

    try:
        removed = clear_active_session()
        print(f"[logout] removed cookies: {removed}")
    except Exception as e:
        print("[logout] cookie removal failed:", e)

    return redirect("/login")
