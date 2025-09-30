from rest_framework import serializers

class AjusteSerializer(serializers.Serializer):
    idproduto = serializers.IntegerField()
    delta = serializers.DecimalField(max_digits=18, decimal_places=4)
    motivo = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    empresa = serializers.CharField(required=False, allow_blank=True)  # opcional

class ProdutoQuerySerializer(serializers.Serializer):
    query = serializers.CharField(required=False, allow_blank=True)
    empresa = serializers.CharField(required=False, allow_blank=True)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=200)
