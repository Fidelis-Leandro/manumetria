"""
Mão 3D procedural para a cena do pyqtgraph.opengl, gerada pelo próprio código
a partir dos 21 pontos do MediaPipe (só numpy, sem modelo externo).

  - ossos: cilindros afinando da base para a ponta;
  - articulações: esferas; as medidas pelo sistema (MCP, PIP e DIP dos dedos,
    MCP e IP do polegar) recebem a cor do seu dedo (mesma regra de cores de
    sempre: kin.grade do % do normal); punho, base do polegar e pontas ficam
    neutros;
  - palma: uma superfície simples ligando o punho às bases dos dedos.

Tudo vira UMA malha (um GLMeshItem), refeita a cada quadro: ~4 mil vértices,
bem abaixo de 1 ms em numpy.

Uso:
    hand = ProceduralHand(gl_view)
    hand.set_pose(pontos_21x3)
    hand.set_finger_colors({"index": (r, g, b, a), ...})
    hand.joint_at(x, y)          # articulação sob o mouse (ou None)
    hand.hide()
"""

import numpy as np
import pyqtgraph.opengl as gl
from pyqtgraph.opengl import shaders

from nucleo import geometria
from nucleo import kinematics as kin

NEUTRAL_COLOR = (0.80, 0.82, 0.85, 1.0)      # articulação sem dados (cinza claro)
BONE_COLOR = (0.72, 0.75, 0.79, 1.0)
PALM_COLOR = (0.56, 0.61, 0.67, 1.0)
PASSIVE_JOINT_COLOR = (0.60, 0.63, 0.67, 1.0)   # punho, base do polegar, pontas

# Tamanhos em fração do comprimento da palma (punho -> base do médio), para a
# mão ficar proporcional seja qual for a escala dos pontos.
JOINT_RADIUS = 0.085
PASSIVE_RADIUS = 0.060
BONE_RADIUS_BASE = 0.058
BONE_RADIUS_TIP = 0.045
PICK_RADIUS_PX = 18                           # tolerância do mouse sobre uma esfera

# Articulações medidas: landmark -> (dedo, sigla). Vem de kin.JOINTS: o vértice
# do ângulo é o ponto da articulação.
MEASURED = {tri[1]: (finger, name) for finger, joints in kin.JOINTS.items() for name, tri in joints}
PALM_POLYGON = [0, 1, 5, 9, 13, 17]           # contorno da palma (leque a partir do punho)

# Luz que sai da câmera (como uma lanterna na cabeça): ambiente + difusa + um
# leve brilho. abs() no produto escalar: a palma fica iluminada dos dois lados.
LIGHT_SHADER = shaders.ShaderProgram("headlight", [
    shaders.VertexShader("""
        uniform mat4 u_mvp;
        uniform mat3 u_normal;
        attribute vec4 a_position;
        attribute vec3 a_normal;
        attribute vec4 a_color;
        varying vec4 v_color;
        varying vec3 v_normal;
        void main() {
            v_normal = normalize(u_normal * a_normal);
            v_color = a_color;
            gl_Position = u_mvp * a_position;
        }
    """),
    shaders.FragmentShader("""
        #ifdef GL_ES
        precision mediump float;
        #endif
        varying vec4 v_color;
        varying vec3 v_normal;
        void main() {
            vec3 n = normalize(v_normal);
            float diffuse = abs(dot(n, normalize(vec3(0.3, 0.4, 1.0))));
            float specular = pow(abs(n.z), 24.0) * 0.25;
            vec3 rgb = v_color.rgb * (0.30 + 0.70 * diffuse) + specular;
            gl_FragColor = vec4(rgb, v_color.a);
        }
    """),
])


# =============================================================================
# Primitivas (geradas uma vez)
# =============================================================================
def _unit_sphere(rows=10, cols=16):
    md = gl.MeshData.sphere(rows=rows, cols=cols, radius=1.0)
    v = md.vertexes().astype(np.float64)
    return v, md.faces().astype(np.int64)


def _unit_tube(segments=14):
    """Tubo aberto de raio 1: anel em z=0 (vértices 0..n-1) e em z=1 (n..2n-1)."""
    a = np.linspace(0, 2 * np.pi, segments, endpoint=False)
    ring = np.column_stack([np.cos(a), np.sin(a)])
    faces = []
    for k in range(segments):
        k2 = (k + 1) % segments
        faces += [(k, k2, segments + k), (k2, segments + k2, segments + k)]
    return ring, np.array(faces, dtype=np.int64)


_SPHERE_V, _SPHERE_F = _unit_sphere()
_TUBE_RING, _TUBE_F = _unit_tube()


