"""Versão do ManuMetria e identificação do método de cálculo.

Cada avaliação guarda "versao_app" e "goniometria" nos resultados (formato 3,
avaliacao/resultados.py): assim um número salvo ou exportado sempre diz com que
cálculo foi obtido. Avaliações nos formatos 1 e 2 não têm esse registro (a mudança de método da
goniometria está no CHANGELOG.md; o método atual, em docs/METODOLOGIA.md).
"""

VERSAO = "1.5.0"

# Ângulos por decomposição por osso, recomendação ISB (Wu et al., 2005)
GONIOMETRIA = "isb_decomposicao_por_osso"
GONIOMETRIA_TEXTO = "Decomposição por osso, recomendação ISB (Wu et al., J Biomech 2005)"
