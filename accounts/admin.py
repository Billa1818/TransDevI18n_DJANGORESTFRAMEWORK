from django.contrib import admin
from .models import User ,OAuthProvider,UserOAuth

# Register your models here.

admin.site.register(User)
admin.site.register(OAuthProvider)
admin.site.register(UserOAuth)