def _perpendicular_basis(d):
    """Dois vetores unitários perpendiculares a d (e entre si)."""
    helper = np.array([0.0, 0.0, 1.0]) if abs(d[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    u = np.cross(d, helper)
    u /= np.linalg.norm(u)
    return u, np.cross(d, u)


def build_mesh(P, joint_colors):
    """21 pontos -> (vértices, faces, normais, cores) da mão inteira.

    joint_colors: {landmark: rgba} das esferas coloridas; as outras ficam neutras."""
    P = np.asarray(P, dtype=np.float64)
    size = np.linalg.norm(P[9] - P[0]) or 1.0
    verts, faces, normals, colors = [], [], [], []
    count = 0

    def add(v, f, n, c):
        nonlocal count
        verts.append(v)
        faces.append(f + count)
        normals.append(n)
        colors.append(np.tile(c, (len(v), 1)))
        count += len(v)

    # palma: leque de triângulos a partir do punho, com a normal de cada triângulo
    for a, b in zip(PALM_POLYGON[1:-1], PALM_POLYGON[2:]):
        tri = P[[0, a, b]]
        n = np.cross(tri[1] - tri[0], tri[2] - tri[0])
        n = n / (np.linalg.norm(n) + 1e-12)
        add(tri, np.array([[0, 1, 2]]), np.tile(n, (3, 1)), PALM_COLOR)

    # ossos
    r0, r1 = BONE_RADIUS_BASE * size, BONE_RADIUS_TIP * size
    for a, b in geometria.HAND_CONNECTIONS:
        d = P[b] - P[a]
        length = np.linalg.norm(d)
        if length < 1e-9:
            continue
        d = d / length
        u, w = _perpendicular_basis(d)
        radial = _TUBE_RING[:, :1] * u + _TUBE_RING[:, 1:] * w          # (n, 3)
        tip = b in geometria.FINGERTIPS or b in (3, 7, 11, 15, 19)
        ra, rb = (r0, r1) if tip else (r0, r0)
        v = np.vstack([P[a] + ra * radial, P[b] + rb * radial])
        add(v, _TUBE_F, np.vstack([radial, radial]), BONE_COLOR)

    # articulações
    for lm in range(21):
        if lm in MEASURED:
            radius, color = JOINT_RADIUS * size, joint_colors.get(lm, NEUTRAL_COLOR)
        else:
            radius, color = PASSIVE_RADIUS * size, PASSIVE_JOINT_COLOR
        add(P[lm] + radius * _SPHERE_V, _SPHERE_F, _SPHERE_V, color)

    return (np.vstack(verts).astype(np.float32), np.vstack(faces).astype(np.uint32),
            np.vstack(normals).astype(np.float32), np.vstack(colors).astype(np.float32))


# =============================================================================
# Item para a cena 3D
# =============================================================================
class ProceduralHand:
    def __init__(self, view):
        self.view = view
        self.item = gl.GLMeshItem(smooth=True, shader=LIGHT_SHADER, glOptions="opaque")
        self.item.setVisible(False)                   # aparece na 1ª pose
        view.addItem(self.item)
        self.points = None                            # últimos 21 pontos desenhados
        self.finger_colors = {}

    def set_finger_colors(self, colors):
        """Cor de cada dedo ({"index": (r,g,b,a), ...}); as esferas das
        articulações do dedo recebem essa cor. Redesenha a última pose."""
        self.finger_colors = dict(colors)
        if self.points is not None:
            self._upload()

    def set_pose(self, P):
        self.points = np.asarray(P, dtype=np.float64)
        self._upload()
        self.item.setVisible(True)

    def hide(self):
        """Esconde a mão até a próxima pose."""
        self.item.setVisible(False)

    def _upload(self):
        joint_colors = {lm: self.finger_colors[f] for lm, (f, _) in MEASURED.items()
                        if self.finger_colors.get(f) is not None}
        v, f, n, c = build_mesh(self.points, joint_colors)
        md = gl.MeshData(vertexes=v, faces=f, vertexColors=c)
        md._vertexNormals = n                         # normais prontas (esferas e tubos)
        self.item.setMeshData(meshdata=md)

    # ------------------------------------------------- mouse sobre a mão
    def screen_positions(self):
        """Posição na tela (pixels do widget) de cada um dos 21 pontos, e a
        profundidade (para escolher o mais à frente)."""
        w, h = self.view.width(), self.view.height()
        if self.points is None or w <= 0 or h <= 0:
            return None
        proj = self.view.projectionMatrix((0, 0, w, h), (0, 0, w, h))
        mvp = proj * self.view.viewMatrix()
        M = np.array(mvp.data(), dtype=np.float64).reshape(4, 4).T     # Qt guarda por coluna
        hom = np.column_stack([self.points, np.ones(21)]) @ M.T
        ndc = hom[:, :3] / hom[:, 3:4]
        x = (ndc[:, 0] + 1) * 0.5 * w
        y = (1 - ndc[:, 1]) * 0.5 * h
        return np.column_stack([x, y]), ndc[:, 2]

    def joint_at(self, x, y):
        """(dedo, sigla) da articulação medida sob o ponto (x, y) do widget, ou None."""
        if not self.item.visible():
            return None
        pos = self.screen_positions()
        if pos is None:
            return None
        xy, depth = pos
        best = None
        for lm in MEASURED:
            d = np.hypot(*(xy[lm] - (x, y)))
            if d <= PICK_RADIUS_PX and (best is None or depth[lm] < depth[best]):
                best = lm
        return MEASURED[best] if best is not None else None
