from flask import Flask, render_template, request, redirect, url_for, flash, session
from koske_galary.config import Config
from koske_galary.database import db
from koske_galary.models import User, Gallery, Image
from flask_login import LoginManager, login_required, login_user
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

config = Config()
app = Flask(__name__)
for key in config.config:
    app.config[key] = config.config[key]
    print(f"Set config {key} to value: {app.config[key]}")

login_manager = LoginManager()
login_manager.login_view = 'login' #pyright: ignore
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
        return db.session.scalar(db.select(User).where(User.id == user_id))

db.init_app(app)
with app.app_context():
    db.create_all()

def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        user = db.session.scalar(db.Select(User))

        if "koske" not in user.username.lower():
            return "Access denied", 403

        return view(*args, **kwargs)

    return wrapped_view

@app.route("/gallery")
def gallary():
    galleries = db.session.scalars(db.select(Gallery).where(Gallery.private==False)).all()
    return render_template('gallery.html', galleries=galleries)

@app.route("/all")
@login_required
def all_galleries():
    galleries = db.session.scalars(db.select(Gallery)).all()
    return render_template('gallery.html', galleries=galleries)

@app.route("/gallery/<int:id>")
def render_gallery(id):
    gallery = db.session.scalars(db.select(Gallery).where(Gallery.id == id)).first()
    images = db.session.scalars(db.select(Image).where(Image.galleryId == id)).all()
    if gallery and images:
        return render_template("gallery_render.html", gallery=gallery, images=images)
    else:
        return "Invalid gallery ID"

@app.route("/build", methods=["GET", "POST"])
@login_required
def build():
    if request.method == "POST":
        name = request.form.get("name")
        description = request.form.get("description")
        longDescription = request.form.get("longDescription")
        is_private = bool(request.form.get("private"))

        if name:
            new_gallery = Gallery(
                name=name, #pyright: ignore
                description=description, #pyright: ignore
                longDescription=longDescription, #pyright: ignore
                private=is_private #pyright: ignore
            )
            db.session.add(new_gallery)
            db.session.commit()
            return redirect(url_for("build"))  

    galleries = db.session.scalars(db.select(Gallery)).all()
    return render_template("galleryBuilder.html", galleries=galleries)

@app.route("/edit/<int:id>", methods=["GET", "POST"])
@login_required
def editGallery(id):
    gallery = db.get_or_404(Gallery, id)
    images = db.session.scalars(db.select(Image).where(Image.galleryId == id)).all()

    if request.method == "POST":
        if "upload_photo" in request.form:
            photoName = request.form.get("name")
            photoDescription = request.form.get("description")
            file = request.files.get("file")

            if file and photoName:
                file.save(f"{app.static_folder}/{file.filename}")

                newImage = Image(
                    name=photoName, #pyright: ignore
                    description=photoDescription, #pyright: ignore
                    filename=file.filename, #pyright: ignore
                    galleryId=gallery.id #pyright: ignore
                )
                db.session.add(newImage)
                
                if not gallery.thumbnailFilename:
                    gallery.thumbnailFilename = file.filename

                db.session.commit()
                return redirect(url_for("editGallery", id=id))

        if "save_changes" in request.form:
            selectedThumbnail = request.form.get("thumbnail")
            if selectedThumbnail:
                thumbImage = db.get_or_404(Image, int(selectedThumbnail))
                gallery.thumbnailFilename = thumbImage.filename

            for img in images:
                if f"delete_{img.id}" in request.form:
                    db.session.delete(img)
                    continue

                updatedName = request.form.get(f"name_{img.id}")
                updatedDesc = request.form.get(f"description_{img.id}")
                if updatedName:
                    img.name = updatedName
                if updatedDesc is not None:
                    img.description = updatedDesc

            db.session.commit()
            return redirect(url_for("editGallery", id=id))

    return render_template('galleryEditor.html', gallery=gallery, images=images)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get('username')
        password = request.form.get('password')

        if username and password:
            # Fetch user safely
            user = db.session.scalar(db.select(User).where(User.username == username))
            
            # Check if user exists BEFORE checking password hash
            if user and check_password_hash(user.password, password):
                login_user(user, remember=True)
                flash("Logged in successfully!", "success")
                
                # Redirect to the page they tried to visit, or fallback to 'build'
                next_page = request.args.get('next')
                return redirect(next_page or url_for('build'))
            else:
                flash("Invalid username or password.", "error")

    return render_template('login.html')

@app.route("/manage", methods=["GET", "POST"])
@login_required
def manage():
    if request.method == "POST":
        username = request.form.get('username')
        password = request.form.get('password')

        if username and password:
            user = db.session.scalar(db.select(User).where(User.username == username))
            hashed_pw = generate_password_hash(password)

            if user:
                user.password = hashed_pw  # Direct object update is cleaner
            else:
                newUser = User(username=username, password=hashed_pw) #pyright: ignore
                db.session.add(newUser)

            db.session.commit()
            flash("User saved successfully!", "success")

    return render_template('manage.html')
    
if __name__ == "__main__":
    app.run(config.config["HOST"], config.config["PORT"], debug=config.config["DEBUG"])