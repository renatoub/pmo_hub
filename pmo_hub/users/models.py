from django.contrib.auth.models import User
from django.db import models


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    image = models.ImageField(default="default.png", upload_to="profile_pics")

    def get_avatar_url(self):
        if self.image and hasattr(self.image, "url"):
            return self.image.url
        return "/static/vendor/adminlte/img/user2-160x160.jpg"  # Fallback

    def get_user_avatar(self):
        try:
            if self.profile.image and hasattr(self.profile.image, "url"):
                return self.profile.image.url
        except Exception:
            pass
        return "/static/vendor/adminlte/img/user2-160x160.jpg"

    def __str__(self):
        return f"Perfil de {self.user.username}"

    User.add_to_class("get_user_avatar", get_user_avatar)
