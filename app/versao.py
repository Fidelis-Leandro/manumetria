"""Versão do ManuMetria e identificação do método de cálculo.

Cada avaliação salva a partir da 1.3.0 guarda "versao_app" e "goniometria" nos
resultados (app/dados/resultados.py): assim um número salvo ou exportado sempre diz
com que cálculo foi obtido. As avaliações salvas antes não têm esse registro
(a 1.2.0 mudou a goniometria; veja o README, "Mudança de método na versão 1.2.0").
"""

VERSAO = "1.3.0"

# Ângulos por decomposição por osso, recomendação ISB (Wu et al., 2005), desde a 1.2.0
GONIOMETRIA = "isb_decomposicao_por_osso"
GONIOMETRIA_TEXTO = "Decomposição por osso, recomendação ISB (Wu et al., J Biomech 2005)"
