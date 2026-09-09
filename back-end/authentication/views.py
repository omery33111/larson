from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import Q



# ------------------------- HOME PAGE START ------------------------- #
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def index(request):
    return Response({"username": request.user.username})
# ------------------------- HOME PAGE END ------------------------- #



# ------------------------- AUTHENTICATION START ------------------------- #

# ------------- REGISTRATION:
@api_view(["POST"])
def register(request):
    username = request.data["username"]
    password = request.data["password"]
    email = request.data["email"]

    if not (username and password and email):
        return Response({"error": "אנא מלא את כל השדות"}, status=status.HTTP_400_BAD_REQUEST)

    if User.objects.filter(Q(username=username) | Q(email=email)).exists():
        return Response({"error": "שם המשתמש או כתובת האימייל כבר בשימוש."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = User.objects.create_user(username=username, password=password, email=email, is_active=True)
    except ValidationError as e:
        return Response({"error": e.message}, status=status.HTTP_400_BAD_REQUEST)

    user.is_staff = False
    user.save()

    return Response({"success": "נרשמת בהצלחה! אפשר להתחבר."}, status=status.HTTP_201_CREATED)



# ------------- LOGIN:
class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["username"] = user.username
        token['is_staff'] = user.is_staff
        return token


class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer



# ------------- LOGOUT:
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout(request):
    refresh_token = request.data.get("refresh_token")

    if not refresh_token:
        return Response({"error": "Refresh token is required."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        token = RefreshToken(refresh_token)
        token.blacklist()
        return Response({"success": "User has been logged out."})
    except Exception as e:
        return Response({"error": "Invalid refresh token."}, status=status.HTTP_400_BAD_REQUEST)

# ------------------------- AUTHENTICATION END ------------------------- #
