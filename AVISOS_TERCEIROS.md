# Avisos de terceiros

O ManuMetria usa as bibliotecas e o modelo abaixo. Nenhum deles é distribuído dentro deste repositório:
os pacotes são instalados pelo `pip` a partir do `requirements.txt`, e o modelo do MediaPipe é baixado na
instalação. Cada componente continua sob a licença do seu autor.

## Dependências diretas (`requirements.txt`)

| Componente | Versão | Licença | Uso no ManuMetria |
|---|---|---|---|
| [PyQt5](https://www.riverbankcomputing.com/software/pyqt/) (Riverbank Computing) | 5.15.11 | GPL v3 (ou licença comercial da Riverbank) | interface gráfica |
| Qt 5 (pacote `PyQt5-Qt5`, The Qt Company) | 5.15.2 | LGPL v3 | biblioteca gráfica usada pelo PyQt5 |
| PyQt5-sip | 12.20.0 | BSD-2-Clause | ligação Python/C++ do PyQt5 |
| [pyqtgraph](https://www.pyqtgraph.org/) | 0.14.0 | MIT | gráficos e cena 3D (OpenGL) |
| [PyOpenGL](https://github.com/mcfletch/pyopengl) | 3.1.10 | BSD | acesso ao OpenGL para a cena 3D |
| [NumPy](https://numpy.org/) | 2.4.6 | BSD-3-Clause (com partes 0BSD, MIT, Zlib, CC0-1.0) | cálculo |
| [MediaPipe](https://github.com/google-ai-edge/mediapipe) (Google) | 1.0.1 | Apache 2.0 | detecção dos 21 pontos da mão |
| Modelo `hand_landmarker.task` (Google, MediaPipe) | float16, "latest" | Apache 2.0 | modelo de detecção da mão (baixado na instalação) |
| [OpenCV](https://opencv.org/) (`opencv-contrib-python`) | 5.0.0.93 | Apache 2.0 | leitura da webcam e imagem |

## Dependências indiretas (instaladas junto com as de cima)

| Componente | Licença |
|---|---|
| absl-py | Apache 2.0 |
| certifi | MPL 2.0 |
| cffi | MIT-0 |
| colorama | BSD |
| contourpy | BSD-3-Clause |
| cycler | BSD |
| flatbuffers | Apache 2.0 |
| fonttools | MIT |
| kiwisolver | BSD |
| matplotlib | licença da Matplotlib (estilo PSF) |
| packaging | Apache 2.0 ou BSD-2-Clause |
| pillow | MIT-CMU |
| pycparser | BSD-3-Clause |
| pyparsing | MIT |
| python-dateutil | BSD / Apache 2.0 |
| six | MIT |
| sounddevice | MIT |
| tzdata | Apache 2.0 |

## Ambiente

| Componente | Licença |
|---|---|
| Python 3.11 (Python Software Foundation) | PSF License |

## Referências científicas usadas no cálculo

Os métodos abaixo foram implementados no próprio código do ManuMetria a partir das publicações (nenhum
código de terceiros foi copiado):

- arco funcional dos dedos: Bain G. I. et al., *J Hand Surg Eur*, 2015;
- suavidade do movimento (SPARC): Balasubramanian S. et al., *J NeuroEng Rehabil*, 2015;
- classificação do TAM em % do normal: critérios no estilo da American Society for Surgery of the Hand
  (ASSH); escore de Strickland para tendões flexores.
