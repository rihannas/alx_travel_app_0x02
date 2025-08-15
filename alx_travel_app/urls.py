from django.contrib import admin
from django.urls import path, re_path, include
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

# Schema view configuration for Swagger
schema_view = get_schema_view(
    openapi.Info(
        title="ALX Travel API",
        default_version='v1',
        description="API documentation for ALX Travel Application",
        terms_of_service="https://www.google.com/policies/terms/",
        contact=openapi.Contact(email="teamkweku@outlook.com"),
        license=openapi.License(name="MIT License"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)

urlpatterns = [
    path('admin/', admin.site.urls),
    
    path('swagger/', 
         schema_view.with_ui('swagger', cache_timeout=0), 
         name='schema-swagger-ui'),
    
    path('', include('listings.urls')),
]
