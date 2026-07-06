from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from marketplace import views as marketplace_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('healthz/', marketplace_views.healthz, name='healthz'),
    path('', include('marketplace.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
