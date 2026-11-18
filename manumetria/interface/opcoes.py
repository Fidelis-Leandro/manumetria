"""Opções fixas da interface, definidas no código (não aparecem nas Configurações)."""

MAO_3D_ATIVA = False
"""Liga a mão 3D na tela de avaliação (miniatura, botões "Câmera / Modelo 3D", legenda
das cores e dica ao passar o mouse). Com False, a tela mostra só a câmera e o módulo da
mão 3D (interface/componentes/mao3d.py) e o OpenGL nem são importados. Não muda nenhum
cálculo. Para religar, basta trocar para True (e atualizar a documentação: README,
Ajuda, docs/ARQUITETURA.md e DESENVOLVIMENTO.md)."""
