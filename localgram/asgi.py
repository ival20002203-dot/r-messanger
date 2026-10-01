import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE","localgram.settings")
from django.core.asgi import get_asgi_application
django_asgi_app = get_asgi_application()
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from apps.chat.routing import websocket_urlpatterns
from localgram.token_auth import TokenAuthMiddleware
application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(TokenAuthMiddleware(URLRouter(websocket_urlpatterns))),
})
