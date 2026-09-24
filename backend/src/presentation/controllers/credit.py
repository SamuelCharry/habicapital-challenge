from rest_framework.response import Response

from src.infrastructure.container import build_wallet
from src.presentation.controllers.accounts import WalletView
from src.presentation.serializers import CreditProfileSerializer, CreditPathSerializer


class CreditPathView(WalletView):
    def get(self, request, account_id):
        return Response(CreditPathSerializer(build_wallet().credit_path(account_id)).data)


class CreditProfileView(WalletView):
    """Solo el perfil, sin el mapa.

    El inicio muestra tres cifras; pedirle la ruta completa le costaría miles
    de puntos de población que no va a dibujar.
    """

    def get(self, request, account_id):
        profile = build_wallet().credit_profile(account_id)
        return Response({
            **CreditProfileSerializer(profile).data,
            'has_enough_evidence': profile.has_enough_evidence,
        })
